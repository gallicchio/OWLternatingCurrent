"""The panel: the frame round the six boards, the slots routed between them, the tabs that
hold them, the mouse bites that break them free, and the assembly line's fiducials and
tooling holes (JLCPCB's rules for a customer's panel, mfg/make_release.py features()).
Called by gen/board.py last, with every board in its final place (the tree turned).

Panel millimetres throughout: x right, y down, origin at the panel's top-left corner.

The tabs are found, not listed: on each side of each board, at a few places along it,
where the board's edge is straight across a tab's width and faces another board or the
frame across a gap no wider than MAX_GAP, and not where an edge must stay
clean (a connector's mouth, a lever, header pins, the bat's and the perch's notches, the
thread hole).  A tab is TAB_W wide; each end that meets a board carries a row of mouse
bites just outside that board's edge.  The slots are the frame's inside less the boards
and the tabs; their outlines, the frame's outer edge and the boards' own holes are
Edge.Cuts.
"""
import math
import pcbnew
import layout as L

TAB_W = 3.0             # mm across
BITE_D = 0.5            # mouse-bite holes (JLCPCB: 0.5-0.8 mm, 0.2-0.3 mm apart)
BITE_PITCH = 0.75
BITE_OUT = 0.15         # their centres this far outside the board's edge: the copper keeps
                        # 0.3 mm from the edge, so 0.2 mm from the holes
STRAIGHT = 0.4          # the edge may bow this much across a tab
MAX_GAP = 6.0           # the longest tab: the tokens' faces stand a few millimetres inside
                        # the 38 mm the panel gives each
FID_EDGE = 3.85         # fiducials' centres from the panel's edge (JLCPCB: at least 3.35)
TOOL_EDGE = 2.5         # tooling holes' centres from the panel's edge, in the rail's middle

# edges that must stay clean, per board, in the board's own frame: (side, lo, hi) where
# side is the board edge's outward direction before any turn and [lo, hi] the span along it
CLEAN = {
    "base": [("up", 86.0, 104.0),        # the USB-C's mouth
             ("up", 143.0, 161.0),       # the barrel jack's
             ("down", 164.0, 181.0)],    # the sound switch's lever
    "tree": [("up", 24.0, 52.0),         # the perch header's pins (and courtyard), out past the top edge
             ("down", 24.0, 52.0)],      # the base header's, past the foot
    "perch": [("left", -5.0, 5.0), ("right", -5.0, 5.0),    # the owl's notches
              ("up", -5.0, 5.0)],                           # the thread hole, 0.8 mm in
    "bat": [("up", -4.0, 4.0), ("down", -4.0, 4.0)],        # the cap's notches
}
DIRS = {"up": (0.0, -1.0), "down": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}


def to_panel(name, x, y):
    ox, oy = L.PANEL_OFFSETS[name]
    rot = L.PANEL_ROT.get(name, 0.0)
    if rot:
        a = math.radians(rot)
        x, y = x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)
    return (ox + x, oy + y)


def dir_to_panel(name, d):
    rot = L.PANEL_ROT.get(name, 0.0)
    if not rot:
        return d
    a = math.radians(rot)
    return (round(d[0] * math.cos(a) + d[1] * math.sin(a), 9), round(-d[0] * math.sin(a) + d[1] * math.cos(a), 9))


# ---- plain geometry -------------------------------------------------------------------
def ray_hits(o, d, poly):
    """Distances t >= 0 at which o + t d crosses the closed polygon's edges."""
    out = []
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - o[0]) * ey - (ay - o[1]) * ex) / den
        u = ((ax - o[0]) * d[1] - (ay - o[1]) * d[0]) / den
        if t >= 0 and 0 <= u <= 1:
            out.append(t)
    return out


def bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


