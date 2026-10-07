#!/usr/bin/env python3
"""Does the part you ORDERED fit the footprint that is ON THE BOARD?

    python3 footprint_check.py [BOM.csv] [--refresh] [--verbose]

Nothing else in this directory asks that question.  parts.py picks an LCSC
code by value and footprint NAME; jlc_api.py checks that the code is in stock;
jlc_rotation.py checks which way round it goes; pin1.py checks whether the
silkscreen says which way round it goes.  Every one of those is happy with a
part whose body does not physically fit the copper, because none of them ever
looks at the part's own land pattern.

Rev A found that out the expensive way.  SW1/SW2 are drawn for a
TS-1088-AR02016, a two-tab SMD tactile switch.  parts.py substituted a
TS-1088C-02026 -- same family, same 4 x 3 mm envelope, same two tabs -- and
left a note saying "check the footprint before ordering".  Nobody did, because
"check" was a sentence in a comment and not a thing that runs.  The C variant
carries two 0.9 mm locating posts on its underside that want two holes in the
board, the board has no holes there, the posts hold the part up off the
copper, and JLCPCB stopped the line and emailed to ask what to do about it.

The ECP5-2ADC-2DAC board (this copy) found out the cheap way.  Its first run
over build 24's BOM said the 2.2 pF 0402 capacitors' code, C1512, draws a 1206
with its pad centres a millimetre off ours: C1512 is a 180 kOhm resistor.  One
wrong code made the whole table suspect, and reading every code's JLCPCB
description back against its value (make_fab.code_value_check, now a release
gate) found seven more resistors that were other resistors -- the DAC's loads,
the PHY's bias, the negative rail's divider, the USB series pair.

THE TEST.  For every (LCSC code, board footprint) pair actually in the BOM,
fetch the land pattern JLCPCB will use -- the same one their reviewer was
looking at -- and ask three things of it:

    HOLE   does the part want a hole where the board has no drill?
    PADS   does it have pads the board has no copper for, or vice versa?
    LAND   does every pad of the part land on the copper meant for it?

A hole is a hard failure: it is mechanical, it cannot be fixed with paste, and
it is the one that bit us.  The other two are reported with the number so you
can decide; 0.04 mm of pad-centre drift is a different animal from 0.30 mm.

THE FOOTPRINT COMES FROM EASYEDA, not from the parts API that jlc_api.py
talks to.  That API returns stock and price and says nothing about geometry.
The land pattern lives at

    GET https://easyeda.com/api/products/<LCSC code>/svgs

which is what the "footprint" tab on the part page draws, which is what
JLCPCB's library holds, which is what their reviewer compared against the
drill file.  It is rendered as SVG in 10-mil units, and the two things worth
reading out of it are `c_partid="part_pad"` (a pad, with its centre, size and
whether it is plated) and `c_partid="part_hole"` (an unplated hole -- a
locating post, not a connection).

It has its own cache file, and the network call is here rather than in
jlc_api.py because jlc_api.py is maintained in GPSDO-PYNQ-Z2 and copied here;
adding an endpoint to the copy would fork it from the original.  (This file
was written for the ECP5-2ADC-2DAC board and copied into GPiBridge; only the
board and BOM paths differ.)

NO pcbnew.  The other scripts here need KiCad's Python; this one deliberately
does not, because the moment you want it is the moment an email arrives from
the fab and you are not necessarily sitting at the machine with the AppImage
extracted.  The .kicad_pcb is an s-expression and the parts we need out of it
-- footprint placements, pad geometry, drills -- are read directly.
"""
import collections
import csv
import datetime
import json
import math
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gen"))
import board_info as BI
PCB = BI.PCB
CACHE = os.path.join(HERE, "jlc_footprint_cache.json")
URL = "https://easyeda.com/api/products/%s/svgs"
MAX_AGE_H = 24 * 30           # land patterns do not move the way stock does
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

UNIT = 0.254                  # EasyEDA canvas unit: 10 mil, in mm
ORIGIN = 4000.0, 3000.0       # and its footprint origin, always this

