#!/usr/bin/env python3
"""Small magnetostatics toolkit for PCB coils and NdFeB magnets.

Everything is SI (metres, amperes, tesla, henries, newtons).  Conductors are
polylines of straight segments; the field of each segment is the closed-form
Biot-Savart result for a finite straight wire, so the answer is exact for the
polyline (and converges to the smooth coil as segments shrink).

A uniformly magnetised body is replaced by its equivalent surface current
(K = M x n, with M = Br/mu0): a cylinder magnetised along its axis becomes a
stack of circular current loops round its side wall; a sphere becomes loops of
current M*R*sin(theta)*dtheta.  The force on the magnet is then the Lorentz
force on those currents in the coil's field, F = sum(I dl x B), and the torque
about its centre sum(r x (I dl x B)).  Newton's third law makes that the
negative of the force on the coil, which is how a PCB "motor" pushes a magnet.

Run this file to execute the self-tests, which compare it with closed forms:
  - on-axis field of a loop and of a cylindrical magnet,
  - mutual inductance of coaxial loops (Neumann sum vs. elliptic integrals),
  - axial force between loops (Lorentz sum vs. I1*I2*dM/dz).
"""
import numpy as np
from scipy.special import ellipk, ellipe

MU0 = 4e-7 * np.pi
RHO_CU = 1.72e-8          # ohm*m at 20 C
OZ = 34.8e-6              # 1 oz/ft^2 copper thickness, m


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------
def circle(r, z=0.0, n=128, center=(0.0, 0.0), axis="z", phase=0.0):
    """Closed polyline (n+1 points) of a circle of radius r."""
    t = phase + np.linspace(0, 2 * np.pi, n + 1)
    cx, cy = center
    if axis == "z":
        return np.stack([cx + r * np.cos(t), cy + r * np.sin(t), np.full_like(t, z)], 1)
    raise ValueError(axis)


def spiral(n_turns, r_out, r_in, z=0.0, per_turn=96, inward=True, sense=+1,
           center=(0.0, 0.0)):
    """Archimedean spiral polyline from r_out to r_in (or the reverse).

    sense=+1 winds counter-clockwise seen from +z.  Current entering at the
    first point circulates in the direction of `sense` either way, so a
    multilayer coil keeps one `sense` on every layer and alternates `inward`.
    """
    m = int(round(n_turns * per_turn)) + 1
    s = np.linspace(0.0, 1.0, m)
    r = r_out + (r_in - r_out) * s if inward else r_in + (r_out - r_in) * s
    th = sense * 2 * np.pi * n_turns * s
    cx, cy = center
    return np.stack([cx + r * np.cos(th), cy + r * np.sin(th), np.full_like(th, z)], 1)


def multilayer_coil(n_turns, r_out, r_in, z_layers, per_turn=96, sense=+1,
                    center=(0.0, 0.0)):
    """Series-connected spirals on several layers, current circulating one way.

    Returns a list of polylines (one per layer); the vias between them are
    short vertical segments whose field is negligible and are omitted.
    """
    out = []
    for i, z in enumerate(z_layers):
        out.append(spiral(n_turns, r_out, r_in, z, per_turn, inward=(i % 2 == 0),
                          sense=sense, center=center))
    return out


def polyline_length(p):
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))


def segments(polylines):
    """(A, B) arrays of segment start and end points from a list of polylines."""
    if isinstance(polylines, np.ndarray):
        polylines = [polylines]
    A = np.concatenate([p[:-1] for p in polylines])
    B = np.concatenate([p[1:] for p in polylines])
    return A, B


# ----------------------------------------------------------------------------
# Fields
# ----------------------------------------------------------------------------
def bfield(A, B, I, P, chunk=4000):
    """Field at points P (N,3) of current I through segments A->B (M,3).

    Closed form for a finite straight segment:
        B = mu0 I / 4pi * (r1 x r2) (|r1| + |r2|) / (|r1||r2| (|r1||r2| + r1.r2))
    with r1 = P - A, r2 = P - B.  I may be a scalar or a per-segment array.
    """
    P = np.atleast_2d(P)
    I = np.broadcast_to(np.asarray(I, float), (A.shape[0],))
    out = np.zeros_like(P, dtype=float)
    for s in range(0, P.shape[0], chunk):
        p = P[s:s + chunk, None, :]
        r1 = p - A[None]
        r2 = p - B[None]
        n1 = np.linalg.norm(r1, axis=2)
        n2 = np.linalg.norm(r2, axis=2)
        cr = np.cross(r1, r2)
        den = n1 * n2 * (n1 * n2 + np.einsum("ijk,ijk->ij", r1, r2))
        den = np.where(np.abs(den) < 1e-30, np.inf, den)
        f = (n1 + n2) / den * I[None]
        out[s:s + chunk] = MU0 / (4 * np.pi) * np.einsum("ij,ijk->ik", f, cr)
    return out


