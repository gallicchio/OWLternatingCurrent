#!/usr/bin/env python3
"""Draw the router's obstacle grid that `gen/board.py --stamp NET X Y R`
saved in build/stamp.json: one panel per routing layer (white free, grey
blocked for the net's width, blue the net's own copper) and one for where a
via fits (green).

    python3 tools/plot_stamp.py [build/stamp.json] [out.png]
"""
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

src = sys.argv[1] if len(sys.argv) > 1 else "build/stamp.json"
out = sys.argv[2] if len(sys.argv) > 2 else "build/view/stamp.png"
d = json.load(open(src))
ny, nx = len(d["via"]), len(d["via"][0])
ext = [d["x0"], d["x0"] + nx * d["pitch"], d["y0"] + ny * d["pitch"], d["y0"]]
fig, axs = plt.subplots(1, 4, figsize=(18, 5), dpi=110)
cm = ListedColormap(["white", "#999999", "#3070d0"])
for ax, rows, name in zip(axs, d["layers"], ("F.Cu", "In2.Cu", "B.Cu")):
    ax.imshow(rows, cmap=cm, vmin=0, vmax=2, extent=ext, interpolation="nearest")
    ax.set_title("%s  %s" % (d["net"], name), fontsize=8)
axs[3].imshow(d["via"], cmap=ListedColormap(["#40c040", "#dddddd"]), vmin=0, vmax=1, extent=ext, interpolation="nearest")
axs[3].set_title("via fits (green)", fontsize=8)
for ax in axs:
    ax.tick_params(labelsize=6)
    ax.grid(True, lw=0.2)
plt.tight_layout()
plt.savefig(out)
print(out)