# ---- finding the tabs -------------------------------------------------------------------
def find_tabs(edges, holes_of=None, courtyards=()):
    """edges: {name: outer outline in panel mm}.  Returns [(name, E, d, g, other)]: the
    board's edge point E, its outward direction d, the gap g to what lies beyond, and the
    other board's name (None: the frame).  No tab where its bites would land in one of
    `courtyards` (panel mm boxes: a part that overhangs the edge, a header's pins)."""
    inner = (L.RAIL, L.RAIL, L.PANEL_W - L.RAIL, L.PANEL_H - L.RAIL)
    tabs = []
    for name, poly in edges.items():
        x0, y0, x1, y1 = bbox(poly)
        for side in ("up", "down", "left", "right"):
            # this side in the board's own frame, and where it points on the panel
            d = dir_to_panel(name, DIRS[side])
            along = (abs(d[1]), abs(d[0]))              # the direction along the side
            lo_, hi_ = (x0, x1) if along[0] else (y0, y1)
            length = hi_ - lo_
            fracs = (0.5,) if length < 40 else ((0.2, 0.8) if length < 100 else (0.12, 0.5, 0.88))
            made = 0
            for f in fracs:
                for nudge in (0.0, 3.0, -3.0, 6.0, -6.0, 9.0, -9.0):
                    s = lo_ + f * length + nudge
                    if not (lo_ + TAB_W < s < hi_ - TAB_W):
                        continue
                    if _clean_conflict(name, side, s, d):
                        continue
                    t = _tab_at(name, poly, s, d, along, (x0, y0, x1, y1), edges, inner)
                    if t and _in_courtyard(t, along, courtyards):
                        continue
                    if t:
                        tabs.append(t)
                        made += 1
                        break
    # a tab between two boards is found from both: keep one
    out, seen = [], []
    for t in tabs:
        name, E, d, g, other = t
        F = (E[0] + d[0] * g, E[1] + d[1] * g)
        dup = any(math.hypot(E[0] - q[0], E[1] - q[1]) < 4.0 or math.hypot(F[0] - q[0], F[1] - q[1]) < 4.0
                  for q in seen)
        if dup:
            continue
        seen += [E, F]
        out.append(t)
    return out


def _in_courtyard(t, along, courtyards):
    """Whether a tab's bites (its width along the edge, both ends of its gap) fall in a
    part's courtyard.  courtyards: [(bounding box, contains(x, y))] in panel mm."""
    name, E, d, g, other = t
    pts = []
    for k in (-1.0, -0.5, 0.0, 0.5, 1.0):
        for f in (BITE_OUT, g - BITE_OUT):                 # the two rows of holes
            for df in (-BITE_D / 2 - 0.05, 0.0, BITE_D / 2 + 0.05):
                off = k * (TAB_W / 2 + BITE_D / 2)
                pts.append((E[0] + d[0] * (f + df) + along[0] * off, E[1] + d[1] * (f + df) + along[1] * off))
    for (x0, y0, x1, y1), contains in courtyards:
        for x, y in pts:
            if x0 <= x <= x1 and y0 <= y <= y1 and contains(x, y):
                return True
    return False


def _clean_conflict(name, side, s_panel, d):
    """Whether a tab at panel coordinate s_panel along this side of the board would land
    on an edge that must stay clean."""
    for side_, lo, hi in CLEAN.get(name, []):
        if side_ != side:
            continue
        # the span's ends on the panel, along the side
        if side in ("up", "down"):
            a = to_panel(name, lo, 0.0)
            b = to_panel(name, hi, 0.0)
        else:
            a = to_panel(name, 0.0, lo)
            b = to_panel(name, 0.0, hi)
        k = 0 if abs(d[1]) > 0.5 else 1           # the panel axis along the side
        lo_p, hi_p = sorted((a[k], b[k]))
        if lo_p - TAB_W / 2 - 0.5 <= s_panel <= hi_p + TAB_W / 2 + 0.5:
            return True
    return False


