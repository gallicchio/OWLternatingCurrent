#!/usr/bin/env python3
"""List the copper in a window of the saved board, for debugging layout by
reading rather than squinting at renders.

    python3 tools/probe.py X0 Y0 X1 Y1 [--layer F.Cu]
    python3 tools/probe.py --at X Y

Board millimetres from the top-left corner.  The window form prints every
track, via and pad that touches it (net, layer, ends or size); --at prints
which zones' fills cover that point, layer by layer.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import board_info as BI

if "--inside" not in sys.argv:
    import subprocess, kienv
    r = subprocess.run(kienv.python() + [os.path.abspath(__file__), "--inside"] + sys.argv[1:],
                       cwd=ROOT, text=True, capture_output=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write("\n".join(l for l in r.stderr.splitlines() if "Font '" not in l))
    sys.exit(r.returncode)

import pcbnew

PCB = BI.PCB
ORIGIN = (100.0, 100.0)


def B(v):
    return (pcbnew.ToMM(v.x) - ORIGIN[0], pcbnew.ToMM(v.y) - ORIGIN[1])


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x + ORIGIN[0]), pcbnew.FromMM(y + ORIGIN[1]))


def main():
    args = [a for a in sys.argv[1:] if a != "--inside"]
    board = pcbnew.LoadBoard(PCB)
    if "--at" in args:
        i = args.index("--at")
        x, y = float(args[i + 1]), float(args[i + 2])
        for z in board.Zones():
            for layer in z.GetLayerSet().Seq():
                if z.HasFilledPolysForLayer(layer):
                    hit = z.GetFilledPolysList(layer).Contains(P(x, y))
                    inside = z.Outline().Contains(P(x, y))
                    if hit or inside:
                        print("%-10s %-10s %-12s outline %s, fill %s" % (board.GetLayerName(layer), z.GetNetname(),
                              z.GetZoneName() or "-", "yes" if inside else "no", "yes" if hit else "no"))
        return 0
    x0, y0, x1, y1 = (float(a) for a in args[:4])
    only = args[args.index("--layer") + 1] if "--layer" in args else None
    box = pcbnew.BOX2I(P(x0, y0), pcbnew.VECTOR2L(pcbnew.FromMM(x1 - x0), pcbnew.FromMM(y1 - y0)))
    for t in board.GetTracks():
        if not t.GetBoundingBox().Intersects(box):
            continue
        lname = board.GetLayerName(t.GetLayer())
        if only and lname != only and t.Type() != pcbnew.PCB_VIA_T:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            print("via    %-18s (%.3f, %.3f) %.2f/%.2f" % (t.GetNetname(), *B(t.GetPosition()),
                  pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)), pcbnew.ToMM(t.GetDrill())))
        else:
            print("track  %-18s %-7s (%.3f, %.3f)-(%.3f, %.3f) w %.3f" % (t.GetNetname(), lname, *B(t.GetStart()),
                  *B(t.GetEnd()), pcbnew.ToMM(t.GetWidth())))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if not p.GetBoundingBox().Intersects(box):
                continue
            sz = p.GetSize(pcbnew.F_Cu)
            print("pad    %-18s %-7s (%.3f, %.3f) %.2fx%.2f rot %g" % (p.GetNetname() or "-", "%s.%s" % (fp.GetReference(), p.GetNumber()),
                  *B(p.GetPosition()), pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y), p.GetOrientationDegrees()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