# ----------------------------------------------------------------------------
# Magnets as equivalent surface currents
# ----------------------------------------------------------------------------
class Magnet:
    """A uniformly magnetised body represented by current loops.

    loops: list of polylines; currents: per-loop current (A).
    """

    def __init__(self, loops, currents, center, moment):
        self.loops = loops
        self.currents = np.asarray(currents, float)
        self.center = np.asarray(center, float)
        self.moment = np.asarray(moment, float)    # A m^2, for reference

    def seg_currents(self):
        A, B = segments(self.loops)
        I = np.concatenate([np.full(len(p) - 1, c) for p, c in zip(self.loops, self.currents)])
        return A, B, I

    def field(self, P):
        A, B, I = self.seg_currents()
        return bfield(A, B, I, P)


def _orient(points, axis):
    """Rotate points defined about +z so +z maps to unit vector `axis`."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, a)
    c = float(np.dot(z, a))
    if np.linalg.norm(v) < 1e-12:
        R = np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * (1 / (1 + c))
    return points @ R.T


def cylinder_magnet(radius, height, Br, center=(0, 0, 0), axis=(0, 0, 1),
                    nz=24, nseg=96):
    """Axially magnetised cylinder (disc) magnet, N pole toward +axis."""
    M = Br / MU0
    dz = height / nz
    zs = -height / 2 + dz * (np.arange(nz) + 0.5)
    loops = []
    for z in zs:
        pts = circle(radius, z, nseg)
        loops.append(_orient(pts, axis) + np.asarray(center, float))
    vol = np.pi * radius ** 2 * height
    mom = M * vol * np.asarray(axis, float) / np.linalg.norm(axis)
    return Magnet(loops, np.full(nz, M * dz), center, mom)


def sphere_magnet(radius, Br, center=(0, 0, 0), axis=(0, 0, 1), nth=40, nseg=96):
    """Uniformly magnetised sphere: K = M sin(theta) phi-hat."""
    M = Br / MU0
    dth = np.pi / nth
    th = dth * (np.arange(nth) + 0.5)
    loops, cur = [], []
    for t in th:
        pts = circle(radius * np.sin(t), radius * np.cos(t), nseg)
        loops.append(_orient(pts, axis) + np.asarray(center, float))
        cur.append(M * radius * np.sin(t) * dth)
    mom = M * 4 / 3 * np.pi * radius ** 3 * np.asarray(axis, float) / np.linalg.norm(axis)
    return Magnet(loops, cur, center, mom)


def force_torque(magnet, coil_polylines, I_coil):
    """Force (N) and torque about the magnet centre (N m) from the coil's field."""
    A, B, Im = magnet.seg_currents()
    mid = 0.5 * (A + B)
    dl = B - A
    CA, CB = segments(coil_polylines)
    Bc = bfield(CA, CB, I_coil, mid)
    dF = Im[:, None] * np.cross(dl, Bc)
    F = dF.sum(0)
    T = np.cross(mid - magnet.center, dF).sum(0)
    return F, T


# ----------------------------------------------------------------------------
# Inductance
# ----------------------------------------------------------------------------
def mutual_coaxial_loops(r1, r2, d):
    """Exact mutual inductance of two coaxial circular filaments (Maxwell)."""
    k2 = 4 * r1 * r2 / ((r1 + r2) ** 2 + d ** 2)
    k = np.sqrt(k2)
    return MU0 * np.sqrt(r1 * r2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))


def mutual_neumann(P1, P2):
    """Mutual inductance of two separated polylines by Neumann's formula."""
    A1, B1 = segments(P1)
    A2, B2 = segments(P2)
    m1, d1 = 0.5 * (A1 + B1), B1 - A1
    m2, d2 = 0.5 * (A2 + B2), B2 - A2
    tot = 0.0
    for s in range(0, len(m1), 2000):
        r = np.linalg.norm(m1[s:s + 2000, None] - m2[None], axis=2)
        tot += np.sum((d1[s:s + 2000] @ d2.T) / r)
    return MU0 / (4 * np.pi) * tot


