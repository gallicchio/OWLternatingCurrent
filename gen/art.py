#!/usr/bin/env python3
"""The art and the outlines of every board on the panel, as plain geometry.

    python3 gen/art.py            draw everything, check it, write hardware/art.json and
                                  the previews docs/images/art_<board>_<top|bottom>.png
    python3 gen/art.py --no-png   the JSON and the checks only
    AppRun python3.11 gen/art.py --extract-font
                                  (KiCad's own Python) re-read KiCad's stroke font into
                                  art/kicad_font.json

Drawing needs shapely (system Python).  gen/board.py runs in KiCad's Python, which has
none, so it reads hardware/art.json; the functions below also work there, from that file.

Coordinates are millimetres in each board's own frame (gen/layout.py): x right, y down,
seen from the top (KiCad's view), origin at the board's top-left corner, or at its coil's
centre for the perch, the bat and the tokens.  Angles are degrees.

Boards: "base", "tree", "perch", "bat", "owl_token", "cat_token".

The Python API
--------------
outline(board) -> [polyline, ...]
    Closed polylines [(x, y), ...] for Edge.Cuts (the last point joins the first; it is
    not repeated).  The first is the board's edge; any others are cut-outs (the perch's
    thread hole).  The base's foot holes are footprints (H1-H4), not outlines.
art(board) -> {layer: [item, ...]}
    Layers "F.SilkS", "B.SilkS", "F.Mask" (openings), "F.Cu", "B.Cu" (copper art; none
    yet beyond the antennas below).  Items:
      ("poly", pts)                          a filled polygon, no holes
      ("polyline", pts, width)               a stroked line, round ends
      ("circle", cx, cy, r, width)           a stroked circle
      ("arc", cx, cy, r, a0, a1, width)      a stroked arc from a0 to a1 (a0 < a1), angles
                                             from +x toward +y (clockwise on the screen)
      ("text", s, x, y, height, angle, justify)
          KiCad text in KiCad's stroke font, one line.  (x, y) is the anchor, vertically
          centred (KiCad's default); justify is "left", "center" or "right"; angle is
          counter-clockwise as seen on the screen.  Stroke width: text_thickness(height)
          = max(0.15, 0.15 * height).  "_{...}" and "^{...}" are KiCad's sub- and
          superscript markup.  Text on B.* layers is mirrored (KiCad's back-side text):
          (x, y) is still in the top view's frame, and "left" means the text starts at
          the anchor and reads to the right as seen from below (toward -x in this frame).
antennas() -> [{"net", "copper", "mask_open", "keepout", "pad"}, ...]
    The base's two theremin antennas, "MOON" (pitch) and "GHOST" (volume):
      copper     [polygon, ...]  F.Cu on that net (a zone or filled shapes; pad
                                 connection solid, or thermal spokes would show in the gold)
      mask_open  [polygon, ...]  F.Mask openings: the gold (they leave the craters, the
                                 witch, the ghost's eyes and smile under the mask)
      keepout    polygon         the shape grown by layout.ANTENNA_KEEPOUT: no copper on
                                 any other net or layer, and no parts
      pad        (x, y)          where the antenna part's pad (AE1 for the moon, AE2 for the
                                 ghost; TestPoint_Pad_D1.5mm) goes: inside the shape, flush
                                 with its edge, on the side toward its oscillator
keepouts(board) -> [(polygon, layers, what), ...]
    Areas the board generator must keep parts out of: layers names the side ("F.Cu" no
    top-side parts, "B.Cu" no bottom-side parts); what says why (the spell book's text,
    the printed owl and bat cap).
text_thickness(h), text_width(s, h), text_segments(...)
    KiCad's stroke font, measured: the widths and strokes KiCad draws (to within 1 um).

hardware/art.json (what gen/board.py reads)
-------------------------------------------
{"meta": {...},
 "boards": {"base": {"outline": [[[x, y], ...], ...],
                     "layers": {"F.SilkS": [item, ...], ...},
                     "keepouts": [{"pts": [[x, y], ...], "layers": ["B.Cu"], "what": "..."}]},
            "tree": {...}, ...},
 "antennas": [{"net": "MOON", "copper": [[[x, y], ...]], "mask_open": [[[x, y], ...], ...],
               "keepout": [[x, y], ...], "pad": [x, y]}, ...]}
with items
  {"kind": "poly", "pts": [[x, y], ...]}
  {"kind": "polyline", "pts": [[x, y], ...], "width": w}
  {"kind": "circle", "c": [x, y], "r": r, "width": w}
  {"kind": "arc", "c": [x, y], "r": r, "a0": a0, "a1": a1, "width": w,
                  "start": [x, y], "mid": [x, y], "end": [x, y]}
  {"kind": "text", "s": "...", "at": [x, y], "h": h, "angle": a, "justify": "center",
                   "thickness": t, "mirror": false}
Everything is already flat (polylines and polygons, no curves) and in each board's own
frame.  meta.inputs_sha256 hashes the files the art is drawn from; when gen/layout.py,
gen/placement.py, gen/mech.py or gen/board_info.py change, run this again (stale() says).

Rules the art keeps (CLAUDE_PCB.md sections 6 and 16, JLCPCB): silk text at least 1.0 mm
high, strokes at least 0.15 mm; silk 0.5 mm inside the edge and 0.3 mm from mask
openings and pads; mask openings and the mask between them at least 0.3 mm across; art
clear of every part's courtyard (gen/placement.py places them; the footprints are
hardware/lib's), of the star LEDs by 3 mm, the small LEDs by 1.75 mm, the pumpkins' 5050s
by 4.2 mm and the feet by 5.5 mm.  Coils take only thin lines on top; the spell book
lies inside the coils and antennas underneath and in patches kept free of parts.
"""
import hashlib, json, math, os, subprocess, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import layout as L
import mech as M
import board_info as BI

BOARDS = ("base", "tree", "perch", "bat", "owl_token", "cat_token")
FONT_JSON = os.path.join(ROOT, "art", "kicad_font.json")
ART_JSON = os.path.join(ROOT, "hardware", "art.json")
IMAGES = os.path.join(ROOT, "docs", "images")
INPUTS = [os.path.join(HERE, f) for f in ("art.py", "layout.py", "placement.py", "mech.py", "board_info.py")] + \
         [os.path.join(ROOT, "art", "shapes.py"), FONT_JSON, os.path.join(ROOT, "hardware", "checks", "netlist.net")]

try:
    from shapely.geometry import Polygon, Point, LineString, MultiPolygon, MultiPoint, GeometryCollection, box
    from shapely.ops import unary_union, linemerge
    from shapely import affinity
    HAVE_SHAPELY = True
except ImportError:                      # KiCad's Python: serve hardware/art.json
    HAVE_SHAPELY = False


# ======================================================================================
# Text: KiCad's own stroke font, so that sizes and widths here are what KiCad draws
# ======================================================================================
_FONT = None


def font():
    global _FONT
    if _FONT is None:
        with open(FONT_JSON, encoding="utf-8") as f:
            _FONT = json.load(f)
    return _FONT


def text_thickness(h):
    """The stroke width of silkscreen text h mm high (board.py uses the same rule)."""
    return round(max(0.15, 0.15 * h), 3)


def _runs(s):
    """KiCad markup: '_{...}' is a subscript, '^{...}' a superscript."""
    out, buf, i = [], "", 0
    while i < len(s):
        if s[i] in "_^" and s[i + 1:i + 2] == "{":
            j = s.find("}", i + 2)
            if j > 0:
                if buf:
                    out.append((buf, ""))
                    buf = ""
                out.append((s[i + 2:j], "sub" if s[i] == "_" else "sup"))
                i = j + 1
                continue
        buf += s[i]
        i += 1
    if buf:
        out.append((buf, ""))
    return out


def _glyph(c):
    g = font()["glyphs"].get(c)
    if g is None:
        raise ValueError("KiCad's stroke font has no glyph for %r" % c)
    return g


def text_width(s, h):
    """The line width KiCad justifies by: the sum of the glyphs' advances."""
    meta = font()["meta"]
    w = 0.0
    for run, style in _runs(s):
        k = meta[style]["scale"] if style else 1.0
        w += sum(_glyph(c)["adv"] for c in run) * k * h
    return w


def text_segments(s, x, y, h, angle=0.0, justify="center", mirror=False, th=None):
    """The stroke centre-lines KiCad draws for one line of text: [((x0, y0), (x1, y1))].
    Checked against pcbnew (KiCad 10.0.6): within 1 um, rotated, mirrored, with
    sub- and superscripts."""
    meta = font()["meta"]
    th = text_thickness(h) if th is None else th
    W = text_width(s, h)
    pen = {"left": meta["x_th"] * th, "center": -W / 2, "right": -(W + meta["x_th"] * th)}[justify]
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    segs = []
    for run, style in _runs(s):
        k = meta[style]["scale"] if style else 1.0
        dy0 = meta[style]["dy"] if style else 0.0
        for c in run:
            g = _glyph(c)
            for (gx0, gy0, gx1, gy1) in g["s"]:
                pts = []
                for gx, gy in ((gx0, gy0), (gx1, gy1)):
                    dx = pen + k * gx * h
                    dy = (k * gy + dy0) * h + meta["y_th"] * th
                    if mirror:
                        dx = -dx
                    pts.append((x + dx * ca + dy * sa, y - dx * sa + dy * ca))
                segs.append(tuple(pts))
            pen += g["adv"] * k * h
    return segs


# ======================================================================================
# The API
# ======================================================================================
_DATA = None


