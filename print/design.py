#!/usr/bin/env python3
"""Every number of the printed parts: the owl, the bat's cap and the four feet.

Board and magnet numbers come from gen/mech.py (the one source of truth, shared
with the board generator); this file adds only what belongs to printing (layer
height, gaps, wall thicknesses, the shapes) and derives the rest.  build.py writes
these into out/params.scad for the OpenSCAD models; check.py re-measures the
generated meshes against mech.py without trusting this file.

Frames (millimetres):
  owl  - origin at the perch's coil centre on the perch's top surface; z up;
         y toward the back of the perch (KiCad y), so the viewer is at -y.
  cap  - origin at the bat's magnet axis on the bat's top surface; z up; the
         bat's head is at -y (BAT_HEAD_Y), its tail at +y (BAT_TAIL_Y).
  foot - origin at the foot's centre on the table; z up.
  print frame = assembled frame + (0, 0, Z0): every part prints the right way up,
  as it is assembled, so one rule sets both magnets' polarity.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import mech as M  # noqa: E402

# --- the printer and the plastic -------------------------------------------------
LAYER = 0.2            # layer height, and the first layer's
NOZZLE = 0.4
GAP_Z = LAYER          # air gap between a stand-in's top and the part printed over it
GAP_XY = 0.4           # sideways gap between a stand-in and a part beside it
PLA_DENSITY = 1.24     # g/cm^3
PLA_E = 3500.0         # MPa; printed PLA is 3.0-3.6 GPa
STRAIN_OK = 0.02       # one-time snap fits in PLA: keep the peak strain under ~2 %
STRAIN_PLA_MAX = 0.03  # PLA starts to yield/craze near 3 %


def snap(z):
    """Nearest layer boundary (the slicer cuts every layer at its mid-height, so a
    horizontal face off the grid lands on the nearest boundary anyway)."""
    return round(z / LAYER) * LAYER


def on_grid(z):
    return abs(z / LAYER - round(z / LAYER)) < 1e-6


# --- the magnet pocket (same in both parts) -----------------------------------------
POCKET_R = M.POCKET_D / 2
# Deepest whole number of layers that fits in POCKET_T: 2.2 mm for a 2.0 mm magnet, so
# its top sits a layer below the first layer printed over it.
POCKET_DEPTH = math.floor(M.POCKET_T / LAYER + 1e-9) * LAYER

# --- the owl ------------------------------------------------------------------------------
OWL_NOTCH_X = M.PERCH_W / 2 - M.OWL_NOTCH_D            # the notch's bottom, |x|
OWL_NOTCH_LEN = M.OWL_NOTCH_Y[1] - M.OWL_NOTCH_Y[0]
OWL_NOTCH_MID = (M.OWL_NOTCH_Y[0] + M.OWL_NOTCH_Y[1]) / 2
OWL_ARM_CLEAR = 0.05      # arm's inner face to the notch bottom
OWL_ARM_IN = OWL_NOTCH_X + OWL_ARM_CLEAR
OWL_ARM_T = 1.0           # the wing-arm's thickness (x) where it flexes
OWL_ARM_HALF_W = OWL_NOTCH_LEN / 2 - 0.2   # fits the notch with 0.2 each side (y)
OWL_ARM_CHAMFER = 0.6     # inner corners, to clear the router's ~0.5 mm fillets in the notch
OWL_SLOT_CLEAR = 0.4      # catch-to-base = board + 0.4: a thick board (1.76) still snaps in
OWL_SLOT = M.PCB_T + OWL_SLOT_CLEAR
OWL_HOOK_T = 1.0          # the lip's height (z): five layers
OWL_LIP_TIP = OWL_NOTCH_X - M.OWL_HOOK                 # reaches OWL_HOOK under the board
OWL_LEADIN_LAND = 0.15    # vertical land at the lip's tip, above the 45 deg lead-in
OWL_Z_CATCH = -OWL_SLOT
OWL_Z_BOTTOM = -(OWL_SLOT + OWL_HOOK_T)
OWL_Z0 = -OWL_Z_BOTTOM    # the lips stand on the bed: assembled z=0 prints at OWL_Z0
# The magnet's bottom face: OWL_LIFT above the top copper, the board's top surface being
# COPPER_TO_SURFACE above that copper; on the layer grid (error reported by check.py).
OWL_FLOOR = snap(OWL_Z0 + M.OWL_LIFT - M.COPPER_TO_SURFACE) - OWL_Z0
OWL_LIFT_DESIGNED = OWL_FLOOR + M.COPPER_TO_SURFACE

# Body: superellipse slices |x/a|^n + |y/b|^n = 1, convex, printed upright.
OWL_A = OWL_ARM_IN - 0.55  # half-width beside the wings (0.55 mm slit to each arm)
OWL_B = 10.0               # half-depth
OWL_N = 3.0                # superellipse exponent (rounded square)
OWL_FLARE = 1.5            # the base is inset this much, rising at 45 deg
OWL_ROOT_Z = 9.0           # the wing-arms join the body here; free below
OWL_TOP_Z = 27.0           # top of the head (ear tufts go higher)
OWL_DOME_P = 2.2           # head roundness
WING_RELIEF = OWL_ARM_IN + OWL_ARM_T - OWL_A   # wing surface stands this far off the body
OWL_WING_MEET_Z = 17.6     # above the root the wing's face leans in, meeting the body here
OWL_RIM = 2.5              # width of the base's contact rim (the middle is recessed)
OWL_EYE_X, OWL_EYE_Z, OWL_EYE_R = 5.35, 19.2, 4.4   # big round eyes: an engraved ring...
OWL_PUPIL_R, OWL_PUPIL_DEPTH = 2.0, 1.2              # ...round a deep pupil (a dark shadow)
OWL_TUFT_BASE = (7.6, 0.5, 22.4, 3.2)   # x, y, z, r of the tuft's root (flattened in y)
OWL_TUFT_TIP = (11.0, 0.5, 29.6, 0.5)
OWL_GROOVE_R = 0.4         # ball that engraves the feather marks
# the hollow under the base: a roof rising at 45 deg from the rim to a ridge along x
OWL_RECESS_A = OWL_A - OWL_FLARE - OWL_RIM
OWL_RECESS_B = OWL_B - OWL_FLARE - OWL_RIM
OWL_RECESS_RIDGE = (OWL_RECESS_A - OWL_RECESS_B, OWL_RECESS_B - 0.5)   # half-length, height

# Wing outline in the (y, z) plane, |y| <= w(z): narrow where it passes the notch,
# widening at <= 40 deg above the board, rounded at the shoulder.
WING_OUTLINE = [(OWL_ARM_HALF_W, OWL_Z_BOTTOM - 0.5), (OWL_ARM_HALF_W, 0.4),
                (3.8, 2.4), (4.5, 4.6), (4.9, 7.0), (5.2, 9.0), (5.4, 11.0),
                (5.0, 14.6), (3.8, 16.8), (2.0, 18.2), (0.0, 18.6)]
OWL_TALON = 1.0            # each arm's foot juts this far outward at the bed (grip, looks)

# The owl's stand-in: a slab under its base (the perch's place at print time).
OWL_SLAB_TOP = OWL_Z0 - GAP_Z            # print z
OWL_SLAB_HALF_X = OWL_A - OWL_FLARE + 0.6
OWL_SLAB_Y = (-(OWL_B + 3.6), OWL_B + 0.6)   # extends in front as a pull tab

# --- the bat's cap -------------------------------------------------------------------------
CAP_FLOOR_T = 2 * LAYER   # under the magnet: the magnet presses on the bat through this
CAP_SLOT = M.PCB_T        # lip catch to floor bottom; the slicer's bridging makes it a
                          # little tighter, so the arms preload the cap onto the board
CAP_HOOK_T = 1.0
CAP_DROP_CLEAR = 0.1      # drop's inner face to the board's edge
CAP_DROP_T = 1.0          # drop thickness (y)
CAP_FOOT = 1.2            # drop widens outward at the bottom: a steadier post on the pedestal
CAP_ARM_T = 0.8           # arm thickness (z): four layers
CAP_ARM_RAISE = 1.6       # arms run this far above the board (a bridge from dome to drop):
                          # a longer lever for the lip, so snapping on strains PLA less
CAP_LEADIN_LAND = 0.1
CAP_DOME_R0 = POCKET_R + 0.75             # the dome's foot on the board...
CAP_DOME_Z1 = 1.6                          # ...flaring out (22 deg) to its widest here...
CAP_DOME_R = POCKET_R + 1.4
CAP_DOME_TOP = 4.6                         # ...then an elliptical roof: >= 0.8 over the magnet
CAP_DOME_P = 2.0
CAP_Z_CATCH = -CAP_SLOT
CAP_Z_BOTTOM = -(CAP_SLOT + CAP_HOOK_T)
CAP_HEAD_DROP_IN = M.BAT_HEAD_Y - CAP_DROP_CLEAR      # y of the head drop's inner face
CAP_TAIL_DROP_IN = M.BAT_TAIL_Y + CAP_DROP_CLEAR
CAP_HEAD_LIP_TIP = M.BAT_HEAD_Y + M.CAP_HOOK
CAP_TAIL_LIP_TIP = M.BAT_TAIL_Y - M.CAP_HOOK

# One pause for both magnets: the cap prints on a pedestal tall enough that its pocket
# closes on the same layer as the owl's.
PAUSE_Z = OWL_Z0 + OWL_FLOOR + POCKET_DEPTH     # top of the last layer before the pause
PAUSE_LAYER = int(round(PAUSE_Z / LAYER)) + 1   # the first layer printed over the magnets
PAUSE_LAYER_TOP = PAUSE_LAYER * LAYER
POCKET_FLOOR_Z = PAUSE_Z - POCKET_DEPTH         # print z of both pocket floors
CAP_Z0 = POCKET_FLOOR_Z - CAP_FLOOR_T           # print z of the bat's top surface
CAP_PLATFORM_TOP = CAP_Z0 + CAP_Z_BOTTOM - GAP_Z   # under the lips
CAP_PLATEAU_TOP = CAP_Z0 - GAP_Z                    # under the floor and arms
CAP_PED_HALF_X = CAP_DOME_R + 1.0

# --- the feet ----------------------------------------------------------------------------
FOOT_PEG_D = M.FOOT_HOLE_D - 0.2     # shaft through the board
FOOT_BARB_D = M.FOOT_HOLE_D + 0.4    # catches 0.2 mm of the board's top face
FOOT_CATCH_Z = M.FOOT_HEIGHT + M.PCB_T + 0.1
FOOT_BARB_H = 1.4
FOOT_SLOT = 1.0                      # splits the peg into two prongs
FOOT_MOAT_DEPTH = 3.5                # frees the prongs below the foot's top face
FOOT_MOAT_R = FOOT_PEG_D / 2 + 0.9
FOOT_BARB_TOP_D = 2.4                # lead-in at the barb's top
FOOT_R = 5.4                         # a little pumpkin, ~11 mm across...
FOOT_LOBES = 8                       # ...of eight lobes (spheroids round a core)
FOOT_LOBE_R = 2.0
FOOT_LOBE_RZ = 4.4                   # lobes cut at 68 % of their height: flanks < 30 deg
FOOT_CORE_R = 3.6

# --- the plate (bed coordinates of each part's print-frame origin) --------------------
BED = (180.0, 180.0)      # the smallest Bambu bed (A1 mini); the plate fits well inside
PLATE = {
    "owl": (-26.0, 10.0),
    "bat_cap": (30.0, 10.0),
    "foot1": (-36.0, -28.0), "foot2": (-12.0, -28.0),
    "foot3": (12.0, -28.0), "foot4": (36.0, -28.0),
}


# =============================================================================
# shapes
# =============================================================================
def owl_profile(z):
    """(a, b, n) of the owl body's slice at height z (assembled frame)."""
    if z <= OWL_FLARE:
        d = OWL_FLARE - max(z, 0.0)
        return OWL_A - d, OWL_B - d, OWL_N
    if z <= OWL_ROOT_Z:
        return OWL_A, OWL_B, OWL_N
    t = min((z - OWL_ROOT_Z) / (OWL_TOP_Z - OWL_ROOT_Z), 1.0)
    s = max(1.0 - t ** OWL_DOME_P, 0.0) ** (1.0 / OWL_DOME_P)
    n = OWL_N - 0.8 * t        # rounder toward the crown
    return OWL_A * s, OWL_B * s, n


