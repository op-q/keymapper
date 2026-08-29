"""QMK keycode tables, encoders and decoders.

QMK renumbered several keycode blocks in the 0.19 "keycode overhaul" (2022).
Firmware built before that ("legacy") and after ("modern") disagree about where
media, mouse and layer keycodes live, so every table that moved is defined twice
and selected by `era`.  Codes we cannot name are never guessed at -- they are
rendered as raw hex so the UI stays honest about what is on the device.
"""

ERAS = ("modern", "legacy")

# --- modifier bitmask (identical in both eras) -----------------------------
MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT = 0x01, 0x02, 0x04, 0x08, 0x10

MODS = [
    ("LCTL", MOD_CTRL, "Left Ctrl"),
    ("LSFT", MOD_SHIFT, "Left Shift"),
    ("LALT", MOD_ALT, "Left Alt"),
    ("LGUI", MOD_GUI, "Left GUI"),
    ("RCTL", MOD_RIGHT | MOD_CTRL, "Right Ctrl"),
    ("RSFT", MOD_RIGHT | MOD_SHIFT, "Right Shift"),
    ("RALT", MOD_RIGHT | MOD_ALT, "Right Alt / AltGr"),
    ("RGUI", MOD_RIGHT | MOD_GUI, "Right GUI"),
]

_MOD_BITS = [(MOD_CTRL, "CTL"), (MOD_SHIFT, "SFT"), (MOD_ALT, "ALT"), (MOD_GUI, "GUI")]


def mod_name(mods):
    """Render a 5-bit modifier mask the way QMK spells it."""
    side = "R" if mods & MOD_RIGHT else "L"
    bits = mods & 0x0F
    if bits == 0x0F:
        return "HYPR" if side == "L" else "RHYP"
    if bits == 0x07:
        return "MEH" if side == "L" else "RMEH"
    parts = [side + n for b, n in _MOD_BITS if bits & b]
    return "+".join(parts) if parts else "----"


# --- basic HID keycodes, 0x00-0xFF ----------------------------------------
# (name, cap label, category).  Shared by both eras.
_BASIC = {
    0x00: ("KC_NO", "", "special"),
    0x01: ("KC_TRNS", "▽", "special"),
}

_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
for _i, _c in enumerate(_ALPHA):
    _BASIC[0x04 + _i] = ("KC_" + _c, _c, "letters")
for _i, _c in enumerate("1234567890"):
    _BASIC[0x1E + _i] = ("KC_" + _c, _c, "numbers")

_BASIC.update({
    0x28: ("KC_ENT", "Enter", "basic"),
    0x29: ("KC_ESC", "Esc", "basic"),
    0x2A: ("KC_BSPC", "Bksp", "basic"),
    0x2B: ("KC_TAB", "Tab", "basic"),
    0x2C: ("KC_SPC", "Space", "basic"),
    0x2D: ("KC_MINS", "-", "punct"),
    0x2E: ("KC_EQL", "=", "punct"),
    0x2F: ("KC_LBRC", "[", "punct"),
    0x30: ("KC_RBRC", "]", "punct"),
    0x31: ("KC_BSLS", "\\", "punct"),
    0x32: ("KC_NUHS", "#~", "punct"),
    0x33: ("KC_SCLN", ";", "punct"),
    0x34: ("KC_QUOT", "'", "punct"),
    0x35: ("KC_GRV", "`", "punct"),
    0x36: ("KC_COMM", ",", "punct"),
    0x37: ("KC_DOT", ".", "punct"),
    0x38: ("KC_SLSH", "/", "punct"),
    0x39: ("KC_CAPS", "Caps", "basic"),
    0x46: ("KC_PSCR", "PrtSc", "nav"),
    0x47: ("KC_SCRL", "ScrLk", "nav"),
    0x48: ("KC_PAUS", "Pause", "nav"),
    0x49: ("KC_INS", "Ins", "nav"),
    0x4A: ("KC_HOME", "Home", "nav"),
    0x4B: ("KC_PGUP", "PgUp", "nav"),
    0x4C: ("KC_DEL", "Del", "nav"),
    0x4D: ("KC_END", "End", "nav"),
    0x4E: ("KC_PGDN", "PgDn", "nav"),
    0x4F: ("KC_RGHT", "→", "nav"),
    0x50: ("KC_LEFT", "←", "nav"),
    0x51: ("KC_DOWN", "↓", "nav"),
    0x52: ("KC_UP", "↑", "nav"),
    0x53: ("KC_NUM", "NumLk", "keypad"),
    0x54: ("KC_PSLS", "KP /", "keypad"),
    0x55: ("KC_PAST", "KP *", "keypad"),
    0x56: ("KC_PMNS", "KP -", "keypad"),
    0x57: ("KC_PPLS", "KP +", "keypad"),
    0x58: ("KC_PENT", "KP ⏎", "keypad"),
    0x62: ("KC_P0", "KP 0", "keypad"),
    0x63: ("KC_PDOT", "KP .", "keypad"),
    0x64: ("KC_NUBS", "\\|", "punct"),
    0x65: ("KC_APP", "Menu", "basic"),
    0x66: ("KC_KB_POWER", "Power", "system"),
    0x67: ("KC_PEQL", "KP =", "keypad"),
    0x74: ("KC_EXEC", "Exec", "basic"),
    0x75: ("KC_HELP", "Help", "basic"),
    0x76: ("KC_MENU", "Menu", "basic"),
    0x77: ("KC_SLCT", "Select", "basic"),
    0x78: ("KC_STOP", "Stop", "basic"),
    0x79: ("KC_AGIN", "Again", "basic"),
    0x7A: ("KC_UNDO", "Undo", "basic"),
    0x7B: ("KC_CUT", "Cut", "basic"),
    0x7C: ("KC_COPY", "Copy", "basic"),
    0x7D: ("KC_PSTE", "Paste", "basic"),
    0x7E: ("KC_FIND", "Find", "basic"),
    0x85: ("KC_PCMM", "KP ,", "keypad"),
    0x87: ("KC_INT1", "Int1", "intl"),
    0x88: ("KC_INT2", "Int2", "intl"),
    0x89: ("KC_INT3", "Int3", "intl"),
    0x8A: ("KC_INT4", "Int4", "intl"),
    0x8B: ("KC_INT5", "Int5", "intl"),
    0x8C: ("KC_INT6", "Int6", "intl"),
    0x90: ("KC_LNG1", "Lang1", "intl"),
    0x91: ("KC_LNG2", "Lang2", "intl"),
    0x92: ("KC_LNG3", "Lang3", "intl"),
    0x93: ("KC_LNG4", "Lang4", "intl"),
})
for _i in range(12):                      # F1-F12
    _BASIC[0x3A + _i] = ("KC_F%d" % (_i + 1), "F%d" % (_i + 1), "fkeys")
