"""Talk to a QMK/VIA/Vial keyboard over raw HID, using only the stdlib.

Linux hidraw takes plain read()/write() on /dev/hidrawN, so no hidapi or pyusb
is needed.  Writes are prefixed with a report-number byte of 0x00 because the
QMK raw-HID interface does not use numbered reports.
"""

import fcntl
import glob
import json
import lzma
import os
import struct
import time

REPORT_SIZE = 32
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x61

# VIA command ids
CMD_GET_PROTOCOL_VERSION = 0x01
CMD_GET_KEYBOARD_VALUE = 0x02
CMD_DYNAMIC_KEYMAP_GET_KEYCODE = 0x04
CMD_DYNAMIC_KEYMAP_SET_KEYCODE = 0x05
CMD_DYNAMIC_KEYMAP_RESET = 0x06
CMD_DYNAMIC_KEYMAP_GET_LAYER_COUNT = 0x11
CMD_DYNAMIC_KEYMAP_GET_BUFFER = 0x12
CMD_VIAL_PREFIX = 0xFE

VIAL_GET_KEYBOARD_ID = 0x00
VIAL_GET_SIZE = 0x01
VIAL_GET_DEFINITION = 0x02


class DeviceError(Exception):
    pass


class PermissionProblem(DeviceError):
    pass


def _hidraw_descriptor(node):
    path = "/sys/class/hidraw/%s/device/report_descriptor" % node
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def _hidraw_uevent(node):
    path = "/sys/class/hidraw/%s/device/uevent" % node
    info = {}
    try:
        with open(path) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v
    except OSError:
        pass
    return info


def _is_raw_hid(desc):
    """Usage Page (0xFF60), Usage (0x61) -- the QMK raw-HID signature."""
    return b"\x06\x60\xff\x09\x61" in desc


def find_devices(vid=None, pid=None):
    """All raw-HID capable interfaces, newest-numbered last."""
    found = []
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        node = os.path.basename(path)
        if not _is_raw_hid(_hidraw_descriptor(node)):
            continue
        info = _hidraw_uevent(node)
        hid_id = info.get("HID_ID", "")
        parts = hid_id.split(":")
        dev_vid = int(parts[1], 16) if len(parts) == 3 else 0
        dev_pid = int(parts[2], 16) if len(parts) == 3 else 0
        if vid is not None and dev_vid != vid:
            continue
        if pid is not None and dev_pid != pid:
            continue
        found.append({
            "node": node,
            "path": "/dev/" + node,
            "vid": dev_vid,
            "pid": dev_pid,
            "name": info.get("HID_NAME", "?"),
            "phys": info.get("HID_PHYS", ""),
        })
    return found


class RawHID:
    def __init__(self, path, timeout=1.0):
        self.path = path
        self.timeout = timeout
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as e:
            raise PermissionProblem(
                "no permission to open %s -- install the udev rule "
                "(see README) or run as root" % path) from e
        except OSError as e:
            raise DeviceError("cannot open %s: %s" % (path, e)) from e

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _drain(self):
        """Discard stale replies so a request never reads a previous answer."""
        while True:
            try:
                if not os.read(self.fd, REPORT_SIZE):
                    return
            except BlockingIOError:
                return
            except OSError:
                return

    def transact(self, payload):
        self._drain()
        buf = bytes(payload[:REPORT_SIZE]).ljust(REPORT_SIZE, b"\x00")
        try:
            os.write(self.fd, b"\x00" + buf)          # 0x00 = no numbered reports
        except OSError as e:
            raise DeviceError("write to %s failed: %s" % (self.path, e)) from e

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                data = os.read(self.fd, REPORT_SIZE)
            except BlockingIOError:
                time.sleep(0.001)
                continue
            except OSError as e:
                raise DeviceError("read from %s failed: %s" % (self.path, e)) from e
            if data:
                return data
        raise DeviceError("timed out waiting for a reply from %s" % self.path)


