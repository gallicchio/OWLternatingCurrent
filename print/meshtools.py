#!/usr/bin/env python3
"""Small mesh tools for the print build and its checks (numpy only).

A mesh is an (n, 3, 3) float array of triangles, wound counter-clockwise seen from
outside (STL's convention).
"""
import struct

import numpy as np


# ------------------------------------------------------------------ STL
def read_stl(path):
    data = open(path, "rb").read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        v = [list(map(float, ln.split()[1:4])) for ln in data.decode().splitlines()
             if ln.strip().startswith("vertex")]
        return np.asarray(v, float).reshape(-1, 3, 3)
    n = struct.unpack("<I", data[80:84])[0]
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]),
                        count=n, offset=84)
    return rec["v"].reshape(-1, 3, 3).astype(float)


def canonical(tris):
    """The same triangles in a fixed order (OpenSCAD's CGAL emits them in a run-dependent
    order): each starts at its smallest vertex (winding kept), then all are sorted."""
    t = np.asarray(tris, np.float32)
    if not len(t):
        return t
    first = np.array([min(range(3), key=lambda i: tuple(tri[i])) for tri in t])
    idx = (np.arange(3)[None, :] + first[:, None]) % 3
    t = np.take_along_axis(t, idx[:, :, None].repeat(3, axis=2), axis=1)
    flat = t.reshape(len(t), 9)
    return t[np.lexsort(flat.T[::-1])]


def write_stl(path, tris, name="mesh"):
    tris = canonical(tris)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(ln == 0, 1, ln)
    rec = np.zeros(len(tris), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    rec["n"] = n
    rec["v"] = tris.reshape(-1, 9)
    with open(path, "wb") as f:
        f.write(("OWLternating Current: " + name)[:80].ljust(80).encode())
        f.write(struct.pack("<I", len(tris)))
        f.write(rec.tobytes())


def translate(tris, d):
    return np.asarray(tris) + np.asarray(d, float)


def bbox(tris):
    p = np.asarray(tris).reshape(-1, 3)
    return p.min(axis=0), p.max(axis=0)


def volume(tris):
    t = np.asarray(tris)
    return float(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6.0)


def weld(tris):
    """Indexed form (vertices, faces), merging only bit-identical float32 vertices
    (OpenSCAD writes float32 STLs; rounding would collapse its sliver triangles)."""
    p = canonical(tris).reshape(-1, 3)
    verts, inv = np.unique(p, axis=0, return_inverse=True)
    return verts.astype(float), inv.reshape(-1, 3)


def components(tris):
    """Split a mesh into its connected shells (largest first).  A sealed void inside a
    part (the magnet's pocket) is a shell of negative volume."""
    verts, faces = weld(tris)
    parent = np.arange(len(verts))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, c in faces:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(f[0]) for f in faces])
    shells = [np.asarray(tris)[roots == r] for r in np.unique(roots)]
    return sorted(shells, key=len, reverse=True)


def is_closed(tris):
    """Every edge used exactly twice, once in each direction (watertight, oriented)."""
    _, faces = weld(tris)
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    fwd = {tuple(x) for x in e.tolist()}
    return len(fwd) == len(e) and all((b, a) in fwd for a, b in fwd)


# ------------------------------------------------------------------ slicing
def plane_segments(tris, axis, value):
    """Segments where the plane coord[axis] == value cuts the mesh, in the other two
    coordinates (in increasing axis order), each directed so the solid lies on one
    consistent side: outer boundaries and holes come out with opposite windings."""
    t = np.asarray(tris)
    other = [i for i in range(3) if i != axis]
    d = t[:, :, axis] - value
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)     # nudge vertices that sit on the plane
    s = d > 0
    cross = (s.sum(axis=1) == 1) | (s.sum(axis=1) == 2)
    t, d, s = t[cross], d[cross], s[cross]
    if not len(t):
        return np.zeros((0, 2, 2))
    pts = []
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        m = s[:, i] != s[:, j]
        a, b = t[:, i], t[:, j]
        da, db = d[:, i], d[:, j]
        with np.errstate(divide="ignore", invalid="ignore"):
            f = (da / (da - db))[:, None]
            p = a + f * (b - a)
        pts.append(np.where(m[:, None], p[:, other], np.nan))
    pts = np.stack(pts, axis=1)                    # (n, 3 edges, 2)
    ok = ~np.isnan(pts[:, :, 0])
    seg = np.array([pp[k] for pp, k in zip(pts, ok)]).reshape(-1, 2, 2)
    # direction: plane normal x face normal, in the plane's (u, v) coordinates
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    e = np.zeros(3)
    e[axis] = 1.0
    want = np.cross(e, n)[:, other]
    have = seg[:, 1] - seg[:, 0]
    flip = np.einsum("ij,ij->i", want, have) < 0
    seg[flip] = seg[flip][:, ::-1]
    return seg


def raster(segs, xs, ys):
    """Inside/outside on a grid (even-odd rule over all loops) by scanlines in y."""
    grid = np.zeros((len(ys), len(xs)), bool)
    if len(segs) == 0:
        return grid
    x0, y0 = segs[:, 0, 0], segs[:, 0, 1]
    x1, y1 = segs[:, 1, 0], segs[:, 1, 1]
    for j, y in enumerate(ys):
        m = (y0 > y) != (y1 > y)
        if not m.any():
            continue
        xc = np.sort(x0[m] + (y - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m]))
        cnt = np.searchsorted(xc, xs)
        grid[j] = cnt % 2 == 1
    return grid


def loops(segs, tol=1e-4):
    """Chain directed segments (end of one = start of the next) into closed polylines."""
    key = lambda p: (int(round(p[0] / tol)), int(round(p[1] / tol)))
    start = {}
    for i, (a, b) in enumerate(segs):
        start.setdefault(key(a), []).append(i)
    used = np.zeros(len(segs), bool)
    out = []
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        i = i0
        loop = [segs[i][0]]
        while not used[i]:
            used[i] = True
            loop.append(segs[i][1])
            nxt = [j for j in start.get(key(segs[i][1]), []) if not used[j]]
            if not nxt:
                break
            i = nxt[0]
        out.append(np.array(loop))
    return out


def ray_hits(tris, origin, direction):
    """Sorted distances along a ray to every triangle it crosses (Moller-Trumbore)."""
    t = np.asarray(tris)
    o = np.asarray(origin, float)
    dvec = np.asarray(direction, float)
    e1 = t[:, 1] - t[:, 0]
    e2 = t[:, 2] - t[:, 0]
    p = np.cross(dvec, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
    s = o - t[:, 0]
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = (q @ dvec) * inv
    w = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (w > 0)
    ws = np.sort(w[hit])
    # a ray through a shared edge hits both triangles: merge near-duplicates
    if len(ws):
        keep = np.concatenate([[True], np.diff(ws) > 1e-6])
        ws = ws[keep]
    return ws


def solid_intervals(tris, origin, direction):
    """[(enter, exit), ...] along a ray that starts outside the mesh."""
    h = ray_hits(tris, origin, direction)
    return [(h[i], h[i + 1]) for i in range(0, len(h) - 1, 2)]