for _i in range(12):                      # F13-F24
    _BASIC[0x68 + _i] = ("KC_F%d" % (_i + 13), "F%d" % (_i + 13), "fkeys")
for _i in range(9):                       # keypad 1-9
    _BASIC[0x59 + _i] = ("KC_P%d" % (_i + 1), "KP %d" % (_i + 1), "keypad")
for _i, (_n, _lbl) in enumerate([
    ("KC_LCTL", "Ctrl"), ("KC_LSFT", "Shift"), ("KC_LALT", "Alt"), ("KC_LGUI", "GUI"),
    ("KC_RCTL", "RCtrl"), ("KC_RSFT", "RShift"), ("KC_RALT", "AltGr"), ("KC_RGUI", "RGUI"),
]):
    _BASIC[0xE0 + _i] = (_n, _lbl, "mods")

# --- blocks that moved in the 0.19 overhaul -------------------------------
_SYSTEM_MEDIA = [                      # same base in both eras
    ("KC_PWR", "Power", "system"), ("KC_SLEP", "Sleep", "system"), ("KC_WAKE", "Wake", "system"),
    ("KC_MUTE", "Mute", "media"), ("KC_VOLU", "Vol +", "media"), ("KC_VOLD", "Vol -", "media"),
    ("KC_MNXT", "Next ⏭", "media"), ("KC_MPRV", "Prev ⏮", "media"), ("KC_MSTP", "Stop ⏹", "media"),
    ("KC_MPLY", "Play ⏯", "media"), ("KC_MSEL", "Select", "media"), ("KC_EJCT", "Eject", "media"),
    ("KC_MAIL", "Mail", "app"), ("KC_CALC", "Calc", "app"), ("KC_MYCM", "My PC", "app"),
    ("KC_WSCH", "Search", "app"), ("KC_WHOM", "Home", "app"), ("KC_WBAK", "Back", "app"),
    ("KC_WFWD", "Fwd", "app"), ("KC_WSTP", "Stop", "app"), ("KC_WREF", "Reload", "app"),
    ("KC_WFAV", "Favs", "app"), ("KC_MFFD", "FFwd ⏩", "media"), ("KC_MRWD", "Rew ⏪", "media"),
    ("KC_BRIU", "Bright +", "media"), ("KC_BRID", "Bright -", "media"),
]

