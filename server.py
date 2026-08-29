#!/usr/bin/env python3
"""Local web UI for reviewing and remapping a Corne over VIA/Vial raw HID.

    python3 server.py                 # find the Corne, serve on 127.0.0.1:8777
    python3 server.py --demo          # UI only, no hardware (for layout work)
    python3 server.py --list          # show candidate raw-HID devices

Writes go straight to the keyboard's EEPROM and take effect immediately; there
is no separate "flash" step and nothing to save.
"""

import argparse
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import keycodes as K
import layout
import via

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
CORNE_VID, CORNE_PID = 0x4653, 0x0001


class Backend:
    """Owns the device handle.  One lock: HID transactions cannot interleave."""

    def __init__(self, path=None, demo=False, era=None):
        self.lock = threading.RLock()
        self.path = path
        self.demo = demo
        self.kb = None
        self.error = None
        self.info = {}
        self.layers = 0
        self.keymap = []            # keymap[layer][key-index] -> code
        self.era = era or "modern"
        self.era_forced = era is not None
        self.era_scores = {}

    # -- connection --------------------------------------------------------
    def connect(self):
        with self.lock:
            self.error = None
            if self.demo:
                self._connect_demo()
                return
            try:
                path = self.path
                if path is None:
                    devs = via.find_devices(CORNE_VID, CORNE_PID)
                    if not devs:
                        devs = via.find_devices()
                    if not devs:
                        raise via.DeviceError(
                            "no raw-HID keyboard found. Is the Corne plugged in, "
                            "and does its firmware have VIA or Vial enabled?")
                    path = devs[-1]["path"]
                    self.info = devs[-1]
                else:
                    self.info = {"path": path, "name": "manual", "node": os.path.basename(path)}

                if self.kb:
                    self.kb.close()
                self.kb = via.Keyboard(path)
                self.kb.probe()
                self.layers = self.kb.layer_count()
                if self.kb.vial:
                    self.info["vial_definition"] = bool(self.kb.vial_definition())
                self.read_all()
            except via.DeviceError as e:
                self.error = str(e)
                self.kb = None

    def _connect_demo(self):
        """A plausible QWERTY Corne so the UI can be worked on without hardware."""
        self.info = {"path": "(demo)", "name": "Demo Corne", "node": "-"}
        self.layers = 4
        rows = [
            ["KC_TAB", "KC_Q", "KC_W", "KC_E", "KC_R", "KC_T",
             "KC_Y", "KC_U", "KC_I", "KC_O", "KC_P", "KC_BSPC"],
            ["KC_LCTL", "KC_A", "KC_S", "KC_D", "KC_F", "KC_G",
             "KC_H", "KC_J", "KC_K", "KC_L", "KC_SCLN", "KC_QUOT"],
            ["KC_LSFT", "KC_Z", "KC_X", "KC_C", "KC_V", "KC_B",
             "KC_N", "KC_M", "KC_COMM", "KC_DOT", "KC_SLSH", "KC_ESC"],
        ]
        thumbs = ["KC_LGUI", None, "KC_SPC", "KC_ENT", None, "KC_RALT"]
        by_name = {n: c for c, (n, _l, _c) in K.build_table("modern").items()}

        visual = {}
        for r, row in enumerate(rows):
            for p, name in enumerate(row):
                kid = "L%d%d" % (r, p) if p < 6 else "R%d%d" % (r, 11 - p)
                visual[kid] = by_name[name]
        for p, name in enumerate(thumbs):
            kid = "L3%d" % (3 + p) if p < 3 else "R3%d" % (8 - p)
            visual[kid] = by_name[name] if name else 0
        visual["L34"] = K.LAYER_BASES["modern"]["MO"] + 1     # MO(1)
        visual["R34"] = K.LAYER_BASES["modern"]["MO"] + 2     # MO(2)

        base = [visual.get(k["id"], 0x0000) for k in layout.KEYS]
        self.keymap = [base] + [[0x01] * len(layout.KEYS) for _ in range(3)]
        self.keymap[1][1] = 0x00A9                       # KC_VOLU
        self.keymap[2][5] = K.encode_layer_tap(2, 0x07)  # LT(2, KC_D)
        self.keymap[3][7] = K.encode_mod_tap(0x02, 0x2C)  # LSFT_T(KC_SPC)
        self._detect_era()

    def ensure(self):
        if self.demo:
            return True
        if self.kb is None:
            self.connect()
        return self.kb is not None

    # -- keymap ------------------------------------------------------------
    def read_all(self):
        with self.lock:
            km = []
            for layer in range(self.layers):
                row = [self.kb.get_keycode(layer, k["row"], k["col"])
                       for k in layout.KEYS]
                km.append(row)
            self.keymap = km
            self._detect_era()

    def _detect_era(self):
        flat = [c for lay in self.keymap for c in lay]
        self.era_scores = {e: round(K.score_era(flat, e), 4) for e in K.ERAS}
        if not self.era_forced:
            # Pick whichever keycode generation explains the live keymap better;
            # ties go to modern, which is what current QMK ships.
            best = max(K.ERAS, key=lambda e: (self.era_scores[e], e == "modern"))
            self.era = best

    def set_key(self, layer, index, code):
        with self.lock:
            k = layout.KEYS[index]
            if self.demo:
                self.keymap[layer][index] = code
                return code
            actual = self.kb.set_keycode(layer, k["row"], k["col"], code)
            self.keymap[layer][index] = actual
            return actual

    def reset(self):
        with self.lock:
            if not self.demo:
                self.kb.reset_keymap()
                self.layers = self.kb.layer_count()
                self.read_all()

    # -- serialisation -----------------------------------------------------
    def describe(self, code, table):
        name, label, cat = K.decode(code, self.era, table)
        return {"code": code, "name": name, "label": label, "cat": cat}

    def state(self):
        with self.lock:
            if self.error and not self.demo:
                return {"ok": False, "error": self.error,
                        "hint": self.permission_hint()}
            table = K.build_table(self.era)
            return {
                "ok": True,
                "demo": self.demo,
                "device": {
                    "name": self.info.get("name"),
                    "path": self.info.get("path"),
                    "node": self.info.get("node"),
                    "vid": self.info.get("vid"),
                    "pid": self.info.get("pid"),
                },
                "protocol": None if self.demo else self.kb.protocol,
                "vial": False if self.demo else self.kb.vial,
                "vial_protocol": None if self.demo else self.kb.vial_protocol,
                "uid": None if self.demo else self.kb.keyboard_uid,
                "layers": self.layers,
                "era": self.era,
                "era_forced": self.era_forced,
                "era_scores": self.era_scores,
                "keys": layout.KEYS,
                "keymap": [[self.describe(c, table) for c in lay]
                           for lay in self.keymap],
                "catalog": self.catalog(table),
            }

    def catalog(self, table):
        groups = {}
        for code, (name, label, cat) in sorted(table.items()):
            groups.setdefault(cat, []).append(
                {"code": code, "name": name, "label": label, "cat": cat})
        groups["layers"] = K.layer_keycodes(self.era, max(self.layers, 1))
        return {
            "groups": groups,
            "bases": K.LAYER_BASES[self.era],
            "mods": [{"name": n, "bits": b, "desc": d} for n, b, d in K.MODS],
            "qk_mod_tap": K.QK_MOD_TAP,
            "qk_layer_tap": K.QK_LAYER_TAP,
        }

    def permission_hint(self):
        if self.error and "permission" in self.error.lower():
            return ("Install the udev rule, then replug the keyboard:\n"
                    "  sudo cp %s/60-corne-keymapper.rules /etc/udev/rules.d/\n"
                    "  sudo udevadm control --reload-rules && sudo udevadm trigger"
                    % os.path.dirname(os.path.abspath(__file__)))
        return None


