#!/usr/bin/env python3
"""Re-measure the printed parts' meshes against gen/mech.py:  python3 print/check.py

Every number here is measured from the generated geometry (ray casts and per-layer
slices of out/owl.stl, out/bat_cap.stl, out/foot.stl and out/plate.stl), then compared
with gen/mech.py.  design.py is used only for printer facts (layer height, the stand-in
gap, PLA's modulus and density, the strain allowed), never for where things are.
Exits non-zero if anything is out of tolerance.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D          # noqa: E402  printer facts only
import mech as M            # noqa: E402
import meshtools as mt      # noqa: E402

OUT = os.path.join(HERE, "out")
EPS = 1e-3
OPEN_BRIDGE_REACH = 5.5   # the roof over an empty pocket is a ~10.5 mm bridge, which PLA
                          # spans well; its middle is ~5.3 mm from any wall


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, name, value, ok, want, unit="mm", fmt="%.2f"):
        v = fmt % value if isinstance(value, (int, float, np.floating)) else str(value)
        self.rows.append((bool(ok), name, v + (" " + unit if unit else ""), want))
        return value

    def near(self, name, value, target, tol, unit="mm", fmt="%.2f"):
        return self.add(name, value, abs(value - target) <= tol + 1e-9,
                        ("= " + fmt + " +- %g") % (target, tol), unit, fmt)

    def within(self, name, value, lo, hi, unit="mm", fmt="%.2f"):
        want = ("%s .. %s" % (fmt % lo if lo is not None else "", fmt % hi if hi is not None else "")).strip()
        ok = (lo is None or value >= lo - 1e-9) and (hi is None or value <= hi + 1e-9)
        return self.add(name, value, ok, want, unit, fmt)

    @property
    def ok(self):
        return all(r[0] for r in self.rows)


# ------------------------------------------------------------------ helpers
def shells(tris):
    """(solid shells sorted by volume, sealed voids)"""
    sh = mt.components(tris)
    solids = sorted([s for s in sh if mt.volume(s) > 0], key=mt.volume, reverse=True)
    voids = [s for s in sh if mt.volume(s) < 0]
    return solids, voids


def first_hit(tris, origin, direction):
    h = mt.ray_hits(tris, origin, direction)
    return h[0] if len(h) else None


def along(tris, origin, direction):
    """Solid intervals along a ray, as coordinates along its axis."""
    o = np.asarray(origin, float)
    d = np.asarray(direction, float)
    ax = int(np.argmax(np.abs(d)))
    return [(o[ax] + d[ax] * a, o[ax] + d[ax] * b) for a, b in mt.solid_intervals(tris, o, d)]


def roof(body, c, d, top):
    """Thinnest plastic above a pocket of diameter d centred at c with its top at `top`."""
    t = []
    for r in np.linspace(0, d / 2 - 0.05, 12):
        for a in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            h = first_hit(body, (c[0] + r * np.cos(a), c[1] + r * np.sin(a), top + 0.01), (0, 0, 1))
            t.append((h or 0) + 0.01)
    return min(t)


# ------------------------------------------------------------------ the owl
def check_owl(C, tris):
    solids, voids = shells(tris)
    C.add("owl: closed, one body + its stand-in, no sealed pocket",
          "%d solid, %d void" % (len(solids), len(voids)),
          mt.is_closed(tris) and len(solids) == 2 and not voids, "2 solid, 0 void", "")
    body = solids[0] if mt.bbox(solids[0])[1][2] > mt.bbox(solids[1])[1][2] else solids[1]
    standin = solids[1] if body is solids[0] else solids[0]
    lo, hi = mt.bbox(body)
    C.near("owl: stands on the bed (lowest point)", lo[2], 0.0, EPS)
    zt = hi[2]
    # the board's place: arms' inner faces and lips, found by rays out from the middle
    xs_in, xs_tip = {}, {}
    # base: first surface above a point on the base rim
    rim_x = None
    for x in np.arange(13.9, 9.0, -0.1):
        h = first_hit(body, (x, 0, -1), (0, 0, 1))
        if h is not None and h - 1 < 6:
            rim_x, z_base = x, h - 1
            break
    C.add("owl: base found (rim at x = %.1f)" % (rim_x or 0), z_base if rim_x else -1, rim_x is not None, "", "")
    # catch: top of the lip, under where the board will be
    xn = M.PERCH_W / 2 - M.OWL_NOTCH_D
    iv = along(body, (xn - 0.3, 0, zt + 5), (0, 0, -1))     # (top, bottom) pairs going down
    z_catch = max(a for a, b in iv if a < z_base - 0.5)
    slot = z_base - z_catch
    C.within("owl: lip catch to base (the board's thickness %.1f)" % M.PCB_T, slot, M.PCB_T + D.LAYER,
             M.PCB_T + 3 * D.LAYER)
    z_mid = z_base - M.PCB_T / 2                      # inside the board's thickness
    for s in (-1, 1):
        iv = along(body, (0, 0, z_mid), (s, 0, 0))
        xs_in[s] = min(abs(a) for a, b in iv if abs(a) > 5)
        iv = along(body, (0, 0, z_catch - 0.05), (s, 0, 0))
        xs_tip[s] = min(abs(a) for a, b in iv if abs(a) > 5)
    # the arms' inner faces sit at +a and -b; the notch bottoms are at +-xn about the coil
    centre_x = 0.5 * (xs_in[1] - xs_in[-1])
    for s in (-1, 1):
        side = "+x" if s > 0 else "-x"
        C.within("owl %s: arm's inner face past the notch bottom (%.1f)" % (side, xn), xs_in[s] - xn, 0.0, 0.15)
        C.near("owl %s: hook reaches under the board (OWL_HOOK)" % side, xn - xs_tip[s], M.OWL_HOOK, 0.05)
    # arm's width in y, in the notch
    xa = xs_in[1] + 0.75                         # inside the plate, past its corner chamfers
    iv = along(body, (xa, -20, z_mid), (0, 1, 0))
    y0, y1 = iv[0]
    ny0, ny1 = M.OWL_NOTCH_Y
    C.within("owl: arm fits the notch (y %.2f..%.2f in %.1f..%.1f)" % (y0, y1, ny0, ny1),
             min(y0 - ny0, ny1 - y1), 0.1, 0.5)
    coil_y = 0.5 * (y0 + y1) - 0.5 * (ny0 + ny1)      # coil centre from the notch centre
    C.near("owl: arms centred on the coil (x)", centre_x, 0.0, 0.05)
    C.near("owl: arms centred on the coil (y)", coil_y, 0.0, 0.05)
    # free arm: from the lip to where it joins the body (top of the slit)
    iv = along(body, (xs_in[1] - 0.25, 0, -1), (0, 0, 1))
    z_root = [a for a, b in iv if a > z_base][0]
    iv = along(body, (-50, 0, z_root - 2), (1, 0, 0))
    t_arm = [b - a for a, b in iv if a > 10][0]
    L = z_root - (z_catch - 0.5)
    delta = (xs_in[1] - xs_tip[1]) + 0.05
    strain_owl = 1.5 * delta * t_arm / L ** 2
    C.within("owl: wing-arm snap strain (%.1f thick, %.1f long, lip out %.2f)" % (t_arm, L, delta),
             100 * strain_owl, None, 100 * D.STRAIN_OK, "%", "%.2f")
    # the stand-in clears the lips
    slo, shi = mt.bbox(standin)
    C.within("owl: stand-in clear of the hooks (sideways)", min(xs_tip.values()) - shi[0], D.GAP_XY - 0.01, None)
    C.near("owl: stand-in top one layer under the base", z_base - shi[2], D.GAP_Z, 0.01)
    C.within("owl: height above the perch (tufts)", zt - z_base, 25, 31)
    C.within("owl: width incl. wings and talons", hi[0] - lo[0], None, M.PERCH_W + 4.5)
    return dict(z_base=z_base, slot=slot, body=body,
                strain=strain_owl, mass_g=mt.volume(body) / 1000 * D.PLA_DENSITY, height=zt - z_base,
                standin_g=mt.volume(standin) / 1000 * D.PLA_DENSITY)


# ------------------------------------------------------------------ the cap
def check_cap(C, tris):
    solids, voids = shells(tris)
    C.add("cap: closed, one body + its pedestal, no sealed pocket",
          "%d solid, %d void" % (len(solids), len(voids)),
          mt.is_closed(tris) and len(solids) == 2 and not voids, "2 solid, 0 void", "")
    body = solids[0] if mt.bbox(solids[0])[1][2] > mt.bbox(solids[1])[1][2] else solids[1]
    ped = solids[1] if body is solids[0] else solids[0]
    c = (0.0, 0.0)            # the pocket's axis is the cap's frame origin (x, y kept in print)
    z_board = first_hit(body, (M.POCKET_D / 2 + 0.3, 0, -1), (0, 0, 1)) - 1    # the dome's foot
    # lips: catch height, tips, drops (rays along y from the magnet's axis)
    hy = c[1] + M.BAT_HEAD_Y + 0.3
    iv = along(body, (c[0], hy, 60), (0, 0, -1))           # (top, bottom) pairs going down
    z_catch = max(a for a, b in iv if a < z_board - 0.5)
    C.near("cap: lip catch to floor = board thickness (snug)", z_board - z_catch, M.PCB_T, 0.05)
    tips, drops = {}, {}
    for s, name in ((-1, "head"), (1, "tail")):
        iv = along(body, (c[0], c[1], z_catch - 0.05), (0, s, 0))
        tips[name] = min(abs(a - c[1]) for a, b in iv if abs(a - c[1]) > 6) * s
        iv = along(body, (c[0], c[1], z_board - M.PCB_T / 2), (0, s, 0))
        drops[name] = min(abs(a - c[1]) for a, b in iv if abs(a - c[1]) > 6) * s
    C.near("cap: head hook reaches CAP_HOOK under the head edge", tips["head"] - M.BAT_HEAD_Y, M.CAP_HOOK, 0.05)
    C.near("cap: tail hook reaches CAP_HOOK under the tail edge", M.BAT_TAIL_Y - tips["tail"], M.CAP_HOOK, 0.05)
    C.within("cap: drops clear the head edge (BAT_HEAD_Y %g)" % M.BAT_HEAD_Y, M.BAT_HEAD_Y - drops["head"], 0.0, 0.2)
    C.within("cap: drops clear the tail edge (BAT_TAIL_Y %g)" % M.BAT_TAIL_Y, drops["tail"] - M.BAT_TAIL_Y, 0.0, 0.2)
    # arm: width, thickness, height, length (from the dome to the drop)
    ya = c[1] + drops["head"] + 2.0                  # along the head arm, near its drop
    iv = along(body, (c[0], ya, 60), (0, 0, -1))
    a1, a0 = min(iv)                                   # the arm: lowest solid run here
    iv2 = along(body, (c[0] - 10, ya, (a0 + a1) / 2), (1, 0, 0))
    w = iv2[0][1] - iv2[0][0]
    C.near("cap: arm width (CAP_ARM_W)", w, M.CAP_ARM_W, 0.05)
    # dome's widest radius at the arm's height: where the arm leaves the dome
    xb = M.CAP_ARM_W / 2 + 0.2                   # just beside the arm, from outside
    iv3 = along(body, (c[0] + xb, c[1] - 30, (a0 + a1) / 2), (0, 1, 0))
    r_dome = math.hypot(xb, iv3[0][0] - c[1])     # where the arm leaves the dome
    t_a = a1 - a0
    iv4 = along(body, (c[0], c[1] - 20, z_board - M.PCB_T / 2), (0, 1, 0))
    t_d = iv4[0][1] - iv4[0][0]
    Ld = (a0 + a1) / 2 - (z_catch - 0.5)
    w_ = M.CAP_ARM_W
    Ia, Id = w_ * t_a ** 3 / 12, w_ * t_d ** 3 / 12
    worst = 0
    for name in ("head", "tail"):
        La = abs(drops[name]) - r_dome
        delta = abs(abs(drops[name]) - abs(tips[name])) + 0.05   # lip clears the edge
        comp = Ld * Ld * La / (D.PLA_E * Ia) + Ld ** 3 / (3 * D.PLA_E * Id)
        F = delta / comp
        ea = F * Ld * (t_a / 2) / (D.PLA_E * Ia)
        worst = max(worst, ea)
        C.within("cap %s: snap strain (arm %.1f long, lever %.1f, lip out %.2f)" % (name, La, Ld, delta),
                 100 * ea, None, 100 * D.STRAIN_OK, "%", "%.2f")
    mass = mt.volume(body) / 1000 * D.PLA_DENSITY
    C.within("cap: mass of plastic (100 %% solid, PLA %.2f g/cm3)" % D.PLA_DENSITY, mass, None, 1.0, "g", "%.2f")
    plo, phi = mt.bbox(ped)
    C.near("cap: pedestal top one layer under the floor", z_board - phi[2], D.GAP_Z, 0.01)
    return dict(z_board=z_board, body=body, mass_g=mass, strain=worst,
                slot=z_board - z_catch, tips=tips, drops=drops)


# ------------------------------------------------------------------ a foot
def check_foot(C, tris):
    solids, voids = shells(tris)
    C.add("foot: closed, one body", "%d solid" % len(solids), mt.is_closed(tris) and len(solids) == 1 and not voids,
          "1 solid", "")
    lo, hi = mt.bbox(tris)
    C.near("foot: stands on the bed", lo[2], 0.0, EPS)
    z_top = 60 - first_hit(tris, (4.0, 0, 60), (0, 0, -1))
    C.near("foot: board rests at FOOT_HEIGHT", z_top, M.FOOT_HEIGHT, 0.02)
    iv = along(tris, (-10, 0, z_top + M.PCB_T / 2), (1, 0, 0))
    shaft = iv[-1][1] - iv[0][0]
    C.within("foot: peg passes the hole (FOOT_HOLE_D %.1f)" % M.FOOT_HOLE_D, M.FOOT_HOLE_D - shaft, 0.1, 0.4)
    # the barb: widest just above the board's top face
    best = (0, 0)
    for z in np.arange(z_top + M.PCB_T, z_top + M.PCB_T + 1.0, 0.02):
        iv = along(tris, (-10, 0, z), (1, 0, 0))
        if iv:
            wdt = iv[-1][1] - iv[0][0]
            if wdt > best[0] + 1e-6:
                best = (wdt, z)
    catch = (best[0] - M.FOOT_HOLE_D) / 2
    C.within("foot: barb catches the board's top face", catch, 0.1, 0.4)
    C.within("foot: barb's catch sits above the board", best[1] - (z_top + M.PCB_T), 0.0, 0.2)
    iv = along(tris, (-10, 0, z_top + 1.0), (1, 0, 0))
    slit = iv[1][0] - iv[0][1] if len(iv) > 1 else 0
    C.within("foot: slit lets the prongs close by twice the catch", slit, 2 * catch + 0.2, None)
    z_moat = 60 - first_hit(tris, (shaft / 2 + 0.4, 0, 60), (0, 0, -1))
    L = best[1] - z_moat
    h = shaft / 2 - slit / 2
    strain = 3 * (catch + 0.05) * 0.59 * h / L ** 2       # D-section: outer fibre ~0.59 h
    C.within("foot: prong snap strain (prongs %.1f long)" % L, 100 * strain, None, 100 * D.STRAIN_OK, "%", "%.2f")
    return dict(strain=strain, catch=catch, height=z_top, mass_g=mt.volume(tris) / 1000 * D.PLA_DENSITY)


# ------------------------------------------------------------------ printability
def overhangs(tris, name, magnet_top=None, res=0.05):
    """Slice like a slicer (every layer at its mid-height) and look at what each layer
    lays down over air.  Returns findings: floating islands (fail), and the farthest
    any unsupported spot lies from material in the layer below (a 45 deg slope is one
    layer height; a bridge of span S reaches S/2).  Spots over a stand-in one layer
    below (the designed breakaway gap) and over a magnet's pocket are supported."""
    from scipy import ndimage
    lo, hi = mt.bbox(tris)
    xs = np.arange(lo[0] - 0.2, hi[0] + 0.2, res)
    ys = np.arange(lo[1] - 0.2, hi[1] + 0.2, res)
    n = int(round(hi[2] / D.LAYER))
    prev2 = prev = None
    worst = []
    floating = []
    stand_in = 0
    for k in range(n):
        z = (k + 0.5) * D.LAYER
        g = mt.raster(mt.plane_segments(tris, 2, z), xs, ys)
        if k > 0:
            new = g & ~prev
            if magnet_top is not None:
                for (cx, cy, ztop) in magnet_top:
                    if abs(z - D.LAYER / 2 - ztop) < 1e-3:     # first layer over a pocket
                        X, Y = np.meshgrid(xs, ys)
                        new &= (X - cx) ** 2 + (Y - cy) ** 2 > (M.MAGNET_D / 2) ** 2
            if prev2 is not None:
                over_standin = new & prev2
                stand_in += int(over_standin.sum())
                new &= ~prev2
            if new.any():
                dist = ndimage.distance_transform_edt(~prev) * res
                lab, nl = ndimage.label(g)
                for i in range(1, nl + 1):
                    isl = lab == i
                    if not (isl & prev).any() and not (prev2 is not None and (isl & prev2).any()):
                        floating.append((z, float(xs[np.argmax(isl.any(axis=0))]), float(isl.sum() * res * res)))
                reach = dist[new]
                j = int(np.argmax(reach))
                yy, xx = np.nonzero(new)
                worst.append((float(reach[j]), z, float(xs[xx[j]]), float(ys[yy[j]])))
        prev2, prev = prev, g
    worst.sort(reverse=True)
    return dict(name=name, floating=floating, worst=worst[:6], stand_in_cells=stand_in,
                slope_layers=sum(1 for w in worst if w[0] > D.LAYER * math.tan(math.radians(50)) + res))


