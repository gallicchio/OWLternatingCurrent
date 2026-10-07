#!/usr/bin/env python3
"""List DRC's courtyard overlaps (and other two-part items) by role and board position.

    python3 tools/overlaps.py [kind]      (after tools/pcb_check.py)
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import placement as PL
inv = {v: k for k, v in PL.ROLES.items()}
kind = sys.argv[1] if len(sys.argv) > 1 else "courtyards_overlap"
d = json.load(open(os.path.join(ROOT, "hardware", "checks", "drc.json")))
for v in d["violations"]:
    if v["type"] != kind:
        continue
    out = []
    for it in v["items"]:
        desc = it["description"]
        ref = desc.split()[-1] if desc.startswith("Footprint") else desc
        bname = None
        try:
            bname = PL.board_of(ref)
            x, y, rot, side = PL.BOARDS[bname].place[ref]
            out.append("%s(%s %s %.1f,%.1f %s)" % (ref, inv.get(ref, "-"), bname, x, y, side))
        except Exception:
            out.append(desc[:60])
    print("  " + "  <>  ".join(out))
