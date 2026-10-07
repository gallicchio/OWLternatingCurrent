#!/usr/bin/env python3
"""Draw each character big, on the board's colours, to judge it by eye.

    python3 art/preview.py            -> art/out/characters.png
"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Circle
from matplotlib.path import Path
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shapes as S

MASK = "#3b1f5c"        # purple solder mask
SILK = "#f4f1ea"        # white silkscreen
GOLD = "#d9b24c"        # ENIG
LED = {"orange": "#ff8a1f", "violet": "#9b4dff", "amber": "#ffb000"}


def polys(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)):
        out = []
        for h in g.geoms:
            out += polys(h)
        return out
    return []


def patch(ax, g, color, z=1, alpha=1.0):
    for p in polys(g):
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            xy = list(ring.coords)
            verts += xy
            codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), fc=color, ec="none", zorder=z, alpha=alpha))


def draw(ax, fig, glow=True):
    from shapely.ops import unary_union
    for g in fig.gold:
        patch(ax, g, GOLD, 1)
    for g in fig.shadow:
        h = g.difference(unary_union(fig.hole)) if fig.hole else g
        # craters (shadow over gold, name 'moon') are mask over copper: a tint
        patch(ax, h, "#8a6a3a" if fig.name == "moon" else MASK, 2,
              0.55 if fig.name == "moon" else 1.0)
    ink = fig.merged()
    patch(ax, ink, SILK, 3)
    for (x, y, c) in fig.leds:
        if glow:
            for r, a in ((0.09, 0.15), (0.05, 0.35), (0.025, 1.0)):
                ax.add_patch(Circle((x, y), r * fig_scale(fig), color=LED[c], alpha=a, zorder=4, lw=0))


def fig_scale(fig):
    b = [g.bounds for g in fig.ink + fig.line + fig.gold + fig.shadow if not g.is_empty]
    if not b:
        return 1.0
    return max(max(x[2] for x in b) - min(x[0] for x in b), max(x[3] for x in b) - min(x[1] for x in b))


def main():
    figs = [S.owl(), S.bat(), S.pumpkin(), S.ghost(), S.cat(), S.witch_on_broom(),
            S.magic_circle()]
    moon = S.moon()
    witch = S.place(S.witch_on_broom(), 0.05, -0.05, 1.2)
    fig, axs = plt.subplots(2, 4, figsize=(16, 8.4), facecolor=MASK)
    for ax, f in zip(axs.flat, figs + [None]):
        ax.set_facecolor(MASK)
        ax.set_aspect("equal")
        ax.axis("off")
        if f is None:
            draw(ax, moon, glow=False)
            draw(ax, witch)
            ax.set_xlim(-1.1, 1.1)
            ax.set_ylim(-1.1, 1.1)
            ax.set_title("witch across the moon", color=SILK)
            continue
        draw(ax, f)
        ax.autoscale_view()
        ax.relim()
        b = [g.bounds for g in f.ink + f.line + f.gold + f.shadow]
        x0, y0 = min(x[0] for x in b), min(x[1] for x in b)
        x1, y1 = max(x[2] for x in b), max(x[3] for x in b)
        m = 0.1 * max(x1 - x0, y1 - y0)
        ax.set_xlim(x0 - m, x1 + m)
        ax.set_ylim(y0 - m, y1 + m)
        ax.set_title(f.name, color=SILK)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    out = os.path.join(HERE, "out", "characters.png")
    fig.tight_layout()
    fig.savefig(out, dpi=80, facecolor=MASK)
    print(out)


if __name__ == "__main__":
    main()