def L_mohan(n, d_out, d_in, shape="circle"):
    """Current-sheet inductance of a single-layer planar spiral (Mohan 1999)."""
    c = {"square": (1.27, 2.07, 0.18, 0.13), "hexagon": (1.09, 2.23, 0.0, 0.17),
         "octagon": (1.07, 2.29, 0.0, 0.19), "circle": (1.00, 2.46, 0.0, 0.20)}[shape]
    davg = 0.5 * (d_out + d_in)
    rho = (d_out - d_in) / (d_out + d_in)
    return MU0 * n ** 2 * davg * c[0] / 2 * (np.log(c[1] / rho) + c[2] * rho + c[3] * rho ** 2)


def L_multilayer(n, r_out, r_in, z_layers, shape="circle"):
    """Series multilayer spiral: sum of layer self-inductances (Mohan) plus the
    mutual inductance between layers, from concentric-turn filaments."""
    radii = np.linspace(r_out, r_in, max(int(round(n)), 1))
    Ls = L_mohan(n, 2 * r_out, 2 * r_in, shape)
    L = len(z_layers) * Ls
    for i in range(len(z_layers)):
        for j in range(len(z_layers)):
            if i == j:
                continue
            d = abs(z_layers[i] - z_layers[j])
            # turn-by-turn mutuals between the two layers, scaled to n turns
            Mij = sum(mutual_coaxial_loops(a, b, d) for a in radii for b in radii)
            Mij *= (n / len(radii)) ** 2
            L += Mij
    return L


def skin_depth(f):
    return np.sqrt(RHO_CU / (np.pi * f * MU0))


def R_trace(length, width, thick, f=0.0):
    """DC resistance, with a one-dimensional skin-effect correction for a flat
    strip carrying current on both faces (proximity effect not included)."""
    Rdc = RHO_CU * length / (width * thick)
    if f <= 0:
        return Rdc
    d = skin_depth(f)
    t_eff = min(thick, 2 * d * (1 - np.exp(-thick / (2 * d))))
    return RHO_CU * length / (width * t_eff)


# ----------------------------------------------------------------------------
# Resonant inductive link
# ----------------------------------------------------------------------------
def link_eta_max(k, Q1, Q2):
    x = k * k * Q1 * Q2
    return x / (1 + np.sqrt(1 + x)) ** 2


# ----------------------------------------------------------------------------
# Self-tests
# ----------------------------------------------------------------------------
def _selftest():
    ok = True

    def check(name, got, want, tol):
        nonlocal ok
        err = abs(got - want) / abs(want)
        flag = "ok " if err < tol else "BAD"
        ok &= err < tol
        print(f"  [{flag}] {name}: got {got:.6g}, closed form {want:.6g} ({err * 100:.3f} %)")

    print("self-tests")
    R, I, z = 0.01, 1.0, 0.007
    Bz = bfield(*segments(circle(R, 0, 720)), I, np.array([[0, 0, z]]))[0, 2]
    check("loop on-axis Bz", Bz, MU0 * I * R ** 2 / (2 * (R ** 2 + z ** 2) ** 1.5), 1e-4)

    a, h, Br = 0.005, 0.003, 1.43
    mag = cylinder_magnet(a, h, Br, nz=200, nseg=360)
    zf = 0.002     # 2 mm from the top face
    Bz = mag.field(np.array([[0, 0, h / 2 + zf]]))[0, 2]
    want = Br / 2 * ((zf + h) / np.hypot(zf + h, a) - zf / np.hypot(zf, a))
    check("cylinder magnet on-axis Bz", Bz, want, 2e-3)

    r1, r2, d = 0.012, 0.009, 0.004
    Mn = mutual_neumann(circle(r1, 0, 720), circle(r2, d, 720))
    check("coaxial-loop mutual (Neumann vs elliptic)", Mn, mutual_coaxial_loops(r1, r2, d), 2e-3)

    I1, I2 = 2.0, 3.0
    loop2 = Magnet([circle(r2, d, 720)], [I2], (0, 0, d), (0, 0, 0))
    F, _ = force_torque(loop2, circle(r1, 0, 720), I1)
    dd = 1e-6
    dMdz = (mutual_coaxial_loops(r1, r2, d + dd) - mutual_coaxial_loops(r1, r2, d - dd)) / (2 * dd)
    check("axial force between loops (Lorentz vs I1 I2 dM/dz)", F[2], I1 * I2 * dMdz, 2e-3)

    # sphere: external field equals a point dipole
    sm = sphere_magnet(0.005, 1.43, nth=120, nseg=180)
    p = np.array([[0, 0, 0.012]])
    Bz = sm.field(p)[0, 2]
    m = sm.moment[2]
    check("sphere magnet = dipole outside", Bz, MU0 / (4 * np.pi) * 2 * m / 0.012 ** 3, 3e-3)
    print("all ok" if ok else "SOME TESTS FAILED")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