def superellipse(a, b, n, k=96):
    pts = []
    for i in range(k):
        t = 2 * math.pi * i / k
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def owl_body_points(k=96):
    """Points on the owl body's surface (a convex hull of them is the body)."""
    zs = [0.0, 0.5, 1.0, OWL_FLARE, 4.0, 7.0, OWL_ROOT_Z]
    nd = 44     # dense toward the crown, where the slope is low
    zs += [OWL_ROOT_Z + (OWL_TOP_Z - OWL_ROOT_Z) * math.sin(math.pi / 2 * i / nd) for i in range(1, nd)]
    pts = []
    for z in zs:
        a, b, n = owl_profile(z)
        pts += [(x, y, z) for x, y in superellipse(a, b, n, k)]
    pts.append((0.0, 0.0, OWL_TOP_Z))
    return pts


def owl_front_y(x, z):
    """y of the body's front surface (the face, -y) at (x, z)."""
    a, b, n = owl_profile(z)
    u = min(abs(x) / a, 1.0)
    return -b * (1 - u ** n) ** (1 / n)


def owl_side_x(y, z):
    a, b, n = owl_profile(z)
    u = min(abs(y) / b, 1.0)
    return a * (1 - u ** n) ** (1 / n)


def sphere_dirs(k=42):
    """Roughly uniform unit vectors (Fibonacci sphere)."""
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(k):
        z = 1 - 2 * (i + 0.5) / k
        r = math.sqrt(1 - z * z)
        out.append((r * math.cos(g * i), r * math.sin(g * i), z))
    return out