class Keyboard:
    """VIA dynamic-keymap operations on top of a raw-HID endpoint."""

    def __init__(self, path):
        self.hid = RawHID(path)
        self.path = path
        self.protocol = None
        self.vial = False
        self.vial_protocol = None
        self.keyboard_uid = None

    def close(self):
        self.hid.close()

    # -- discovery ---------------------------------------------------------
    def probe(self):
        r = self.hid.transact([CMD_GET_PROTOCOL_VERSION])
        if r[0] != CMD_GET_PROTOCOL_VERSION:
            raise DeviceError("unexpected reply to protocol query: %s" % r[:4].hex())
        self.protocol = struct.unpack(">H", r[1:3])[0]

        try:
            r = self.hid.transact([CMD_VIAL_PREFIX, VIAL_GET_KEYBOARD_ID])
            vial_proto = struct.unpack("<I", r[0:4])[0]
            uid = r[4:12]
            # A non-Vial board echoes the command or returns junk; Vial protocol
            # numbers are small.
            if vial_proto < 100 and uid != b"\x00" * 8:
                self.vial = True
                self.vial_protocol = vial_proto
                self.keyboard_uid = uid.hex()
        except DeviceError:
            pass
        return self.protocol

    def layer_count(self):
        r = self.hid.transact([CMD_DYNAMIC_KEYMAP_GET_LAYER_COUNT])
        if r[0] != CMD_DYNAMIC_KEYMAP_GET_LAYER_COUNT:
            raise DeviceError("device did not answer the layer-count query")
        n = r[1]
        if not 1 <= n <= 32:
            raise DeviceError("implausible layer count from device: %d" % n)
        return n

    # -- keymap ------------------------------------------------------------
    def get_keycode(self, layer, row, col):
        r = self.hid.transact([CMD_DYNAMIC_KEYMAP_GET_KEYCODE, layer, row, col])
        if r[0] != CMD_DYNAMIC_KEYMAP_GET_KEYCODE:
            raise DeviceError("bad reply reading L%d r%d c%d" % (layer, row, col))
        return struct.unpack(">H", r[4:6])[0]

    def set_keycode(self, layer, row, col, code):
        hi, lo = (code >> 8) & 0xFF, code & 0xFF
        r = self.hid.transact(
            [CMD_DYNAMIC_KEYMAP_SET_KEYCODE, layer, row, col, hi, lo])
        if r[0] != CMD_DYNAMIC_KEYMAP_SET_KEYCODE:
            raise DeviceError("device rejected the write")
        # Read back: VIA writes straight to EEPROM, so this confirms persistence.
        return self.get_keycode(layer, row, col)

    def reset_keymap(self):
        self.hid.transact([CMD_DYNAMIC_KEYMAP_RESET])

    def get_buffer(self, offset, size):
        out = bytearray()
        while size > 0:
            chunk = min(28, size)
            r = self.hid.transact([CMD_DYNAMIC_KEYMAP_GET_BUFFER,
                                   (offset >> 8) & 0xFF, offset & 0xFF, chunk])
            out += r[4:4 + chunk]
            offset += chunk
            size -= chunk
        return bytes(out)

    # -- Vial payload ------------------------------------------------------
    def vial_definition(self):
        """Decompress the keyboard definition Vial firmware carries onboard."""
        if not self.vial:
            return None
        r = self.hid.transact([CMD_VIAL_PREFIX, VIAL_GET_SIZE])
        size = struct.unpack("<I", r[0:4])[0]
        if not 0 < size < 1 << 20:
            return None
        blob = bytearray()
        block = 0
        while len(blob) < size:
            r = self.hid.transact([CMD_VIAL_PREFIX, VIAL_GET_DEFINITION,
                                   block & 0xFF, (block >> 8) & 0xFF])
            blob += r
            block += 1
        try:
            raw = lzma.decompress(bytes(blob[:size]))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None
