#!/usr/bin/env python3
"""Where do a symbol's pins land on the sheet for a given rotation and mirror?

    python3 tools/pinprobe.py Q_PMOS_SSSGDDDD 90 x      (rotation clockwise, mirror x|y|-)

Prints each pin's number, name and offset from the symbol's anchor (sheet frame:
x right, y DOWN), so a generator can wire a rotated part without guessing.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kisch
from parts import LIB


def probe(name, rot=0, mirror=None):
    kisch.SYMS.load_library(os.path.join(ROOT, "hardware", "lib", LIB + ".kicad_sym"), LIB)
    s = kisch.Sch("probe", "probe.kicad_sch")
    pl = s.sym(LIB + ":" + name, 101.6, 101.6, rot=rot, mirror=mirror, ref="X1", value="")
    _, pins = kisch.SYMS.get(LIB + ":" + name)
    out = []
    for p in pins:
        x, y = pl.pin(p["num"])
        out.append((p["num"], p["name"], round(x - 101.6, 2), round(y - 101.6, 2)))
    return out


if __name__ == "__main__":
    name = sys.argv[1]
    rot = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    mir = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    for n, nm, dx, dy in probe(name, rot, mir):
        print("%4s %-12s dx %7.2f  dy %7.2f" % (n, nm, dx, dy))