def hull_polyhedron(points):
    """Convex hull -> (points, faces) with OpenSCAD's winding (clockwise seen from outside)."""
    import numpy as np
    from scipy.spatial import ConvexHull
    P = np.asarray(points, float)
    h = ConvexHull(P)
    used = sorted(set(h.simplices.ravel()))
    remap = {j: i for i, j in enumerate(used)}
    c = P[used].mean(axis=0)
    faces = []
    for s in h.simplices:
        a, b, d = P[s[0]], P[s[1]], P[s[2]]
        n = np.cross(b - a, d - a)
        tri = [remap[s[0]], remap[s[1]], remap[s[2]]]
        if np.dot(n, a - c) > 0:     # counter-clockwise from outside: flip for OpenSCAD
            tri = [tri[0], tri[2], tri[1]]
        faces.append(tri)
    return P[used].tolist(), faces


def offset_hull(points, d):
    """Grow a convex body by d along its vertex normals (area-weighted facet normals):
    for a smooth convex surface this is its offset surface.  Returns (points, faces)."""
    import numpy as np
    from scipy.spatial import ConvexHull
    P = np.asarray(points, float)
    h = ConvexHull(P)
    N = np.zeros_like(P)
    c = P.mean(axis=0)
    for s in h.simplices:
        a, b, e = P[s]
        n = np.cross(b - a, e - a)          # length = 2 x area
        if np.dot(n, a - c) < 0:
            n = -n
        N[s] += n
    used = sorted(set(h.simplices.ravel()))
    Q = [tuple(P[i] + d * N[i] / np.linalg.norm(N[i])) for i in used]
    return hull_polyhedron(Q)


