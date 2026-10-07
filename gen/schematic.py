#!/usr/bin/env python3
"""Draw OWLternating Current's schematic: a root sheet with the block diagram, and one
sheet per board on the panel.

    python3 gen/schematic.py        writes hardware/OWLternatingCurrent.kicad_sch and its sheets

The boards are separate pieces of the panel; their nets meet only through mated
connectors (the base's socket and the tree's header, the tree's and the perch's), so no
sheet shares a net with another: each board's power nets have their own names (GND_T on
the tree), and the root sheet's boxes have no pins.  Each sheet module (gen/sch_*.py)
draws one board.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import kisch
from parts import LIB
import board_info as BI
import sch_util as U
import sch_base
import sch_boards

HW = os.path.join(ROOT, "hardware")

# (sheet name, file, paper, module, what it is)
SHEETS = [
    ("Base", "base.kicad_sch", "A1", sch_base.build, "the base board: power, RP2354A, LEDs, sensors, coil drivers, theremin, audio"),
    ("Tree", "tree.kicad_sch", "A3", sch_boards.build_tree, "the tree: its LED driver, owls' eyes, stars; the coil's and the Hall sensor's lines"),
    ("Perch", "perch.kicad_sch", "A4", sch_boards.build_perch, "the perch: the levitation coil, the Hall sensor, two downlights"),
    ("Bat", "bat.kicad_sch", "A4", sch_boards.build_bat, "the bat: a coil, a capacitor, two eyes"),
    ("Owl token", "owl_token.kicad_sch", "A4", sch_boards.build_owl, "the owl familiar: a tank at 142 kHz"),
    ("Cat token", "cat_token.kicad_sch", "A4", sch_boards.build_cat, "the cat familiar: a tank at 303 kHz"),
]


def company():
    return BI.AUTHORS + ("  --  https://" + BI.URL if BI.URL else "")


def draw():
    kisch.SYMS.load_library(os.path.join(HW, "lib", LIB + ".kicad_sym"), LIB)
    root = kisch.Sch(BI.NAME, BI.NAME + ".kicad_sch", paper="A3", title="%s: %s" % (BI.TITLE, BI.TAGLINE),
                     rev=BI.REV, date=BI.DATE, company=company(),
                     comments=["Made by gen/schematic.py from gen/pins.py, gen/parts.py, gen/leds.py",
                               BI.LICENCE])
    root.text(17.78, 21.59, "%s: %s" % (BI.TITLE, BI.TAGLINE), size=3.0, bold=True)
    sheets = []
    for i, (name, fn, paper, build, what) in enumerate(SHEETS):
        x, y = 30.48 + 63.5 * (i % 3), 50.8 + 50.8 * (i // 3)
        u, _ = root.sheet(x, y, 50.8, 25.4, name, fn, i + 2)
        root.note(x, y + 30.48, what, cols=30)
        s = kisch.Sch(BI.NAME, fn, paper=paper, title="%s: %s" % (BI.TITLE, name.lower()), rev=BI.REV, date=BI.DATE,
                      company=company(), comments=["Made by gen/%s.py" % build.__module__, BI.LICENCE],
                      root=root.uuid, sheet_box_uuid=u)
        build(s)
        sheets.append(s)
    return root, sheets


def main():
    root, sheets = draw()
    # what each part is for, for gen/placement.py (refs change when the sheets change)
    import json
    json.dump(dict(sorted(U.ROLES.items())), open(os.path.join(HW, "checks", "roles.json"), "w"), indent=1)
    bad = 0
    for s in [root] + sheets:
        touches, nets, over = s.touches(), s.nets(), s.overlaps()
        out = s.save(HW, is_root=(s is root))
        print("%-28s %3d accidental touches, %3d net problems, %3d overlaps"
              % (os.path.relpath(out, ROOT), len(touches), len(nets), len(over)))
        for m in (touches + nets + over)[:80]:
            print("    ", m)
        bad += len(touches) + len(nets) + len(over)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
