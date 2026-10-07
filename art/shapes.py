#!/usr/bin/env python3
"""Cute Halloween characters as exact 2-D geometry (shapely), in millimetres.

Each character function returns a `Figure`: named lists of shapely geometries
for the layers they will become on the board, plus the points where LEDs sit.
The same geometry draws the concept sketch (matplotlib) and, later, the KiCad
silkscreen, solder-mask openings and gold (ENIG) copper, so the picture Jason
approves is the board he gets.

Conventions: x to the right, y UP (art convention; the board writer flips y),
each character drawn about its own origin at size 1 = its nominal height, then
placed with `place(fig, x, y, scale, angle, mirror)`.

Layers a Figure may carry:
  ink    - solid printed shape (silkscreen, white on the dark mask)
  line   - outlines as polygons already buffered to a stroke width
  hole   - areas cut out of the ink (eyes, smiles: the mask shows through)
  gold   - exposed ENIG copper (the moon)
  shadow - mask drawn over gold (a silhouette against the moon)
  leds   - (x, y, colour) where an LED's light appears ('orange', 'violet', ...)
"""
import math
from dataclasses import dataclass, field
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity


# ----------------------------------------------------------------------------
# primitives
# ----------------------------------------------------------------------------
def ellipse(cx, cy, rx, ry, angle=0.0, n=96):
    pts = [(cx + rx * math.cos(t), cy + ry * math.sin(t))
           for t in (2 * math.pi * i / n for i in range(n))]
    p = Polygon(pts)
    return affinity.rotate(p, angle, origin=(cx, cy)) if angle else p