# --- owl decorations: where they sit on the body's surface ----------------------------
def owl_eye_centres():
    return [(s * OWL_EYE_X, OWL_EYE_Z) for s in (-1, 1)]


def owl_eye_rings():
    """Each eye's outline: a closed ring on the face, engraved with the groove ball."""
    out = []
    for ex, ez in owl_eye_centres():
        pts = []
        for i in range(37):
            t = 2 * math.pi * i / 36
            x, z = ex + OWL_EYE_R * math.cos(t), ez + OWL_EYE_R * math.sin(t)
            pts.append((x, owl_front_y(x, z), z))
        out.append(pts)
    return out


def owl_belly_grooves():
    """Little 'U' feather marks on the belly (as in art/shapes.py's owl), as 3-D
    polylines on the front surface."""
    out = []
    for cx, cz in ((-2.9, 10.6), (2.9, 10.6), (0.0, 8.0), (-2.9, 5.4), (2.9, 5.4)):
        pts = []
        for i in range(7):
            t = math.radians(200 + 140 * i / 6)
            x, z = cx + 1.5 * math.cos(t), cz + 1.5 * math.sin(t)
            pts.append((x, owl_front_y(x, z), z))
        out.append(pts)
    return out


def owl_wing_lean():
    """The wing's outer face above its root is the plane x = x0 - (z - z0) * tan(lean):
    (x0, z0, lean in degrees).  It stands WING_RELIEF off the body at the root and meets
    the body at OWL_WING_MEET_Z, so the folded wing tucks into the shoulder."""
    x0 = OWL_A + WING_RELIEF
    x1 = owl_profile(OWL_WING_MEET_Z)[0]
    return x0, OWL_ROOT_Z, math.degrees(math.atan((x0 - x1) / (OWL_WING_MEET_Z - OWL_ROOT_Z)))


