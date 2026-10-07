#!/usr/bin/env python3
"""Concept sketch of the recommended board (not a layout): top view + side view.

    python3 art/concept.py  ->  docs/images/concept_v1.png
"""
import math, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Polygon as MPoly
from shapely.geometry import box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shapes as S
sys.path.insert(0, os.path.join(ROOT, "gen"))
import board_info as BI
from preview import patch, MASK, SILK, GOLD, LED

W, H = 170.0, 120.0


def glow(ax, x, y, c, r=2.2, z=6):
    for k, a in ((3.2, 0.10), (2.0, 0.22), (1.1, 0.5), (0.55, 1.0)):
        ax.add_patch(Circle((x, y), r * k / 2, color=LED[c], alpha=a, lw=0, zorder=z))


def draw_fig(ax, f, leds=True, led_r=1.6):
    for g in f.gold:
        patch(ax, g, GOLD, 2)
    hole = unary_union(f.hole) if f.hole else None
    for g in f.shadow:
        h = g.difference(hole) if hole is not None else g
        patch(ax, h, "#8a6a3a" if f.name == "moon" else MASK, 3, 0.55 if f.name == "moon" else 1)
    patch(ax, f.merged(), SILK, 4)
    if leds:
        for (x, y, c) in f.leds:
            glow(ax, x, y, c, led_r)


def coil(ax, cx, cy, r_out, r_in, turns, z=1.5, color="#6d4a8f"):
    th = [i * 2 * math.pi / 64 for i in range(int(turns * 64) + 1)]
    xs = [cx + (r_out - (r_out - r_in) * t / th[-1]) * math.cos(t) for t in th]
    ys = [cy + (r_out - (r_out - r_in) * t / th[-1]) * math.sin(t) for t in th]
    ax.plot(xs, ys, color=color, lw=0.9, zorder=z)


def top_view(ax):
    ax.add_patch(FancyBboxPatch((0, 0), W, H, boxstyle="round,pad=0,rounding_size=8",
                                fc=MASK, ec="#22102f", lw=2, zorder=0))
    # moon with the little witch
    draw_fig(ax, S.place(S.moon(), 50, 80, 31))
    draw_fig(ax, S.place(S.witch_on_broom(), 54, 77, 38, angle=8))
    # branch with owls from the right edge
    br = S.stroke(S.bezier((W, 97), (150, 90), (128, 99), (100, 92)), 2.6)
    tw = [S.stroke([(138, 95.5), (132, 104)], 1.2), S.stroke([(112, 94), (106, 100)], 1.0)]
    patch(ax, unary_union([br] + tw), SILK, 4)
    for x in (152, 134, 116):
        draw_fig(ax, S.place(S.owl(), x, 93.5, 19), led_r=1.5)
    # bats and stars
    draw_fig(ax, S.place(S.bat(), 98, 108, 22, angle=-8), led_r=1.0)
    draw_fig(ax, S.place(S.bat(), 22, 109, 14, angle=10), leds=False)
    draw_fig(ax, S.place(S.bat(), 160, 113, 11, angle=-12), leds=False)
    for (x, y) in ((10, 96), (92, 82), (122, 113), (138, 77), (8, 60), (100, 70), (75, 112),
                   (162, 72), (30, 50), (147, 108)):
        patch(ax, S.star(x, y, 1.6, 0.7), SILK, 4)
        glow(ax, x, y, "violet", 1.6)
    # familiar perches with their coils, and the pendulum/levitation coils
    for (x, y, name) in ((120, 27, "OWL"), (153, 27, "CAT")):
        coil(ax, x, y, 13, 4, 9)
        draw_fig(ax, S.place(S.magic_circle(), x, y, 15))
        ax.text(x, y, name, color=SILK, ha="center", va="center", fontsize=7, zorder=5,
                family="DejaVu Sans", weight="bold")
    for k in range(3):
        a = math.radians(90 + 120 * k)
        cx, cy = 82 + 17 * math.cos(a), 40 + 17 * math.sin(a)
        coil(ax, cx, cy, 11, 3, 8)
    ax.text(82, 40, "pendulum\ncoils", color=SILK, ha="center", va="center", fontsize=6, zorder=5)
    # pumpkins with glowing faces along the bottom
    for (x, s) in ((18, 20), (46, 16), (70, 11)):
        draw_fig(ax, S.place(S.pumpkin(), x, 4, s), led_r=2.6)
    # tree (3D print) footprint and the board's identity
    ax.add_patch(Circle((152, 60), 6, fc="none", ec=SILK, lw=0.8, ls="--", zorder=5))
    ax.text(152, 60, "tree\nfoot", color=SILK, ha="center", va="center", fontsize=5.5, zorder=5)
    ax.text(5, 4, "", color=SILK, fontsize=6)
    ax.text(W - 4, 3.5, BI.TITLE.upper() + "  (working name)  rev " + BI.REV, color=SILK, ha="right", fontsize=6.5,
            zorder=5, weight="bold")
    ax.set_xlim(-4, W + 4)
    ax.set_ylim(-4, H + 4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Top view (concept, not the layout): 170 x 120 mm, purple mask, ENIG gold moon",
                 fontsize=9)