def _tab_at(name, poly, s, d, along, box, edges, inner):
    x0, y0, x1, y1 = box

    def edge_point(s_):
        # from outside the board's box, inward against d, to its edge
        if along[0]:
            o = (s_, (y0 - 1.0) if d[1] < 0 else (y1 + 1.0))
        else:
            o = ((x0 - 1.0) if d[0] < 0 else (x1 + 1.0), s_)
        din = (-d[0], -d[1])
        hits = ray_hits(o, din, poly)
        if not hits:
            return None
        t = min(hits)
        return (o[0] + din[0] * t, o[1] + din[1] * t), t
    c = edge_point(s)
    if c is None or c[1] - 1.0 > 0.8:                  # the edge must be at the box's side
        return None
    E = c[0]
    for ds in (-TAB_W / 2, TAB_W / 2):
        q = edge_point(s + ds)
        if q is None or abs(q[1] - c[1]) > STRAIGHT:
            return None
    # what lies beyond: another board's edge or the frame's inside
    best, other = None, None
    for n2, p2 in edges.items():
        if n2 == name:
            continue
        for ds in (-TAB_W / 2, 0.0, TAB_W / 2):
            o = (E[0] + along[0] * ds, E[1] + along[1] * ds)
            for t in ray_hits(o, d, p2):
                if best is None or t < best:
                    best, other = t, n2
    if d[0] > 0:
        tf = inner[2] - E[0]
    elif d[0] < 0:
        tf = E[0] - inner[0]
    elif d[1] > 0:
        tf = inner[3] - E[1]
    else:
        tf = E[1] - inner[1]
    if best is None or tf < best:
        best, other = tf, None
    if best > MAX_GAP:
        return None
    if other is not None:
        # the other board's edge must be straight across the tab too
        for ds in (-TAB_W / 2, TAB_W / 2):
            o = (E[0] + along[0] * ds, E[1] + along[1] * ds)
            hits = ray_hits(o, d, edges[other])
            if not hits or abs(min(hits) - best) > STRAIGHT:
                return None
    return (name, E, d, best, other)