# How far a pad centre may drift before we say something.  A tactile switch
# tab is over a millimetre across, so 0.15 mm is nothing and 0.50 mm means the
# land pattern is for a different part.
LAND_OK = 0.15
LAND_WARN = 0.50
HOLE_NEAR = 0.30              # a board drill this close counts as "that hole"
DATUM_OK = 0.10               # how far the two libraries' zeroes may differ

# The quarter turn that laid each part's land pattern on our footprint, by
# (LCSC code, bottom side): check() fills it and make_release.py prints it
# beside the CPL corrections (jlc_rotation.py) as a cross-check.
FITS = {}


# ---------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------
def sexp(text):
    """Parse an s-expression into nested lists.  Atoms stay strings."""
    out, stack, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            new = []
            (stack[-1] if stack else out).append(new)
            stack.append(new)
            i += 1
        elif c == ")":
            stack.pop()
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            stack[-1].append("".join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    return out


def kids(node, tag):
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def kid(node, tag):
    g = kids(node, tag)
    return g[0] if g else None


def nums(node, k=None):
    v = [float(x) for x in node[1:] if _isnum(x)]
    return v if k is None else (v + [0.0] * k)[:k]


def _isnum(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def top_forms(text):
    """The board file's top-level items as (head, text) pairs, without parsing it
    all.  KiCad writes every top-level item on a line of its own that starts with
    one tab and "(", and a quoted string never holds a raw newline, so splitting
    there is exact.  A panel's filled zones are most of the file and nothing here
    needs their outlines, so they are never parsed."""
    chunks = text.split("\n\t(")
    out = []
    for i, c in enumerate(chunks[1:], 1):
        if i == len(chunks) - 1:                  # the last one carries the file's own ")"
            c = c.rstrip()
            if c.endswith(")"):
                c = c[:-1]
        m = re.match(r"[A-Za-z_]+", c)
        out.append((m.group(0) if m else "", "(" + c))
    return out


_BOARDS = {}


def read_board_full(path):
    """Everything the release needs from a .kicad_pcb, cached by path and mtime.

    Returns a dict:
      fps      footprints: ref, value, short, lib, at (x, y, angle as stored),
               layer, attrs (the (attr ...) words), dnp, props {name: value},
               pads (number, type, shape, x, y, rot, w, h, drill, layers;
               x and y local to the footprint, as the file stores them)
      drills   (x, y, d) of every plated or unplated drill, vias included
      vias     (x, y, size, drill)
      aux      the drill/place file origin (aux_axis_origin), or None
      edges    point lists of every Edge.Cuts shape, in board millimetres
      texts    (text, layer, x, y) of the board's free texts
      copper   the copper layers' names, thickness, the number of filled zone
               polygons, and the widths of the tracks (Counter)
    """
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key in _BOARDS:
        return _BOARDS[key]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    B = dict(fps=[], drills=[], vias=[], aux=None, edges=[], texts=[], copper=[], thickness=None,
             filled=text.count("(filled_polygon"), widths=collections.Counter())
    for head, chunk in top_forms(text):
        if head in ("segment", "arc"):
            m = re.search(r"\(width ([\d.]+)\)", chunk)
            if m:
                B["widths"][float(m.group(1))] += 1
            continue
        if head not in ("footprint", "via", "setup", "general", "layers", "gr_line", "gr_rect", "gr_arc",
                        "gr_circle", "gr_poly", "gr_curve", "gr_text"):
            continue
        node = sexp(chunk)[0]
        if head == "footprint":
            B["fps"].append(_footprint(node, B))
        elif head == "via":
            vat = nums(kid(node, "at"), 2)
            d = kid(node, "drill")
            s = kid(node, "size")
            dd = nums(d, 1)[0] if d else 0.0
            B["vias"].append((vat[0], vat[1], nums(s, 1)[0] if s else 0.0, dd))
            B["drills"].append((vat[0], vat[1], dd))
        elif head == "setup":
            a = kid(node, "aux_axis_origin")
            if a:
                B["aux"] = tuple(nums(a, 2))
        elif head == "general":
            t = kid(node, "thickness")
            B["thickness"] = nums(t, 1)[0] if t else None
        elif head == "layers":
            B["copper"] = [c[1] for c in node[1:] if isinstance(c, list) and len(c) > 2
                           and str(c[1]).endswith(".Cu")]
        elif head == "gr_text":
            lay = kid(node, "layer")
            at = nums(kid(node, "at"), 2) if kid(node, "at") else [0.0, 0.0]
            B["texts"].append((node[1], lay[1] if lay else "", at[0], at[1]))
        else:
            lay = kid(node, "layer")
            if lay and lay[1] == "Edge.Cuts":
                B["edges"].append(_shape_points(node, None, None))
    _BOARDS[key] = B
    return B


def _footprint(fp, B):
    lib = fp[1]
    at = nums(kid(fp, "at"), 3)
    layer = kid(fp, "layer")[1]
    props = {}
    for pr in kids(fp, "property"):
        if len(pr) > 2:
            props[pr[1]] = pr[2]
    attr = kid(fp, "attr")
    attrs = [str(a) for a in attr[1:] if not isinstance(a, list)] if attr else []
    dnp = "dnp" in attrs or any(len(d) > 1 and d[1] == "yes" for d in kids(fp, "dnp"))
    pads = []
    for p in kids(fp, "pad"):
        number, ptype, shape = p[1], p[2], p[3]
        pat = nums(kid(p, "at"), 3)
        size = nums(kid(p, "size"), 2)
        dr = kid(p, "drill")
        layers = kid(p, "layers")
        drill = 0.0
        if dr:
            v = [float(x) for x in dr[1:] if _isnum(x)]
            drill = min(v) if v else 0.0           # an oval drill: its narrow way
        mm = kid(p, "solder_mask_margin")
        pads.append(dict(number=number, type=ptype, shape=shape, x=pat[0], y=pat[1], rot=pat[2],
                         w=size[0], h=size[1], drill=drill, mask=nums(mm, 1)[0] if mm else None,
                         layers=[str(s) for s in (layers[1:] if layers else [])]))
        if dr:
            bx, by = to_board(pat[0], pat[1], at, layer)
            B["drills"].append((bx, by, drill))
    for g in fp:
        if isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect", "fp_arc", "fp_circle", "fp_poly", "fp_curve"):
            lay = kid(g, "layer")
            if lay and lay[1] == "Edge.Cuts":
                B["edges"].append(_shape_points(g, at, layer))
    return dict(ref=props.get("Reference", ""), value=props.get("Value", ""), short=lib.split(":")[-1], lib=lib,
                at=at, layer=layer, attrs=attrs, dnp=dnp, props=props, pads=pads)


def _shape_points(g, at, layer):
    """Points along one outline shape (line, rect, arc, circle, polygon), in board mm."""
    def P(tag):
        n = kid(g, tag)
        return tuple(nums(n, 2)) if n else None
    head = g[0]
    pts = []
    if head.endswith("line"):
        pts = [P("start"), P("end")]
    elif head.endswith("rect"):
        (x0, y0), (x1, y1) = P("start"), P("end")
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    elif head.endswith("circle"):
        (cx, cy), (ex, ey) = P("center"), P("end")
        r = math.hypot(ex - cx, ey - cy)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(0, 360)]
    elif head.endswith("arc"):
        (x0, y0), (xm, ym), (x1, y1) = P("start"), P("mid"), P("end")
        pts = _arc(x0, y0, xm, ym, x1, y1)
    elif head.endswith("poly"):
        pl = kid(g, "pts")
        pts = [tuple(nums(xy, 2)) for xy in kids(pl, "xy")] if pl else []
    elif head.endswith("curve"):                  # a cubic Bezier: four control points
        pl = kid(g, "pts")
        c = [tuple(nums(xy, 2)) for xy in kids(pl, "xy")] if pl else []
        if len(c) == 4:
            pts = [tuple((1 - t) ** 3 * c[0][k] + 3 * (1 - t) ** 2 * t * c[1][k] + 3 * (1 - t) * t * t * c[2][k]
                         + t ** 3 * c[3][k] for k in (0, 1)) for t in (i / 64.0 for i in range(65))]
    if at is not None:
        pts = [to_board(x, y, at, layer) for x, y in pts]
    return pts


def _arc(x0, y0, xm, ym, x1, y1, n=360):
    """Points along the arc from (x0, y0) through (xm, ym) to (x1, y1)."""
    ax, ay, bx, by, cx, cy = x0, y0, xm, ym, x1, y1
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [(x0, y0), (x1, y1)]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, am, a1 = (math.atan2(y - uy, x - ux) for x, y in ((x0, y0), (xm, ym), (x1, y1)))
    sweep = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sweep:             # the mid point says it goes the other way
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


def read_board(path):
    """Footprint placements with their pads, plus every drill on the board."""
    B = read_board_full(path)
    return B["fps"], B["drills"]


def to_board(lx, ly, at, layer):
    """Footprint-local mm -> board mm, honouring rotation and side.

    KiCad stores a bottom-side footprint's pads in local coordinates that are
    already mirrored, so the side does not enter here -- only the rotation,
    which KiCad applies counter-clockwise in a y-down world.
    """
    a = math.radians(at[2] if len(at) > 2 else 0.0)
    ca, sa = math.cos(a), math.sin(a)
    return at[0] + lx * ca + ly * sa, at[1] - lx * sa + ly * ca


# ---------------------------------------------------------------------------
# the part, as JLCPCB's library holds it
# ---------------------------------------------------------------------------
def _cache_load():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            pass
    return {}


_cache = _cache_load()


def _cache_save():
    tmp = CACHE + ".tmp"
    json.dump(_cache, open(tmp, "w", encoding="utf-8"), indent=1,
              sort_keys=True)
    os.replace(tmp, CACHE)


def svgs(code, refresh=False):
    ent = _cache.get(code)
    if ent and not refresh:
        if (time.time() - ent["fetched_epoch"]) / 3600.0 < MAX_AGE_H:
            return ent["result"], ent["fetched"]
    req = urllib.request.Request(URL % code, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Referer": "https://easyeda.com/"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if not d.get("success"):
                raise RuntimeError("easyeda said no for %s" % code)
            now = datetime.datetime.now().astimezone()
            _cache[code] = dict(result=d["result"],
                                fetched=now.isoformat(timespec="seconds"),
                                fetched_epoch=time.time())
            _cache_save()
            time.sleep(0.35)                      # be polite to their server
            return d["result"], _cache[code]["fetched"]
        except Exception as e:                    # noqa: BLE001
            last = e
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("cannot fetch footprint for %s: %s" % (code, last))


def _attrs(tag):
    """Attributes of one SVG start tag.  EasyEDA writes `plated ="Y"`."""
    return {k: v for k, v in re.findall(r'([\w-]+)\s*=\s*"([^"]*)"', tag)}


def land_pattern(code, refresh=False):
    """{package, origin, pads[], holes[]} in mm, footprint-local, y down.

    The origin is NOT always the canvas centre.  Most footprints are drawn at
    (4000, 3000), but plenty are not -- the 0805 inductor sits at
    (4002.365, 3014.213) and the ECP5's BGA is drawn at (400, 300) entirely --
    and assuming the centre puts a 256-ball package a metre away from where it
    really is.  The outer <g> carries `c_origin`, and that is the footprint's
    own zero; everything below is measured from it.
    """
    result, ts = svgs(code, refresh)
    body = None
    for r in result:
        b = r.get("svg", "").split("</style>", 1)[-1]
        if 'c_partid="part_pad"' in b or 'c_partid="part_hole"' in b:
            body = b
            break
    if body is None:
        return None, ts

    top = re.search(r"<g [^>]*c_origin=\"([-\d.]+),([-\d.]+)\"[^>]*>", body)
    ox, oy = ((float(top.group(1)), float(top.group(2))) if top else ORIGIN)
    pkg = re.search(r"package`([^`]*)`", body)

    pads, holes = [], []
    for m in re.finditer(r"<g ([^>]*c_partid=\"part_(?:pad|hole)\"[^>]*)>",
                         body):
        a = _attrs(m.group(1))
        cx, cy = a.get("c_origin", "0,0").split(",")
        x = (float(cx) - ox) * UNIT
        y = (float(cy) - oy) * UNIT
        if a.get("c_partid") == "part_hole":
            # An unplated hole: a locating post, not a connection.  Its size
            # is the radius of the circle immediately inside the group.
            c = re.search(r"<circle[^>]*r=\"([\d.]+)\"", body[m.end():])
            holes.append(dict(x=x, y=y,
                              d=2 * float(c.group(1)) * UNIT if c else 0.0))
            continue
        # A pad.  c_padhole gives the drill; r="0" means there is not one.
        h = re.search(r"<circle[^>]*c_padhole=\"1\"[^>]*r=\"([\d.]+)\"",
                      body[m.end():m.end() + 800])
        pads.append(dict(number=a.get("number", ""),
                         layer=int(a.get("layerid") or 0),
                         plated=a.get("plated", "Y") == "Y",
                         x=x, y=y,
                         w=float(a.get("c_width") or 0) * UNIT,
                         h=float(a.get("c_height") or 0) * UNIT,
                         rot=float(a.get("c_rotation") or 0),
                         shape=a.get("c_shape", "?"),
                         drill=2 * float(h.group(1)) * UNIT if h else 0.0))
    return dict(package=pkg.group(1) if pkg else "?", origin=(ox, oy),
                pads=pads, holes=holes), ts


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------
def placed(pts, deg, mirror):
    """Rotate a set of footprint-local points, and mirror them for the back.

    KiCad stores a flipped footprint's pads already mirrored in y -- SW1 and
    SW2 sit on B.Cu and their pads carry B.Cu/B.Mask/B.Paste in the board file
    -- while EasyEDA always draws the part seen from the top.  So a
    bottom-side placement is compared against the part's mirror image.
    """
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    s = -1.0 if mirror else 1.0
    return [(x * ca - y * sa, s * (x * sa + y * ca)) for x, y in pts]


def best_fit(jpads, kpads, mirror, by_name, hint=(0.0, 0.0)):
    """Which quarter turn lines the part up with the footprint, and how well.

    JLCPCB's zero for a footprint need not be KiCad's -- that is the whole
    subject of jlc_rotation.py -- so a straight coordinate comparison would
    flag every part whose library draws it sideways.  Try all four turns.

    PADS ARE MATCHED BY NAME where the two libraries agree on names, which
    they do for anything with real pin numbers.  Nearest-neighbour matching is
    the obvious thing and it is wrong on exactly the parts that matter: on a
    256-ball BGA every ball is 0.8 mm from four others, so a whole package can
    be a pitch out of position and still score zero.  Names are only dropped
    when there is no overlap at all -- two-pad passives whose libraries call
    them 1/2 versus A/K, and the like.

    A TRANSLATION IS FITTED TOO, and the two numbers that come out mean
    different things.  The residual after the best translation is shape: does
    this land pattern have the same pads in the same places as that one.  The
    translation itself is datum: the two libraries measured from different
    zeroes.  The USB-C is the example -- its pads and its two locating holes
    are all exactly 1.305 mm out in y, together, which is not a part that
    fails to fit but a library that calls a different point the origin.  Only
    the residual can tell you the part is wrong.  The datum is not harmless,
    though: JLCPCB puts THEIR origin where the CPL says, so a part with one
    lands that far off its pads (every USB-C, 1.3-1.6 mm, until GPiBridge's
    preview, 2026-10-06).  make_release.py moves the JLCPCB CPL by it.

    Returns (dx, dy): where their origin sits in our footprint's frame.
    """
    kby = collections.defaultdict(list)
    for p in kpads:
        kby[p["number"]].append((p["x"], p["y"]))
    named = [p for p in jpads if p["number"] in kby]
    if by_name and len(named) < 2:
        return None
    use = named if by_name else jpads

    def pair(p, x, y):
        cands = kby[p["number"]] if by_name else [(q["x"], q["y"])
                                                  for q in kpads]
        return min(cands, key=lambda c: math.hypot(x - c[0], y - c[1]))

    kc = (sum(p["x"] for p in kpads) / len(kpads),
          sum(p["y"] for p in kpads) / len(kpads))
    best = None
    for deg in (0, 90, 180, 270):
        moved = placed([(p["x"], p["y"]) for p in use], deg, mirror)
        jc = (sum(x for x, _ in moved) / len(moved),
              sum(y for _, y in moved) / len(moved))
        # Pair, shift by the mean error, pair again.  That is plain ICP and,
        # like all ICP, it settles into whatever basin it starts in -- which
        # is why it is started from more than one place.  With the microSD the
        # two libraries are 3.4 mm apart, further than the pads are from each
        # other, so starting at zero pairs every finger with the wrong one and
        # the mean of eighteen wrong pairings is nonsense.  Starting from the
        # centroids, or from where matching the NAMES said the part was, both
        # land in the right basin.
        for seed in {(0.0, 0.0), (kc[0] - jc[0], kc[1] - jc[1]), tuple(hint)}:
            dx, dy = seed
            for _ in range(5):
                pairs = [(pair(p, x + dx, y + dy), (x, y))
                         for p, (x, y) in zip(use, moved)]
                ndx = sum(k[0] - j[0] for k, j in pairs) / len(pairs)
                ndy = sum(k[1] - j[1] for k, j in pairs) / len(pairs)
                if abs(ndx - dx) < 1e-9 and abs(ndy - dy) < 1e-9:
                    break
                dx, dy = ndx, ndy
            worst, total, at = 0.0, 0.0, ""
            for p, (k, j) in zip(use, pairs):
                d = math.hypot(j[0] + dx - k[0], j[1] + dy - k[1])
                total += d
                if d > worst:
                    worst, at = d, p["number"]
            if best is None or total < best["total"]:
                best = dict(deg=deg, worst=worst, total=total, at=at,
                            n=len(use), dx=dx, dy=dy,
                            how="by name" if by_name else "by position")
    return best


def check(code, insts, board_drills, refresh=False, verbose=False):
    """One (board footprint, ordered part, side) group.  Returns problems."""
    lp, ts = land_pattern(code, refresh)
    if lp is None:
        return [("NOFP", "no land pattern published for %s" % code)], None, ts
    kpads = insts[0]["pads"]
    mirror = insts[0]["layer"].startswith("B.")
    out = []

    # Fit by pad name first.  If that fits, it is the answer and it is the
    # strong one -- it says this pad is that pad.  If it does not fit, try
    # again ignoring names: a land pattern that lines up perfectly once the
    # names are dropped is not a part that does not fit, it is two libraries
    # that number the pins differently, and J6's microSD is exactly that.
    fit = best_fit(lp["pads"], kpads, mirror, by_name=True) if lp["pads"] \
        else None
    renamed = None
    if fit is None or fit["worst"] > LAND_WARN:
        loose = best_fit(lp["pads"], kpads, mirror, by_name=False,
                         hint=(fit["dx"], fit["dy"]) if fit else (0.0, 0.0)) \
            if lp["pads"] else None
        if loose and (fit is None or loose["worst"] <= LAND_OK):
            renamed, fit = fit, loose
    if fit is None:
        fit = dict(deg=0, worst=0.0, at="", n=0, dx=0.0, dy=0.0, how="")
    deg, dx, dy = fit["deg"], fit["dx"], fit["dy"]
    FITS[(code, mirror)] = dict(fit)
    # and by footprint too: one code can sit on two footprints drawn differently
    FITS[(code, mirror, insts[0]["short"])] = dict(fit)

    # ---- HOLE: the part wants a hole and the board has no drill -----------
    wants = ([dict(h, what="%.2f mm hole" % h["d"]) for h in lp["holes"]]
             + [dict(p, d=p["drill"],
                     what="%.2f mm through-hole pad %s" % (p["drill"],
                                                           p["number"]))
                for p in lp["pads"] if p["drill"] > 0])
    for h in wants:
        hx, hy = placed([(h["x"], h["y"])], deg, mirror)[0]
        hx, hy = hx + dx, hy + dy
        for inst in insts:
            bx, by = to_board(hx, hy, inst["at"], inst["layer"])
            near = min((math.hypot(bx - ox, by - oy)
                        for ox, oy, _ in board_drills), default=1e9)
            if near > HOLE_NEAR:
                out.append(("HOLE",
                            "%s wants a %s at (%+.2f, %+.2f) in the footprint; "
                            "nearest drill on the board is %.2f mm away"
                            % (inst["ref"], h["what"], hx, hy, near)))

    # ---- PADS: different numbers of them ----------------------------------
    # Counted as DISTINCT POSITIONS, not as pads.  KiCad draws the USB-C's
    # shorted A1/B12 pairs as two pads on one piece of copper and calls all
    # four shell tabs S1; counting pad records would say 22 against 16 and
    # mean nothing.  Unplated holes are not pads and are left out -- they are
    # the HOLE test's business.
    def spots(items):
        return {(round(x, 2), round(y, 2)) for x, y in items}
    n_j = len(spots((p["x"], p["y"]) for p in lp["pads"]
                    if p["layer"] in (1, 2, 11)))
    n_k = len(spots((p["x"], p["y"]) for p in kpads
                    if p["type"] != "np_thru_hole"
                    and any(l.endswith(".Cu") for l in p["layers"])))
    if n_j != n_k:
        out.append(("PADS", "part has %d pad position(s), footprint has %d"
                            % (n_j, n_k)))

    # ---- LAND: every pad of the part sitting on the copper meant for it ---
    if lp["pads"] and fit["worst"] > LAND_OK:
        out.append(("LAND" if fit["worst"] > LAND_WARN else "land",
                    "worst pad-centre miss %.3f mm (pad %s) at %d deg, "
                    "%d pad(s) matched %s"
                    % (fit["worst"], fit["at"] or "?", deg, fit["n"],
                       fit["how"])))
    if renamed:
        out.append(("names", "the land pattern fits to %.3f mm but the two "
                             "libraries number the pins differently -- by name "
                             "the worst miss is %.2f mm at pad %s.  Placement "
                             "is fine; the NET on each pin is the thing to "
                             "look at"
                             % (fit["worst"], renamed["worst"], renamed["at"])))
    # ---- datum: the two libraries measure from different zeroes ----------
    if math.hypot(dx, dy) > DATUM_OK:
        out.append(("datum", "their origin sits at (%+.3f, %+.3f) mm in our "
                             "footprint; the JLCPCB CPL is moved there"
                             % (dx, dy)))
    if verbose:
        print("    %-34s origin (%g, %g), fetched %s"
              % (lp["package"], lp["origin"][0], lp["origin"][1], ts))
        print("    fitted at %d deg%s, shifted (%+.3f, %+.3f), %d pad(s) %s, "
              "worst residual %.3f mm"
              % (deg, ", mirrored" if mirror else "", dx, dy, fit["n"],
                 fit["how"], fit["worst"]))
        for p in lp["pads"]:
            x, y = placed([(p["x"], p["y"])], deg, mirror)[0]
            print("      part %-4s (%+7.3f,%+7.3f) %5.2f x %5.2f %-9s%s"
                  % (p["number"], x + dx, y + dy, p["w"], p["h"], p["shape"],
                     "  drill %.2f" % p["drill"] if p["drill"] else ""))
        for h in lp["holes"]:
            x, y = placed([(h["x"], h["y"])], deg, mirror)[0]
            print("      HOLE      (%+7.3f,%+7.3f) dia %.2f"
                  % (x + dx, y + dy, h["d"]))
        for p in kpads:
            print("      brd  %-4s (%+7.3f,%+7.3f) %5.2f x %5.2f %-9s %s"
                  % (p["number"] or "-", p["x"], p["y"], p["w"], p["h"],
                     p["type"], ",".join(p["layers"])))
    return out, lp, ts


def report(bom, refresh=False, verbose=False, pcb=None, bom_label=None):
    """The whole check, as (hard_failure_count, lines).

    make_release.py calls this and writes the lines into the release beside
    PLACEMENT_CHECKS.txt, so that what was checked ships with what was sent.
    `pcb` is the board file (default: the project's); `bom_label` what to call the
    BOM in the report (the release's own name for a BOM still being staged).
    """
    pcb = pcb or PCB
    fps, drills = read_board(pcb)
    by_ref = {f["ref"]: f for f in fps}

    def rel(p):
        r = os.path.relpath(p, os.path.dirname(HERE))
        return r if not r.startswith("..") else os.path.basename(p)     # never a machine's own path
    L = ["FOOTPRINT vs ORDERED PART -- does the part fit the copper?",
         "=========================================================",
         "",
         "board  %s" % rel(pcb),
         "BOM    %s" % (bom_label or rel(bom)),
         "run    %s" % datetime.datetime.now().astimezone()
         .isoformat(timespec="seconds"),
         "%d footprint(s) placed, %d drill(s) on the board"
         % (len(fps), len(drills)), ""]

    bad = collections.Counter()
    for row in csv.DictReader(open(bom, encoding="utf-8")):
        code = (row.get("LCSC") or row.get("LCSC Part #") or "").strip()      # JLCPCB BOM column name as this board writes it
        refs = [r.strip() for r in row["Designator"].split(",") if r.strip()]
        insts = [by_ref[r] for r in refs if r in by_ref]
        if not insts:
            L.append("  ?  %-11s %s: no such reference on the board"
                     % (code, ",".join(refs)))
            bad["REF"] += 1
            continue
        # One BOM line can hold both sides of the board, and the two are not
        # the same comparison, so split them.
        groups = collections.defaultdict(list)
        for i in insts:
            groups[(i["short"], i["layer"].startswith("B."))].append(i)
        for (fpname, back), g in sorted(groups.items()):
            try:
                probs, lp, _ = check(code, g, drills, refresh, verbose)
            except RuntimeError as e:
                L.append("  ?  %-11s %-44s %s" % (code, fpname[:44], e))
                bad["NET"] += 1
                continue
            head = "%-11s %-44s %-18s %d placement(s)%s" % (
                code, fpname[:44], (lp or {}).get("package", "?")[:18],
                len(g), " bottom" if back else "")
            L.append(("  !! " if probs else "  ok ") + head)
            for tag, msg in probs:
                bad[tag] += 1
                L.append("       %-5s %s" % (tag, msg))

    hard = {k: v for k, v in bad.items() if k.isupper()}
    soft = {k: v for k, v in bad.items() if not k.isupper()}
    L.append("")
    if soft:
        L.append("worth a look: " + ", ".join("%s x%d" % kv
                                              for kv in sorted(soft.items())))
        L.append("  land  a pad centre out by less than half a millimetre")
        L.append("  datum the two libraries measure from different zeroes, and")
        L.append("        JLCPCB places THEIR zero where the CPL says: the JLCPCB")
        L.append("        CPL is moved by it (make_release.py), the native one not")
        L.append("  names the pads line up but the pin NUMBERS disagree")
    if not hard:
        L.append("")
        L.append("every ordered part fits the footprint it is going on.")
        return 0, L
    L += ["", "PROBLEMS: " + ", ".join("%s x%d" % kv
                                       for kv in sorted(hard.items())),
          "",
          "HOLE is a stop-the-order problem: the part cannot sit down on the",
          "copper at all, and no amount of paste fixes it.  PADS and LAND want",
          "a human with the two drawings side by side."]
    return sum(hard.values()), L


def main(argv):
    refresh = "--refresh" in argv
    verbose = "--verbose" in argv or "-v" in argv
    pos = [a for a in argv if not a.startswith("-")]
    bom = pos[0] if pos else default_bom()
    if bom is None:
        raise SystemExit("no BOM given and none found; pass one explicitly")
    nbad, lines = report(bom, refresh, verbose)
    print("\n".join(lines))
    return 1 if nbad else 0


def default_bom():
    """The BOM to check when none is named.

    `release/` if it exists -- that is the one being worked on.  Otherwise the
    last `release_*` archive, so that after a rev is sent off and its folder
    renamed, running this with no arguments still checks what went out.
    """
    def bom(d):
        p = os.path.join(HERE, d, "BOM_JLCPCB.csv")
        return p if os.path.exists(p) else None

    return bom(os.path.basename(BI.RELEASE)) or next(
        (b for d in sorted(os.listdir(HERE), reverse=True)
         if d.startswith("release_") for b in [bom(d)] if b), None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