class Handler(BaseHTTPRequestHandler):
    backend = None
    server_version = "corne-keymapper"

    def log_message(self, fmt, *args):
        pass                                    # keep the console quiet

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            self.backend.ensure()
            return self._send(200, self.backend.state())
        if path == "/api/export":
            self.backend.ensure()
            st = self.backend.state()
            if not st.get("ok"):
                return self._send(503, st)
            dump = {
                "device": st["device"], "layers": st["layers"], "era": st["era"],
                "keys": [{"id": k["id"], "row": k["row"], "col": k["col"]}
                         for k in layout.KEYS],
                "keymap": [[e["code"] for e in lay] for lay in st["keymap"]],
                "names": [[e["name"] for e in lay] for lay in st["keymap"]],
            }
            data = json.dumps(dump, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition",
                             'attachment; filename="corne-keymap.json"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)

        rel = "index.html" if path == "/" else path.lstrip("/")
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/key":
                b = self._body()
                if not self.backend.ensure():
                    return self._send(503, {"error": self.backend.error})
                try:
                    li, idx = int(b["layer"]), int(b["index"])
                    code = int(b["code"]) & 0xFFFF
                except (KeyError, TypeError, ValueError):
                    return self._send(400, {"error": "need layer, index and code"})
                if not 0 <= li < self.backend.layers:
                    return self._send(400, {"error": "layer %d out of range (0-%d)"
                                            % (li, self.backend.layers - 1)})
                if not 0 <= idx < len(layout.KEYS):
                    return self._send(400, {"error": "key index %d out of range" % idx})
                actual = self.backend.set_key(li, idx, code)
                table = K.build_table(self.backend.era)
                return self._send(200, {
                    "ok": True,
                    "entry": self.backend.describe(actual, table),
                    "matched": actual == code,
                })
            if path == "/api/reset":
                if not self.backend.ensure():
                    return self._send(503, {"error": self.backend.error})
                self.backend.reset()
                return self._send(200, {"ok": True})
            if path == "/api/reload":
                self.backend.connect()
                return self._send(200, self.backend.state())
            if path == "/api/era":
                b = self._body()
                era = b.get("era")
                with self.backend.lock:
                    if era in K.ERAS:
                        self.backend.era, self.backend.era_forced = era, True
                    else:
                        self.backend.era_forced = False
                        self.backend._detect_era()
                return self._send(200, self.backend.state())
            if path == "/api/import":
                b = self._body()
                codes = b.get("keymap") or []
                if not self.backend.ensure():
                    return self._send(503, {"error": self.backend.error})
                if not isinstance(codes, list):
                    return self._send(400, {"error": '"keymap" must be a list of layers'})
                written = 0
                for li, lay in enumerate(codes[:self.backend.layers]):
                    if not isinstance(lay, list):
                        continue
                    for ki, code in enumerate(lay[:len(layout.KEYS)]):
                        code = int(code) & 0xFFFF
                        if self.backend.keymap[li][ki] != code:
                            self.backend.set_key(li, ki, code)
                            written += 1
                return self._send(200, {"ok": True, "written": written})
        except via.DeviceError as e:
            self.backend.kb = None
            return self._send(503, {"error": str(e)})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})
        self._send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--device", help="raw-HID node, e.g. /dev/hidraw9")
    ap.add_argument("--era", choices=K.ERAS, help="force the keycode generation")
    ap.add_argument("--demo", action="store_true", help="run without hardware")
    ap.add_argument("--list", action="store_true", help="list raw-HID devices")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if args.list:
        devs = via.find_devices()
        if not devs:
            print("no raw-HID (0xFF60/0x61) interfaces found")
        for d in devs:
            print("%(path)s  %(name)s  %(vid)04x:%(pid)04x  %(phys)s" % d)
        return 0

    backend = Backend(path=args.device, demo=args.demo, era=args.era)
    backend.connect()
    if backend.error:
        print("warning: %s" % backend.error, file=sys.stderr)
        hint = backend.permission_hint()
        if hint:
            print(hint, file=sys.stderr)
        print("starting anyway; the UI will show the problem and can retry.\n",
              file=sys.stderr)
    else:
        kb = backend.kb
        if kb:
            print("connected: %s on %s" % (backend.info.get("name"), backend.info.get("path")))
            print("  VIA protocol 0x%04X%s, %d layers, keycodes: %s"
                  % (kb.protocol, ", Vial" if kb.vial else "", backend.layers, backend.era))

    Handler.backend = backend
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = "http://%s:%d/" % (args.host, args.port)
    print("serving %s  (ctrl-c to stop)" % url)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
