"""Physical layout of the Corne (crkbd) LAYOUT_split_3x6_3.

The right half is wired mirrored: in QMK's crkbd.h the right rows are listed
inner-to-outer, so the physically leftmost key of the right half is matrix
column 5.  Positions are in key units; the renderer scales them.
"""

# Per-column vertical stagger of the left half, outer pinky -> inner index.
COL_STAGGER = [0.38, 0.38, 0.13, 0.00, 0.13, 0.28]
BOARD_WIDTH = 13.0          # left cols 0-5, gap, right cols at x=7..12
MIRROR = 12.0               # x' = MIRROR - x

FINGERS = ["pinky+", "pinky", "ring", "middle", "index", "index+"]


def _mirror(x):
    return MIRROR - x


def build():
    """Ordered list of physical keys, each mapped to its matrix cell."""
    keys = []

    # --- left half: rows 0-2, matrix columns run left to right -------------
    for r in range(3):
        for c in range(6):
            keys.append({
                "id": "L%d%d" % (r, c),
                "row": r, "col": c,
                "x": float(c), "y": r + COL_STAGGER[c],
                "half": "left", "finger": FINGERS[c],
            })

    # --- left thumbs: matrix row 3, columns 3-5 ---------------------------
    for i in range(3):
        keys.append({
            "id": "L3%d" % (3 + i),
            "row": 3, "col": 3 + i,
            "x": 3.25 + i, "y": 3.30 + i * 0.18,
            "half": "left", "finger": "thumb",
        })

    # --- right half mirrors the left, matrix rows 4-7 ---------------------
    for r in range(3):
        for c in range(6):
            keys.append({
                "id": "R%d%d" % (r, c),
                "row": r + 4, "col": c,
                "x": _mirror(float(c)), "y": r + COL_STAGGER[c],
                "half": "right", "finger": FINGERS[c],
            })
    for i in range(3):
        keys.append({
            "id": "R3%d" % (3 + i),
            "row": 7, "col": 3 + i,
            "x": _mirror(3.25 + i), "y": 3.30 + i * 0.18,
            "half": "right", "finger": "thumb",
        })

    return keys


KEYS = build()
MATRIX_ROWS = 8
MATRIX_COLS = 6
