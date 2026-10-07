#!/usr/bin/env python3
"""Optional: slice out/plate_bambu.3mf with a real Bambu Studio and check its G-code.

    python3 print/slicer_check.py /path/to/bambu-studio [--printers X1C,P1S,A1,A1M]

Needs a Bambu Studio 2.x binary (an extracted AppImage works: point at
squashfs-root/bin/bambu-studio, and set LD_LIBRARY_PATH if it needs libraries).  Its
system profiles are flattened (inheritance resolved) into a scratch directory and
passed in explicitly, standing in for the printer the owner picks.  For each printer:
the slicer's warnings, time and filament, where the pause lands, and how the critical
layers are printed (the stand-in interfaces, the cap's bridges, the cover over the
magnets).  Exits non-zero if the pause is missing or misplaced.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402

PRINTERS = {   # name: (machine preset, process preset, filament preset)
    "X1C": ("Bambu Lab X1 Carbon 0.4 nozzle", "0.20mm Standard @BBL X1C", "Bambu PLA Basic @BBL X1C"),
    "P1S": ("Bambu Lab P1S 0.4 nozzle", "0.20mm Standard @BBL P1P", "Bambu PLA Basic @BBL X1C"),
    "A1": ("Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1", "Bambu PLA Basic @BBL A1"),
    "A1M": ("Bambu Lab A1 mini 0.4 nozzle", "0.20mm Standard @BBL A1M", "Bambu PLA Basic @BBL A1M"),
}
# layers worth reading (1-based): the owl's base over its slab, the cap's drops on their
# pedestal, the cap's floor, the cap's arms, the cover over both magnets
LAYERS = {
    int(round((D.OWL_Z0 + D.LAYER) / D.LAYER)): "owl's base over its slab",
    int(round((D.CAP_Z0 + D.CAP_Z_BOTTOM + D.LAYER) / D.LAYER)): "cap's drops on the pedestal",
    int(round((D.CAP_Z0 + D.LAYER) / D.LAYER)): "cap's floor over the pedestal",
    int(round((D.CAP_Z0 + D.CAP_ARM_RAISE + D.LAYER) / D.LAYER)): "cap's arms (bridges)",
    D.PAUSE_LAYER: "cover over the magnets",
}


def flatten(profiles, kind, name):
    d = json.load(open(os.path.join(profiles, kind, name + ".json")))
    if d.get("inherits"):
        base = flatten(profiles, kind, d["inherits"])
        base.update(d)
        d = base
    d.pop("inherits", None)
    return d


def features(gcode):
    """{layer: Counter(feature)} of extruding moves, and the custom G-code's position."""
    out, layer, feat = {}, 0, None
    pause = None
    lines = gcode.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("; Z_HEIGHT:"):
            layer += 1
            out[layer] = Counter()
        elif ln.startswith("; FEATURE:"):
            feat = ln.split(":", 1)[1].strip()
        elif ln.startswith("M400 U1") and pause is None:
            pause = layer
        elif ln[:2] in ("G1", "G2", "G3") and " E" in ln and layer:
            m = re.search(r" E([-\d.]+)", ln)
            if m and float(m.group(1)) > 0:
                out[layer][feat] += 1
    return out, pause


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bambu", help="the bambu-studio binary")
    ap.add_argument("--profiles", help="its resources/profiles/BBL directory (found from the binary by default)")
    ap.add_argument("--printers", default=",".join(PRINTERS))
    ap.add_argument("--plate", default=os.path.join(HERE, "out", "plate_bambu.3mf"))
    args = ap.parse_args()
    profiles = args.profiles or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(args.bambu))),
                                             "resources", "profiles", "BBL")
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for name in args.printers.split(","):
            files = []
            for kind, preset in zip(("machine", "process", "filament"), PRINTERS[name]):
                f = os.path.join(tmp, "%s_%s.json" % (name, kind))
                json.dump(flatten(profiles, kind, preset), open(f, "w"))
                files.append(f)
            out = os.path.join(tmp, name)
            os.makedirs(out)
            cmd = [args.bambu, "--datadir", os.path.join(tmp, "data"), "--debug", "2", "--slice", "0", "--arrange", "0",
                   "--orient", "0", "--load-settings", files[0] + ";" + files[1], "--load-filaments", files[2],
                   "--outputdir", out, "--export-3mf", "sliced.3mf", args.plate]
            p = subprocess.run(cmd, capture_output=True, text=True)
            gpath = os.path.join(out, "plate_1.gcode")
            if not os.path.exists(gpath):
                print("%s: slicing FAILED (exit %d)\n%s" % (name, p.returncode, p.stdout[-2000:] + p.stderr[-2000:]))
                ok = False
                continue
            g = open(gpath).read()
            head = {k: (re.search(pat, g) or [None, "?"])[1] for k, pat in (
                ("layers", r"total layer number: (\d+)"), ("time", r"total estimated time: ([^;\n]+)"),
                ("grams", r"total filament weight \[g\] : ([\d.]+)"))}
            warn = sorted({re.sub(r".*\] ", "", ln) for ln in (p.stdout + p.stderr).splitlines()
                           if "slicing warnings" in ln})
            feats, pause = features(g)
            good = pause == D.PAUSE_LAYER
            ok &= good
            print("%s: %s layers, %s, %s g of PLA; pause %s layer %s (want %d)" % (
                name, head["layers"], head["time"].strip(), head["grams"], "before" if good else "MISPLACED:",
                pause, D.PAUSE_LAYER))
            for w in warn:
                print("    slicer: " + w)
            for L, what in sorted(LAYERS.items()):
                c = feats.get(L, Counter())
                print("    layer %3d, %-30s bridge moves %3d, overhang-wall moves %3d" % (
                    L, what + ":", c["Bridge"], c["Overhang wall"]))
    print("slicer_check: %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