def side_view(ax):
    ax.add_patch(Rectangle((0, 0), W, 1.6, fc="#3b1f5c", ec="k", lw=0.5, zorder=2))
    ax.add_patch(Rectangle((0, -9), W, 9, fc="none", ec="#999", lw=0.5, ls=":", zorder=1))
    ax.text(3, -6, "rubber feet / 3D-printed base", fontsize=6, color="#777")
    # tree: trunk from (150, 0) curving over to the perch at (82, 140)
    trunk = S.stroke(S.bezier((152, 0), (158, 70), (140, 150), (96, 148)), 6)
    patch(ax, trunk, "#5b3a1e", 3)
    patch(ax, S.stroke([(96, 148), (84, 146)], 5), "#5b3a1e", 3)
    ax.add_patch(Rectangle((70, 140.5), 24, 2.2, fc="#2a7a3a", ec="k", lw=0.4, zorder=4))
    ax.text(40, 158, "perch PCB: 4-layer coil + Hall sensor,\ntiny bias magnet above it", fontsize=6.5, va="top")
    # levitating bat 8.4 mm under the perch
    draw_fig(ax, S.place(S.bat(), 82, 127, 20), led_r=1.2)
    ax.annotate("", xy=(100, 131.5), xytext=(100, 140.5),
                arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax.text(103, 128, "PCB bat floats 8 mm\nbelow; eyes lit by\ninduction", fontsize=6.5)
    # pendulum alternative (dashed thread)
    ax.plot([82, 64], [140.5, 22], color="#aaa", lw=0.6, ls="--", zorder=1)
    ax.text(28, 30, "or: on a thread, a pendulum\nkicked by the 3 coils below", fontsize=6.5,
            color="#777")
    # familiars standing on their perches
    for (x, f, s, name) in ((120, S.owl(), 30, "owl"), (153, S.cat(), 26, "cat")):
        g = S.place(f, x, 1.6, s)
        for p in g.ink + g.line:
            patch(ax, p, "#d8ffd8", 3, 0.85)
        for (lx, ly, c) in g.leds:
            glow(ax, lx, ly, c, 1.3)
        ax.text(x, -4.5, f"{name}: glow PLA,\ncoil in its base", fontsize=5.5, ha="center")
    ax.set_xlim(-4, W + 4)
    ax.set_ylim(-12, 162)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Side view: 3D-printed tree, levitating bat, wireless familiars", fontsize=9)


def main():
    fig, ax = plt.subplots(1, 2, figsize=(15, 6.6), gridspec_kw=dict(width_ratios=[1.25, 1]))
    top_view(ax[0])
    side_view(ax[1])
    fig.tight_layout()
    out = os.path.join(ROOT, "docs", "images")
    os.makedirs(out, exist_ok=True)
    fn = os.path.join(out, "concept_v1.png")
    fig.savefig(fn, dpi=110)
    print(fn)


if __name__ == "__main__":
    main()