def owl_wing_x(y, z):
    """x of the +x wing's outer surface at (y, z) (above the root)."""
    x0, z0, lean = owl_wing_lean()
    return min(owl_side_x(y, z) + WING_RELIEF, x0 - (z - z0) * math.tan(math.radians(lean)))


def owl_wing_grooves():
    """Scalloped feather marks on the +x wing (mirrored for -x), near its bottom where
    it stands off the body."""
    out = []
    for cy, cz, r in ((-2.3, 11.4, 1.8), (1.3, 11.4, 1.8), (-0.5, 13.6, 1.5)):
        pts = []
        for i in range(7):
            t = math.radians(200 + 140 * i / 6)
            y, z = cy + r * math.cos(t), cz + r * math.sin(t)
            pts.append((owl_wing_x(y, z), y, z))
        out.append(pts)
    return out


def owl_beak():
    """Spheres (x, y, z, r) whose hull is the beak: wide at the top between the eyes,
    a point at the bottom, sloping back at well under 45 deg."""
    zt, zm, zb = 17.9, 16.8, 14.0
    yt, ym, yb = owl_front_y(0, zt), owl_front_y(0, zm), owl_front_y(0, zb)
    return [(-1.6, yt + 0.5, zt, 0.6), (1.6, yt + 0.5, zt, 0.6),
            (0.0, ym - 1.4, zm, 0.7), (0.0, yb - 0.25, zb, 0.4)]


def cap_ears():
    """Two little bat ears on the dome, toward the head: (base x, y, z, r, tip x, y, z, r)."""
    out = []
    for s in (-1, 1):
        x, y = 2.7 * s, -3.4
        z = cap_dome_z(math.hypot(x, y))
        out.append((x, y, z - 0.6, 1.6, 1.25 * x, y - 0.3, z + 2.6, 0.35))
    return out


def bat_outline():
    """A schematic bat board for the fit views (the real outline is the board
    generator's): a round body over the receive coil with straight head and tail
    edges where the cap hooks, ears, and scalloped wings to BAT_SPAN."""
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import unary_union
    h, t = M.BAT_HEAD_Y, M.BAT_TAIL_Y
    body = Point(0, 0).buffer(M.RX_R_OUT + 1.5, 64).intersection(box(-30, h, 30, t))
    flat = box(-(M.CAP_ARM_W / 2 + 1.5), h, M.CAP_ARM_W / 2 + 1.5, t)
    parts = [body, flat]
    half = M.BAT_SPAN / 2
    for s in (-1, 1):
        parts.append(Polygon([(s * 3.4, h + 1.2), (s * 6.8, h - 2.6), (s * 8.6, h + 4.0)]))
        tips = [(half, -6.0), (0.80 * half, 3.0), (0.56 * half, 7.0), (0.36 * half, 8.5)]
        pts = [(s * 9.0, -6.5), (s * 0.62 * half, -10.5), (s * half, -6.0)]
        for (x0, y0), (x1, y1) in zip(tips, tips[1:]):
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            pts += [(s * (mx - 1.2), my - 2.0), (s * x1, y1)]
        pts.append((s * 8.0, 6.0))
        parts.append(Polygon(pts).buffer(0))
    shape = unary_union(parts).buffer(0.3).buffer(-0.3)
    return [tuple(p) for p in shape.exterior.coords[:-1]]