# ------------------------------------------------------------------ the plate
def check_plate(C):
    plate = mt.read_stl(os.path.join(OUT, "plate.stl"))
    parts = [mt.read_stl(os.path.join(OUT, f)) for f in ("owl.stl", "bat_cap.stl", "foot.stl", "foot.stl",
                                                         "foot.stl", "foot.stl")]
    want = sum(len(shells(t)[0]) for t in parts)
    psol, pvoid = shells(plate)
    C.add("plate.stl: owl, bat cap, four feet and two stand-ins; no sealed pocket",
          "%d solid, %d void" % (len(psol), len(pvoid)),
          len(psol) == want and not pvoid and len(plate) == sum(len(t) for t in parts),
          "%d solid, 0 void" % want, "")
    lo, hi = mt.bbox(plate)
    C.within("plate: footprint x", hi[0] - lo[0], None, D.BED[0] - 20)
    C.within("plate: footprint y", hi[1] - lo[1], None, D.BED[1] - 20)
    C.near("plate: on the bed", lo[2], 0.0, EPS)
    return {}


# ------------------------------------------------------------------ the magnets' pockets
def z_base_of(body):
    """The owl's base: the first surface above a point on its rim (as in check_owl)."""
    for x in np.arange(13.9, 9.0, -0.1):
        h = first_hit(body, (x, 0, -1), (0, 0, 1))
        if h is not None and h - 1 < 6:
            return h - 1
    return None


