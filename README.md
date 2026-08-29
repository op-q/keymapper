# Corne Keymapper

A small local web UI to review and remap the keys on a Corne (crkbd) that speaks
the VIA/Vial raw-HID protocol. Pure Python standard library — no pip installs,
no Node, no Electron.

```
python3 server.py            # connect, serve http://127.0.0.1:8777, open a browser
python3 server.py --list     # show raw-HID capable devices
python3 server.py --demo     # UI only, no hardware attached
```

Changes are written straight to the keyboard's EEPROM and take effect the moment
you click. There is no save step and no reflashing.

## One-time setup: device permissions

`/dev/hidraw*` is root-only by default, so install the udev rule once:

```sh
sudo cp 60-corne-keymapper.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then unplug and replug the keyboard. To check it worked:

```sh
python3 server.py --list
python3 -c "import via; k=via.Keyboard(via.find_devices(0x4653,1)[0]['path']); print(hex(k.probe()))"
```

If you would rather not add a rule, `sudo python3 server.py --no-browser` also
works; open the printed URL yourself.

## Does my firmware support this?

Live remapping needs `VIA_ENABLE = yes` (or Vial) in the firmware. The raw-HID
endpoint your Corne exposes (usage page `0xFF60`, usage `0x61`) is a strong
signal that it does, but it is also present with plain `RAW_ENABLE`. The UI tells
you what it found on connect — VIA protocol version, Vial version if present, and
the number of dynamic layers. If the device answers the protocol query but not
the layer-count query, the firmware has raw HID but not dynamic keymaps, and you
will need to rebuild and flash QMK instead.

## Keycode generations

QMK renumbered the media, mouse and layer keycode blocks in the 0.19 "keycode
overhaul". Firmware built before and after that disagree about what `0x5221`
means, and nothing in the protocol reports which generation is in use.

On connect, the app decodes your live keymap with both tables and picks whichever
one leaves fewer unrecognised keycodes — the score for each is shown in the
header. If the labels still look wrong, override it with the **keycodes** dropdown
(or `--era legacy`). Anything the chosen table cannot name is shown as raw hex
rather than guessed at, and you can always assign a raw hex keycode directly.

## Using it

- **Layer tabs** switch layers; **Review all layers** stacks every layer at once.
- **Click any key** to open the picker: search, browse by category, or use the
  tap–hold builder for `LT()` / `MT()` codes.
- Hovering a key shows its matrix position and the exact keycode.
- **Export** downloads the current keymap as JSON; **Import** writes one back.
  Export first — it is the only backup, and **Reset to firmware** is irreversible.

## Layout

`layout.py` encodes `LAYOUT_split_3x6_3`. The right half is wired mirrored: in
QMK's `crkbd.h` the right rows are listed inner-to-outer, so the physically
leftmost key of the right half is matrix column 5. Rows 0–3 are the left half,
rows 4–7 the right.

## Files

| file | what it does |
| --- | --- |
| `server.py` | HTTP server, JSON API, device session |
| `via.py` | raw HID over `/dev/hidraw*`, VIA + Vial commands |
| `keycodes.py` | keycode tables, both generations, encode/decode |
| `layout.py` | Corne physical layout ↔ matrix mapping |
| `web/` | the UI |