def owl_toes():
    """Capsules (x0, y0, x1, y1, r) of the toes peeping out at the front of the base."""
    r = 0.75
    out = []
    for fx in (-4.0, 4.0):
        for ang in (-28, 0, 28):
            a = math.radians(ang)
            x0 = fx + 0.6 * math.sin(a)
            y0 = owl_front_y(x0, r) + 0.9
            out.append((x0, y0, fx + 2.6 * math.sin(a), y0 - 2.6 * math.cos(a), r))
    return out


def cap_dome_profile(k=24):
    """(r, z) outline of the cap's dome for rotate_extrude: wall, then elliptical roof."""
    pts = [(0.0, 0.0), (CAP_DOME_R0, 0.0)]
    for i in range(k + 1):
        t = math.pi / 2 * i / k
        pts.append((CAP_DOME_R * math.cos(t), CAP_DOME_Z1 + (CAP_DOME_TOP - CAP_DOME_Z1) * math.sin(t)))
    pts[-1] = (0.0, CAP_DOME_TOP)
    return pts


def cap_dome_z(r):
    """Height of the dome's surface at radius r."""
    if r > CAP_DOME_R:
        return 0.0
    h = CAP_DOME_TOP - CAP_DOME_Z1
    return CAP_DOME_Z1 + h * math.sqrt(max(1 - (r / CAP_DOME_R) ** 2, 0.0))


# =============================================================================
# mechanics: snap strains, preloads, masses
# =============================================================================
def wing_half_width(z):
    pts = WING_OUTLINE
    if z <= pts[0][1]:
        return pts[0][0]
    for (w0, z0), (w1, z1) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            return w0 + (w1 - w0) * (z - z0) / (z1 - z0)
    return 0.0


def owl_arm_snap():
    """The wing-arm is a cantilever from its root (OWL_ROOT_Z) down to the lip; snapping
    on pushes the lip out until its tip clears the notch bottom.  Integrates the
    tapered plate (width 2*w(z), thickness OWL_ARM_T) numerically."""
    t = OWL_ARM_T
    z_load = OWL_Z_BOTTOM + 0.5 * (OWL_HOOK_T - OWL_LEADIN_LAND)   # middle of the lead-in
    delta = (OWL_ARM_IN - OWL_LIP_TIP) + 0.05                         # lip clears the edge
    n = 400
    zs = [z_load + (OWL_ROOT_Z - z_load) * (i + 0.5) / n for i in range(n)]
    dz = (OWL_ROOT_Z - z_load) / n
    # unit load at z_load: moment at z is (z - z_load); deflection by unit-load method
    comp = 0.0
    eps_per_F = 0.0
    for z in zs:
        w = 2 * wing_half_width(z)
        I = w * t ** 3 / 12
        m = z - z_load
        comp += m * m / (PLA_E * I) * dz
        eps_per_F = max(eps_per_F, m * (t / 2) / (PLA_E * I))
    F = delta / comp
    return dict(length=OWL_ROOT_Z - z_load, thickness=t, deflection=delta,
                force_N=F, strain=F * eps_per_F,
                strain_uniform_formula=1.5 * delta * t / (OWL_ROOT_Z - z_load) ** 2)


def cap_hook_snap():
    """Snapping the cap on pushes each lip out (y) by its reach plus clearance.  The lip
    hangs below the arm on the drop: the arm curls (constant moment F*Ld) and the drop
    bends.  Both arms; the shorter (tail) one is the stiffer and worse."""
    w = M.CAP_ARM_W
    Ia = w * CAP_ARM_T ** 3 / 12
    Id = w * CAP_DROP_T ** 3 / 12
    Ld = CAP_ARM_RAISE + CAP_ARM_T / 2 - (CAP_Z_BOTTOM + 0.5 * (CAP_HOOK_T - CAP_LEADIN_LAND))
    delta = M.CAP_HOOK + CAP_DROP_CLEAR + 0.05
    out = {}
    for name, La in (("head", -CAP_HEAD_DROP_IN - CAP_DOME_R), ("tail", CAP_TAIL_DROP_IN - CAP_DOME_R)):
        comp = Ld * Ld * La / (PLA_E * Ia) + Ld ** 3 / (3 * PLA_E * Id)
        F = delta / comp
        out[name] = dict(arm_length=La, drop_lever=Ld, deflection=delta, force_N=F,
                         strain_arm=F * Ld * (CAP_ARM_T / 2) / (PLA_E * Ia),
                         strain_drop=F * Ld * (CAP_DROP_T / 2) / (PLA_E * Id))
        # vertical preload: the board is thicker than the slot by e -> the arm's end lifts e
        out[name]["preload"] = {}
        for e in (0.1, 0.2, 0.3):
            Fv = 3 * PLA_E * Ia * e / La ** 3
            out[name]["preload"][e] = dict(force_N=Fv, stress_MPa=1.5 * PLA_E * CAP_ARM_T * e / La ** 2)
    return out