def inputs_sha():
    h = hashlib.sha256()
    for p in INPUTS:
        if os.path.exists(p):
            h.update(os.path.basename(p).encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()


def stale():
    """True when hardware/art.json is missing or older than what it is drawn from."""
    try:
        with open(ART_JSON, encoding="utf-8") as f:
            return json.load(f)["meta"]["inputs_sha256"] != inputs_sha()
    except (OSError, ValueError, KeyError):
        return True


class ArtUnavailable(ImportError):
    """No shapely here and no hardware/art.json yet (an ImportError, so that a caller
    that falls back when the art module is missing falls back here too)."""


def _data():
    global _DATA
    if _DATA is None:
        if HAVE_SHAPELY and stale():
            _DATA = build()
        else:
            if not os.path.exists(ART_JSON):
                raise ArtUnavailable("hardware/art.json is missing: run python3 gen/art.py (it needs shapely)")
            with open(ART_JSON, encoding="utf-8") as f:
                _DATA = json.load(f)
            if stale():
                sys.stderr.write("art: hardware/art.json is older than its inputs; run python3 gen/art.py\n")
    return _DATA


def _pts(p):
    return [tuple(q) for q in p]


def _item_tuple(it):
    k = it["kind"]
    if k == "poly":
        return ("poly", _pts(it["pts"]))
    if k == "polyline":
        return ("polyline", _pts(it["pts"]), it["width"])
    if k == "circle":
        return ("circle", it["c"][0], it["c"][1], it["r"], it["width"])
    if k == "arc":
        return ("arc", it["c"][0], it["c"][1], it["r"], it["a0"], it["a1"], it["width"])
    if k == "text":
        return ("text", it["s"], it["at"][0], it["at"][1], it["h"], it["angle"], it["justify"])
    raise ValueError(k)


def outline(board):
    return [_pts(p) for p in _data()["boards"][board]["outline"]]


def art(board):
    return {lay: [_item_tuple(it) for it in items] for lay, items in _data()["boards"][board]["layers"].items()}


def antennas():
    return [{"net": a["net"], "copper": [_pts(p) for p in a["copper"]], "mask_open": [_pts(p) for p in a["mask_open"]],
             "keepout": _pts(a["keepout"]), "pad": tuple(a["pad"])} for a in _data()["antennas"]]


def keepouts(board):
    return [(_pts(k["pts"]), tuple(k["layers"]), k["what"]) for k in _data()["boards"][board]["keepouts"]]


# ======================================================================================
# Geometry (shapely; the board's frame: x right, y down, millimetres)
# ======================================================================================
def polys(g):
    """The polygons in any geometry."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    out = []
    for h in getattr(g, "geoms", []):
        out += polys(h)
    return out


def lines(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    out = []
    for h in getattr(g, "geoms", []):
        out += lines(h)
    return out


def U(*gs):
    flat = []
    for g in gs:
        if isinstance(g, (list, tuple)):
            flat += [h for h in g if h is not None]
        elif g is not None:
            flat.append(g)
    return unary_union(flat) if flat else GeometryCollection()


def circle(cx, cy, r, n=None):
    n = n or max(32, int(2 * math.pi * r / 0.25))
    return Polygon([(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)])


def ellipse(cx, cy, rx, ry, angle=0.0, n=96):
    p = Polygon([(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)])
    return affinity.rotate(p, angle, origin=(cx, cy)) if angle else p


def superellipse(cx, cy, a, b, n=2.5, k=180):
    pts = []
    for i in range(k):
        t = 2 * math.pi * i / k
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + a * math.copysign(abs(c) ** (2 / n), c), cy + b * math.copysign(abs(s) ** (2 / n), s)))
    return Polygon(pts)


def arc_pts(cx, cy, r, a0, a1, n=None):
    """Points on an arc; degrees from +x toward +y (clockwise on the screen)."""
    n = n or max(4, int(abs(a1 - a0) / 360 * 2 * math.pi * r / 0.3))
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def chain(*segs):
    """Join point lists, dropping each joint's repeated point."""
    out = []
    for s in segs:
        s = list(s)
        if not s:
            continue
        out += s if not out else (s[1:] if math.dist(out[-1], s[0]) < 1e-6 else s)
    return out


def catmull(pts, n=12):
    """A smooth curve through the points (Catmull-Rom)."""
    P = list(pts)
    P = [(2 * P[0][0] - P[1][0], 2 * P[0][1] - P[1][1])] + P + [(2 * P[-1][0] - P[-2][0], 2 * P[-1][1] - P[-2][1])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    out.append(P[-2])
    return out


def stroke(pts, w):
    return LineString(pts).buffer(w / 2, cap_style=1, join_style=1, resolution=8)


def taper(pts, w0, w1):
    """A stroke whose width runs from w0 to w1 along it."""
    n = len(pts)
    parts = []
    for i in range(n - 1):
        a = Point(pts[i]).buffer((w0 + (w1 - w0) * i / (n - 1)) / 2, resolution=8)
        b = Point(pts[i + 1]).buffer((w0 + (w1 - w0) * (i + 1) / (n - 1)) / 2, resolution=8)
        parts.append(U(a, b).convex_hull)
    return U(parts)


def star_pts(cx, cy, r_out, r_in, n=5, rot=-90.0):
    """A star's outline; rot is the first tip's direction (-90 = up on the screen)."""
    return [(cx + (r_out if i % 2 == 0 else r_in) * math.cos(math.radians(rot + 180.0 * i / n)),
             cy + (r_out if i % 2 == 0 else r_in) * math.sin(math.radians(rot + 180.0 * i / n))) for i in range(2 * n)]


def rounded(g, r):
    """Round convex and concave corners by r."""
    return g.buffer(r, resolution=8).buffer(-2 * r, resolution=8).buffer(r, resolution=8)


def tf(g, dx=0.0, dy=0.0, s=1.0, rot=0.0, flipy=False):
    """Flip (art/shapes.py draws y up), scale, turn (degrees, clockwise on the screen),
    move."""
    if flipy:
        g = affinity.scale(g, 1, -1, origin=(0, 0))
    if s != 1.0:
        g = affinity.scale(g, s, s, origin=(0, 0))
    if rot:
        g = affinity.rotate(g, rot, origin=(0, 0))
    return affinity.translate(g, dx, dy)


def rrect(x0, y0, x1, y1, r, n=12):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def ring_pts(p):
    """A polygon's exterior as points (no closing repeat), rounded to 0.1 um."""
    return [(round(x, 4), round(y, 4)) for x, y in list(p.exterior.coords)[:-1]]


def simple_polys(g, min_area=0.004):
    """Hole-free polygons that together cover g (a KiCad filled shape has no holes): a
    polygon with holes is cut through its first hole, recursively."""
    out = []
    for p in polys(g):
        for q in polys(p.buffer(0)):
            if q.area < min_area:
                continue
            if not q.interiors:
                out.append(q)
                continue
            hx = Polygon(q.interiors[0]).representative_point().x
            x0, y0, x1, y1 = q.bounds
            out += simple_polys(q.intersection(box(x0 - 1, y0 - 1, hx, y1 + 1)), min_area)
            out += simple_polys(q.intersection(box(hx, y0 - 1, x1 + 1, y1 + 1)), min_area)
    return out


def edge_clear(outline_pts, margin):
    """Everything outside the board, grown inward by margin."""
    p = Polygon(outline_pts)
    x0, y0, x1, y1 = p.bounds
    return box(x0 - 20, y0 - 20, x1 + 20, y1 + 20).difference(p.buffer(-margin))


# ======================================================================================
# A board's drawing: items per layer, each clipped against what it must leave clear.
# Things are drawn front to back: whatever stands in front adds itself to the clear area
# (keep_clear), so that what is behind it is hidden.
# ======================================================================================
SILK_EDGE = 0.5          # silk this far inside a board's edge
MASK_GAP = 0.3           # silk, and other openings, this far from a mask opening
PAD_GAP = 0.3            # silk this far from a pad
COURT_GAP = 0.25         # and from a courtyard
MIN_TEXT = 1.0           # mm, JLCPCB's legible minimum is 0.8; the brief asks for 1.0
MIN_STROKE = 0.15


class Canvas:
    def __init__(self, name):
        self.name = name
        self.items = defaultdict(list)       # layer -> API tuples
        self.geoms = defaultdict(list)       # layer -> each item's shapely geometry
        self.clear = {}                      # layer -> what nothing on the layer may cover
        self.notes = []                      # problems the checks found

    def keep_clear(self, layer, g):
        self.clear[layer] = U(self.clear.get(layer), g)

    def line(self, layer, pts, w, clip=True):
        assert w >= MIN_STROKE - 1e-9, "stroke under 0.15 mm"
        ls = LineString(pts)
        c = self.clear.get(layer)
        pieces = lines(ls.difference(c.buffer(w / 2, resolution=8))) if (clip and c is not None and not c.is_empty) else [ls]
        merged = lines(linemerge(pieces)) if len(pieces) > 1 else pieces
        for p in merged:
            if p.length < max(w, 0.25):
                continue
            self.items[layer].append(("polyline", [(round(x, 4), round(y, 4)) for x, y in p.coords], round(w, 3)))
            self.geoms[layer].append(p.buffer(w / 2, resolution=8))

    def circle(self, layer, cx, cy, r, w, clip=True):
        g = circle(cx, cy, r + w / 2).difference(circle(cx, cy, max(r - w / 2, 0.001)))
        c = self.clear.get(layer)
        if clip and c is not None and g.intersects(c):
            self.line(layer, arc_pts(cx, cy, r, 0, 360), w)
            return
        self.items[layer].append(("circle", round(cx, 4), round(cy, 4), round(r, 4), round(w, 3)))
        self.geoms[layer].append(g)

    def arc(self, layer, cx, cy, r, a0, a1, w, clip=True):
        pts = arc_pts(cx, cy, r, a0, a1)
        g = LineString(pts).buffer(w / 2, resolution=8)
        c = self.clear.get(layer)
        if clip and c is not None and g.intersects(c):
            self.line(layer, pts, w)
            return
        self.items[layer].append(("arc", round(cx, 4), round(cy, 4), round(r, 4), round(a0, 3), round(a1, 3), round(w, 3)))
        self.geoms[layer].append(g)

    def poly(self, layer, g, clip=True, min_area=0.02):
        c = self.clear.get(layer)
        if clip and c is not None and not c.is_empty:
            g = g.difference(c)
        for p in simple_polys(g, min_area):
            self.items[layer].append(("poly", ring_pts(p)))
            self.geoms[layer].append(p)

    def outline_strokes(self, layer, g, w):
        """Every ring of a shape, as a stroked line."""
        for p in polys(g):
            for r in [p.exterior] + list(p.interiors):
                self.line(layer, list(r.coords), w)

    def text(self, layer, s, x, y, h, angle=0.0, justify="center"):
        if h < MIN_TEXT - 1e-9:
            raise ValueError("silk text under %.1f mm: %r" % (MIN_TEXT, s))
        mirror = layer.startswith("B.")
        th = text_thickness(h)
        g = text_geom(s, x, y, h, angle, justify, mirror)
        c = self.clear.get(layer)
        if c is not None and g.intersects(c):
            self.notes.append("%s %s: text %r crosses a keep-clear area" % (self.name, layer, s))
        self.items[layer].append(("text", s, round(x, 4), round(y, 4), round(h, 3), round(angle, 3), justify))
        self.geoms[layer].append(g)
        return g


def text_geom(s, x, y, h, angle=0.0, justify="center", mirror=False):
    th = text_thickness(h)
    return U([LineString(sg).buffer(th / 2, resolution=6) if math.dist(*sg) > 1e-6 else Point(sg[0]).buffer(th / 2)
              for sg in text_segments(s, x, y, h, angle, justify, mirror, th)])


# ======================================================================================
# The parts, as gen/placement.py places them: their courtyards and pads (the footprints
# are hardware/lib/OWL.pretty's, named by the schematic's netlist)
# ======================================================================================
LIBDIR = os.path.join(ROOT, "hardware", "lib", "OWL.pretty")
_FP, _NET = {}, None
COIL_FP = {"L3": "Coil_PEND", "L4": "Coil_PEND", "L5": "Coil_PEND", "L6": "Coil_PERCH", "L7": "Coil_PERCH",
           "L201": "Coil_LEV", "L301": "Coil_BAT", "L401": "Coil_TOKEN", "L501": "Coil_TOKEN"}
MISSING = set()


def _sexp():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from sexp import parse, kids, kid, val
    return parse, kids, kid, val


def footprint_geometry(name):
    """(courtyard or None, [(pad, through-hole?)]) in the footprint's own frame."""
    if name in _FP:
        return _FP[name]
    parse, kids, kid, val = _sexp()
    doc = parse(open(os.path.join(LIBDIR, name + ".kicad_mod"), encoding="utf-8").read())[0]
    num = lambda node, i: float(node[i][1])
    pts, shapes = [], []
    for node in doc:
        if not isinstance(node, list) or not node or not isinstance(node[0], tuple):
            continue
        h, lay = node[0][1], kid(node, "layer")
        if lay is None or val(lay) != "F.CrtYd":
            continue
        if h in ("fp_line", "fp_rect"):
            s, e = kid(node, "start"), kid(node, "end")
            x0, y0, x1, y1 = num(s, 1), num(s, 2), num(e, 1), num(e, 2)
            pts += [(x0, y0), (x1, y1)] if h == "fp_line" else [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif h == "fp_circle":
            c, e = kid(node, "center"), kid(node, "end")
            shapes.append(circle(num(c, 1), num(c, 2), math.hypot(num(e, 1) - num(c, 1), num(e, 2) - num(c, 2))))
        elif h == "fp_poly":
            pts += [(num(p, 1), num(p, 2)) for p in kids(kid(node, "pts"), "xy")]
        elif h == "fp_arc":
            a, m, e = [(num(kid(node, k), 1), num(kid(node, k), 2)) for k in ("start", "mid", "end")]
            pts += [a, m, e]
    court = MultiPoint(pts).convex_hull if len(pts) >= 3 else None
    if shapes:
        court = U(court, shapes)
    pads = []
    for node in kids(doc, "pad"):
        at, sz = kid(node, "at"), kid(node, "size")
        x, y = num(at, 1), num(at, 2)
        rot = num(at, 3) if len(at) > 3 else 0.0
        w, hh = num(sz, 1), num(sz, 2)
        shape = val(node, 3)
        if shape == "circle":
            g = circle(x, y, w / 2, 24)
        elif shape == "oval":
            r = min(w, hh) / 2
            g = box(x - w / 2 + r, y - hh / 2 + r, x + w / 2 - r, y + hh / 2 - r).buffer(r, resolution=6)
        else:
            g = box(x - w / 2, y - hh / 2, x + w / 2, y + hh / 2)
        pads.append((affinity.rotate(g, -rot, origin=(x, y)), val(node, 2) in ("thru_hole", "np_thru_hole")))
    _FP[name] = (court, pads)
    return _FP[name]


def footprints_by_ref():
    global _NET
    if _NET is None:
        parse, kids, kid, val = _sexp()
        doc = parse(open(os.path.join(ROOT, "hardware", "checks", "netlist.net"), encoding="utf-8").read())[0]
        _NET = {}
        for c in kids(kid(doc, "components"), "comp"):
            fp = val(kid(c, "footprint"))
            if fp and ":" in fp and not fp.endswith(":"):
                _NET[val(kid(c, "ref"))] = fp.split(":", 1)[1]
    return _NET


def placed(board):
    """[(ref, footprint, courtyard, [(pad, tht)], side)] on a board, in its frame, placed
    the way gen/placement.py says (placement.rel: mirrored in y on the bottom, then turned
    counter-clockwise).  A coil whose netlist entry is older than its generated
    footprint uses the generated one."""
    import placement as PL
    fps = footprints_by_ref()
    out = []
    for ref, (x, y, rot, side) in sorted(PL.BOARDS[board].place.items()):
        name = fps.get(ref)
        if ref in COIL_FP and (not name or not os.path.exists(os.path.join(LIBDIR, name + ".kicad_mod"))):
            name = COIL_FP[ref]
        if not name or not os.path.exists(os.path.join(LIBDIR, name + ".kicad_mod")):
            MISSING.add((board, ref, name))
            continue
        court, pads = footprint_geometry(name)

        def T(g, side=side, rot=rot, x=x, y=y):
            if side == "B":
                g = affinity.scale(g, 1, -1, origin=(0, 0))
            return affinity.translate(affinity.rotate(g, -rot, origin=(0, 0)), x, y)
        out.append((ref, name, T(court) if court is not None else None, [(T(p), th) for p, th in pads], side))
    return out


def keep_parts_clear(cv, board):
    """Silk stays off every courtyard on its side (coils excepted: they take thin lines)
    and off every pad, through-hole pads on both sides.  Returns the parts for the
    previews: {side: [(geometry, colour)]}."""
    seen = {"F": [], "B": []}
    for ref, name, court, pads, side in placed(board):
        coil = name.startswith("Coil_")
        if name.startswith(("MountingHole", "TestPoint")):
            continue
        if court is not None and not coil:
            cv.keep_clear(side + ".SilkS", court.buffer(COURT_GAP))
            seen[side].append((court, "led" if name.startswith("LED") else "part"))
        for pd, th in pads:
            for sd in (("F", "B") if th else (side,)):
                cv.keep_clear(sd + ".SilkS", pd.buffer(PAD_GAP))
                if th or not coil:
                    seen[sd].append((pd, "pad"))
    return seen


# ======================================================================================
# Little drawings shared by the boards (board millimetres, y down)
# ======================================================================================
TOP, BOT = "F.SilkS", "B.SilkS"
STAR_CLEAR = 3.1         # the violet 3528 star LEDs: "a clear centre, radius about 3 mm"
SMALL_LED_CLEAR = 1.75   # 0603 ring, wisp and eye LEDs
PUMPKIN_CLEAR = 4.2      # the 5050 behind each pumpkin's face
FOOT_CLEAR = 5.5         # the printed foot's top is 11 mm across (print/README.md)


def _shapes():
    sys.path.insert(0, os.path.join(ROOT, "art"))
    import shapes
    return shapes


def tiny_star(x, y, r, rot=-90.0):
    return Polygon(star_pts(x, y, r, r * 0.45, 5, rot))


def tiny_twinkle(x, y, r):
    pts = []
    for i in range(8):
        a = math.radians(45 * i - 90)
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    return Polygon(pts)


def crescent(x, y, r, a=-35.0):
    """A little crescent moon, its horns away from direction a."""
    d = 0.5 * r
    return circle(x, y, r, 40).difference(circle(x + d * math.cos(math.radians(a)), y + d * math.sin(math.radians(a)), 0.85 * r, 40))


def pointy_star(cv, x, y, r_out, r_in=3.45, rot=-90.0, w=0.26, layer=TOP):
    p = Polygon(star_pts(x, y, r_out, r_in, 5, rot)).buffer(0.35, join_style=1).buffer(-0.35, join_style=1)
    cv.line(layer, list(p.exterior.coords), w)


def star_zone(x, y, r_out):
    return Polygon(star_pts(x, y, r_out + 0.6, 3.6, 5, -90)).buffer(0.8)


def arc_star(cv, x, y, tangent):
    """One of the twelve stars on the quantum ghost's arc: a halo and six rays, none along
    the arc, so neighbours 8 mm apart never touch."""
    cv.circle(TOP, x, y, 3.5, 0.22)
    for da, r1 in ((-90, 6.4), (90, 5.6), (-45, 5.2), (-135, 5.2), (45, 4.9), (135, 4.9)):
        a = math.radians(tangent + da)
        cv.line(TOP, [(x + 4.15 * math.cos(a), y + 4.15 * math.sin(a)), (x + r1 * math.cos(a), y + r1 * math.sin(a))], 0.24)


def wisp(cv, x, y, flip=1):
    """A will-o'-the-wisp: a little flame round its LED, its tip flicking over."""
    d, r = flip, 2.35
    P = lambda u, v: (x + d * u, y + v)
    base = [P(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in range(-15, 196, 7)]  # round the bottom
    up_a = bez(base[-1], P(-r - 0.4, -2.4), P(-1.6, -4.4), P(-0.6, -5.6), 14)                  # the far side up
    tip = bez(P(-0.6, -5.6), P(0.2, -6.7), P(1.8, -7.6), P(3.0, -7.0), 10)                       # over to the tip
    down = bez(P(3.0, -7.0), P(1.6, -6.4), P(1.3, -5.2), P(1.9, -4.0), 10)                        # back under it
    down2 = bez(P(1.9, -4.0), P(2.6, -2.6), P(r + 0.5, -1.4), base[0], 12)                         # and down the near side
    cv.line(TOP, chain(base, up_a, tip, down, down2), 0.22)
    cv.line(TOP, bez(P(-0.3, -2.8), P(-0.6, -3.7), P(-0.2, -4.5), P(0.5, -4.9), 8), 0.2)          # a flicker inside
    cv.poly(TOP, U(circle(*P(4.0, -4.6), 0.3, 12), circle(*P(-3.4, -1.0), 0.24, 12)))


def wisp_zone(x, y):
    return U(circle(x, y, 3.2), circle(x, y - 3.8, 3.6))


def silk_bat(x, y, width, rot=0.0):
    """A small flying bat (art/shapes.py's), white with two little eyes."""
    S = _shapes()
    f = S.bat()
    g = unary_union(f.ink)
    x0, y0, x1, y1 = g.bounds
    s = width / (x1 - x0)
    g = tf(g, x, y, s, rot, flipy=True)
    eyes = U([tf(circle(sx * 0.05, 0.04, 0.045, 24), x, y, s, rot, flipy=True) for sx in (-1, 1)])
    return g.difference(eyes)


def curved_text(cv, layer, s, cx, cy, r, h, a_mid=270.0):
    """Letters round the top of a circle, each upright to it (one text item each)."""
    advs = [text_width(c, h) for c in s]
    a = math.radians(a_mid) - sum(advs) / r / 2
    for c, adv in zip(s, advs):
        am = a + adv / r / 2
        if c != " ":
            cv.text(layer, c, cx + r * math.cos(am), cy + r * math.sin(am), h, 270.0 - math.degrees(am), "center")
        a += adv / r


def owl_round(cv, cx, cy, perched=True, layer=TOP):
    """A round owl whose two eye LEDs sit at (cx -+ spacing/2, cy): little ear tufts, eye
    rings round the LEDs, brows, a beak, folded wings, a speckled chest and feet.
    Returns its silhouette (what it hides of the drawing behind it)."""
    e = L.OWL_EYE_SPACING / 2
    body = ellipse(cx, cy + 4.6, 9.0, 11.6, n=120)
    tufts = [Polygon([(cx - 3.4, cy - 6.4), (cx - 6.4, cy - 9.2), (cx - 7.6, cy - 4.8)]),
             Polygon([(cx + 3.4, cy - 6.4), (cx + 6.4, cy - 9.2), (cx + 7.6, cy - 4.8)])]
    head = rounded(U(body, tufts), 0.5)
    cv.outline_strokes(layer, head, 0.3)
    for sx in (-1, 1):
        ex = cx + sx * e
        cv.circle(layer, ex, cy, 3.15, 0.26)                                          # eye rings
        cv.line(layer, arc_pts(ex, cy, 4.25, 205 if sx < 0 else 245, 295 if sx < 0 else 335, 20), 0.24)   # brows
        cv.line(layer, bez((cx + sx * 7.2, cy + 4.0), (cx + sx * 7.6, cy + 9.4), (cx + sx * 6.6, cy + 12.6),
                           (cx + sx * 3.9, cy + 14.6), 24), 0.26)                    # folded wings
        for k in range(2):
            y0 = cy + 9.4 + 1.6 * k
            cv.line(layer, [(cx + sx * (7.0 - 0.6 * k), y0), (cx + sx * (5.8 - 0.6 * k), y0 + 0.9)], 0.2)
        if perched:
            fx = cx + sx * 2.6
            for dx in (-0.75, 0.0, 0.75):                                            # toes
                cv.line(layer, [(fx + dx * 0.5, cy + 15.7), (fx + dx, cy + 16.9)], 0.24)
    cv.poly(layer, rounded(Polygon([(cx - 1.25, cy + 2.4), (cx + 1.25, cy + 2.4), (cx, cy + 4.6)]), 0.2))   # beak
    for (u, v) in ((-2.6, 7.6), (0.0, 7.6), (2.6, 7.6), (-1.3, 10.2), (1.3, 10.2), (0.0, 12.6)):          # chest
        cv.line(layer, [(cx + u - 0.8, cy + v - 0.5), (cx + u, cy + v + 0.35), (cx + u + 0.8, cy + v - 0.5)], 0.22)
    return U(head, box(cx - 4.3, cy + 15.0, cx + 4.3, cy + 17.3))


def grass(cv, layer, x, y, scale=1.0):
    for dx, hh, lean in ((-0.7, 1.4, -0.7), (0.0, 2.0, 0.2), (0.6, 1.6, 0.8)):
        dx, hh, lean = dx * scale, hh * scale, lean * scale
        cv.line(layer, bez((x + dx, y), (x + dx, y - hh * 0.5), (x + dx + lean * 0.4, y - hh * 0.8),
                           (x + dx + lean, y - hh), 8), 0.18)


# ======================================================================================
# The base: the moon (the theremin's pitch antenna) with the witch, and the ghost (its
# volume antenna), in ENIG gold
# ======================================================================================
def witch_silhouette():
    """The witch on her broom with her cat (art/shapes.py's drawing, its cat larger and its
    eyes, her eye and her smile big enough to print as gold).  Art units, y up, 1 = the
    broom.  Returns (silhouette, gold details inside it)."""
    S = _shapes()
    broom = S.stroke([(-0.42, -0.03), (0.52, 0.05)], 0.024)
    bristles = S.path([((-0.42, -0.01), (-0.52, 0.05), (-0.64, 0.07), (-0.74, 0.10)),
                       ((-0.74, 0.10), (-0.70, 0.01), (-0.70, -0.08), (-0.76, -0.14)),
                       ((-0.76, -0.14), (-0.64, -0.11), (-0.52, -0.08), (-0.42, -0.05))])
    ties = S.stroke([(-0.44, 0.02), (-0.44, -0.07)], 0.024)
    head = S.circle(0.10, 0.285, 0.075)
    pigtails = [S.ellipse(0.02, 0.27, 0.037, 0.024, -25), S.ellipse(0.035, 0.222, 0.032, 0.022, -50)]
    brim = S.ellipse(0.095, 0.348, 0.158, 0.028, 8)
    cone = S.path([((0.00, 0.35), (0.02, 0.43), (0.05, 0.52), (0.04, 0.60)),
                   ((0.04, 0.60), (0.10, 0.55), (0.15, 0.45), (0.18, 0.36)),
                   ((0.18, 0.36), (0.12, 0.36), (0.06, 0.35), (0.00, 0.35))])
    tip = S.stroke(S.bezier((0.04, 0.60), (0.00, 0.66), (-0.07, 0.64), (-0.08, 0.57)), 0.03)
    dress = S.path([((0.06, 0.22), (0.02, 0.14), (0.00, 0.07), (-0.02, 0.02)),
                    ((-0.02, 0.02), (0.06, 0.05), (0.14, 0.06), (0.20, 0.04)),
                    ((0.20, 0.04), (0.18, 0.11), (0.16, 0.17), (0.14, 0.22))])
    cape = S.path([((0.06, 0.22), (-0.04, 0.24), (-0.14, 0.20), (-0.22, 0.14)),
                   ((-0.22, 0.14), (-0.16, 0.13), (-0.12, 0.11), (-0.16, 0.07)),
                   ((-0.16, 0.07), (-0.08, 0.10), (0.00, 0.12), (0.05, 0.14))])
    arm = S.stroke([(0.12, 0.19), (0.21, 0.12), (0.29, 0.065)], 0.034)
    legs = [S.stroke([(0.13, 0.04), (0.16, -0.07), (0.215, -0.075)], 0.036),
            S.stroke([(0.05, 0.03), (0.07, -0.08), (0.12, -0.085)], 0.036)]
    kitty = S.place(S.cat(), -0.29, -0.012, 0.25)
    sil = unary_union([broom, bristles, ties, head, brim, cone, tip, dress, cape, arm] + pigtails + legs + kitty.ink)
    gold = [S.circle(0.137, 0.292, 0.016),                                        # her eye
            S.stroke(S.arc_pts(0.121, 0.272, 0.029, 235, 322, 10), 0.014)]       # her smile
    for sx in (-1, 1):                                                             # the cat's eyes
        gold.append(S.circle(-0.29 + sx * 0.075 * 0.25, -0.012 + 0.71 * 0.25, 0.0105))
    return sil, unary_union(gold)


def oscillator_at(ref, fallback):
    """Where a theremin oscillator sits (gen/placement.py), so the antenna's pad faces it."""
    try:
        import placement as PL
        x, y, _, _ = PL.BASE.place[ref]
        return (x, y)
    except Exception:
        return fallback


def clean_opening(opening, shape):
    """No gold and no mask narrower than 0.3 mm."""
    g = opening.buffer(-0.15).buffer(0.15).buffer(0.15).buffer(-0.15)
    return g.intersection(shape)


PAD_R = 0.75             # the antenna part's pad (TestPoint_Pad_D1.5mm)


def moon_parts():
    """The moon: copper disc, gold opening (craters and the witch are mask islands), pad."""
    mx, my, mr = L.MOON
    disc = circle(mx, my, mr, 360)
    sil, gold = witch_silhouette()
    c_art = (-0.12, 0.26)                               # the drawing's middle, art units
    def place(g):
        return tf(affinity.translate(g, -c_art[0], -c_art[1]), mx + 1.5, my + 0.6, 27.4, -9.0, flipy=True)
    sil, gold = place(sil), place(gold)
    island = sil.difference(gold)
    ox, oy = oscillator_at("U12", L.BLOCKS.get("theremin", (L.BASE_W / 2, L.BASE_H / 2)))
    a = math.atan2(oy - my, ox - mx)
    pad = (mx + (mr - PAD_R - 0.05) * math.cos(a), my + (mr - PAD_R - 0.05) * math.sin(a))
    craters = []
    for (u, v, r) in ((0.42, -0.52, 0.15), (-0.50, -0.42, 0.11), (-0.12, -0.72, 0.07), (0.30, -0.80, 0.06),
                      (-0.80, -0.10, 0.06), (0.70, -0.25, 0.08), (-0.62, 0.22, 0.08), (0.72, 0.12, 0.07),
                      (0.14, 0.64, 0.15), (-0.30, 0.66, 0.09), (0.52, 0.52, 0.07), (-0.04, 0.88, 0.055),
                      (-0.60, 0.55, 0.06), (0.36, 0.84, 0.05), (0.60, 0.70, 0.05)):
        c = circle(mx + u * mr, my + v * mr, r * mr, 64)
        if c.distance(sil) > 0.8 and c.distance(Point(pad)) > PAD_R + 1.0 and all(c.distance(k) > 0.8 for k in craters):
            craters.append(c)
    island = U(island, craters).difference(circle(pad[0], pad[1], PAD_R + 1.0))
    return disc, clean_opening(disc.difference(island), disc), pad


def ghost_shape():
    """The friendly ghost at layout.GHOST (centre, half-height): a round head, a body that
    flares a little, a hem of three soft scallops, one arm waving hello."""
    gx, gy, gh = L.GHOST
    H = 2 * gh
    top, bot = gy - gh, gy + gh
    r = 0.37 * H
    hc = (gx, top + r)
    pts = arc_pts(hc[0], hc[1], r, 180, 360, 60)
    hem_y = bot - 0.13 * H
    pts += bez((gx + r, hc[1]), (gx + r + 0.01 * H, hc[1] + 0.25 * H), (gx + r + 0.07 * H, hem_y - 0.15 * H),
               (gx + r + 0.09 * H, hem_y), 16)[1:]
    xs = [gx + r + 0.09 * H, gx + 0.17 * H, gx - 0.14 * H, gx - r - 0.06 * H]
    for i, drop in enumerate((0.13, 0.11, 0.12)):
        x0, x1 = xs[i], xs[i + 1]
        pts += bez((x0, hem_y), (x0 - 0.02 * H, hem_y + drop * H * 1.4), (x1 + 0.03 * H, hem_y + drop * H * 1.4),
                   (x1, hem_y), 16)[1:]
    pts += bez((gx - r - 0.06 * H, hem_y), (gx - r - 0.05 * H, hem_y - 0.15 * H), (gx - r - 0.01 * H, hc[1] + 0.25 * H),
               (gx - r, hc[1]), 16)[1:]
    arms = [ellipse(gx - r - 0.03 * H, top + 0.36 * H, 0.085 * H, 0.05 * H, 55),        # waving
            ellipse(gx + r + 0.06 * H, top + 0.56 * H, 0.085 * H, 0.05 * H, -25)]
    return rounded(U(Polygon(pts).buffer(0), arms), 0.45)


def ghost_parts():
    gx, gy, gh = L.GHOST
    H = 2 * gh
    shape = ghost_shape()
    top = gy - gh
    island = []
    for sx in (-1, 1):                                    # eyes, each with a glint of gold
        e = ellipse(gx + sx * 0.12 * H, top + 0.33 * H, 0.052 * H, 0.072 * H)
        island.append(e.difference(circle(gx + sx * 0.12 * H + 0.02 * H, top + 0.33 * H - 0.028 * H, 0.38)))
    island.append(stroke(arc_pts(gx, top + 0.40 * H, 0.10 * H, 35, 145, 24), 0.55))     # a smile
    ox, oy = oscillator_at("U13", L.BLOCKS.get("theremin", (L.BASE_W / 2, L.BASE_H / 2)))
    d = (ox - gx, oy - gy)
    n = math.hypot(*d)
    far = max(shape.exterior.coords, key=lambda p: (p[0] * d[0] + p[1] * d[1]) / n)
    inner = shape.buffer(-(PAD_R + 0.05))
    p = inner.exterior.interpolate(inner.exterior.project(Point(far)))
    pad = (p.x, p.y)
    island = U(island).difference(circle(pad[0], pad[1], PAD_R + 1.0))
    return shape, clean_opening(shape.difference(island), shape), pad


def antennas_geometry():
    mdisc, mopen, mpad = moon_parts()
    gshape, gopen, gpad = ghost_parts()
    return [("MOON", mdisc, mopen, mpad), ("GHOST", gshape, gopen, gpad)]


# ======================================================================================
# The base's top: the scene she looks at
# ======================================================================================
def ring_leds(perch):
    px, py = perch
    return [(px + L.RING_R * math.cos(math.radians(a)), py + L.RING_R * math.sin(math.radians(a))) for a in L.RING_ANGLES]


def base_led_clear():
    """What the art leaves round each LED of the scene, and the other places it keeps off."""
    g = [circle(x, y, STAR_CLEAR) for (x, y) in list(L.star_arc()) + list(L.STARX)]
    g += [circle(x, y, SMALL_LED_CLEAR) for perch in (L.OWL_PERCH, L.CAT_PERCH) for (x, y) in ring_leds(perch)]
    g += [circle(x, y, SMALL_LED_CLEAR) for (x, y) in L.WISPS]
    g += [circle(x, y, PUMPKIN_CLEAR) for (x, y, s) in L.PUMPKINS]
    g += [circle(x, y, FOOT_CLEAR) for (x, y) in L.FEET]
    sx, sy = L.SPEAKER
    g.append(circle(sx, sy, 12.3))
    mx, my = getattr(L, "MCU", (105.0, 15.0))
    g.append(box(mx - 15.5, -2, mx + 15.5, my + 15.5))         # the RP2354A's corner: no art
    return U(g)


def magic_circle(cv, cx, cy, label):
    """A familiar's perch: two rings, the three ring LEDs between them, little stars and
    moons in the band, and the familiar's name round the top."""
    R = L.PERCH_ART_R
    cv.circle(TOP, cx, cy, R, 0.3)
    cv.circle(TOP, cx, cy, R - 4.0, 0.2)
    deco = []
    for g0 in (a + 60 for a in L.RING_ANGLES):
        for k, da in enumerate((-36, -18, 0, 18, 36)):
            a = math.radians(g0 + da)
            x, y = cx + (R - 2.0) * math.cos(a), cy + (R - 2.0) * math.sin(a)
            deco.append(tiny_star(x, y, 1.05, g0 + da) if k in (0, 4) else
                        crescent(x, y, 1.0, g0 + da + 180) if k == 2 else circle(x, y, 0.32, 16))
    cv.poly(TOP, U(deco))
    curved_text(cv, TOP, label, cx, cy, R + 2.5, 2.6)


def pumpkin(cv, x, y, s):
    """A jack-o'-lantern round its LED at (x, y), s its half-width: the LED sits in the
    middle of its face, between two triangle eyes and a toothy grin."""
    face = []
    re = max(5.3, 0.66 * s)                              # the eyes clear the LED
    for sx in (-1, 1):
        a = math.radians(-90 + sx * 47)
        ex, ey = x + re * math.cos(a), y + re * math.sin(a)
        r = 0.95 + 0.04 * s
        face.append(Polygon([(ex - r, ey + 0.55 * r), (ex + r, ey + 0.55 * r), (ex + sx * 0.3 * r, ey - 0.95 * r)]))
    rg = max(4.75, 0.6 * s)                              # the grin, below the LED
    grin = circle(x, y, rg + 0.75).difference(circle(x, y, rg))
    wedge = Polygon([(x, y), (x + 3 * s * math.cos(math.radians(25)), y + 3 * s * math.sin(math.radians(25))),
                     (x, y + 3 * s), (x + 3 * s * math.cos(math.radians(155)), y + 3 * s * math.sin(math.radians(155)))])
    grin = grin.intersection(wedge)
    for a in (72, 108):                                  # two teeth
        t = math.radians(a)
        grin = grin.difference(box(x + rg * math.cos(t) - 0.28, y + rg * math.sin(t) - 0.1,
                                   x + rg * math.cos(t) + 0.28, y + rg * math.sin(t) + 0.45))
    face = rounded(U(face + [grin]), 0.1)
    cv.poly(TOP, face)
    cv.keep_clear(TOP, face.buffer(0.4))
    lobes = U(ellipse(x, y + 0.02 * s, 0.50 * s, 0.86 * s), ellipse(x - 0.42 * s, y + 0.06 * s, 0.58 * s, 0.78 * s),
              ellipse(x + 0.42 * s, y + 0.06 * s, 0.58 * s, 0.78 * s))
    cv.outline_strokes(TOP, lobes, 0.3)
    for sx in (-1, 1):                                   # ribs
        cv.line(TOP, bez((x + sx * 0.16 * s, y - 0.82 * s), (x + sx * 0.52 * s, y - 0.45 * s),
                         (x + sx * 0.52 * s, y + 0.45 * s), (x + sx * 0.16 * s, y + 0.86 * s)), 0.18)
    top = y - 0.82 * s
    stem = Polygon([(x - 0.11 * s, top + 0.10 * s), (x - 0.13 * s, top - 0.20 * s), (x + 0.02 * s, top - 0.34 * s),
                    (x + 0.10 * s, top - 0.28 * s), (x + 0.08 * s, top + 0.10 * s)])
    cv.poly(TOP, rounded(stem, 0.12))
    cv.line(TOP, bez((x + 0.05 * s, top - 0.18 * s), (x + 0.35 * s, top - 0.48 * s), (x + 0.58 * s, top - 0.12 * s),
                     (x + 0.42 * s, top - 0.02 * s)), 0.2)
    return lobes.buffer(0.8)


def pendulum_hint(cv):
    """The bat's swing round its rest point: a dashed circle through the three coils."""
    px, py = L.PEND_REST
    r, n = L.PEND_R, 36
    for k in range(n):
        a0 = 360.0 * k / n
        cv.arc(TOP, px, py, r, a0, a0 + 360.0 / n * 0.55, 0.2)
    for a in (60.0, 180.0, 300.0):                       # arrowheads: round it goes
        a = math.radians(a)
        tx, ty = px + r * math.cos(a), py + r * math.sin(a)
        d, nrm = (-math.sin(a), math.cos(a)), (math.cos(a), math.sin(a))
        tip = (tx + 1.0 * d[0], ty + 1.0 * d[1])
        cv.line(TOP, [(tip[0] - 1.4 * d[0] + 0.9 * nrm[0], tip[1] - 1.4 * d[1] + 0.9 * nrm[1]), tip,
                      (tip[0] - 1.4 * d[0] - 0.9 * nrm[0], tip[1] - 1.4 * d[1] - 0.9 * nrm[1])], 0.22)
    cv.poly(TOP, tiny_twinkle(px, py, 1.6))
    cv.keep_clear(TOP, LineString(arc_pts(px, py, r, 0, 360)).buffer(0.5))


def hill(cv):
    """A gentle hill along the front, a little below the wisps that float over it."""
    pts = [(-1.0, 105.0), (22.0, 106.5)]
    for (wx, wy) in L.WISPS:
        pts.append((wx, wy + 3.2))
    pts.append((105.0, 100.0))
    pts.append((191.0, 112.0))
    curve = catmull(sorted(pts), 16)
    cv.line(TOP, curve, 0.3)
    hl = LineString(curve)
    for x in (8, 58, 75, 96, 116, 137, 157, 186):        # tufts of grass
        p = hl.intersection(LineString([(x, 0), (x, 200)]))
        if isinstance(p, Point):
            grass(cv, TOP, p.x, p.y - 0.05)


def courtyard_of(board, ref):
    for r, name, court, pads, side in placed(board):
        if r == ref:
            return court if court is not None else U([pd for pd, th in pads])
    return None


def place_label(cv, layer, lines_, part, prefer=("above", "below", "left", "right"), gap=0.8):
    """Lines [(text, h)] by a part (its courtyard): the first spot round it, in order of
    preference, that nothing else is in.  Returns where they went."""
    if part is None:
        return None
    x0, y0, x1, y1 = part.bounds
    hs = [h for _, h in lines_]
    tot = sum(h * 1.45 for h in hs)
    for where in prefer:
        if where in ("above", "below"):
            y = (y0 - gap - tot) if where == "above" else (y1 + gap)
            spots = [((x0 + x1) / 2, y, "center")]
        else:
            y = (y0 + y1) / 2 - tot / 2
            spots = [((x0 - gap) if where == "left" else (x1 + gap), y, "right" if where == "left" else "left")]
        for (x, yt, j) in spots:
            geo, yy, ok = [], yt, True
            for s_, h in lines_:
                g = text_geom(s_, x, yy + 0.72 * h, h, 0, j, layer.startswith("B."))
                if cv.clear.get(layer) is not None and g.intersects(cv.clear[layer]):
                    ok = False
                    break
                geo.append((s_, x, yy + 0.72 * h, h, j))
                yy += 1.45 * h
            if ok:
                for (s_, x_, y_, h, j_) in geo:
                    cv.text(layer, s_, x_, y_, h, 0, j_)
                return where
    cv.notes.append("%s: no room for the label %r" % (cv.name, lines_[0][0]))
    return None


def base_labels(cv):
    jx, jy = L.JACK
    cv.text(TOP, "12 V", jx, jy + 7.2, 2.0, 0, "center")
    cv.text(TOP, "DC, centre +", jx, jy + 9.8, 1.0, 0, "center")
    cv.text(TOP, "3 A or more", jx, jy + 11.4, 1.0, 0, "center")
    ux, uy = L.USB
    cv.text(TOP, "USB", ux - 6.6, 3.4, 1.6, 0, "right")
    mx, my = getattr(L, "MCU", (105.0, 15.0))
    cv.text(TOP, "↑ the owl's brain ↑", mx, my + 17.6, 1.2, 0, "center")
    sw2 = courtyard_of("base", "SW2")
    if place_label(cv, TOP, [("SPELL", 1.7)], sw2) is not None:
        x0, y0, x1, y1 = sw2.bounds
    sw3 = courtyard_of("base", "SW3")
    place_label(cv, TOP, [("SOUND", 1.6), ("on / off", 1.0)], sw3)
    tx, ty = L.TREE_SOCKET
    pts = rrect(tx - 12.2, ty - 4.3, tx + 12.2, ty + 4.3, 1.5)
    cv.line(TOP, pts + [pts[0]], 0.25)
    cv.text(TOP, "TREE", tx - 13.6, ty + 0.1, 1.6, 0, "right")
    cv.text(TOP, "owls face this way ↓", tx + 13.6, ty + 0.1, 1.0, 0, "left")
    x3, y3 = L.pend_coil("L3")
    cv.text(TOP, BI.TITLE, x3 + 5.0, L.BASE_H - 4.7, 2.5, 0, "center")


def base_top(cv):
    """Front to back: the LEDs' own drawings first, then what stands round them."""
    mx, my, mr = L.MOON
    for k in range(60):                                   # the moon's glow, a ring of dots
        a = math.radians(6.0 * k + 3)
        cv.poly(TOP, circle(mx + (mr + 2.2) * math.cos(a), my + (mr + 2.2) * math.sin(a), 0.28, 12))
    arc = L.star_arc()
    for i, (x, y) in enumerate(arc):
        j0, j1 = max(i - 1, 0), min(i + 1, len(arc) - 1)
        arc_star(cv, x, y, math.degrees(math.atan2(arc[j1][1] - arc[j0][1], arc[j1][0] - arc[j0][0])))
    for i, (x, y) in enumerate(L.WISPS):
        wisp(cv, x, y, 1 if i % 2 == 0 else -1)
    cv.keep_clear(TOP, U([wisp_zone(x, y) for (x, y) in L.WISPS] + [circle(x, y, 6.6) for (x, y) in arc]))
    for (x, y, s) in L.PUMPKINS:
        cv.keep_clear(TOP, pumpkin(cv, x, y, s))
    base_labels(cv)
    pendulum_hint(cv)
    for (px, py), nm in ((L.OWL_PERCH, "OWL"), (L.CAT_PERCH, "CAT")):
        magic_circle(cv, px, py, nm)
        cv.keep_clear(TOP, circle(px, py, L.PERCH_ART_R + 1.0))
    for i, (x, y) in enumerate(L.STARX):
        pointy_star(cv, x, y, 7.4, 3.45, -90 + 12 * (i - 1.5))
    hill(cv)
    for (x, y, w, rot) in ((64.0, 27.0, 9.0, -8.0), (81.0, 34.0, 6.5, 6.0), (157.0, 55.0, 7.5, -4.0)):
        cv.poly(TOP, silk_bat(x, y, w, rot))
    for (x, y, r) in ((9.0, 63.0, 1.3), (84.0, 8.0, 1.1), (125.0, 21.0, 1.2), (172.0, 52.0, 1.1), (6.0, 82.0, 1.1),
                      (57.0, 59.0, 1.0), (186.0, 92.0, 1.1), (126.0, 45.0, 1.1), (147.0, 40.0, 1.0)):
        cv.poly(TOP, tiny_twinkle(x, y, r))


# ======================================================================================
# The base's bottom: the spell book.  Each spell lies where the thing it explains is on
# the other side: inside the coils and the antennas (nothing else can be there), and in a
# few patches that keepouts() keeps free of parts.  Drawn as seen from below: u = W - x.
# ======================================================================================
class BottomView:
    def __init__(self, cv, width):
        self.cv, self.W = cv, width
        self.patches = []                     # (polygon in the board's frame, what)

    def g(self, geom):
        return affinity.scale(geom, -1, 1, origin=(self.W / 2, 0))

    def text(self, s, u, y, h, justify="center"):
        return self.cv.text(BOT, s, self.W - u, y, h, 0.0, justify)

    def line(self, pts, w):
        self.cv.line(BOT, [(self.W - u, y) for u, y in pts], w)

    def circle(self, u, y, r, w):
        self.cv.circle(BOT, self.W - u, y, r, w)

    def poly(self, geom):
        self.cv.poly(BOT, self.g(geom))

    def claim(self, u0, y0, u1, y1, what):
        self.patches.append((box(self.W - u1, y0, self.W - u0, y1), what))


PITCH, GAP = 1.62, 0.55      # line pitch and the extra gap between blocks, in text heights


NBSP = "\u00a0"         # in a spell's words: a space the line may not break at


def layout_lines(blocks, top, width_at_y, blocked=None, stats=None):
    """blocks: [(text, h, mode)], mode "wrap" (a paragraph), "fit" (one line, made smaller
    until it fits) or "fixed".  A line never lies across a band that blocked(y0, y1)
    refuses (a pad); it moves down past it (stats["mid"] counts the times that happens
    inside a paragraph).  Returns [(text, y_centre, h)] and the bottom."""
    out, y = [], top
    free = lambda y0, y1: blocked is None or not blocked(y0, y1)
    for bi, (s, h, mode) in enumerate(blocks):
        if bi:
            y += GAP * h
        words = s.split(" ")
        first = True
        while words:
            moved = False
            for _ in range(400):
                if free(y - 0.1 * h, y + 1.2 * h):
                    break
                y += 0.1
                moved = True
            if moved and not first and stats is not None:
                stats["mid"] = stats.get("mid", 0) + 1
            first = False
            room = width_at_y(y, y + 1.25 * h)
            if mode == "wrap":
                line = words[0]
                for w in words[1:]:
                    if text_width((line + " " + w).replace(NBSP, " "), h) > room:
                        break
                    line += " " + w
                words = words[len(line.split(" ")):]
            else:
                line, words = s, []
                while mode == "fit" and h > MIN_TEXT + 0.1 and text_width(line.replace(NBSP, " "), h) > room:
                    h -= 0.05
            out.append((line.replace(NBSP, " "), y + 0.55 * h, h))
            y += PITCH * h if words else 1.3 * h
    return out, y


def chord(cy, r, y0, y1):
    d = max(abs(y0 - cy), abs(y1 - cy))
    return 2 * math.sqrt(max(r * r - d * d, 0.0))


def shape_width(shape, uc, margin):
    inner = shape.buffer(-margin)
    def w(y0, y1):
        best = None
        for y in (y0, y1, (y0 + y1) / 2):
            room = 0.0
            for piece in lines(LineString([(uc - 500, y), (uc + 500, y)]).intersection(inner)):
                a, b = sorted((piece.coords[0][0], piece.coords[-1][0]))
                if a <= uc <= b:
                    room = 2 * min(uc - a, b - uc)
            best = room if best is None else min(best, room)
        return best
    return w


def centre_layout(blocks, cy, width_at, top0, blocked=None):
    """Lay the blocks out round cy: of the heights that fit, the one whose pads fall
    between the blocks rather than inside a paragraph, then the one nearest the middle.
    Returns (lines, all fit?)."""
    best = None
    lines0, bottom0 = layout_lines(blocks, top0, width_at, blocked)
    span = bottom0 - top0
    for k in range(-60, 61):
        top = cy - span / 2 + 0.2 * k
        st = {}
        lines_, bottom = layout_lines(blocks, top, width_at, blocked, st)
        fits = all(text_width(s, h) <= width_at(y - 0.55 * h, y + 0.7 * h) + 0.01 for (s, y, h) in lines_)
        score = (0 if fits else 1, st.get("mid", 0), abs((top + bottom) / 2 - cy))
        if best is None or score < best[0]:
            best = (score, lines_, fits)
    return best[1], best[2]


def centred_text(bv, blocks, uc, cy, width_at, top0, blocked=None):
    """Lines centred on uc, the block centred on cy, each line within width_at; a
    paragraph is made a little smaller (down to 1.05 mm) until it all fits."""
    for shrink in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25):
        b2 = [(s, (h - shrink if mode == "wrap" else h), mode) for (s, h, mode) in blocks]
        if any(h < 1.05 - 1e-9 for (s, h, mode) in b2):
            break
        lines_, fits = centre_layout(b2, cy, width_at, top0, blocked)
        if fits:
            break
    for (s, y, h) in lines_:
        bv.text(s, uc, y, h, "center")
    if not fits:
        bv.cv.notes.append("spell book: %r does not fit its place" % blocks[0][0])
    return lines_


def box_text(bv, blocks, u0, y0, u1):
    lines_, bottom = layout_lines(blocks, y0, lambda a, b: u1 - u0)
    for (s, y, h) in lines_:
        bv.text(s, (u0 + u1) / 2, y, h, "center")
        if text_width(s, h) > u1 - u0 + 0.01:
            bv.cv.notes.append("spell book: %r does not fit its box" % s)
    return bottom


def pad_bands(board, u_c, cy, r, W):
    """The heights (bottom view) that pads take inside a disc, merged: [(y0, y1)]."""
    bands = []
    for ref, name, court, pads, side in placed(board):
        for pd, th in pads:
            if not (th or side == "B"):
                continue
            x0, y0, x1, y1 = pd.bounds
            if math.hypot(W - (x0 + x1) / 2 - u_c, (y0 + y1) / 2 - cy) < r + 1.0:
                bands.append([y0 - PAD_GAP - 0.1, y1 + PAD_GAP + 0.1])
    bands.sort()
    merged = []
    for b in bands:
        if merged and b[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b[1])
        else:
            merged.append(b)
    return [tuple(b) for b in merged]


def _stack(blocks, y_from, cy, r, up):
    """Lines of blocks stacked from y_from, downward or (up) upward, in the disc."""
    width = lambda y0, y1: chord(cy, r, y0, y1)
    if not up:
        return layout_lines(blocks, y_from, width)
    top = y_from - 10.0
    for _ in range(30):
        lines_, bottom = layout_lines(blocks, top, width)
        top += y_from - bottom
        if abs(y_from - bottom) < 0.01:
            break
    return layout_lines(blocks, top, width)


def spell(bv, heading, eq, text, cu, cy, r, h_txt=1.2, h_head=1.7, h_eq=2.0, stars=(270, 45, 135)):
    """A spell in a disc: its name, its equation, a few words; a starry ring round it.
    Where a coil's two vias sit near its middle, the equation goes between them, the
    name and the first sentence above, the second sentence below.  "|" splits text."""
    first, _, second = text.partition("|")
    bands = [b for b in pad_bands("base", cu, cy, r, bv.W) if abs((b[0] + b[1]) / 2 - cy) < 6.0]
    done = False
    width = lambda y0, y1: chord(cy, r, y0, y1)
    if len(bands) == 2 and second:
        (a0, a1), (b0, b1) = bands
        for shrink in (0.0, 0.05, 0.1, 0.15):
            ht = h_txt - shrink
            # A: the name and the first sentence above the vias, the equation between them
            # B: the first sentence above, the name and the equation between them
            for variant in ("A", "B"):
                above = [(heading, h_head, "fit"), (first.strip(), ht, "wrap")] if variant == "A" else \
                        [(first.strip(), ht, "wrap")]
                middle = [(eq, h_eq, "fit")] if variant == "A" else [(heading, h_head, "fit"), (eq, h_eq, "fit")]
                top, _ = _stack(above, a0 - 0.25, cy, r, True)
                for k in range(12):                      # the middle, as big as fits between the vias
                    mid_blocks = [(t_, h_ * (1 - 0.04 * k), m_) for (t_, h_, m_) in middle]
                    mlines, mbot = layout_lines(mid_blocks, a1 + 0.2, lambda y0, y1: width(y0, y1) - 2.0)
                    if mbot <= b0 - 0.1:
                        break
                off = ((b0 - 0.1) - mbot) / 2
                mlines = [(t_, y_ + off, h_) for (t_, y_, h_) in mlines]
                bot, _ = _stack([(second.strip(), ht, "wrap")], b1 + 0.25, cy, r, False)
                lines_ = top + mlines + bot
                fits = (mbot <= b0 - 0.1 and min(h_ for (_, _, h_) in lines_) >= 1.05 - 1e-9 and
                        all(text_width(t_, h_) <= width(y_ - 0.55 * h_, y_ + 0.75 * h_) + 0.01 for (t_, y_, h_) in lines_))
                if fits:
                    for (t_, y_, h_) in lines_:
                        bv.text(t_, cu, y_, h_, "center")
                    done = True
                    break
            if done:
                break
    if not done:
        blocks = [(heading, h_head, "fit"), (eq, h_eq, "fit"), ((first + " " + second).strip(), h_txt, "wrap")]
        blk = lambda y0, y1: any(y0 < q1 and y1 > q0 for q0, q1 in bands)
        centred_text(bv, blocks, cu, cy, lambda y0, y1: chord(cy, r, y0, y1), cy - r, blk)
    rr = r + 1.0
    bv.circle(cu, cy, rr, 0.2)
    words = U([g for g in bv.cv.geoms[BOT] if g.distance(Point(bv.W - cu, cy)) < r])
    put = 0
    for a in list(stars) + [a_ for a_ in (270, 45, 135, 0, 180, 225, 315) if a_ not in stars]:
        t = math.radians(a)
        st = tiny_star(cu + rr * math.cos(t), cy + rr * math.sin(t), 1.1, a)
        if put < len(stars) and bv.g(st).distance(words) > 0.3:
            bv.poly(st)
            put += 1


def rframe(bv, u0, y0, u1, y1, r=1.6, w=0.2, double=False, stars=True):
    pts = rrect(u0, y0, u1, y1, r)
    bv.line(pts + [pts[0]], w)
    if double:
        pts = rrect(u0 + 0.7, y0 + 0.7, u1 - 0.7, y1 - 0.7, max(r - 0.7, 0.3))
        bv.line(pts + [pts[0]], 0.15)
    if stars:
        for (u, y) in ((u0, y0), (u1, y0), (u0, y1), (u1, y1)):
            bv.poly(tiny_twinkle(u, y, 1.3))


def tunnelling_picture(bv, u0, y0, w, hgt):
    """A wave packet meeting a wall: most of it bounces back, a little gets through."""
    base, mid, wall = y0 + hgt, y0 + 0.5 * hgt, u0 + 0.6 * w
    bv.poly(box(wall - 0.7, y0 + 0.1 * hgt, wall + 0.7, base))
    bv.line([(u0, base), (u0 + w, base)], 0.15)
    pin, pout = [], []
    for k in range(300):
        t = k / 299
        pin.append((u0 + t * (wall - 1.5 - u0), mid - 0.42 * hgt * math.exp(-((t - 0.55) / 0.22) ** 2) * math.cos(12 * math.pi * t)))
    for k in range(160):
        t = k / 159
        pout.append((wall + 1.5 + t * (u0 + w - wall - 1.5),
                     mid - 0.42 * hgt * 0.4 * math.exp(-((t - 0.45) / 0.28) ** 2) * math.cos(6 * math.pi * t)))
    bv.line(pin, 0.2)
    bv.line(pout, 0.2)


def moon_phase(bv, u, y, r, k, waxing, w=0.18):
    """A moon k lit (0..1) as seen from the north: a waxing moon is lit on the right."""
    bv.circle(u, y, r, w)
    if k <= 0.02:
        return
    side = 1 if waxing else -1
    limb = [(u + side * r * math.sin(math.radians(a)), y - r * math.cos(math.radians(a))) for a in range(0, 181, 6)]
    e = (1 - 2 * k) * r
    term = [(u + side * e * math.sin(math.radians(a)), y + r * math.cos(math.radians(a))) for a in range(0, 181, 6)]
    bv.poly(Polygon(limb + term).buffer(0))


def spell_book(cv):
    W = L.BASE_W
    bv = BottomView(cv, W)
    U_ = lambda x: W - x                                 # top-view x to bottom-view u
    mx, my, mr = L.MOON
    ox, oy = L.OWL_PERCH
    cx, cy = L.CAT_PERCH
    gx, gy, gh = L.GHOST
    tx, ty = L.TREE_SOCKET
    # --- the spells in the coils and the antennas ---
    spell(bv, "The theremin", "C = εA/d",
          "Your hand and the gold moon on the other side make a capacitor. Bring your hand closer "
          "(smaller d) and C grows, and the note changes. Near the ghost, the sound gets louder or softer.",
          U_(mx), my, mr - 1.0, h_txt=1.35, h_head=2.2, h_eq=2.6, stars=(0, 45, 90, 270, 315))
    spell(bv, "Faraday's law", "EMF = −dΦ/dt",
          "A changing magnet field pushes electrons round a coil.|That is how the tokens light up, with no "
          "battery and no wires.", U_(ox), oy, 13.8, stars=(270, 135))
    spell(bv, "Resonance", "f = 1/(2π√(LC))",
          "Each token rings at its own note, like a swing pushed in time.|The owl's is 148\u00a0kHz, "
          "the cat's 316\u00a0kHz: the perch hears who is there.", U_(cx), cy, 13.8)
    x3, y3 = L.pend_coil("L3")
    spell(bv, "The pendulum", "T = 2π√(l/g)",
          "A bat on a thread swings in the same time however far it goes.|The coils give it a tiny "
          "push as it passes, so it never stops.", U_(x3), y3, 13.8)
    x4, y4 = L.pend_coil("L4")
    spell(bv, "Light", "E = hf",
          "Light comes in tiny packets called photons.|Violet ones (3.1\u00a0eV) carry more energy than "
          "orange ones (2.0\u00a0eV): enough to make glow-in-the-dark things glow.", U_(x4), y4, 13.8)
    x5, y5 = L.pend_coil("L5")
    spell(bv, "Biot and Savart", "dB = μ_{0}I dl×r / 4πr^{3}",
          "Every bit of moving charge makes a little swirl of magnet field.|Many turns of copper add "
          "their swirls into a magnet you can switch on and off.", U_(x5), y5, 13.8)
    # --- the quantum ghost, in the ghost's place ---
    gshape = ghost_shape()
    cv.line(BOT, list(gshape.buffer(0.6).exterior.coords), 0.2)
    for sx in (-1, 1):
        bv.poly(ellipse(U_(gx) + sx * 0.24 * gh, gy - gh + 0.60 * gh, 0.08 * gh, 0.11 * gh))
    gb = bv.g(gshape)
    centred_text(bv, [("Quantum ghost", 1.25, "fit"), ("iħ ∂ψ/∂t = Ĥψ", 1.45, "fit"),
                      ("Ghosts walk through walls, and so do electrons.", 1.05, "wrap")],
                 U_(gx), gy + 3.4, shape_width(gb, U_(gx), 0.9), gy - gh)
    # --- the wall it walks through, beside it ---
    du0, du1, dy0 = U_(gx) - 52.0, U_(gx) - 25.0, gy - 12.6
    box_text(bv, [("Tunnelling", 1.6, "fit")], du0, dy0, du1)
    tunnelling_picture(bv, du0 + 0.5, dy0 + 3.6, du1 - du0 - 1.0, 7.0)
    b = box_text(bv, [("Most of a wave bounces off a wall, but a little gets through. Tap the board twice "
                       "and watch it happen along the stars.", 1.1, "wrap")], du0, dy0 + 12.6, du1)
    bv.claim(du0 - 0.5, dy0 - 0.5, du1 + 0.5, b + 0.5, "spell book: tunnelling")
    # --- Earnshaw, by the tree's socket ---
    u0, u1 = U_(tx) - 11.0, U_(tx) + 13.0
    b = box_text(bv, [("The floating bat", 1.6, "fit"), ("\u2207\u00b2V = 0: no dip to rest in", 1.4, "fit"),
                      ("A magnet cannot float on its own (Earnshaw, 1842)... unless something watches it and "
                       "nudges it 10,000\u00a0times a second: a Hall sensor and the perch's coil.", 1.1, "wrap")],
                 u0, ty - 20.5, u1)
    bv.claim(u0 - 0.5, ty - 20.5, u1 + 0.5, b + 0.5, "spell book: Earnshaw's theorem")
    # --- the fireflies, by the pumpkins ---
    px, py, ps = L.PUMPKINS[2]
    ku0, ku1, ky0 = U_(px) - 20.0, U_(px) + 14.0, py - 21.0
    b = box_text(bv, [("Fireflies in step", 1.7, "fit"),
                      ("dθ_{i}/dt = ω_{i} + K Σ sin(θ_{j} − θ_{i})", 1.5, "fit"),
                      ("Each pumpkin glows at its own pace, but each one nudges the others a little, and soon "
                       "they all glow together, like fireflies on a summer night.", 1.15, "wrap")], ku0, ky0, ku1)
    for k, ph in enumerate((0.0, 2.1, 4.0)):              # three waves, out of step, then in step
        pts = []
        for i in range(161):
            t = i / 160
            pts.append((ku0 + 1 + t * (ku1 - ku0 - 2),
                        b + 2.6 + 1.6 * k + 0.55 * math.sin(2 * math.pi * 4.5 * t + ph * max(0.0, 1 - 1.6 * t))))
        bv.line(pts, 0.18)
    bv.claim(ku0 - 0.5, ky0 - 0.5, ku1 + 0.5, b + 7.6, "spell book: the fireflies")
    # --- the moon on Halloween ---
    hu0, hu1, hy = U_(mx) - 22.0, U_(mx) + 30.0, my + mr + 6.0
    box_text(bv, [("The moon on Halloween 2026: waning gibbous, 65% lit", 1.15, "fit")], hu0, hy - 2.6, hu1)
    phases = [(0.0, True), (0.25, True), (0.5, True), (0.75, True), (1.0, True), (0.65, False), (0.5, False), (0.25, False)]
    for i, (k, wax) in enumerate(phases):
        u = hu0 + 3.0 + i * (hu1 - hu0 - 6.0) / (len(phases) - 1)
        moon_phase(bv, u, hy + 4.4, 2.2, k, wax)
        if i == 5:
            bv.circle(u, hy + 4.4, 3.1, 0.18)
    bv.claim(hu0 - 0.5, hy - 3.1, hu1 + 0.5, hy + 8.0, "spell book: the moon's phases")
    # --- the title page, beside the moon ---
    tu0, tu1 = U_(mx) - 53.2, U_(mx) - 22.6
    rframe(bv, tu0, 1.6, tu1, 30.6, 2.0, 0.22, double=True)
    y = box_text(bv, [("The Spell Book", 2.6, "fit"), ("of " + BI.TITLE, 1.4, "fit")], tu0 + 1.6, 3.6, tu1 - 1.6)
    name = "for " + (BI.FOR_NAME if BI.FOR_NAME else "______")
    rframe(bv, tu0 + 2.6, y + 1.2, tu1 - 2.6, y + 9.0, 1.4, 0.2, stars=False)
    box_text(bv, [(name, 3.0, "fit")], tu0 + 3.6, y + 2.7, tu1 - 3.6)
    box_text(bv, [("Made by her dad and Claude, Halloween 2026", 1.3, "wrap")], tu0 + 1.6, y + 11.2, tu1 - 1.6)
    bv.claim(tu0 - 1.4, 0.5, tu1 + 1.4, 32.0, "spell book: the title page and her name")
    # --- the footer: revision, date and where the design lives ---
    fy = L.BASE_H - 2.6
    footer = "%s rev %s, %s   %s" % (BI.TITLE, BI.REV, BI.DATE, BI.URL)
    bv.text(footer, U_(x3), fy, 1.0, "center")
    fw = text_width(footer, 1.0) / 2 + 0.6
    bv.claim(U_(x3) - fw, fy - 1.0, U_(x3) + fw, fy + 1.0, "spell book: the footer")
    # --- a few stars between the spells ---
    for (u, y, r) in ((172.0, 82.0, 1.3), (180.0, 68.0, 1.0), (178.0, 95.0, 1.1), (12.0, 108.0, 1.2), (6.0, 98.0, 1.0),
                      (139.0, 99.0, 1.1), (62.0, 99.0, 1.0), (114.0, 93.0, 1.0), (40.0, 38.0, 0.0)):
        if r:
            bv.poly(tiny_twinkle(u, y, r))
    return bv.patches


# ======================================================================================
# The tree: a puffy crown round its owls and stars, rising to the flat top where the
# perch plugs on, and a trunk on roots down to the flat bottom that stands in the base
# ======================================================================================
def tree_outline():
    W, H = L.TREE_W, L.TREE_H
    cx = L.TREE_TOP_PLUG[0]
    crown = [circle(x, y, 9.4) for (x, y) in L.TREE_STARS if y < 80]
    crown += [circle(x, y, 7.4) for (x, y) in L.TREE_WISPS if y < 80]
    crown += [ellipse(x, y + 3.0, 12.8, 16.0) for (x, y) in L.OWLS[:2]]
    crown += [box(cx - 14.0, -8.0, cx + 14.0, 12.0), circle(cx, 30, 14), circle(cx, 46, 13),
              circle(cx - 19.5, 8.8, 8.2), circle(cx + 19.5, 8.8, 8.2)]
    crown = U(crown).buffer(3.0, resolution=16).buffer(-3.0, resolution=16)
    trunk = Polygon(chain(bez((cx - 10.5, 58), (cx - 11.0, 80), (cx - 12.0, 96), (cx - 26.0, H + 2), 20),
                          bez((cx + 26.0, H + 2), (cx + 12.0, 96), (cx + 11.0, 80), (cx + 10.5, 58), 20)))
    ox, oy = L.OWLS[2]
    lower = [ellipse(ox, oy + 4.5, 12.2, 14.6)]
    lower += [circle(x, y + 0.5, 7.0) for (x, y) in L.TREE_WISPS if y >= 80]
    lower += [circle(x, y, 8.6) for (x, y) in L.TREE_STARS if y >= 80]
    g = U(crown, trunk, lower)
    g = g.buffer(1.6, resolution=16).buffer(-1.6, resolution=16)
    g = g.buffer(-1.2, resolution=16).buffer(1.2, resolution=16).intersection(box(0, 0, W, H))
    g = g.buffer(-0.8, resolution=16).buffer(0.8, resolution=16).intersection(box(0, 0, W, H))   # child-safe corners
    return max(polys(g), key=lambda p: p.area)


def tree_skeleton():
    """The trunk and its limbs as one shape, drawn as an outline: a limb out under each
    crown owl, and a leader up to the top."""
    cx, H = L.TREE_TOP_PLUG[0], L.TREE_H
    (ax, ay), (bx, by) = L.OWLS[0], L.OWLS[1]
    trunk = Polygon(chain(bez((cx - 15.5, H + 1), (cx - 9.0, 102.0), (cx - 8.0, 86.0), (cx - 7.6, 62.0), 30),
                          bez((cx + 7.6, 62.0), (cx + 8.0, 86.0), (cx + 9.0, 102.0), (cx + 15.5, H + 1), 30)))
    left = taper(bez((cx - 3.0, 64.0), (cx - 9.0, 66.0), (ax + 8.0, ay + 17.2), (ax + 3.0, ay + 16.2), 40), 7.0, 2.0)
    right = taper(bez((cx + 3.0, 63.0), (cx + 9.0, 58.0), (bx - 8.0, by + 17.2), (bx - 3.0, by + 16.2), 40), 7.0, 2.0)
    lead = taper(bez((cx, 62.0), (cx + 1.0, 46.0), (cx - 1.5, 30.0), (cx + 1.0, 16.0), 40), 6.5, 3.0)
    twigs = [taper(bez((cx - 0.5, 40.0), (cx - 4.0, 36.5), (cx - 6.0, 33.5), (cx - 6.5, 29.0), 16), 2.0, 0.7),
             taper(bez((cx + 0.5, 28.0), (cx + 3.5, 24.0), (cx + 6.0, 22.0), (cx + 9.5, 21.5), 16), 1.8, 0.6)]
    return rounded(U([trunk, left, right, lead] + twigs), 0.4)


def tree_front(cv):
    cx = L.TREE_TOP_PLUG[0]
    owls = [owl_round(cv, x, y) for (x, y) in L.OWLS]      # front to back: the owls first
    cv.keep_clear(TOP, U([o.buffer(0.7) for o in owls]))
    for i, (x, y) in enumerate(L.TREE_STARS):
        pointy_star(cv, x, y, 6.8, 3.45, -90 + 14 * ((i % 3) - 1))
    for (x, y) in L.TREE_WISPS:
        wisp(cv, x, y, 1 if x < cx else -1)
    cv.keep_clear(TOP, U([star_zone(x, y, 6.8) for (x, y) in L.TREE_STARS] + [wisp_zone(x, y) for (x, y) in L.TREE_WISPS]))
    sk = tree_skeleton()
    cv.outline_strokes(TOP, sk, 0.3)
    for dx, y0, y1, wob in ((-3.0, 99, 107, 0.6), (3.2, 100, 108, -0.6), (-1.0, 66, 72, 0.5), (2.5, 50, 57, -0.5),
                            (-1.5, 40, 46, 0.4)):                      # bark
        cv.line(TOP, [(cx + dx + wob * math.sin(t * 3.0), y0 + (y1 - y0) * t) for t in [k / 16 for k in range(17)]], 0.2)
    cv.keep_clear(TOP, sk.buffer(0.6))
    for gx in (cx - 18.0, cx + 18.0):
        grass(cv, TOP, gx, 110.6)
    for (x, y, r) in ((20.0, 6.5, 1.1), (55.5, 4.0, 1.0), (49.0, 21.0, 1.2), (21.0, 38.5, 1.0), (5.0, 56.0, 1.0),
                      (72.0, 49.0, 1.1)):
        cv.poly(TOP, tiny_twinkle(x, y, r))


def tree_back(cv):
    cx = L.TREE_TOP_PLUG[0]
    name = "for " + (BI.FOR_NAME if BI.FOR_NAME else "______")
    for s, y, h in ((BI.TITLE, 24.0, 2.6), ("the owls' tree, rev " + BI.REV, 28.4, 1.5), (name, 34.0, 2.4)):
        cv.text(BOT, s, cx, y, h, 0, "center")
    return [(box(cx - 24.0, 20.5, cx + 24.0, 37.0), "the tree's name, on its back")]


# ======================================================================================
# The perch: a rectangle with the owl's notches and the bat's thread hole
# ======================================================================================
def perch_outline():
    W2, F, B = L.PERCH_W / 2, L.PERCH_FRONT, L.PERCH_BACK
    y0, y1 = M.OWL_NOTCH_Y
    d = M.OWL_NOTCH_D
    g = Polygon(rrect(-W2, F, W2, B, 2.0, 12))
    for sx in (-1, 1):
        g = g.difference(box(W2 - d, y0, W2 + 1.0, y1) if sx > 0 else box(-W2 - 1.0, y0, -W2 + d, y1))
    g = g.buffer(0.5, resolution=16).buffer(-0.5, resolution=16)     # the notches' inside corners: router r 0.5
    hole = arc_pts(M.THREAD_HOLE[0], M.THREAD_HOLE[1], M.THREAD_HOLE_D / 2, 0, 360, 36)[:-1]
    return g, hole


OWL_ON_PERCH = (-15.5, -11.6, 15.5, 10.0)      # the printed owl covers this (print/README.md)


def perch_front(cv):
    y = 20.5                                     # a little branch across the back
    cv.line(TOP, bez((-15.5, y - 1.0), (-6, y - 2.2), (5, y - 0.4), (15.5, y - 1.6), 40), 0.25)
    cv.line(TOP, bez((-15.5, y + 1.4), (-6, y + 0.4), (5, y + 2.0), (15.5, y + 0.9), 40), 0.25)
    for x0 in (-11.0, -3.5, 4.5, 11.5):          # bark
        cv.line(TOP, bez((x0, y - 0.3), (x0 + 0.8, y), (x0 + 1.2, y + 0.2), (x0 + 2.0, y + 0.4), 8), 0.18)
    cv.line(TOP, bez((6.0, y - 1.2), (7.0, y - 3.4), (8.6, y - 4.4), (10.0, y - 4.8), 14), 0.22)       # a twig
    leaf = Polygon(bez((10.0, y - 4.8), (11.4, y - 6.6), (13.9, y - 6.2), (14.6, y - 5.0), 12) +
                   bez((14.6, y - 5.0), (13.2, y - 4.0), (11.6, y - 3.9), (10.0, y - 4.8), 12)[1:])
    cv.poly(TOP, leaf.buffer(0))
    cv.line(TOP, bez((-9.0, y + 1.7), (-9.8, y + 3.9), (-11.6, y + 4.7), (-13.0, y + 4.3), 12), 0.22)  # a curl
    cv.text(TOP, "PERCH", 0.0, 26.4, 1.4, 0, "center")
    hx, hy = M.THREAD_HOLE
    cv.text(TOP, "← the bat's thread", hx + 1.6, hy, 1.0, 0, "left")
    return [(box(*OWL_ON_PERCH), "the printed owl stands here (print/README.md)")]


# ======================================================================================
# The bat: seen from above, its head forward (-y)
# ======================================================================================
BAT_TIPS = [(24.0, -6.2), (21.0, 3.4), (14.9, 9.0), (10.9, 9.3)]     # wingtip, fingertips, body (right half)
BAT_WRIST = (16.2, -11.6)
CAP_DOME_R = 6.6                                                      # print/README.md, for the board designer


def bat_outline():
    """Straight head and tail edges with the cap's notches, pointed wingtips, three
    scallops between the fingers."""
    head, tail = L.BAT_HEAD_Y, L.BAT_TAIL_Y                           # the edges, -13 and +12
    nw, nd = M.BAT_NOTCH_W / 2, M.BAT_NOTCH_D
    right = [(0.0, head), (7.4, head)]
    right += bez((7.4, head), (10.5, head), (13.5, head + 0.2), (16.4, head + 0.4), 12)[1:]          # the arm
    right += bez((16.4, head + 0.4), (19.5, head + 0.8), (22.5, head + 3.4), BAT_TIPS[0], 14)[1:]     # to the wingtip
    for (a, b), dd in zip(zip(BAT_TIPS[:-1], BAT_TIPS[1:]), (2.6, 2.4, 0.9)):                     # scallops
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        n = (-(b[1] - a[1]), b[0] - a[0])
        ln = math.hypot(*n)
        c = (m[0] + n[0] / ln * dd, m[1] + n[1] / ln * dd)
        right += bez(a, ((a[0] + 2 * c[0]) / 3, (a[1] + 2 * c[1]) / 3), ((b[0] + 2 * c[0]) / 3, (b[1] + 2 * c[1]) / 3), b, 16)[1:]
    right += bez(BAT_TIPS[-1], (9.0, 10.6), (5.6, tail), (3.5, tail), 12)[1:]
    right += [(0.0, tail)]
    left = [(-x, y) for x, y in reversed(right)]
    g = Polygon(right[:-1] + left[1:-1]).buffer(0)
    g = g.buffer(-0.5, resolution=12).buffer(0.5, resolution=12)                                 # no sharp tips
    straight = box(-6.5, head, 6.5, head + 3.0).union(box(-3.4, tail - 3.0, 3.4, tail))             # but straight edges
    g = U(g, straight.intersection(Polygon(right[:-1] + left[1:-1]).buffer(0)))
    return g.difference(box(-nw, head - 1, nw, head + nd)).difference(box(-nw, tail - nd, nw, tail + 1))


def bat_wings(cv, layer):
    for sx in (-1, 1):                          # the fingers' bones, from the wrist
        wx, wy = sx * BAT_WRIST[0], BAT_WRIST[1]
        for tx, ty in BAT_TIPS[:3]:
            tx, ty = sx * (tx - (1.1 if tx > 20 else 0.66)), ty - 0.8
            mx, my = (wx + tx) / 2, (wy + ty) / 2
            cv.line(layer, bez((wx, wy), (mx - sx * 0.6, my - 0.3), (mx + sx * 0.2, my + 0.2), (tx, ty), 16), 0.22)
        cv.poly(layer, circle(wx, wy, 0.5, 16))


def bat_front(cv):
    bat_wings(cv, TOP)
    for sx in (-1, 1):                          # a friendly face round the glowing eyes: lids, rosy cheeks
        ex, ey = sx * 4.6, L.BAT_HEAD_Y + 0.9
        cv.arc(TOP, ex, ey, 2.45, 25, 155, 0.22)
        for k in range(3):
            cv.line(TOP, [(sx * (7.9 + 0.55 * k), -8.9), (sx * (7.5 + 0.55 * k), -8.0)], 0.18)
    return [(circle(0, 0, CAP_DOME_R, 96), "the printed cap's dome (print/README.md)"),
            (box(-2.5, L.BAT_HEAD_Y, 2.5, L.BAT_TAIL_Y), "under the cap's arms: parts under 1.4 mm only")]


# ======================================================================================
# The tokens: an owl and a cat, each round its coil, its parts in a patch at the bottom
# ======================================================================================
TOKEN_PATCH = (-6.3, 11.6, 6.3, 19.5)      # the parts at the bottom of each token: no silk there


def owl_token_outline():
    body = superellipse(0, 0.6, 16.6, 17.9, 2.4)
    tufts = [Polygon([(-15.0, -6.0), (-12.6, -17.2), (-6.5, -13.5)]), Polygon([(15.0, -6.0), (12.6, -17.2), (6.5, -13.5)])]
    feet = [ellipse(-3.6, 17.6, 3.0, 1.5), ellipse(3.6, 17.6, 3.0, 1.5)]
    return rounded(U(body, tufts, feet), 0.9).intersection(circle(0, 0, L.TOKEN_R - 0.05, 400))


def token_back(cv, name, f_khz):
    """The token's name and the note it rings at, on its back."""
    cv.text(BOT, name, 0.0, -7.6, 2.6, 0, "center")
    cv.text(BOT, "%d kHz" % f_khz, 0.0, 7.4, 1.6, 0, "center")


def owl_token_front(cv):
    for sx in (-1, 1):
        ex, ey = sx * 5.7, -4.6
        cv.circle(TOP, ex, ey, 4.3, 0.28)
        cv.poly(TOP, circle(ex + sx * 0.4, ey + 0.3, 2.0).difference(circle(ex + sx * 0.4 + 0.7, ey - 0.4, 0.55)))
        cv.line(TOP, arc_pts(ex, ey, 5.4, 205 if sx < 0 else 235, 305 if sx < 0 else 335, 24), 0.25)   # brows
        cv.line(TOP, bez((sx * 13.8, -3.5), (sx * 15.8, 2.5), (sx * 14.2, 8.5), (sx * 9.6, 11.2), 24), 0.25)  # wings
    cv.poly(TOP, rounded(Polygon([(-1.4, -0.6), (1.4, -0.6), (0.0, 2.2)]), 0.25))                   # beak
    for (u, v) in ((-3.4, 5.6), (0.0, 5.6), (3.4, 5.6), (-1.7, 8.4), (1.7, 8.4)):                   # chest
        cv.line(TOP, arc_pts(u, v, 1.3, 20, 160, 12), 0.22)
    return []


def cat_token_outline():
    head = superellipse(0, 2.6, 16.8, 15.8, 2.4)
    ears = [Polygon([(-15.2, -6.0), (-10.0, -17.6), (-3.2, -12.0)]), Polygon([(15.2, -6.0), (10.0, -17.6), (3.2, -12.0)])]
    return rounded(U(head, ears), 0.9).intersection(circle(0, 0, L.TOKEN_R - 0.05, 400))


def cat_token_front(cv):
    for sx in (-1, 1):
        ex, ey = sx * 5.6, -2.6
        eye = Polygon(bez((ex - 3.0, ey), (ex - 1.6, ey - 2.6), (ex + 1.6, ey - 2.6), (ex + 3.0, ey), 14) +
                      bez((ex + 3.0, ey), (ex + 1.6, ey + 2.2), (ex - 1.6, ey + 2.2), (ex - 3.0, ey), 14)[1:])
        cv.line(TOP, list(eye.exterior.coords), 0.26)
        cv.poly(TOP, ellipse(ex, ey, 0.75, 1.9).difference(circle(ex + 0.25, ey - 0.8, 0.3, 12)))   # slit pupil
        cv.line(TOP, [(sx * 10.0, -13.0), (sx * 10.6, -10.6), (sx * 12.6, -9.0)], 0.22)           # inner ear
        for dy in (-0.8, 0.9, 2.6):                                                                 # whiskers
            cv.line(TOP, bez((sx * 5.2, 3.6 + dy * 0.4), (sx * 8.5, 3.0 + dy), (sx * 11.5, 2.8 + dy * 1.3),
                             (sx * 14.4, 2.6 + dy * 1.7), 16), 0.2)
    cv.poly(TOP, rounded(Polygon([(-1.3, 2.2), (1.3, 2.2), (0.0, 3.6)]), 0.25))                      # nose
    cv.line(TOP, arc_pts(-1.0, 4.0, 1.0, 10, 170, 12)[::-1], 0.22)                                   # the mouth
    cv.line(TOP, arc_pts(1.0, 4.0, 1.0, 10, 170, 12), 0.22)
    for k in (-1, 0, 1):                                                                            # forehead stripes
        cv.line(TOP, [(k * 1.6, -8.6 - (0.6 if k == 0 else 0)), (k * 1.6 * 1.15, -6.6)], 0.22)
    return []


# ======================================================================================
# Building every board, and checking it
# ======================================================================================
_CANVAS = {}                     # board -> Canvas, from the last build (the previews use them)


def board_outline(board):
    """(edge polygon, [cut-out point lists]), simplified to within 10 um."""
    edge, holes = _board_outline(board)
    return edge.simplify(0.01, preserve_topology=True), holes


def _board_outline(board):
    if board == "base":
        return Polygon(rrect(0, 0, L.BASE_W, L.BASE_H, L.BASE_R, 16)), []
    if board == "tree":
        return tree_outline(), []
    if board == "perch":
        g, hole = perch_outline()
        return g, [hole]
    if board == "bat":
        return bat_outline(), []
    return (owl_token_outline() if board == "owl_token" else cat_token_outline()), []


def _json_item(it, layer):
    k = it[0]
    if k == "poly":
        return {"kind": "poly", "pts": [list(p) for p in it[1]]}
    if k == "polyline":
        return {"kind": "polyline", "pts": [list(p) for p in it[1]], "width": it[2]}
    if k == "circle":
        return {"kind": "circle", "c": [it[1], it[2]], "r": it[3], "width": it[4]}
    if k == "arc":
        _, cx, cy, r, a0, a1, w = it
        P = lambda a: [round(cx + r * math.cos(math.radians(a)), 4), round(cy + r * math.sin(math.radians(a)), 4)]
        return {"kind": "arc", "c": [cx, cy], "r": r, "a0": a0, "a1": a1, "width": w,
                "start": P(a0), "mid": P((a0 + a1) / 2), "end": P(a1)}
    if k == "text":
        _, s, x, y, h, a, j = it
        return {"kind": "text", "s": s, "at": [x, y], "h": h, "angle": a, "justify": j,
                "thickness": text_thickness(h), "mirror": layer.startswith("B.")}
    raise ValueError(k)


def build(verbose=False):
    """Draw every board.  Returns the dict hardware/art.json holds."""
    out = {"meta": {"generator": "gen/art.py", "units": "mm", "inputs_sha256": inputs_sha(),
                    "frame": "each board's own (gen/layout.py): x right, y down, seen from the top",
                    "text": "KiCad stroke font; anchor vertically centred; thickness = max(0.15, 0.15 h); "
                            "B.* text mirrored; _{} and ^{} are KiCad's sub/superscript markup",
                    "boards": list(BOARDS)},
           "boards": {}, "antennas": []}
    ants = antennas_geometry()
    for net, cu, op, pad in ants:
        out["antennas"].append({"net": net, "copper": [[list(p) for p in ring_pts(q)] for q in simple_polys(cu)],
                                "mask_open": [[list(p) for p in ring_pts(q)] for q in simple_polys(op)],
                                "keepout": [list(p) for p in ring_pts(cu.buffer(L.ANTENNA_KEEPOUT, resolution=16))],
                                "pad": [round(pad[0], 4), round(pad[1], 4)]})
    for board in BOARDS:
        cv = Canvas(board)
        edge, holes = board_outline(board)
        for lay in (TOP, BOT):
            cv.keep_clear(lay, edge_clear(ring_pts(edge), SILK_EDGE))
            for h in holes:
                cv.keep_clear(lay, Polygon(h).buffer(SILK_EDGE))
        cv.parts = keep_parts_clear(cv, board)
        keep = []
        if board == "base":
            cv.keep_clear(TOP, base_led_clear())
            cv.keep_clear(BOT, U([circle(x, y, FOOT_CLEAR) for (x, y) in L.FEET]))
            for net, cu, op, pad in ants:
                cv.keep_clear(TOP, op.buffer(MASK_GAP))
                cv.keep_clear(TOP, cu.buffer(MASK_GAP))
            base_top(cv)
            keep += [(g, ("B.Cu",), what) for g, what in spell_book(cv)]
        elif board == "tree":
            for (x, y) in L.TREE_STARS:
                cv.keep_clear(TOP, circle(x, y, STAR_CLEAR))
            for (x, y) in L.TREE_WISPS:
                cv.keep_clear(TOP, circle(x, y, SMALL_LED_CLEAR))
            for (x, y) in L.OWLS:
                for sx in (-1, 1):
                    cv.keep_clear(TOP, circle(x + sx * L.OWL_EYE_SPACING / 2, y, 1.5))
            tree_front(cv)
            keep += [(g, ("B.Cu",), what) for g, what in tree_back(cv)]
        elif board == "perch":
            cv.keep_clear(TOP, box(*OWL_ON_PERCH))
            keep += [(g, ("F.Cu",), what) for g, what in perch_front(cv)]
        elif board == "bat":
            cv.keep_clear(TOP, circle(0, 0, CAP_DOME_R + 0.3))
            cv.keep_clear(TOP, box(-2.5 - 0.3, -20, 2.5 + 0.3, 20))
            keep += [(g, ("F.Cu",), what) for g, what in bat_front(cv)]
            bat_wings(cv, BOT)
        else:
            cv.keep_clear(TOP, box(*TOKEN_PATCH))
            keep += (owl_token_front if board == "owl_token" else cat_token_front)(cv)
            token_back(cv, "OWL" if board == "owl_token" else "CAT", 148 if board == "owl_token" else 316)
        _CANVAS[board] = cv
        out["boards"][board] = {
            "outline": [[list(p) for p in ring_pts(edge)]] + [[[round(x, 4), round(y, 4)] for x, y in h] for h in holes],
            "layers": {lay: [_json_item(it, lay) for it in items] for lay, items in sorted(cv.items.items())},
            "keepouts": [{"pts": [list(p) for p in ring_pts(g)], "layers": list(ls), "what": w} for g, ls, w in keep]}
    return out


def check(data):
    """What the art can see is wrong, its own faults and the floor plan's.  [(level, text)]"""
    out = []
    for board in BOARDS:
        cv = _CANVAS.get(board)
        edge = Polygon(data["boards"][board]["outline"][0])
        for n in (cv.notes if cv else []):
            out.append(("art", n))
        for lay, items in data["boards"][board]["layers"].items():
            for it in items:
                if it["kind"] == "text" and it["h"] < MIN_TEXT - 1e-9:
                    out.append(("art", "%s %s: text %r is %.2f mm high" % (board, lay, it["s"], it["h"])))
                if "width" in it and it["width"] < MIN_STROKE - 1e-9:
                    out.append(("art", "%s %s: a %s %.2f mm wide" % (board, lay, it["kind"], it["width"])))
        # every pad and courtyard inside the board, clear of its edge
        for ref, name, court, pads, side in placed(board):
            for pd, th in pads:
                if not edge.buffer(-0.2).contains(pd):
                    out.append(("plan", "%s: %s's pads cross the board's edge (or come within 0.2 mm of it)" % (board, ref)))
                    break
    # the floor plan's crowding the art had to work round
    for i, (x, y) in enumerate(L.WISPS):
        for nm, (px, py) in (("owl", L.OWL_PERCH), ("cat", L.CAT_PERCH)):
            d = math.hypot(x - px, y - py)
            if L.PERCH_ART_R - 2.0 < d < L.PERCH_ART_R + 2.0:
                out.append(("plan", "base: WISP%d at (%g, %g) sits on the %s perch's circle (%.1f mm from its centre)"
                            % (i, x, y, nm, d)))
    for i, (x, y) in enumerate(L.STARX):
        for nm, (px, py) in (("owl", L.OWL_PERCH), ("cat", L.CAT_PERCH)):
            d = math.hypot(x - px, y - py)
            if d < L.PERCH_ART_R + STAR_CLEAR + 1.0:
                out.append(("plan", "base: STARX%d at (%g, %g) sits on the %s perch's circle (%.1f mm from its centre)"
                            % (i, x, y, nm, d)))
    # the tokens and the bat: the shapes the prints and coils need
    for board in ("owl_token", "cat_token"):
        e = Polygon(data["boards"][board]["outline"][0])
        if not e.contains(circle(0, 0, 13.0)):
            out.append(("art", "%s: the outline does not hold a 13 mm disc" % board))
        if max(math.hypot(x, y) for x, y in e.exterior.coords) > L.TOKEN_R + 1e-6:
            out.append(("art", "%s: the outline leaves radius %.1f" % (board, L.TOKEN_R)))
    bat = Polygon(data["boards"]["bat"]["outline"][0])
    for yy, nm in ((L.BAT_HEAD_Y, "head"), (L.BAT_TAIL_Y, "tail")):
        seg = LineString([(-3.0, yy), (-M.BAT_NOTCH_W / 2, yy)]), LineString([(M.BAT_NOTCH_W / 2, yy), (3.0, yy)])
        if not all(bat.exterior.buffer(0.01).contains(s) for s in seg):
            out.append(("art", "bat: the %s edge is not straight across |x| <= 3" % nm))
    tree = Polygon(data["boards"]["tree"]["outline"][0])
    for yy, (cx, _) in ((0.0, L.TREE_TOP_PLUG), (L.TREE_H, L.TREE_BASE_PLUG)):
        if not tree.exterior.buffer(0.01).contains(LineString([(cx - 13.0, yy), (cx + 13.0, yy)])):
            out.append(("art", "tree: no straight 26 mm edge at y = %g" % yy))
    # the antennas' gold: nothing narrower than 0.3 mm, mask or opening
    for a in data["antennas"]:
        op = U([Polygon(p).buffer(0.001) for p in a["mask_open"]])
        cu = U([Polygon(p) for p in a["copper"]])
        thin_gold = op.difference(op.buffer(-0.149).buffer(0.149)).area
        thin_mask = cu.difference(op).difference(cu.difference(op).buffer(-0.149).buffer(0.149)).area
        if thin_gold > 0.05 or thin_mask > 0.05:
            out.append(("art", "%s: features under 0.3 mm in the mask (%.2f, %.2f mm2)" % (a["net"], thin_gold, thin_mask)))
    for b, ref, name in sorted(MISSING):
        out.append(("plan", "%s: %s's footprint %r is not in hardware/lib (left out of the art's checks)" % (b, ref, name)))
    return out


# ======================================================================================
# Previews: each board's top and bottom as the fab will make it (purple mask, white
# silk, ENIG gold where the mask opens over copper), the bottom seen from below
# ======================================================================================
BG, MASK, MASK_CU, MASK_DARK = "#17121d", "#3b1f5c", "#55307d", "#2e1849"
GOLD, SILK = "#d9b24c", "#f4f1ea"
PART = {"part": "#6a6a75", "led": "#f3efe6", "pad": GOLD}
LED_DOT = {"violet": "#a67cff", "purple": "#d36bff", "orange": "#ffa040"}


def _coils(board):
    """(cx, cy, r_in, r_out, turns, width) of each coil on a board, for the previews."""
    import parts as PA
    import placement as PL
    out = []
    for ref, fp in COIL_FP.items():
        if ref in PL.BOARDS[board].place:
            x, y, _, _ = PL.BOARDS[board].place[ref]
            c = PA.COILS["COIL_" + fp.split("_", 1)[1]]
            out.append((x, y, c["r_in"], c["r_out"], c["turns"], c["width"]))
    return out


def item_geom(it, mirror):
    k = it[0]
    if k == "poly":
        return Polygon(it[1])
    if k == "polyline":
        return LineString(it[1]).buffer(it[2] / 2, resolution=8)
    if k == "circle":
        _, cx, cy, r, w = it
        return circle(cx, cy, r + w / 2).difference(circle(cx, cy, max(r - w / 2, 1e-3)))
    if k == "arc":
        _, cx, cy, r, a0, a1, w = it
        return LineString(arc_pts(cx, cy, r, a0, a1)).buffer(w / 2, resolution=8)
    _, s, x, y, h, a, j = it
    return text_geom(s, x, y, h, a, j, mirror)


def render(board, side, path, px_per_mm=10):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    outl = outline(board)
    edge = Polygon(outl[0])
    x0, y0, x1, y1 = edge.bounds
    m = 3.0
    flip = (x0 + x1) if side == "bottom" else None
    F = "F" if side == "top" else "B"

    def patch(ax, g, color, z):
        for p in polys(g):
            verts, codes = [], []
            for ring in [p.exterior] + list(p.interiors):
                xy = [((flip - x) if flip is not None else x, y) for x, y in ring.coords]
                verts += xy
                codes += [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), fc=color, ec="none", lw=0, zorder=z))

    W, H = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=25.4 * px_per_mm)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0 - m, x1 + m)
    ax.set_ylim(y1 + m, y0 - m)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    patch(ax, edge, MASK, 1)
    if board == "base" and side == "bottom":
        for a in antennas():
            patch(ax, Polygon(a["keepout"]), MASK_DARK, 1.5)             # no copper there: darker
    for (cx, cy, r0, r1, turns, w) in _coils(board):
        N = int(turns * 90)
        pts = [(cx + (r1 - (r1 - r0) * k / N) * math.cos(2 * math.pi * turns * k / N),
                cy + (r1 - (r1 - r0) * k / N) * math.sin(2 * math.pi * turns * k / N)) for k in range(N + 1)]
        patch(ax, LineString(pts).buffer(max(w, 0.2) / 2), MASK_CU, 2)
    if board == "base" and side == "top":
        for a in antennas():
            patch(ax, U([Polygon(c) for c in a["copper"]]), MASK_CU, 2.5)
            patch(ax, U([Polygon(o).buffer(0.002) for o in a["mask_open"]]), GOLD, 3)
    lay = art(board)
    patch(ax, U([item_geom(it, side == "bottom").buffer(0.002) for it in lay.get(F + ".Mask", [])]), GOLD, 3.1)
    patch(ax, U([item_geom(it, side == "bottom") for it in lay.get(F + ".SilkS", [])]), SILK, 4)
    cv = _CANVAS.get(board)
    for g, kind in (cv.parts[F] if cv is not None else []):
        patch(ax, g.buffer(-0.15) if kind != "pad" else g, PART[kind], 5)
    for h in outl[1:]:
        patch(ax, Polygon(h), BG, 6)
    if board == "base":
        for (x, y) in L.FEET:
            patch(ax, circle(x, y, M.FOOT_HOLE_D / 2), BG, 6)
    fig.savefig(path, dpi=25.4 * px_per_mm, facecolor=BG)
    plt.close(fig)
    try:                                   # a small palette keeps the committed images small
        from PIL import Image
        Image.open(path).convert("RGB").quantize(colors=64, method=0).save(path, optimize=True)     # 0: median cut
    except Exception:
        pass
    return path


