#!/usr/bin/env python3
"""Draw the router's view round each net left in pieces (gen/board.py --stamps):

    python3 tools/stamps.py base        build/view/stamp_base_<n>.png

Per stamp, one panel a layer (F.Cu, In1, B.Cu) and one for vias: white free, grey
blocked for the net's track, the net's own copper in colour; vias: black where none fits.
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "base"
    st = json.load(open(os.path.join(ROOT, "build", "stamps_%s.json" % name)))
    out = os.path.join(ROOT, "build", "view")
    os.makedirs(out, exist_ok=True)
    for n, s in enumerate(st):
        fig, ax = plt.subplots(1, 4, figsize=(16, 4.4))
        for L, title in enumerate(("F.Cu", "In1", "B.Cu")):
            a = np.array(s["layers"][L])
            img = np.ones(a.shape + (3,))
            img[a == 1] = (0.6, 0.6, 0.6)
            img[a == 2] = (0.85, 0.2, 0.2)
            ax[L].imshow(img, origin="upper", interpolation="nearest")
            ax[L].set_title(title)
        v = np.array(s["via"])
        ax[3].imshow(1 - v, cmap="gray", origin="upper", interpolation="nearest", vmin=0, vmax=1)
        ax[3].set_title("vias")
        for a in ax:
            a.set_xticks([]); a.set_yticks([])
        fig.suptitle("%s at (%.1f, %.1f) on %s: %s" % (s["net"], s["at"][0], s["at"][1], s["board"], ", ".join(s["what"])))
        p = os.path.join(out, "stamp_%s_%02d.png" % (name, n))
        fig.savefig(p, dpi=70)
        plt.close(fig)
        print(p)


if __name__ == "__main__":
    main()