def check_pockets(C, owl_info, cap_info):
    """The owl's pocket opens out of its back (+y) as a slot the magnet slides along; the
    cap's pocket has no floor.  Each magnet must end up where mech.py puts it, and must
    be able to get in."""
    # --- the owl
    body = owl_info["body"]
    z_base = owl_info["z_base"]
    # the channel: heights where a ray from behind the owl runs in past the coil's axis
    front = {}
    for z in np.arange(z_base + 5, z_base + 25, D.LAYER / 4):
        h = first_hit(body, (0, 40, z), (0, -1, 0))
        if h is not None and 40 - h < -2:
            front[round(float(z), 4)] = 40 - h
    zs = sorted(front)
    zm = (zs[0] + zs[-1]) / 2
    y_front = front[min(zs, key=lambda z: abs(z - zm))]
    # floor and roof exactly, by rays down and up from the middle of the pocket
    yc = y_front + M.POCKET_D / 2
    floor = zm - first_hit(body, (0, yc, zm), (0, 0, -1))
    top = zm + first_hit(body, (0, yc, zm), (0, 0, 1))
    C.add("owl: one channel from the back to the pocket",
          "z %.2f..%.2f" % (floor - z_base, top - z_base),
          all(abs(b - a - D.LAYER / 4) < 1e-6 for a, b in zip(zs, zs[1:])), "unbroken", "")
    C.within("owl: channel height (magnet %.1f)" % M.MAGNET_T, top - floor, M.MAGNET_T + 0.15,   # snug since 2026-11-09 (Jason)
             M.MAGNET_T + 1.0)
    lift = floor - z_base + M.COPPER_TO_SURFACE
    C.near("owl: MAGNET'S BOTTOM ABOVE THE PERCH'S TOP COPPER (OWL_LIFT)", lift, M.OWL_LIFT, 0.1)
    # the channel's width all the way out, and its middle
    narrow, mid = 99.0, []
    for y in np.arange(y_front + 0.5, 15.0, 0.25):
        iv = along(body, (-30, y, zm), (1, 0, 0))
        gaps = [(b0, a1) for (a0, b0), (a1, b1) in zip(iv, iv[1:]) if b0 < 0 < a1]
        if not gaps and y > 8:
            break                                   # out through the back
        g = gaps[0] if gaps else (0, 0)
        if y > y_front + M.MAGNET_D / 2:            # past the round end: the straight slot
            narrow = min(narrow, g[1] - g[0])
            mid.append((g[0] + g[1]) / 2)
    C.within("owl: slot width all the way out (magnet %.0f)" % M.MAGNET_D, narrow, M.MAGNET_D + 0.2,   # snug since 2026-11-09 (Jason)
             M.MAGNET_D + 0.8)
    C.near("owl: slot centred on the coil (x)", float(np.mean(mid)), 0.0, 0.05)
    C.near("owl: seated magnet centred on the coil (y)", y_front + M.MAGNET_D / 2, 0.0, 0.2)
    back = first_hit(body, (0, 40, top + 1.0), (0, -1, 0))
    C.add("owl: the slot opens out of the owl's back", "yes",
          first_hit(body, (0, y_front + 1, zm), (0, 1, 0)) is None, "", "")
    plug = 40 - back - (y_front + M.MAGNET_D)
    C.within("owl: epoxy plug behind the magnet", plug, 3.0, None)
    C.within("owl: thinnest plastic over the pocket", roof(body, (0, y_front + M.POCKET_D / 2), M.POCKET_D,
                                                                    top), 1.0, None)
    # --- the cap
    cbody = cap_info["body"]
    z_board = cap_info["z_board"]
    z_roof = first_hit(cbody, (0, 0, -1), (0, 0, 1)) - 1
    C.add("cap: pocket open to the bat (no floor)", "yes", z_roof > z_board + M.MAGNET_T, "", "")
    C.within("cap: MAGNET'S TOP ABOVE THE BAT, against the roof", z_roof - z_board,
             M.MAGNET_T + 0.1 + D.LAYER, M.POCKET_T + 3 * D.LAYER)
    dia = 2 * min(first_hit(cbody, (0, 0, z_board + 1.0), (np.cos(t), np.sin(t), 0))
                  for t in np.linspace(0, 2 * np.pi, 180, endpoint=False))
    C.near("cap: pocket diameter (flat to flat)", dia, M.POCKET_D, 0.02)
    C.within("cap: thinnest plastic over the magnet", roof(cbody, (0, 0), M.POCKET_D, z_roof), 0.8, None)
    return dict(lift=lift, gap=top - floor, slot=narrow, plug=plug, magnet_top=z_roof - z_board,
                y_front=y_front, pocket_floor=floor, pocket_top=top)