# ======================================================================================
# KiCad's stroke font, read from KiCad itself (run inside KiCad's Python)
# ======================================================================================
FONT_CHARS = "".join(chr(c) for c in range(32, 127)) + \
    "ΦΨΩΣΔΘΛΠΓαβγδεζηθικ" \
    "λμνξπρστυφχψωϕϵħĤĥ∂" \
    "√∑∫∇−·×÷±≈≠≤≥∞°²³¹⁰" \
    "⁴₀₁₂ᵢ→←↑↓↔⇒…–—‘’“”•" \
    "©®µ⋅∼′″∝Ååéèüöä⊙⊗⊕⊖" \
    "▲△►◄⌀★"


def extract_font():
    import re
    import pcbnew
    b = pcbnew.BOARD()
    SEG = re.compile(r"SHAPE_SEGMENT\(\s*VECTOR2I\(\s*(-?\d+),\s*(-?\d+)\),\s*VECTOR2I\(\s*(-?\d+),\s*(-?\d+)\)")

    def mk(s):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
        t.SetTextThickness(0)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        t.SetLayer(pcbnew.F_SilkS)
        return t

    def segs(s):
        return [[round(int(v) / 1e6, 5) for v in m.groups()] for m in SEG.finditer(mk(s).GetEffectiveTextShape(False).Format())]

    def width(s):
        return mk(s).GetTextBox(None).GetWidth() / 1e6

    box_glyph = segs("★")                  # a character KiCad lacks: it draws a box
    glyphs, missing = {}, ""
    for c in FONT_CHARS:
        g = segs(c)
        if c != "★" and g == box_glyph:
            missing += c
            continue
        if c == "★":
            continue
        glyphs[c] = {"adv": round(width(c * 3) - width(c * 2), 5), "s": g}
    meta = {"source": "KiCad %s stroke font (newstroke, CC0 1.0), read with pcbnew by gen/art.py --extract-font"
                      % pcbnew.Version(),
            "size": 1.0, "x_th": 1 / 1.52, "y_th": -0.052,
            "sub": {"scale": 0.8, "dy": 0.2030}, "sup": {"scale": 0.8, "dy": -0.1970},
            "missing_drawn_as_box": missing,
            "note": "glyph segments [x0, y0, x1, y1] for a 1 mm text of thickness 0, left-justified and "
                    "vertically centred (KiCad's default): x from the pen, y from the anchor.  A thickness th moves "
                    "the glyphs by x_th*th (left and right justification) and y_th*th; sub- and superscripts are "
                    "scale times as big and dy (times the height) lower"}
    with open(FONT_JSON, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "glyphs": glyphs}, f, ensure_ascii=False, separators=(",", ":"))
    print("%d glyphs -> %s (missing: %s)" % (len(glyphs), os.path.relpath(FONT_JSON, ROOT), missing))