def foot_prong_snap():
    """Each prong (half the split peg, a circular segment) bends inward as the barb
    passes the hole; the root is the moat floor, the load at the barb's catch."""
    R = FOOT_PEG_D / 2
    c = FOOT_SLOT / 2
    # circular segment beyond the chord at distance c: area, centroid, I about its centroid
    n = 2000
    A = Sy = Syy = 0.0
    for i in range(n):
        y = c + (R - c) * (i + 0.5) / n
        dy = (R - c) / n
        wdt = 2 * math.sqrt(max(R * R - y * y, 0.0))
        A += wdt * dy
        Sy += wdt * y * dy
        Syy += wdt * y * y * dy
    yc = Sy / A
    I = Syy - A * yc * yc
    ymax = max(R - yc, yc - c)
    L = FOOT_CATCH_Z - (M.FOOT_HEIGHT - FOOT_MOAT_DEPTH)
    delta = (FOOT_BARB_D - M.FOOT_HOLE_D) / 2 + 0.05
    strain = 3 * delta * ymax / L ** 2
    F = 3 * PLA_E * I * delta / L ** 3
    return dict(length=L, deflection=delta, strain=strain, force_N=F, I=I, ymax=ymax)


def float_gap(lift):
    """The bat's float gap (perch bottom copper to the bat magnet's top face) for a given
    bias-magnet lift, interpolated from sim/physics/results/levitation_onemagnet.json."""
    import json
    p = os.path.join(ROOT, "sim", "physics", "results", "levitation_onemagnet.json")
    try:
        rows = sorted(json.load(open(p)), key=lambda r: r["lift_mm"])
    except (OSError, ValueError):
        return None
    for r0, r1 in zip(rows, rows[1:]):
        if r0["lift_mm"] <= lift <= r1["lift_mm"]:
            f = (lift - r0["lift_mm"]) / (r1["lift_mm"] - r0["lift_mm"])
            return r0["gap_mm"] + f * (r1["gap_mm"] - r0["gap_mm"])
    return None


def check_invariants():
    """Fail early on a parameter set that cannot work."""
    assert POCKET_DEPTH >= M.MAGNET_T + 0.1, "pocket too shallow for the magnet"
    assert M.POCKET_D > M.MAGNET_D, "pocket narrower than the magnet"
    for z in (OWL_Z0, OWL_Z0 + OWL_FLOOR, PAUSE_Z, CAP_Z0, CAP_PLATFORM_TOP, CAP_PLATEAU_TOP,
              OWL_SLAB_TOP, OWL_HOOK_T, CAP_HOOK_T, CAP_ARM_T, CAP_FLOOR_T):
        assert on_grid(z), "off the layer grid: %r" % z
    assert abs(OWL_LIFT_DESIGNED - M.OWL_LIFT) <= LAYER / 2 + 1e-9
    assert OWL_A < OWL_ARM_IN - 0.4, "no slit between the owl's body and its arms"
    assert OWL_SLAB_HALF_X <= OWL_LIP_TIP - GAP_XY, "owl's stand-in touches its lips"
    assert CAP_PLATFORM_TOP > 0
    assert OWL_ARM_HALF_W * 2 < OWL_NOTCH_LEN


check_invariants()

if __name__ == "__main__":
    import json
    out = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, tuple))}
    print(json.dumps(out, indent=1, default=str))
    print("owl arm", owl_arm_snap())
    print("cap hooks", json.dumps(cap_hook_snap(), indent=1))
    print("foot prongs", foot_prong_snap())
    print("float gap at the designed lift", float_gap(OWL_LIFT_DESIGNED))
