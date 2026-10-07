#!/usr/bin/env python3
"""
shapes.py -- parametric geometry for every antenna in this study, as plain dicts
that antsim.run() understands (see the antsim docstring for the convention:
mm, board in xy, top copper at z = h, ground edge at y = 0, antenna at y > 0).

  dipole_freespace   strip dipole in vacuum (validation against mom_dipole.py)
  dn007              TI DN007 / SWRU120 inverted-F, as dimensioned in its Table 1-1
  bat                the bat: 'ifa' (feet = feed + short, the bat hangs on the ground
                     edge) or 'dipole' (body split, balanced port across it)
  ghost              a teardrop planar monopole with a ghost's face and arms

Every character is built from simple overlapping polygons (the metal is their
union -- CSXCAD rasterises each one and PEC wins wherever any of them covers an
edge).  Holes (eyes) are made with a zero-width keyhole bridge so that one polygon
can carry them; pec_dump() in antsim.py shows that the Yee grid gets them right.
"""
import numpy as np

H_FR4 = 1.6
ER_FR4 = 4.4
TAND_FR4 = 0.02


# ----------------------------------------------------------------- 2D helpers
def rect(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def ellipse(cx, cy, rx, ry, n=48, a0=0.0, a1=2 * np.pi):
    t = np.linspace(a0, a1, n, endpoint=(a1 - a0) < 2 * np.pi - 1e-9)
    return np.c_[cx + rx * np.cos(t), cy + ry * np.sin(t)]


def bezier(p0, p1, p2, p3=None, n=16):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = map(np.asarray, (p0, p1, p2))
    if p3 is None:
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
    p3 = np.asarray(p3)
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def scallop(a, b, depth, n=10):
    """Concave arc from a to b, bulging by `depth` to the LEFT of a->b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    nrm = np.array([-d[1], d[0]]) / np.hypot(*d)
    t = np.linspace(0, 1, n)[:, None]
    return a + t * d + nrm * depth * 4 * t * (1 - t)


def mirror_x(P):
    P = np.asarray(P, float).copy()
    P[:, 0] *= -1
    return P[::-1]


def clip_x(P, xc, keep="right"):
    """Sutherland-Hodgman clip of polygon P to x >= xc ('right') or x <= xc ('left')."""
    P = np.asarray(P, float)
    inside = (lambda p: p[0] >= xc) if keep == "right" else (lambda p: p[0] <= xc)
    out = []
    for i in range(len(P)):
        cur, prv = P[i], P[i - 1]
        if inside(cur):
            if not inside(prv):
                t = (xc - prv[0]) / (cur[0] - prv[0])
                out.append(prv + t * (cur - prv))
            out.append(cur)
        elif inside(prv):
            t = (xc - prv[0]) / (cur[0] - prv[0])
            out.append(prv + t * (cur - prv))
    return np.array(out)


def signed_area(P):
    P = np.asarray(P, float)
    return 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])


def with_holes(outer, holes):
    """One polygon carrying holes via zero-width keyhole bridges (even-odd fill)."""
    outer = np.asarray(outer, float)
    if signed_area(outer) < 0:
        outer = outer[::-1]
    poly = [p for p in outer]
    for hole in holes:
        hole = np.asarray(hole, float)
        if signed_area(hole) > 0:
            hole = hole[::-1]
        P = np.array(poly)
        # bridge from the hole's highest point to the nearest outer vertex above it
        j = int(np.argmax(hole[:, 1]))
        hj = hole[j]
        d = np.hypot(P[:, 0] - hj[0], P[:, 1] - hj[1]) + 1e3 * (P[:, 1] < hj[1])
        i = int(np.argmin(d))
        hole_seq = [hole[(j + k) % len(hole)] for k in range(len(hole) + 1)]
        poly = poly[:i + 1] + hole_seq + poly[i:]
    return np.array(poly)


def port_y(xc, w, g):
    """y-directed lumped port at the ground edge: from y=0 up to the feed trace at y=g."""
    return dict(x0=xc - w / 2, x1=xc + w / 2, y0=0.0, y1=g, dir="y", R=50.0)


def standard_board(d, gnd_w=100.0, gnd_l=80.0, tab=None, h=H_FR4, er=ER_FR4, tand=TAND_FR4,
                   gnd_x0=None):
    """Ground plane gnd_w x gnd_l below the edge y = 0 (centred on x = 0 unless
    gnd_x0 is given), FR4 under it, and an FR4 tab (x0, x1, y_top) above it."""
    x0 = -gnd_w / 2 if gnd_x0 is None else gnd_x0
    d["ground"] = (x0, x0 + gnd_w, -gnd_l, 0.0)
    fr4 = [(x0, x0 + gnd_w, -gnd_l, 0.0)]
    if tab is not None:
        fr4.append((tab[0], tab[1], 0.0, tab[2]))
    d["fr4"] = fr4
    d["h"], d["er"], d["tand"] = h, er, tand
    return d


# ----------------------------------------------------------------- validation shapes
def dipole_freespace(L=58.0, w=1.0, gap=1.0):
    """Strip dipole along x in vacuum, centre gap with an x-directed port."""
    polys = [rect(-L / 2, -gap / 2, -w / 2, w / 2), rect(gap / 2, L / 2, -w / 2, w / 2)]
    port = dict(x0=-gap / 2, x1=gap / 2, y0=-w / 2, y1=w / 2, dir="x", R=50.0)
    return dict(name="dipole_fs", polys=polys, port=port, ground=None, fr4=[], h=0.0,
                er=None, tand=0.0, params=dict(L=L, w=w, gap=gap),
                lines_y=[-w / 2, w / 2])


def dn007(h=1.0, er=ER_FR4, tand=TAND_FR4, gnd_l=60.0, gnd_left=1.6, gnd_right=1.4,
          g=0.5, scale=1.0):
    """TI DN007 (SWRU120D) inverted-F, Table 1-1 dimensions, x = 0 at its left edge.

    Read off Figure 1-1: top bar L1 x W1 at y = H1..H1+W1; its left 9.18 mm
    (L1-L2) thickened down to H1+W1-H4; left leg L3 wide; inner cut-out L4 wide
    from the bottom bar (y = H2..H2+H3) to the thick part; feed block L7 x H6 sitting
    H5 above the bottom bar, joined to the thick part by a 1.20 mm stub (the L5 x H7
    notch beside it) and to the 0.46 mm feed trace (W2) by a 45-degree jog; the
    bottom bar touches the ground through two feet at its right end.  The feed
    trace stops g above the ground edge, where the port is."""
    H1, H2, H3, H4, H5, H6, H7, H8, H9 = 5.70, 0.74, 1.29, 2.21, 0.66, 1.21, 0.80, 1.80, 0.61
    W1, W2 = 1.21, 0.46
    L1, L2, L3, L4, L5, L6, L7, L8 = 25.58, 16.40, 2.18, 4.80, 1.00, 1.00, 3.20, 0.45
    top = H1 + W1                       # 6.91
    xa = L1 - L2                        # 9.18: where the free arm starts
    xc = L3 + L4                        # 6.98: right edge of the cut-out
    yb1 = H2 + H3                       # 2.03: top of bottom bar
    yfb0 = yb1 + H5                     # 2.69: feed block bottom
    yfb1 = yfb0 + H6                    # 3.90: feed block top
    xfb1 = xc + L7                      # 10.18: feed block / bottom bar right end
    xt0 = xfb1 + L8                     # 10.63: feed trace
    xt1 = xt0 + W2
    polys = [
        rect(0, L1, H1, top),                       # top bar / free arm
        rect(0, xa, top - H4, top),                 # thick left part
        rect(0, L3, H2, top),                       # left leg
        rect(0, xfb1, H2, yb1),                     # bottom bar
        rect(xc + L5, xa, yfb1, top - H4 + 0.01),   # stub thick-part -> feed block
        rect(xc, xfb1, yfb0, yfb1),                 # feed block
        rect(xc, xc + 1.28, -0.3, H2 + 0.01),       # foot 1 (to ground)
        rect(xfb1 - 1.08, xfb1, -0.3, H2 + 0.01),   # foot 2 (to ground)
        rect(xt0, xt1, g, 2.25),                    # feed trace
        # 45-degree jog from the trace up-left into the feed block's right end
        [[xt0, 2.25], [xt1, 2.25], [xt1, 2.25 + 0.30], [xfb1 - 0.01, 3.45],
         [xfb1 - 0.01, 2.85], [xt0, 2.25]],
    ]
    polys = [(np.asarray(p, float) * scale).tolist() for p in polys]
    port = port_y((xt0 + xt1) / 2 * scale, W2 * scale, g)
    d = dict(name="dn007", polys=polys, port=port,
             params=dict(h=h, er=er, gnd_l=gnd_l, gnd_left=gnd_left, gnd_right=gnd_right, scale=scale))
    gx0 = -gnd_left
    gw = L1 * scale + gnd_left + gnd_right
    standard_board(d, gnd_w=gw, gnd_l=gnd_l, tab=(gx0, gx0 + gw, top * scale + H9), h=h, er=er,
                   tand=tand, gnd_x0=gx0)
    d["lines_y"] = [0.0, g]
    return d


# ----------------------------------------------------------------- the bat
BAT_DEFAULT = dict(
    span=44.0,        # wing tip to wing tip
    yb=9.0,           # body centre above the ground edge
    bw=3.6, bh=5.0,   # body half-width, half-height
    hr=3.3,           # head radius
    ear_h=3.0, ear_w=1.5,
    wrist_x=0.40,     # wrist position as a fraction of the half span
    wrist_rise=4.0,   # wrist height above the body top
    tip_dy=1.5,       # wing tip height relative to the body centre
    n_sc=3,           # scallops along each trailing edge
    sc_depth=2.0,     # scallop depth
    trail_sag=1.0,    # how far the finger tips sag below the straight tip-root line
    root_lo=0.45,     # trailing-edge root height (fraction of bh below the centre)
    s=3.0,            # leg spacing (centre to centre): the IFA feed-short distance
    lw=1.0,           # leg width
    g=0.5,            # port gap at the feed foot
    gap=1.0,          # (dipole) feed gap through the body
    pw=1.5,           # (dipole) port height
    scale=1.0,        # uniform scale about the feed point (sensitivity)
    feed_side=1,      # +1: feed on the right foot, short on the left
    short=True,       # False: no shorting leg (plain top-loaded monopole)
    fw=2.0,           # (pm) feed stub width
    ytip=1.0,         # (pm) height of the tail point above the ground edge
)


def bat_outline(P):
    """The bat silhouette as overlapping polygons (no legs)."""
    span, yb, bw, bh, hr = P["span"], P["yb"], P["bw"], P["bh"], P["hr"]
    hs = span / 2
    body = ellipse(0, yb, bw, bh, 56)
    hc = (0, yb + bh + 0.35 * hr)
    head = ellipse(hc[0], hc[1], hr, hr * 0.92, 48)
    # ears: triangles rooted inside the head
    ex = 0.55 * hr
    ear_r = [[ex - P["ear_w"], hc[1] + 0.2 * hr], [ex + 0.6 * P["ear_w"], hc[1] + 0.1 * hr],
             [ex + 0.35 * P["ear_w"], hc[1] + 0.85 * hr + P["ear_h"]]]
    ear_l = mirror_x(ear_r)
    # right wing
    root_top = np.array([0.3 * bw, yb + 0.55 * bh])
    wrist = np.array([P["wrist_x"] * hs, yb + bh + P["wrist_rise"]])
    tip = np.array([hs, yb + P["tip_dy"]])
    root_bot = np.array([0.3 * bw, yb - P["root_lo"] * bh])
    lead1 = bezier(root_top, root_top + [0.35 * (wrist[0] - root_top[0]), 0.1 * bh],
                   wrist, n=14)
    lead2 = bezier(wrist, wrist + [0.45 * (tip[0] - wrist[0]), 0.6], tip, n=14)
    n = P["n_sc"]
    fingers = []
    for k in range(n + 1):
        t = k / n
        q = tip + t * (root_bot - tip)
        q[1] -= P["trail_sag"] * 4 * t * (1 - t)
        fingers.append(q)
    trail = []
    for k in range(n):
        # going tip -> root, the wing interior is to the RIGHT of travel (above);
        # scallop() bulges to the left, so pass a negative depth
        seg = scallop(fingers[k], fingers[k + 1], -P["sc_depth"] * (1 - 0.25 * k / max(n - 1, 1)), 10)
        trail.append(seg if k == 0 else seg[1:])
    wing_r = np.vstack([lead1, lead2[1:], np.vstack(trail)[1:]])
    wing_l = mirror_x(wing_r)
    return [body, head, np.array(ear_r), ear_l, wing_r, wing_l]


def _scale_about(polys, s, origin=(0.0, 0.0)):
    o = np.asarray(origin, float)
    return [((np.asarray(p, float) - o) * s + o) for p in polys]


def bat(kind="ifa", tab_w=None, tab_h=None, gnd_w=100.0, gnd_l=80.0, h=H_FR4, er=ER_FR4,
        tand=TAND_FR4, cover=None, **kw):
    P = dict(BAT_DEFAULT)
    P.update(kw)
    sc = P["scale"]
    polys = bat_outline(P)
    if kind == "ifa":
        s, lw, g = P["s"], P["lw"], P["g"]
        xf = P["feed_side"] * s / 2
        xs = -xf
        top = P["yb"] - 0.6 * P["bh"]           # legs end inside the body
        # scale the bat about the feed point, but keep the port gap fixed
        polys = _scale_about(polys, sc, (xf, 0.0))
        polys.append(np.array(rect(xf - lw / 2, xf + lw / 2, g, (top - 0) * sc + 0.0)))
        if P["short"]:
            xs_s = xf + (xs - xf) * sc
            polys.append(np.array(rect(xs_s - lw / 2, xs_s + lw / 2, -0.4, top * sc)))
        port = port_y(xf, lw, g)
        name = "bat_ifa"
    elif kind == "dipole":
        gp = P["gap"]
        polys = _scale_about(polys, sc, (0.0, P["yb"]))
        right = [clip_x(p, gp / 2, "right") for p in polys]
        left = [clip_x(p, -gp / 2, "left") for p in polys]
        polys = [p for p in right + left if len(p) >= 3]
        port = dict(x0=-gp / 2, x1=gp / 2, y0=P["yb"] - P["pw"] / 2, y1=P["yb"] + P["pw"] / 2,
                    dir="x", R=50.0)
        name = "bat_dipole"
    elif kind == "pm":
        # planar monopole: no legs.  The body tapers to a point (the tail / folded
        # feet) that sits on a short, wide feed stub at the ground edge, like the ghost.
        g, fw = P["g"], P["fw"]
        polys = _scale_about(polys, sc, (0.0, 0.0))
        yb, bh, bw = P["yb"] * sc, P["bh"] * sc, P["bw"] * sc
        ytip = P["ytip"]                       # where the tail point meets the stub
        # tail: a soft triangle from the lower body down to the stub
        tail = np.vstack([bezier([-0.8 * bw, yb - 0.55 * bh], [-0.35 * bw, yb - 0.95 * bh],
                                 [-0.5 * fw, ytip + 0.4], [-0.5 * fw, ytip], n=12),
                          [[0.5 * fw, ytip]],
                          bezier([0.5 * fw, ytip], [0.5 * fw, ytip + 0.4],
                                 [0.35 * bw, yb - 0.95 * bh], [0.8 * bw, yb - 0.55 * bh], n=12)[1:]])
        polys.append(tail)
        polys.append(np.array(rect(-fw / 2, fw / 2, g, ytip + 0.3)))
        port = port_y(0.0, fw, g)
        name = "bat_pm"
    elif kind in ("split_ifa", "legfed"):
        # the body is split down the middle (a dipole); the two legs are a twin-lead
        # (CPS) feeder down to the board edge.  split_ifa: the right foot is fed against
        # ground and the left foot is soldered to the ground pour -- single-ended, no balun.
        # legfed: an ideal balanced port across the two feet (a balun at the board edge).
        gp, s, lw, g = P["gap"], P["s"], P["lw"], P["g"]
        assert s - lw > gp, "legs must sit under their own half of the body"
        polys = _scale_about(polys, sc, (0.0, 0.0))
        right = [clip_x(p, gp / 2, "right") for p in polys]
        left = [clip_x(p, -gp / 2, "left") for p in polys]
        polys = [p for p in right + left if len(p) >= 3]
        top = (P["yb"] - 0.6 * P["bh"]) * sc
        xf, xs = s / 2, -s / 2
        if kind == "split_ifa":
            polys.append(np.array(rect(xf - lw / 2, xf + lw / 2, g, top)))
            polys.append(np.array(rect(xs - lw / 2, xs + lw / 2, -0.4, top)))
            port = port_y(xf, lw, g)
            name = "bat_split_ifa"
        else:
            # feet end g above the ground edge; a short x-directed port bridges them
            yp = g + 0.0
            polys.append(np.array(rect(xf - lw / 2, xf + lw / 2, yp, top)))
            polys.append(np.array(rect(xs - lw / 2, xs + lw / 2, yp, top)))
            port = dict(x0=xs + lw / 2, x1=xf - lw / 2, y0=yp, y1=yp + P["pw"], dir="x", R=50.0)
            name = "bat_legfed"
    else:
        raise ValueError(kind)
    polys = [np.round(np.asarray(p, float), 4).tolist() for p in polys]
    allp = np.vstack(polys)
    if tab_w is None:
        tab_w = (allp[:, 0].max() - allp[:, 0].min()) + 12.0
    if tab_h is None:
        tab_h = allp[:, 1].max() + 4.0
    d = dict(name=name, polys=polys, port=port, params=dict(kind=kind, **P))
    standard_board(d, gnd_w=gnd_w, gnd_l=gnd_l, tab=(-tab_w / 2, tab_w / 2, tab_h), h=h,
                   er=er, tand=tand)
    d["params"].update(tab_w=tab_w, tab_h=tab_h, gnd_w=gnd_w, gnd_l=gnd_l, h=h, er=er)
    d["lines_y"] = [0.0, port["y0"], port["y1"]] if kind != "dipole" else [0.0]
    if cover:
        c = dict(cover)
        c.setdefault("x0", -tab_w / 2 - 5)
        c.setdefault("x1", tab_w / 2 + 5)
        c.setdefault("y0", -20.0)
        c.setdefault("y1", tab_h + 5)
        d["cover"] = c
    return d


# ----------------------------------------------------------------- the ghost
GHOST_DEFAULT = dict(
    R=9.0,          # head radius (half the body width)
    yc=15.0,        # head centre above the ground edge
    tail_dx=1.5,    # sideways swish of the tail tip
    stub=1.2,       # straight feed stub under the tail
    fw=1.2,         # feed width
    g=0.5,          # port gap
    arm=2.2,        # arm bump size
    eyes=True,
    flat=0.55,      # how steeply the flanks leave the tail point (smaller = flatter bottom)
    scale=1.0,
)


def ghost(tab_w=None, tab_h=None, gnd_w=100.0, gnd_l=80.0, h=H_FR4, er=ER_FR4, tand=TAND_FR4,
          cover=None, **kw):
    P = dict(GHOST_DEFAULT)
    P.update(kw)
    R, yc, g, fw = P["R"], P["yc"], P["g"], P["fw"]
    ytip = g + P["stub"]
    # outline: head arc from the right side (angle -15 deg) over the top to the left,
    # then the left flank sweeps down to the tail tip, the right flank back up
    a0, a1 = np.deg2rad(-15), np.deg2rad(195)
    arc = ellipse(0, yc, R, R, 60, a0, a1)
    pl = arc[-1]
    pr = arc[0]
    tip = np.array([P["tail_dx"], ytip])
    fl = P["flat"]
    left = bezier(pl, pl + [0.15 * R, -0.55 * R], tip + [-0.9 * R, fl * R], tip, n=22)
    right = bezier(tip, tip + [0.55 * R, (0.25 / 0.55) * fl * R], pr + [0.10 * R, -0.60 * R], pr, n=22)
    outer = np.vstack([arc, left[1:], right[1:-1]])
    holes = []
    if P["eyes"]:
        holes = [ellipse(-0.36 * R, yc + 0.12 * R, 0.13 * R, 0.21 * R, 20),
                 ellipse(0.36 * R, yc + 0.12 * R, 0.13 * R, 0.21 * R, 20),
                 ellipse(0.0, yc - 0.33 * R, 0.17 * R, 0.12 * R, 20)]
    body = with_holes(outer, holes)
    arm_r = ellipse(R * 0.93, yc - 0.35 * R, P["arm"], 0.55 * P["arm"], 24)
    arm_l = ellipse(-R * 0.93, yc - 0.35 * R, P["arm"], 0.55 * P["arm"], 24)
    stub = rect(P["tail_dx"] - fw / 2, P["tail_dx"] + fw / 2, g, ytip + 0.8)
    polys = [body, arm_r, arm_l, np.array(stub)]
    sc = P["scale"]
    polys = _scale_about(polys, sc, (P["tail_dx"], 0.0))
    # keep the port gap fixed when scaling
    polys[-1] = np.array(rect(P["tail_dx"] - fw / 2, P["tail_dx"] + fw / 2, g, ytip * sc + 0.8))
    polys = [np.round(np.asarray(p, float), 4).tolist() for p in polys]
    allp = np.vstack(polys)
    if tab_w is None:
        tab_w = (allp[:, 0].max() - allp[:, 0].min()) + 12.0
    if tab_h is None:
        tab_h = allp[:, 1].max() + 4.0
    port = port_y(P["tail_dx"], fw, g)
    d = dict(name="ghost", polys=polys, port=port, params=dict(**P))
    standard_board(d, gnd_w=gnd_w, gnd_l=gnd_l, tab=(-tab_w / 2, tab_w / 2, tab_h), h=h, er=er,
                   tand=tand)
    d["params"].update(tab_w=tab_w, tab_h=tab_h, gnd_w=gnd_w, gnd_l=gnd_l, h=h, er=er)
    d["lines_y"] = [0.0, g]
    if cover:
        c = dict(cover)
        c.setdefault("x0", -tab_w / 2 - 5)
        c.setdefault("x1", tab_w / 2 + 5)
        c.setdefault("y0", -20.0)
        c.setdefault("y1", tab_h + 5)
        d["cover"] = c
    return d