# ======================================================================================
def main():
    args = sys.argv[1:]
    if "--extract-font" in args:
        extract_font()
        return 0
    if not HAVE_SHAPELY:
        raise SystemExit("gen/art.py draws with shapely: run it with the system python3")
    global _DATA
    data = build()
    _DATA = data
    os.makedirs(os.path.dirname(ART_JSON), exist_ok=True)
    with open(ART_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = {b: sum(len(v) for v in data["boards"][b]["layers"].values()) for b in BOARDS}
    print("art: %s -> %s" % (", ".join("%s %d items" % kv for kv in n.items()), os.path.relpath(ART_JSON, ROOT)))
    for a in data["antennas"]:
        print("  antenna %-5s pad at (%.2f, %.2f), %d copper and %d opening polygons"
              % (a["net"], a["pad"][0], a["pad"][1], len(a["copper"]), len(a["mask_open"])))
    problems = check(data)
    for level, text in problems:
        print("  %s: %s" % ("ART " if level == "art" else "PLAN", text))
    if "--no-png" not in args:
        os.makedirs(IMAGES, exist_ok=True)
        for b in BOARDS:
            for side in ("top", "bottom"):
                p = render(b, side, os.path.join(IMAGES, "art_%s_%s.png" % (b, side)), 10 if b == "base" else 20)
                print("  " + os.path.relpath(p, ROOT))
    return 1 if any(level == "art" for level, _ in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