def circle(cx, cy, r, n=96):
    return Point(cx, cy).buffer(r, resolution=max(8, n // 4))


def bezier(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def path(segs, n=24):
    """Closed polygon from a chain of cubic Bezier segments [(p0,p1,p2,p3), ...]."""
    pts = []
    for s in segs:
        b = bezier(*s, n=n)
        pts.extend(b if not pts else b[1:])
    return Polygon(pts).buffer(0)


def star(cx, cy, r_out, r_in=None, n=5, angle=90.0, round_=0.0):
    r_in = r_in if r_in is not None else r_out * 0.45
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        t = math.radians(angle) + math.pi * i / n
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    p = Polygon(pts)
    return p.buffer(round_).buffer(-round_) if round_ else p


def stroke(points, width, closed=False):
    """A centre-line drawn with round caps, as a polygon."""
    if closed:
        points = list(points) + [points[0]]
    return LineString(points).buffer(width / 2, cap_style=1, join_style=1)


def arc_pts(cx, cy, r, a0, a1, n=32):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


# ----------------------------------------------------------------------------
# a figure and its placement
# ----------------------------------------------------------------------------
@dataclass
class Figure:
    name: str
    ink: list = field(default_factory=list)
    line: list = field(default_factory=list)
    hole: list = field(default_factory=list)
    gold: list = field(default_factory=list)
    shadow: list = field(default_factory=list)
    leds: list = field(default_factory=list)

    def merged(self):
        """ink+line with holes removed: what prints."""
        g = unary_union(self.ink + self.line)
        if self.hole:
            g = g.difference(unary_union(self.hole))
        return g


def place(fig, x=0.0, y=0.0, scale=1.0, angle=0.0, mirror=False):
    def tf(g):
        if mirror:
            g = affinity.scale(g, -1, 1, origin=(0, 0))
        g = affinity.scale(g, scale, scale, origin=(0, 0))
        g = affinity.rotate(g, angle, origin=(0, 0))
        return affinity.translate(g, x, y)

    def tp(p):
        px, py = (-p[0] if mirror else p[0]) * scale, p[1] * scale
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        return (x + c * px - s * py, y + s * px + c * py)

    out = Figure(fig.name)
    for k in ("ink", "line", "hole", "gold", "shadow"):
        setattr(out, k, [tf(g) for g in getattr(fig, k)])
    out.leds = [(*tp(p[:2]), p[2]) for p in fig.leds]
    return out


# ----------------------------------------------------------------------------
# characters (each about 1 unit tall before scaling; LEDs marked where they glow)
# ----------------------------------------------------------------------------
def owl(w=0.03):
    """A round, sleepy-eyed owl. Eyes are LED windows (orange)."""
    f = Figure("owl")
    body = ellipse(0, 0.42, 0.36, 0.42)
    tufts = [Polygon([(-0.30, 0.70), (-0.27, 0.98), (-0.12, 0.80)]),
             Polygon([(0.30, 0.70), (0.27, 0.98), (0.12, 0.80)])]
    head = unary_union([body] + tufts).buffer(0.02).buffer(-0.02)
    f.line.append(head.exterior.buffer(w / 2))
    for sx in (-1, 1):
        # eye discs with an LED pupil
        f.line.append(circle(sx * 0.15, 0.62, 0.135).exterior.buffer(w / 2))
        f.ink.append(circle(sx * 0.15, 0.62, 0.05))
        f.leds.append((sx * 0.15, 0.62, "orange"))
        # wing
        f.line.append(stroke(bezier((sx * 0.30, 0.50), (sx * 0.42, 0.35),
                                    (sx * 0.38, 0.12), (sx * 0.20, 0.06)), w))
        # feet
        for dx in (-0.04, 0.0, 0.04):
            f.line.append(stroke([(sx * 0.13 + dx, 0.0), (sx * 0.13 + dx * 1.6, -0.06)], w * 0.9))
    f.ink.append(Polygon([(-0.05, 0.52), (0.05, 0.52), (0.0, 0.43)]))      # beak
    for (cx, cy) in ((-0.09, 0.30), (0.09, 0.30), (0.0, 0.22), (-0.09, 0.14), (0.09, 0.14)):
        f.line.append(stroke(arc_pts(cx, cy + 0.03, 0.045, 200, 340, 12), w * 0.8))  # chest
    return f


def bat(w=0.025):
    """A chubby little bat: pointed wing tips, scalloped trailing edges with
    finger lines, a round face with violet LED eyes and a tiny smile."""
    f = Figure("bat")
    body = ellipse(0, 0.0, 0.13, 0.16)
    ears = [Polygon([(-0.11, 0.08), (-0.10, 0.27), (-0.02, 0.13)]),
            Polygon([(0.11, 0.08), (0.10, 0.27), (0.02, 0.13)])]
    wings, fingers = [], []
    for sx in (-1, 1):
        wrist, tip = (sx * 0.36, 0.30), (sx * 0.88, 0.18)
        pts = bezier((sx * 0.09, 0.06), (sx * 0.18, 0.20), (sx * 0.26, 0.29), wrist, 12)
        pts += bezier(wrist, (sx * 0.55, 0.33), (sx * 0.75, 0.28), tip, 12)[1:]
        # trailing edge: three scallops between finger tips
        ftips = [tip, (sx * 0.66, -0.06), (sx * 0.42, -0.14), (sx * 0.12, -0.10)]
        for a, b in zip(ftips[:-1], ftips[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            pts += bezier(a, (a[0] - sx * 0.02, my + 0.10), (b[0] + sx * 0.04, my + 0.10), b, 12)[1:]
        wings.append(Polygon(pts).buffer(0))
        for ft in ftips[1:3]:
            fingers.append(stroke([wrist, ft], 0.016))
    f.ink.append(unary_union([body] + ears + wings).buffer(0.008).buffer(-0.008))
    f.hole.extend(fingers)
    for sx in (-1, 1):
        f.hole.append(circle(sx * 0.05, 0.04, 0.032))
        f.leds.append((sx * 0.05, 0.04, "violet"))
    f.hole.append(stroke(arc_pts(0, -0.015, 0.04, 215, 325, 10), 0.016))     # smile
    f.hole.append(Polygon([(-0.022, -0.052), (-0.008, -0.052), (-0.015, -0.078)]))  # tiny fang
    f.hole.append(Polygon([(0.008, -0.052), (0.022, -0.052), (0.015, -0.078)]))
    return f


def pumpkin(w=0.03, face=True):
    """Round jack-o'-lantern with a friendly face; the face glows (orange LEDs)."""
    f = Figure("pumpkin")
    ribs = [ellipse(dx, 0.36, rx, 0.36) for dx, rx in ((-0.22, 0.26), (0.22, 0.26),
                                                         (-0.10, 0.30), (0.10, 0.30), (0, 0.30))]
    body = unary_union(ribs)
    f.line.append(body.exterior.buffer(w / 2))
    for dx in (-0.12, 0.12):
        f.line.append(stroke(bezier((dx, 0.70), (dx * 1.6, 0.50), (dx * 1.6, 0.25), (dx, 0.02)), w * 0.8))
    f.ink.append(path([((-0.03, 0.70), (-0.05, 0.80), (-0.02, 0.86), (0.04, 0.90)),
                       ((0.04, 0.90), (0.06, 0.86), (0.03, 0.80), (0.04, 0.70)),
                       ((0.04, 0.70), (0.02, 0.69), (-0.01, 0.69), (-0.03, 0.70))]))     # stem
    f.line.append(stroke(bezier((0.04, 0.82), (0.14, 0.92), (0.22, 0.86), (0.16, 0.78)), w * 0.8))
    if face:
        eyes = [ellipse(-0.12, 0.47, 0.055, 0.07), ellipse(0.12, 0.47, 0.055, 0.07)]
        smile = path([((-0.20, 0.32), (-0.12, 0.14), (0.12, 0.14), (0.20, 0.32)),
                      ((0.20, 0.32), (0.10, 0.25), (-0.10, 0.25), (-0.20, 0.32))])
        tooth = Polygon([(0.02, 0.255), (0.08, 0.262), (0.075, 0.21), (0.03, 0.21)])
        f.ink.extend(eyes + [smile.difference(tooth)])
        f.leds.append((0, 0.33, "orange"))
    return f


def ghost(w=0.03):
    """A little ghost with a wavy hem and a surprised 'o' mouth."""
    f = Figure("ghost")
    top = arc_pts(0, 0.55, 0.30, 180, 0, 32)
    hem = []
    xs = [0.30, 0.15, 0.0, -0.15, -0.30]
    for i in range(4):
        hem += bezier((xs[i], 0.02 if i % 2 == 0 else 0.08), (xs[i] - 0.03, -0.05),
                      (xs[i + 1] + 0.05, -0.05), (xs[i + 1], 0.08 if i % 2 == 0 else 0.02))[1:]
    body = Polygon(top + [(0.30, 0.02)] + hem).buffer(0.02).buffer(-0.02)
    arms = [ellipse(-0.32, 0.35, 0.09, 0.05, 30), ellipse(0.32, 0.35, 0.09, 0.05, -30)]
    f.ink.append(unary_union([body] + arms))
    for sx in (-1, 1):
        f.hole.append(ellipse(sx * 0.10, 0.55, 0.045, 0.065))
    f.hole.append(ellipse(0, 0.40, 0.04, 0.05))
    f.leds.append((0, 0.45, "violet"))
    return f


def cat(w=0.03):
    """A sitting black cat seen from behind-ish, tail curled; orange LED eyes."""
    f = Figure("cat")
    body = ellipse(0, 0.28, 0.24, 0.28)
    head = circle(0, 0.70, 0.19)
    ears = [Polygon([(-0.17, 0.76), (-0.16, 1.0), (-0.04, 0.86)]),
            Polygon([(0.17, 0.76), (0.16, 1.0), (0.04, 0.86)])]
    tail = stroke(bezier((0.18, 0.05), (0.50, 0.0), (0.52, 0.35), (0.36, 0.42)), 0.07)
    f.ink.append(unary_union([body, head, tail] + ears).buffer(0.01).buffer(-0.01))
    for sx in (-1, 1):
        f.hole.append(ellipse(sx * 0.075, 0.71, 0.045, 0.06))
        f.leds.append((sx * 0.075, 0.71, "orange"))
    f.hole.append(Polygon([(-0.025, 0.63), (0.025, 0.63), (0.0, 0.60)]))
    return f


def witch_on_broom():
    """A six-year-old witch on her broom, as a silhouette (for the moon).

    Round face, a big floppy hat, pigtails, a cape streaming back, legs dangling,
    both hands on the broom, and her cat riding behind.  Units: 1 = broom length.
    """
    f = Figure("witch")
    broom = stroke([(-0.42, -0.03), (0.52, 0.05)], 0.022)
    bristles = path([((-0.42, -0.01), (-0.52, 0.05), (-0.64, 0.07), (-0.74, 0.10)),
                     ((-0.74, 0.10), (-0.70, 0.01), (-0.70, -0.08), (-0.76, -0.14)),
                     ((-0.76, -0.14), (-0.64, -0.11), (-0.52, -0.08), (-0.42, -0.05))])
    ties = stroke([(-0.44, 0.02), (-0.44, -0.07)], 0.022)
    head = circle(0.10, 0.285, 0.072)
    pigtails = [ellipse(0.02, 0.27, 0.035, 0.022, -25), ellipse(0.035, 0.225, 0.03, 0.02, -50)]
    brim = ellipse(0.095, 0.345, 0.155, 0.026, 8)
    cone = path([((0.00, 0.35), (0.02, 0.43), (0.05, 0.52), (0.04, 0.60)),
                 ((0.04, 0.60), (0.10, 0.55), (0.15, 0.45), (0.18, 0.36)),
                 ((0.18, 0.36), (0.12, 0.36), (0.06, 0.35), (0.00, 0.35))])
    tip = stroke(bezier((0.04, 0.60), (0.00, 0.66), (-0.07, 0.64), (-0.08, 0.57)), 0.028)
    dress = path([((0.06, 0.22), (0.02, 0.14), (0.00, 0.07), (-0.02, 0.02)),
                  ((-0.02, 0.02), (0.06, 0.05), (0.14, 0.06), (0.20, 0.04)),
                  ((0.20, 0.04), (0.18, 0.11), (0.16, 0.17), (0.14, 0.22))])
    cape = path([((0.06, 0.22), (-0.04, 0.24), (-0.14, 0.20), (-0.22, 0.14)),
                 ((-0.22, 0.14), (-0.16, 0.13), (-0.12, 0.11), (-0.16, 0.07)),
                 ((-0.16, 0.07), (-0.08, 0.10), (0.00, 0.12), (0.05, 0.14))])
    arm = stroke([(0.12, 0.19), (0.21, 0.12), (0.29, 0.065)], 0.032)
    legs = [stroke([(0.13, 0.04), (0.16, -0.07), (0.215, -0.075)], 0.034),
            stroke([(0.05, 0.03), (0.07, -0.08), (0.12, -0.085)], 0.034)]
    kitty = place(cat(), -0.26, -0.005, 0.19)
    f.shadow.append(unary_union([broom, bristles, ties, head, brim, cone, tip, dress, cape, arm]
                                + pigtails + legs + kitty.ink))
    f.hole.append(circle(0.135, 0.29, 0.011))                                   # eye
    f.hole.append(stroke(arc_pts(0.125, 0.262, 0.028, 250, 335, 8), 0.010))     # smile
    f.hole.extend(kitty.hole)
    return f


def moon(r=1.0, craters=True):
    """Full moon in gold with soft craters (mask dots over the gold)."""
    f = Figure("moon")
    f.gold.append(circle(0, 0, r, 256))
    if craters:
        for (cx, cy, cr) in ((0.35, 0.45, 0.16), (-0.42, 0.20, 0.11), (0.10, -0.50, 0.20),
                             (-0.20, -0.25, 0.08), (0.55, -0.10, 0.07), (-0.55, -0.45, 0.09),
                             (0.20, 0.10, 0.05), (-0.05, 0.62, 0.06)):
            f.shadow.append(circle(cx * r, cy * r, cr * r))
    return f


def magic_circle(r=1.0, label=None, w=0.03):
    """A familiar's perch: a ring of little stars and moons (no occult symbols)."""
    f = Figure("perch")
    f.line.append(circle(0, 0, r).exterior.buffer(w / 2))
    f.line.append(circle(0, 0, r * 0.86).exterior.buffer(w / 3))
    for i in range(8):
        a = math.radians(90 + 45 * i)
        x, y = 0.93 * r * math.cos(a), 0.93 * r * math.sin(a)
        if i % 2 == 0:
            f.ink.append(star(x, y, 0.06 * r, 0.026 * r, 5, angle=90 + 45 * i))
        else:
            c = circle(x, y, 0.045 * r).difference(circle(x + 0.022 * r, y + 0.012 * r, 0.04 * r))
            f.ink.append(c)
    return f


def stars_field(points, size=0.8):
    f = Figure("stars")
    for (x, y) in points:
        f.ink.append(star(x, y, size, size * 0.42, 5))
    return f
