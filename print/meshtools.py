#!/usr/bin/env python3
"""Small mesh tools for the print build and its checks (numpy only).

A mesh is an (n, 3, 3) float array of triangles, wound counter-clockwise seen from
outside (STL's and 3MF's convention).
"""
import struct
import zipfile
from xml.sax.saxutils import escape

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


def write_stl(path, tris, name="mesh"):
    tris = np.asarray(tris, np.float32)
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
    p = np.asarray(tris, np.float32).reshape(-1, 3)
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


# ------------------------------------------------------------------ 3MF
def write_3mf(path, objects, title="", designer="", extra_files=None):
    """objects: list of (name, tris_in_local_frame, (tx, ty, tz)).  One <object> each,
    placed by its build item, so slicers list the parts by name."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">']
    if title:
        out.append(' <metadata name="Title">%s</metadata>' % escape(title))
    if designer:
        out.append(' <metadata name="Designer">%s</metadata>' % escape(designer))
    out.append(" <resources>")
    for i, (name, tris, _) in enumerate(objects, 1):
        verts, faces = weld(tris)
        out.append('  <object id="%d" name="%s" type="model"><mesh><vertices>' % (i, escape(name)))
        out.extend('<vertex x="%.5f" y="%.5f" z="%.5f"/>' % tuple(v) for v in verts)
        out.append("</vertices><triangles>")
        out.extend('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in faces)
        out.append("</triangles></mesh></object>")
    out.append(" </resources>\n <build>")
    for i, (_, _, (tx, ty, tz)) in enumerate(objects, 1):
        out.append('  <item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.4f %.4f %.4f"/>' % (i, tx, ty, tz))
    out.append(" </build>\n</model>\n")
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '</Types>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "\n".join(out))
        for name, text in (extra_files or {}).items():
            z.writestr(name, text)


def read_3mf(path):
    """[(name, tris placed by its build item)] -- for the checks."""
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("3D/3dmodel.model"))
    objs = {}
    for o in root.find("m:resources", ns).findall("m:object", ns):
        m = o.find("m:mesh", ns)
        v = np.array([[float(x.get(k)) for k in "xyz"] for x in m.find("m:vertices", ns)])
        f = np.array([[int(t.get(k)) for k in ("v1", "v2", "v3")] for t in m.find("m:triangles", ns)])
        objs[o.get("id")] = (o.get("name"), v[f])
    out = []
    for it in root.find("m:build", ns).findall("m:item", ns):
        name, tris = objs[it.get("objectid")]
        t = [float(x) for x in it.get("transform", "1 0 0 0 1 0 0 0 1 0 0 0").split()]
        R = np.array(t[:9]).reshape(3, 3)
        out.append((name, tris @ R + np.array(t[9:])))
    return out


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


# ------------------------------------------------------------------ Bambu Studio project
BAMBU_APP = "BambuStudio-02.08.02.61"     # the version this layout was verified with


def write_bambu_3mf(path, objects, settings, title="", designer="", pauses=(), note=""):
    """A Bambu Studio project: the objects (as write_3mf), Bambu's project settings
    (`settings`, the JSON text of Metadata/project_settings.config: Bambu Studio needs a
    full set), and custom G-code run before each layer listed in `pauses` as
    (layer top z, [G-code lines]).  Layout as Bambu Studio 2.8 writes it: per-object
    meshes in 3D/Objects, a production-extension 3dmodel.model placing them,
    Metadata/model_settings.config naming them, Metadata/custom_gcode_per_layer.xml
    (type 4 = custom G-code)."""
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')
    uid = lambda a, b: "%08x-%04x-4c03-9d28-80fed5dfa1dc" % (a, b)
    files = {}
    rels = []
    top = ['<?xml version="1.0" encoding="UTF-8"?>', '<model unit="millimeter" xml:lang="en-US" %s>' % ns,
           ' <metadata name="Application">%s</metadata>' % BAMBU_APP,
           ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
           ' <metadata name="Title">%s</metadata>' % escape(title),
           ' <metadata name="Designer">%s</metadata>' % escape(designer),
           ' <metadata name="Description">%s</metadata>' % escape(note),
           " <resources>"]
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    items = []
    for k, (name, tris, (tx, ty, tz)) in enumerate(objects, 1):
        mesh_id, obj_id = 2 * k - 1, 2 * k
        verts, faces = weld(tris)
        m = ['<?xml version="1.0" encoding="UTF-8"?>', '<model unit="millimeter" xml:lang="en-US" %s>' % ns,
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>', " <resources>",
             '  <object id="%d" p:UUID="%s" type="model">' % (mesh_id, uid(k << 16, 0)), "   <mesh>", "    <vertices>"]
        m.extend('     <vertex x="%.5f" y="%.5f" z="%.5f"/>' % tuple(v) for v in verts)
        m.append("    </vertices>\n    <triangles>")
        m.extend('     <triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in faces)
        m.append("    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n")
        fn = "3D/Objects/object_%d.model" % k
        files[fn] = "\n".join(m)
        rels.append(' <Relationship Target="/%s" Id="rel-%d" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>' % (fn, k))
        top.append('  <object id="%d" p:UUID="%s" type="model">\n   <components>\n'
                   '    <component p:path="/%s" objectid="%d" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
                   '   </components>\n  </object>' % (obj_id, uid(k, 0), fn, mesh_id, uid(k << 16, 1)))
        items.append('  <item objectid="%d" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 %.4f %.4f %.4f" printable="1"/>'
                     % (obj_id, uid(k, 2), tx, ty, tz))
        cfg += ['  <object id="%d">' % obj_id,
                '    <metadata key="name" value="%s"/>' % escape(name, {'"': "&quot;"}),
                '    <metadata key="extruder" value="1"/>',
                '    <part id="%d" subtype="normal_part">' % mesh_id,
                '      <metadata key="name" value="%s"/>' % escape(name, {'"': "&quot;"}),
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                "    </part>", "  </object>"]
    top.append(" </resources>")
    top.append(' <build p:UUID="%s">' % uid(0xb0, 3))
    top += items
    top.append(" </build>\n</model>\n")
    cfg += ["  <plate>", '    <metadata key="plater_id" value="1"/>', '    <metadata key="plater_name" value=""/>',
            '    <metadata key="locked" value="false"/>', "  </plate>", "  <assemble>", "  </assemble>",
            "</config>\n"]
    gc = ['<?xml version="1.0" encoding="utf-8"?>', "<custom_gcodes_per_layer>", "<plate>", '<plate_info id="1"/>']
    for z, lines in pauses:
        g = "&#10;".join(escape(ln, {'"': "&quot;"}) for ln in lines)
        gc.append('<layer top_z="%g" type="4" extruder="1" color="" extra="%s" gcode="%s"/>' % (z, g, g))
    gc += ['<mode value="SingleExtruder"/>', "</plate>", "</custom_gcodes_per_layer>\n"]
    files["3D/3dmodel.model"] = "\n".join(top)
    files["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                                            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                                            + "\n".join(rels) + "\n</Relationships>\n")
    files["Metadata/model_settings.config"] = "\n".join(cfg)
    files["Metadata/custom_gcode_per_layer.xml"] = "\n".join(gc)
    files["Metadata/project_settings.config"] = settings
    files["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
                            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    files["[Content_Types].xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types '
                                    'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                                    ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                                    ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                                    ' <Default Extension="xml" ContentType="application/xml"/>\n'
                                    ' <Default Extension="config" ContentType="application/xml"/>\n</Types>\n')
    order = ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "3D/_rels/3dmodel.model.rels"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order + sorted(k for k in files if k not in order):
            z.writestr(n, files[n])