_MOUSE = [
    ("MS_UP", "Ms ↑", "mouse"), ("MS_DOWN", "Ms ↓", "mouse"),
    ("MS_LEFT", "Ms ←", "mouse"), ("MS_RGHT", "Ms →", "mouse"),
    ("MS_BTN1", "Btn 1", "mouse"), ("MS_BTN2", "Btn 2", "mouse"), ("MS_BTN3", "Btn 3", "mouse"),
    ("MS_BTN4", "Btn 4", "mouse"), ("MS_BTN5", "Btn 5", "mouse"),
    ("MS_WHLU", "Wh ↑", "mouse"), ("MS_WHLD", "Wh ↓", "mouse"),
    ("MS_WHLL", "Wh ←", "mouse"), ("MS_WHLR", "Wh →", "mouse"),
    ("MS_ACL0", "Acc 0", "mouse"), ("MS_ACL1", "Acc 1", "mouse"), ("MS_ACL2", "Acc 2", "mouse"),
]

# Layer-keycode block bases.  These are the codes that moved.
LAYER_BASES = {
    "modern": {"TO": 0x5200, "MO": 0x5220, "DF": 0x5240, "TG": 0x5260,
               "OSL": 0x5280, "OSM": 0x52A0, "TT": 0x52C0},
    "legacy": {"TO": 0x5010, "MO": 0x5100, "DF": 0x5200, "TG": 0x5300,
               "OSL": 0x5400, "OSM": 0x5500, "TT": 0x5800},
}
_LAYER_SPAN = {"modern": 0x20, "legacy": 0x100}

QK_MODS, QK_MOD_TAP, QK_LAYER_TAP = 0x0100, 0x2000, 0x4000


def build_table(era):
    """code -> (name, label, category) for every keycode we can name."""
    t = dict(_BASIC)
    for i, (n, lbl, cat) in enumerate(_SYSTEM_MEDIA):
        t[0xA5 + i] = (n, lbl, cat)
    mouse_base = 0xCD if era == "modern" else 0xF0
    for i, (n, lbl, cat) in enumerate(_MOUSE):
        # legacy has no BTN6-8 gap; both eras run contiguously from their base
        t[mouse_base + i] = (n, lbl, cat)
    return t


def layer_keycodes(era, layer_count):
    """MO/TO/TG/TT/DF/OSL entries for every layer the device actually has."""
    out = []
    bases = LAYER_BASES[era]
    for kind in ("MO", "TO", "TG", "TT", "DF", "OSL"):
        for n in range(layer_count):
            out.append({
                "code": bases[kind] + n,
                "name": "%s(%d)" % (kind, n),
                "label": "%s %d" % (kind, n),
                "cat": "layers",
            })
    return out


def encode_mod_tap(mods, kc):
    return QK_MOD_TAP | ((mods & 0x1F) << 8) | (kc & 0xFF)


def encode_layer_tap(layer, kc):
    return QK_LAYER_TAP | ((layer & 0x0F) << 8) | (kc & 0xFF)


def decode(code, era, table=None):
    """Describe a 16-bit keycode.  Returns (name, cap-label, category)."""
    table = table if table is not None else build_table(era)
    code &= 0xFFFF

    if code in table:
        return table[code]

    if QK_MOD_TAP <= code <= 0x3FFF:
        mods, kc = (code >> 8) & 0x1F, code & 0xFF
        base = table.get(kc, ("0x%02X" % kc, "%02X" % kc, "unknown"))
        return ("%s_T(%s)" % (mod_name(mods), base[0]),
                "%s\n%s" % (mod_name(mods), base[1]), "modtap")

    if QK_LAYER_TAP <= code <= 0x4FFF:
        layer, kc = (code >> 8) & 0x0F, code & 0xFF
        base = table.get(kc, ("0x%02X" % kc, "%02X" % kc, "unknown"))
        return ("LT(%d,%s)" % (layer, base[0]),
                "LT%d\n%s" % (layer, base[1]), "layertap")

    bases = LAYER_BASES[era]
    span = _LAYER_SPAN[era]
    for kind in ("TO", "MO", "DF", "TG", "OSL", "TT"):
        b = bases[kind]
        if b <= code < b + span:
            n = code - b
            if n < 32:
                return ("%s(%d)" % (kind, n), "%s %d" % (kind, n), "layers")

    b = bases["OSM"]
    if b <= code < b + span:
        mods = (code - b) & 0x1F
        return ("OSM(%s)" % mod_name(mods), "OSM\n%s" % mod_name(mods), "layers")

    if QK_MODS <= code <= 0x1FFF:
        mods, kc = (code >> 8) & 0x1F, code & 0xFF
        base = table.get(kc, ("0x%02X" % kc, "%02X" % kc, "unknown"))
        return ("%s(%s)" % (mod_name(mods), base[0]),
                "%s\n%s" % (mod_name(mods), base[1]), "modded")

    return ("0x%04X" % code, "0x%04X" % code, "unknown")


def score_era(codes, era):
    """How well `era` explains a keymap: fraction of non-empty keys we can name."""
    table = build_table(era)
    known = total = 0
    for c in codes:
        if c in (0x0000, 0x0001):
            continue
        total += 1
        if decode(c, era, table)[2] != "unknown":
            known += 1
    return 1.0 if total == 0 else known / total
