#!/usr/bin/env python3
"""
view_geom.py -- top-view drawing of an antenna design (and, optionally, of what the
openEMS rasteriser actually made PEC at the copper plane, z = h).

    em-env python view_geom.py                 # previews of all shapes -> figs/geom_*.png
    em-env python view_geom.py --pec bat_ifa   # overlay the PEC edges for one design

Used by make_figs.py for the README pictures.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
import numpy as np

import shapes

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figs")

CU = "#c8902e"          # copper / ENIG
FR4 = "#7a8a5a"         # bare laminate
GND = "#5d6b77"


def draw(ax, d, show_ground=True, ground_depth=12.0, label_port=True, cu=CU, alpha=1.0,
         ann=True):
    if d.get("fr4"):
        for (x0, x1, y0, y1) in d["fr4"]:
            if y0 >= -1e-9:   # the tab / antenna strip
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=FR4, ec="none", alpha=0.35,
                                       zorder=0))
    if show_ground and d.get("ground"):
        gx0, gx1, gy0, gy1 = d["ground"]
        yb = max(gy0, gy1 - ground_depth)
        ax.add_patch(Rectangle((gx0, yb), gx1 - gx0, gy1 - yb, fc=GND, ec="none", alpha=0.85,
                               zorder=1))
        if ann:
            pc = 0.5 * (d["port"]["x0"] + d["port"]["x1"])
            ax.text(pc - 3.0, gy1 - 1.2, "ground (all layers)", color="w",
                    fontsize=7, va="top", ha="right", zorder=5)
    for P in d["polys"]:
        P = np.asarray(P, float)
        path = Path(np.vstack([P, P[:1]]), closed=True)
        ax.add_patch(PathPatch(path, fc=cu, ec="none", alpha=alpha, zorder=3))
    p = d["port"]
    ax.add_patch(Rectangle((p["x0"], p["y0"]), p["x1"] - p["x0"], p["y1"] - p["y0"], fc="#d62728",
                           ec="none", zorder=4))
    if label_port and ann:
        ax.annotate("50 Ω port", (0.5 * (p["x0"] + p["x1"]), 0.5 * (p["y0"] + p["y1"])),
                    xytext=(12, -16), textcoords="offset points", fontsize=7, color="#d62728",
                    arrowprops=dict(arrowstyle="-", color="#d62728", lw=0.6), zorder=6)
    ax.set_aspect("equal")


def preview(d, fn, title=None, xlim=None, ylim=None):
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
    draw(ax, d)
    allp = np.vstack([np.asarray(P, float) for P in d["polys"]])
    if xlim is None:
        xlim = (allp[:, 0].min() - 6, allp[:, 0].max() + 6)
    if ylim is None:
        ylim = (-8, allp[:, 1].max() + 5)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_title(title or d["name"], fontsize=9)
    ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout()
    fig.savefig(fn)
    plt.close(fig)


def pec_overlay(d, sim, fn, xlim=None, ylim=None):
    import antsim
    pts, lines, grid = antsim.pec_dump(d, sim)
    h = d["h"]
    z = pts[:, 2]
    a, b = lines[:, 0], lines[:, 1]
    on = (np.abs(z[a] - h) < 1e-6) & (np.abs(z[b] - h) < 1e-6)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=140)
    draw(ax, d, alpha=0.35, ann=False)
    seg = np.stack([pts[a[on], :2], pts[b[on], :2]], axis=1)
    from matplotlib.collections import LineCollection
    ax.add_collection(LineCollection(seg, colors="k", linewidths=0.5, zorder=8))
    allp = np.vstack([np.asarray(P, float) for P in d["polys"]])
    ax.set_xlim(*(xlim or (allp[:, 0].min() - 3, allp[:, 0].max() + 3)))
    ax.set_ylim(*(ylim or (-3, allp[:, 1].max() + 3)))
    ax.set_title(f"{d['name']}: PEC edges openEMS built at z = h (black) over the drawn copper",
                 fontsize=8)
    fig.tight_layout()
    fig.savefig(fn)
    plt.close(fig)
    return int(on.sum())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pec", default=None)
    ap.add_argument("--res", type=float, default=0.25)
    a = ap.parse_args()
    os.makedirs(FIGS, exist_ok=True)
    from run_candidates import BAT_PM, bat_design, ghost_design
    designs = {
        "dn007": shapes.dn007(),
        "bat_ifa": shapes.bat("ifa", span=44.0),
        "bat_dipole": shapes.bat("dipole", span=46.0, yb=16.0),
        "bat_split_ifa": shapes.bat("split_ifa", span=50.0),
        "bat_legfed": shapes.bat("legfed", span=50.0),
        "bat_pm": bat_design(BAT_PM),
        "ghost": ghost_design(),
    }
    if a.pec:
        n = pec_overlay(designs[a.pec], dict(res_fine=a.res),
                        os.path.join(FIGS, f"pec_{a.pec}.png"))
        print("PEC edges at z=h:", n)
    else:
        for k, d in designs.items():
            preview(d, os.path.join(FIGS, f"geom_{k}.png"))
            print("wrote", k)