def run(verbose=True):
    C = Checks()
    owl_t = mt.read_stl(os.path.join(OUT, "owl.stl"))
    cap_t = mt.read_stl(os.path.join(OUT, "bat_cap.stl"))
    foot_t = mt.read_stl(os.path.join(OUT, "foot.stl"))
    owl = check_owl(C, owl_t)
    cap = check_cap(C, cap_t)
    foot = check_foot(C, foot_t)
    plate = check_plate(C)
    opn = check_pockets(C, owl, cap)
    oh = []
    # the roofs over the empty pockets are bridges ~10.4 mm across: halfway is ~5.2 mm out
    for t, name, reach in ((owl_t, "owl", OPEN_BRIDGE_REACH), (cap_t, "bat cap", OPEN_BRIDGE_REACH),
                           (foot_t, "foot", 5.0)):
        r = overhangs(t, name)
        oh.append(r)
        C.add("%s: no floating islands when sliced" % name, len(r["floating"]), not r["floating"], "0", "", "%d")
        far = r["worst"][0][0] if r["worst"] else 0.0
        C.within("%s: farthest unsupported spot from the layer below" % name, far, None, reach)
    # summary for the README and the pictures
    hk = D.cap_hook_snap()
    s = [
        "magnet bottom above the perch's top copper  %.2f mm  (OWL_LIFT %.1f; on the 0.2 mm layer grid)"
        % (opn["lift"], M.OWL_LIFT),
        "no pause: both magnets go in after printing, glued with epoxy (magnet %g x %g)" % (M.MAGNET_D, M.MAGNET_T),
        "owl  slot %.2f x %.1f out through its back; %.1f mm of epoxy behind the magnet"
        % (opn["slot"], opn["gap"], opn["plug"]),
        "cap  no floor; pocket %.2f across, magnet top %.1f mm above the bat, against the roof"
        % (M.POCKET_D, opn["magnet_top"]),
        "owl hooks  %.1f mm under the perch, slot %.1f for a %.1f board" % (M.OWL_HOOK, owl["slot"], M.PCB_T),
        "cap hooks  %.1f under the head (y %g) and tail (y %g), slot %.2f" % (M.CAP_HOOK, M.BAT_HEAD_Y, M.BAT_TAIL_Y,
                                                                         cap["slot"]),
        "snap strains  owl wing-arm %.1f %%, cap arm %.1f %%, foot prong %.1f %%  (PLA: keep < %.0f %%)"
        % (100 * owl["strain"], 100 * cap["strain"], 100 * foot["strain"], 100 * D.STRAIN_OK),
        "cap preload  %.1f / %.1f N per hook (arm stress %.0f / %.0f MPa) when the board is 0.1 / 0.2 mm"
        " thicker than the slot" % (hk["tail"]["preload"][0.1]["force_N"], hk["tail"]["preload"][0.2]["force_N"],
                                    hk["tail"]["preload"][0.1]["stress_MPa"], hk["tail"]["preload"][0.2]["stress_MPa"]),
        "cap mass  %.2f g of PLA (it prints solid; %.2f g/cm3)" % (cap["mass_g"], D.PLA_DENSITY),
        "owl  %.1f mm tall above the perch; bat floats %.1f mm below the perch (sim/physics)"
        % (owl["height"], D.float_gap(opn["lift"]) or float("nan")),
        "overhangs  no floating islands; farthest unsupported spot %s (the pockets' roofs are bridges)"
        % ", ".join("%s %.1f mm" % (r["name"], r["worst"][0][0] if r["worst"] else 0) for r in oh),
    ]
    if verbose:
        w = max(len(r[1]) for r in C.rows)
        for ok, name, v, want in C.rows:
            print("  %s  %-*s  %-14s %s" % ("ok  " if ok else "FAIL", w, name, v, want))
        for r in oh:
            print("  %s: worst unsupported spots (mm from the layer below, z, x, y):" % r["name"])
            for wv in r["worst"][:4]:
                print("      %.2f at z %.1f (%.1f, %.1f)" % wv)
        print("\n".join("  " + x for x in s))
        print("check.py: %s (%d checks)" % ("ALL OK" if C.ok else "FAILED", len(C.rows)))
    return dict(ok=C.ok, rows=C.rows, summary=s, owl=owl, cap=cap, foot=foot, plate=plate, pockets=opn,
                overhangs=oh)


if __name__ == "__main__":
    sys.exit(0 if run(verbose=True)["ok"] else 1)