# ---- drawing --------------------------------------------------------------------------
def build(board, PP, mm, edges, holes, load_fp, seed):
    """Draw the panel: Edge.Cuts, tabs' mouse bites, fiducials, tooling holes.
    edges: {name: outer outline}; holes: [outline] (the boards' own cut-outs)."""
    o = PP(0.0, 0.0)
    ox, oy = pcbnew.ToMM(o.x), pcbnew.ToMM(o.y)
    yards, keep = [], []
    for fp in board.GetFootprints():
        fp.BuildCourtyardCaches()
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            cy = pcbnew.SHAPE_POLY_SET(fp.GetCourtyard(layer))     # (a copy, kept alive)
            if cy.OutlineCount():
                keep.append(cy)
                bb = cy.BBox()
                a, b = bb.GetOrigin(), bb.GetEnd()
                box = (pcbnew.ToMM(min(a.x, b.x)) - ox, pcbnew.ToMM(min(a.y, b.y)) - oy,
                       pcbnew.ToMM(max(a.x, b.x)) - ox, pcbnew.ToMM(max(a.y, b.y)) - oy)
                yards.append((box, lambda x, y, cy=cy: cy.Contains(PP(x, y))))
    tabs = find_tabs(edges, courtyards=yards)

    def sps(polys):
        ps = pcbnew.SHAPE_POLY_SET()
        for pts in polys:
            ps.NewOutline()
            for x, y in pts:
                v = PP(x, y)
                ps.Append(v.x, v.y)
        return ps
    # the material inside the frame: the boards and the tabs
    rects = []
    for name, E, d, g, other in tabs:
        along = (abs(d[1]), abs(d[0]))
        a = (E[0] - d[0] * 0.6, E[1] - d[1] * 0.6)
        b = (E[0] + d[0] * (g + 0.6), E[1] + d[1] * (g + 0.6))
        w = TAB_W / 2
        rects.append([(a[0] - along[0] * w, a[1] - along[1] * w), (b[0] - along[0] * w, b[1] - along[1] * w),
                      (b[0] + along[0] * w, b[1] + along[1] * w), (a[0] + along[0] * w, a[1] + along[1] * w)])
    material = sps(list(edges.values()))
    material.BooleanAdd(sps(rects))
    inner = sps([[(L.RAIL, L.RAIL), (L.PANEL_W - L.RAIL, L.RAIL), (L.PANEL_W - L.RAIL, L.PANEL_H - L.RAIL),
                  (L.RAIL, L.PANEL_H - L.RAIL)]])
    inner.BooleanSubtract(material)

    def edge_chain(chain):
        n = chain.PointCount()
        for i in range(n):
            a, b = chain.CPoint(i), chain.CPoint((i + 1) % n)
            if a.x == b.x and a.y == b.y:
                continue
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(a); s.SetEnd(b)
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
            board.Add(s)
    seed("panel:edges")
    for i in range(inner.OutlineCount()):
        edge_chain(inner.Outline(i))
        for h in range(inner.HoleCount(i)):
            edge_chain(inner.Hole(i, h))
    # (each polygon set kept in a name while its outline is read: Outline() is a view
    # into the set, and a temporary set is freed under it)
    frame = sps([_rounded(0, 0, L.PANEL_W, L.PANEL_H, 2.0)])
    edge_chain(frame.Outline(0))
    for pts in holes:
        hole = sps([pts])
        edge_chain(hole.Outline(0))
    # mouse bites: a row across each tab at each end that meets a board
    seed("panel:bites")
    k = 0
    for name, E, d, g, other in tabs:
        along = (abs(d[1]), abs(d[0]))
        ends = [(E, 1.0)] + ([((E[0] + d[0] * g, E[1] + d[1] * g), -1.0)] if other else [])
        nb = int(TAB_W / BITE_PITCH)
        for (px, py), sgn in ends:
            cx, cy = px + d[0] * BITE_OUT * sgn, py + d[1] * BITE_OUT * sgn
            for j in range(nb):
                off = (j - (nb - 1) / 2) * BITE_PITCH
                k += 1
                fp = load_fp("OWL:MouseBite_NPTH_0.5mm")
                fp.SetReference("MB%d" % k)
                fp.Reference().SetVisible(False)
                fp.SetPosition(PP(cx + along[0] * off, cy + along[1] * off))
                board.Add(fp)
    # the assembly line's marks on the rails: three fiducials (not symmetric, so the
    # machine sees which way round the panel is) and four tooling holes
    seed("panel:marks")
    W, H = L.PANEL_W, L.PANEL_H
    for i, (x, y) in enumerate(((12.0, FID_EDGE), (W - 12.0, FID_EDGE), (12.0, H - FID_EDGE))):
        fp = load_fp("OWL:Fiducial_1mm_Mask2mm")
        fp.SetReference("FID%d" % (i + 1))
        fp.Reference().SetVisible(False)
        fp.SetBoardOnly(True)
        fp.SetExcludedFromPosFiles(True)
        fp.SetExcludedFromBOM(True)
        fp.SetPosition(PP(x, y))
        board.Add(fp)
    for i, (x, y) in enumerate(((5.0, TOOL_EDGE), (W - 5.0, TOOL_EDGE), (5.0, H - TOOL_EDGE),
                                (W - 5.0, H - TOOL_EDGE))):
        fp = load_fp("OWL:Tooling_NPTH_2mm")
        fp.SetReference("TH%d" % (i + 1))
        fp.Reference().SetVisible(False)
        fp.SetPosition(PP(x, y))
        board.Add(fp)
    per = {}
    for name, E, d, g, other in tabs:
        per[name] = per.get(name, 0) + 1
        if other:
            per[other] = per.get(other, 0) + 1
    return tabs, k, per


def _rounded(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts
