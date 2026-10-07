#!/usr/bin/env python3
"""
antsim.py -- a parametric openEMS (FDTD) model of a printed antenna at the edge of a
PCB ground plane, plus the post-processing every study in this directory shares.

Geometry convention (all lengths in mm):

  * The board lies in the xy-plane and the FR4 occupies 0 <= z <= h.
  * The antenna is zero-thickness copper on the top surface, z = h.  It is PEC by
    default; `sim['cu_loss']` makes it a 35 um conducting sheet (sigma = 5.8e7 S/m),
    which is how the conductor loss is quantified.  Zero thickness is justified at
    2.4 GHz: 35 um is 1/200 of the 0.25 mm cell and 1/3500 of a wavelength, and the
    one thing thickness does -- add a little edge capacitance to a narrow trace -- is
    far below the FR4 tolerance (see README).
  * The ground plane is a solid PEC block over the ground region, 0 <= z <= h.  That
    is the limit of a top pour and a bottom (and inner) plane stitched by vias at a
    pitch << lambda/10; it also means a 2-layer and a 4-layer board are the same
    model, as long as every layer is cleared under the antenna.
  * The ground edge that faces the antenna is y = 0; the antenna lives at y > 0.
  * The feed is a lumped port in the plane of the top copper, bridging a small gap
    between the end of the feed trace and the ground edge.  Its plane is the
    antenna's reference plane: what a 50-ohm line / the pi network would see.

A design is a plain dict (so it hashes into a cache key):

    polys   : list of (N,2) point lists -- top copper polygons (union is the metal)
    port    : dict(x0, x1, y0, y1, dir='x'|'y', R=50)       -- in the plane z = h
    ground  : (x0, x1, y0, y1) or None                       -- PEC block, z in [0,h]
    fr4     : list of (x0, x1, y0, y1) rectangles of bare FR4 (board outline)
    h, er, tand                                              -- substrate (er None: no FR4)
    cover   : optional dict(x0,x1,y0,y1, gap, t, er, tand)  -- e.g. a PLA lid
    blocks  : optional list of dict(x0,x1,y0,y1,z0,z1, er, sigma) -- e.g. a hand
    fine    : optional (x0, x1, y0, y1) region that gets the fine mesh

The FDTD and mesh settings are a second dict (`sim`), see DEFAULT_SIM.

Lessons carried over from SMABridgeTestAnalysis/fieldsolver (FIELD_SOLVER.md):
grade the mesh out of the dielectric, never step it; use 32 cores as many
independent 4-6-thread solves, because openEMS is memory-bandwidth bound; put a model
revision into every cache key; and ask the rasteriser what it actually built
(`pec_dump`) instead of trusting the drawing.
"""
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RESULTS = os.path.join(HERE, "results")

MODEL_REV = 3          # bump whenever the geometry/port/mesh *code* changes meaning

C0 = 299792458.0
EPS0 = 8.8541878128e-12
SIGMA_CU = 5.8e7
T_CU = 0.035

DEFAULT_SIM = dict(
    res_fine=0.25,      # mm, uniform cell over the antenna (and 'fine' box)
    res_gnd=2.0,        # mm, over the ground plane
    res_air=4.0,        # mm, max cell in air  (lambda0/25 at 3 GHz)
    ratio=1.3,          # max neighbour-cell ratio when grading
    nz=5,               # cells across the substrate thickness
    margin=55.0,        # mm of air from the structure to the domain edge (PML inside it)
    pad=4.0,            # mm of fine mesh around the antenna's bounding box
    pml=8,
    f0=2.5e9, fc=1.0e9,  # Gaussian excitation (centre, 20 dB half-width)
    end=1e-5,           # energy end criterion (-50 dB)
    nrts=400000,
    f_nf=[2.40e9, 2.44e9, 2.48e9],   # NF2FF frequencies (frequency-domain dumps)
    f_lo=1.8e9, f_hi=3.2e9, nf=1401,
    cu_loss=False,
    hdump=False,        # dump |H| just above the copper at 2.44 GHz (current map)
    threads=4,
)


def kappa(er, tand, f=2.45e9):
    """Conductivity that gives loss tangent `tand` at frequency f."""
    return 2 * np.pi * f * EPS0 * er * tand


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, float):
        return round(o, 6)
    return o


def case_key(design, sim):
    # everything that can change the answer, and nothing that cannot (threads)
    sim = {k: v for k, v in sim.items() if k not in ("threads",)}
    blob = json.dumps(dict(rev=MODEL_REV, design=_jsonable(design), sim=_jsonable(sim)),
                      sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()[:10]


# --------------------------------------------------------------------------- mesh
def _bbox(design):
    pts = [np.asarray(p, float) for p in design["polys"]]
    P = np.vstack(pts)
    p = design["port"]
    x0 = min(P[:, 0].min(), p["x0"], p["x1"])
    x1 = max(P[:, 0].max(), p["x0"], p["x1"])
    y0 = min(P[:, 1].min(), p["y0"], p["y1"])
    y1 = max(P[:, 1].max(), p["y0"], p["y1"])
    return x0, x1, y0, y1


def _structure_bbox(design):
    x0, x1, y0, y1 = _bbox(design)
    for r in ([design["ground"]] if design.get("ground") else []) + list(design.get("fr4", [])):
        x0, x1, y0, y1 = min(x0, r[0]), max(x1, r[1]), min(y0, r[2]), max(y1, r[3])
    for b in design.get("blocks", []):
        x0, x1, y0, y1 = min(x0, b["x0"]), max(x1, b["x1"]), min(y0, b["y0"]), max(y1, b["y1"])
    return x0, x1, y0, y1


def build_mesh(mesh, design, sim):
    """Fine uniform cells over the antenna, graded to the ground and then to air."""
    r = sim["res_fine"]
    h = design["h"]
    p = design["port"]
    if design.get("fine"):
        fx0, fx1, fy0, fy1 = design["fine"]
    else:
        fx0, fx1, fy0, fy1 = _bbox(design)
        fx0 -= sim["pad"]; fx1 += sim["pad"]; fy0 -= sim["pad"]; fy1 += sim["pad"]

    # 1) fine region: fixed lines at the port edges and the ground edge, then fill
    xs = [fx0, fx1, p["x0"], p["x1"]]
    ys = [fy0, fy1, p["y0"], p["y1"]]
    g = design.get("ground")
    if g is not None and fy0 <= g[3] <= fy1:
        ys.append(g[3])
    for extra in design.get("lines_x", []):
        xs.append(extra)
    for extra in design.get("lines_y", []):
        ys.append(extra)
    mesh.AddLine("x", xs)
    mesh.AddLine("y", ys)
    mesh.SmoothMeshLines("x", r, ratio=1.2)
    mesh.SmoothMeshLines("y", r, ratio=1.2)

    # 2) the ground plane and the FR4 outline
    xg, yg = [], []
    for rect in ([g] if g is not None else []) + list(design.get("fr4", [])):
        xg += [rect[0], rect[1]]
        yg += [rect[2], rect[3]]
    for b in design.get("blocks", []):
        xg += [b["x0"], b["x1"]]
        yg += [b["y0"], b["y1"]]
    if design.get("cover"):
        c = design["cover"]
        xg += [c["x0"], c["x1"]]
        yg += [c["y0"], c["y1"]]
    # keep only those outside the fine box (inside it the fine grid already serves)
    xg = [v for v in xg if v < fx0 - 1e-6 or v > fx1 + 1e-6]
    yg = [v for v in yg if v < fy0 - 1e-6 or v > fy1 + 1e-6]
    if xg:
        mesh.AddLine("x", xg)
    if yg:
        mesh.AddLine("y", yg)
    mesh.SmoothMeshLines("x", sim["res_gnd"], ratio=sim["ratio"])
    mesh.SmoothMeshLines("y", sim["res_gnd"], ratio=sim["ratio"])

    # 3) air out to the domain edge
    sx0, sx1, sy0, sy1 = _structure_bbox(design)
    m = sim["margin"]
    mesh.AddLine("x", [sx0 - m, sx1 + m])
    mesh.AddLine("y", [sy0 - m, sy1 + m])
    mesh.SmoothMeshLines("x", sim["res_air"], ratio=sim["ratio"])
    mesh.SmoothMeshLines("y", sim["res_air"], ratio=sim["ratio"])

    # z: substrate cells, graded (not stepped) into the air on both sides
    if h > 0:
        zl = list(np.linspace(0.0, h, sim["nz"] + 1))
    else:
        zl = list(np.arange(-2 * r, 2 * r + 1e-9, r))
    ztop = h
    if design.get("cover"):
        c = design["cover"]
        zc0 = h + c["gap"]
        zc1 = zc0 + c["t"]
        nzc = max(2, int(np.ceil(c["t"] / (h / sim["nz"] if h > 0 else r))))
        zl += list(np.linspace(zc0, zc1, nzc + 1))
        ztop = zc1
    for b in design.get("blocks", []):
        # lossy high-er blocks (a hand): <= 2 mm cells through them (lambda/10 in tissue)
        zl += list(np.linspace(b["z0"], b["z1"], int(np.ceil((b["z1"] - b["z0"]) / 2.0)) + 1))
        ztop = max(ztop, b["z1"])
    zbot = min([0.0] + [b["z0"] for b in design.get("blocks", [])])
    mesh.AddLine("z", zl)
    mesh.SmoothMeshLines("z", h / sim["nz"] if h > 0 else r, ratio=1.2)
    mesh.AddLine("z", [zbot - m, ztop + m])
    mesh.SmoothMeshLines("z", sim["res_air"], ratio=sim["ratio"])
    return mesh


# --------------------------------------------------------------------------- model
def build(design, sim):
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    h = design["h"]
    FDTD = openEMS(NrTS=sim["nrts"], EndCriteria=sim["end"])
    FDTD.SetGaussExcite(sim["f0"], sim["fc"])
    FDTD.SetBoundaryCond([f"PML_{sim['pml']}"] * 6)
    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1e-3)

    # substrate
    if design.get("er"):
        fr4 = CSX.AddMaterial("FR4", epsilon=design["er"],
                              kappa=kappa(design["er"], design["tand"]))
        for (x0, x1, y0, y1) in design["fr4"]:
            fr4.AddBox([x0, y0, 0.0], [x1, y1, h], priority=1)
    if design.get("cover"):
        c = design["cover"]
        cov = CSX.AddMaterial("cover", epsilon=c["er"], kappa=kappa(c["er"], c["tand"]))
        cov.AddBox([c["x0"], c["y0"], h + c["gap"]],
                   [c["x1"], c["y1"], h + c["gap"] + c["t"]], priority=2)
    for i, b in enumerate(design.get("blocks", [])):
        mat = CSX.AddMaterial(f"block{i}", epsilon=b["er"], kappa=b["sigma"])
        mat.AddBox([b["x0"], b["y0"], b["z0"]], [b["x1"], b["y1"], b["z1"]], priority=3)

    # ground block
    if design.get("ground"):
        gx0, gx1, gy0, gy1 = design["ground"]
        gnd = CSX.AddMetal("GND")
        gnd.AddBox([gx0, gy0, 0.0], [gx1, gy1, h], priority=10)

    # antenna copper
    if sim["cu_loss"]:
        cu = CSX.AddConductingSheet("CU", conductivity=SIGMA_CU, thickness=T_CU * 1e-3)
    else:
        cu = CSX.AddMetal("CU")
    for P in design["polys"]:
        P = np.asarray(P, float)
        cu.AddPolygon(points=[P[:, 0], P[:, 1]], norm_dir="z", elevation=h, priority=10)

    build_mesh(mesh, design, sim)

    p = design["port"]
    port = FDTD.AddLumpedPort(1, p.get("R", 50.0), [p["x0"], p["y0"], h],
                              [p["x1"], p["y1"], h], p["dir"], 1.0, priority=20)

    nf2ff = FDTD.CreateNF2FFBox(frequency=list(sim["f_nf"]))
    hdump = None
    if sim.get("hdump"):
        zl = np.array(mesh.GetLines("z"))
        zup = zl[zl > h + 1e-9][0]
        zd = 0.5 * (h + zup)
        x0, x1, y0, y1 = _bbox(design)
        hdump = CSX.AddDump("Hplane", dump_type=11, dump_mode=1, file_type=1)
        hdump.SetFrequency([2.44e9])
        hdump.AddBox([x0 - 3, y0 - 3, zd], [x1 + 3, y1 + 3, zd])
    return FDTD, CSX, port, nf2ff


def grid_info(CSX):
    g = CSX.GetGrid()
    nl = [len(g.GetLines(d)) for d in "xyz"]
    dmin = [np.min(np.diff(g.GetLines(d))) for d in "xyz"]
    return nl, dmin


# --------------------------------------------------------------------------- run
def run(design, sim=None, name=None, force=False, keep_fields=True, verbose=0):
    """Run (or load from cache) one case.  Returns the summary dict."""
    s = dict(DEFAULT_SIM)
    s.update(sim or {})
    name = name or design.get("name", "case")
    key = case_key(design, s)
    tag = f"{name}_{key}"
    sim_path = os.path.join(OUT, tag)
    res_npz = os.path.join(sim_path, "result.npz")
    res_json = os.path.join(RESULTS, f"{tag}.json")
    if not force and os.path.exists(res_npz) and os.path.exists(res_json):
        with open(res_json) as fh:
            return json.load(fh)

    os.makedirs(sim_path, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(sim_path, "case.json"), "w") as fh:
        json.dump(dict(rev=MODEL_REV, design=_jsonable(design), sim=_jsonable(s)), fh, indent=1)

    FDTD, CSX, port, nf2ff = build(design, s)
    nl, dmin = grid_info(CSX)
    log = os.path.join(sim_path, "openems.log")
    t0 = time.time()
    # openEMS writes to the C-level stdout: redirect it into the case's log file
    sys.stdout.flush()
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    saved = os.dup(1)
    os.dup2(fd, 1)
    try:
        FDTD.Run(sim_path, cleanup=False, numThreads=s["threads"], verbose=max(verbose, 1))
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(fd)
        os.close(saved)
    t_run = time.time() - t0

    out = postprocess(design, s, sim_path, port, nf2ff)
    out.update(name=name, key=key, tag=tag, cells=int(np.prod(nl)), grid=nl,
               dmin=[float(v) for v in dmin], t_run=t_run, rev=MODEL_REV,
               nts=_timesteps(log))
    np.savez_compressed(res_npz, **{k: v for k, v in out["_arrays"].items()})
    summ = {k: v for k, v in out.items() if k != "_arrays"}
    summ["design_name"] = design.get("name")
    summ["params"] = _jsonable(design.get("params", {}))
    summ["sim"] = _jsonable({k: s[k] for k in ("res_fine", "res_gnd", "res_air", "nz",
                                               "margin", "end", "cu_loss")})
    with open(res_json, "w") as fh:
        json.dump(_jsonable(summ), fh, indent=1)
    if not keep_fields:
        for fn in os.listdir(sim_path):
            if fn.endswith(".h5") and not fn.startswith("nf2ff_res"):
                os.remove(os.path.join(sim_path, fn))
    return _jsonable(summ)


def _timesteps(log):
    n = None
    try:
        with open(log, errors="ignore") as fh:
            for line in fh:
                if "Time for" in line and "iterations" in line:
                    try:
                        n = int(line.split("Time for")[1].split("iterations")[0])
                    except ValueError:
                        pass
    except OSError:
        pass
    return n


def band_edges(f, s11db, thr=-10.0, f_ref=2.44e9):
    """The contiguous band around f_ref (or around the S11 minimum) below thr."""
    below = s11db < thr
    i_ref = int(np.argmin(abs(f - f_ref)))
    if not below[i_ref]:
        i_ref = int(np.argmin(s11db))
        if not below[i_ref]:
            return np.nan, np.nan
    i0 = i_ref
    while i0 > 0 and below[i0 - 1]:
        i0 -= 1
    i1 = i_ref
    while i1 < len(f) - 1 and below[i1 + 1]:
        i1 += 1

    def interp(ia, ib):
        ya, yb = s11db[ia], s11db[ib]
        if ya == yb:
            return f[ia]
        return f[ia] + (thr - ya) / (yb - ya) * (f[ib] - f[ia])

    flo = interp(i0 - 1, i0) if i0 > 0 else np.nan
    fhi = interp(i1, i1 + 1) if i1 < len(f) - 1 else np.nan
    return flo, fhi


def postprocess(design, s, sim_path, port, nf2ff):
    f = np.linspace(s["f_lo"], s["f_hi"], s["nf"])
    port.CalcPort(sim_path, f)
    s11 = port.uf_ref / port.uf_inc
    zin = port.uf_tot / port.if_tot
    s11db = 20 * np.log10(np.abs(s11))
    i_min = int(np.argmin(s11db))
    flo, fhi = band_edges(f, s11db)

    # resonance in the X = 0 sense too (first upward zero crossing near the band)
    def at(fq):
        i = int(np.argmin(abs(f - fq)))
        return i

    f_nf = np.array(s["f_nf"], float)
    port.CalcPort(sim_path, f_nf)
    P_acc = np.real(port.P_acc)
    s11_nf = port.uf_ref / port.uf_inc

    theta = np.arange(0.0, 180.0 + 1e-9, 2.0)
    phi = np.arange(0.0, 360.0, 4.0)
    h = design["h"]
    cx = 0.5 * (_bbox(design)[0] + _bbox(design)[1])
    cy = 0.5 * (_bbox(design)[2] + _bbox(design)[3])
    ff = nf2ff.CalcNF2FF(sim_path, f_nf, theta, phi, center=[cx * 1e-3, cy * 1e-3, h * 1e-3],
                         read_cached=False)
    Prad = np.array(ff.Prad, float)
    Dmax = np.array(ff.Dmax, float)
    eta = Prad / P_acc
    mism = 1 - np.abs(s11_nf) ** 2
    E_norm = np.array([np.abs(e) for e in ff.E_norm], dtype=np.float32)
    E_th = np.array([np.abs(e) for e in ff.E_theta], dtype=np.float32)
    E_ph = np.array([np.abs(e) for e in ff.E_phi], dtype=np.float32)

    # series resonance: Im(Zin) crossing zero upward, the one nearest 2.44 GHz
    X = zin.imag
    ix = np.where((X[:-1] < 0) & (X[1:] >= 0))[0]
    if len(ix):
        fx = f[ix] - X[ix] * (f[ix + 1] - f[ix]) / (X[ix + 1] - X[ix])
        k = int(np.argmin(abs(fx - 2.44e9)))
        f_res = float(fx[k])
        r_res = float(np.interp(f_res, f, zin.real))
    else:
        f_res, r_res = float("nan"), float("nan")

    i244 = at(2.44e9)
    arrays = dict(f=f, s11=s11, zin=zin, f_nf=f_nf, P_acc=P_acc, Prad=Prad, Dmax=Dmax,
                  eta=eta, s11_nf=s11_nf, theta=theta, phi=phi, E_norm=E_norm,
                  E_theta=E_th, E_phi=E_ph)
    k244 = int(np.argmin(abs(f_nf - 2.44e9)))
    out = dict(
        f_min=float(f[i_min]), s11_min_db=float(s11db[i_min]), f_res=f_res, r_res=r_res,
        bw_lo=float(flo), bw_hi=float(fhi),
        bw=float(fhi - flo) if np.isfinite(flo) and np.isfinite(fhi) else float("nan"),
        s11_2400=float(s11db[at(2.40e9)]), s11_2440=float(s11db[i244]),
        s11_2484=float(s11db[at(2.484e9)]),
        s11_worst_band=float(np.max(s11db[(f >= 2.40e9) & (f <= 2.484e9)])),
        zin_2440=[float(zin[i244].real), float(zin[i244].imag)],
        f_nf=f_nf.tolist(), eta_rad=eta.tolist(), Dmax_dBi=(10 * np.log10(Dmax)).tolist(),
        gain_dBi=(10 * np.log10(Dmax * eta)).tolist(),
        realized_gain_dBi=(10 * np.log10(Dmax * eta * mism)).tolist(),
        eta_tot=(eta * mism).tolist(),
        _arrays=arrays,
    )
    return out


# --------------------------------------------------------------------------- checks
def pec_dump(design, sim=None):
    """Ask the rasteriser which Yee edges it made PEC.  Returns (points_mm, lines)."""
    import tempfile
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    s = dict(DEFAULT_SIM)
    s.update(sim or {})
    s["nrts"] = 10
    FDTD, CSX, port, nf2ff = build(design, s)
    sp = tempfile.mkdtemp(prefix="pec_", dir=OUT)
    try:
        sys.stdout.flush()
        fd = os.open(os.devnull, os.O_WRONLY)
        saved = os.dup(1)
        os.dup2(fd, 1)
        try:
            FDTD.Run(sp, cleanup=True, verbose=0, setup_only=True, debug_PEC=True)
        finally:
            os.dup2(saved, 1)
            os.close(fd)
            os.close(saved)
        rd = vtk.vtkXMLPolyDataReader()
        rd.SetFileName(os.path.join(sp, "PEC_dump.vtp"))
        rd.Update()
        o = rd.GetOutput()
        pts = vtk_to_numpy(o.GetPoints().GetData()) * 1e3
        lines = vtk_to_numpy(o.GetLines().GetData()).reshape(-1, 3)[:, 1:]
        grid = [np.array(CSX.GetGrid().GetLines(d)) for d in "xyz"]
    finally:
        shutil.rmtree(sp, ignore_errors=True)
    return pts, lines, grid


def load(tag_or_json):
    """Load a finished case: (summary dict, arrays dict)."""
    if tag_or_json.endswith(".json"):
        with open(tag_or_json) as fh:
            summ = json.load(fh)
    else:
        with open(os.path.join(RESULTS, f"{tag_or_json}.json")) as fh:
            summ = json.load(fh)
    arr = dict(np.load(os.path.join(OUT, summ["tag"], "result.npz")))
    return summ, arr


def fmt(summ):
    eta = summ["eta_rad"]
    k = len(eta) // 2
    return (f"{summ['name']:<28s} fmin={summ['f_min']/1e9:6.3f} GHz  S11min={summ['s11_min_db']:6.1f} dB  "
            f"BW10=[{summ['bw_lo']/1e9:5.3f},{summ['bw_hi']/1e9:5.3f}] "
            f"worst-in-band={summ['s11_worst_band']:6.1f} dB  "
            f"Z(2.44)={summ['zin_2440'][0]:6.1f}{summ['zin_2440'][1]:+6.1f}j  "
            f"eta={100*eta[k]:5.1f}%  G={summ['gain_dBi'][k]:5.2f} dBi  "
            f"cells={summ['cells']/1e6:4.2f}M  t={summ['t_run']/60:5.1f} min")
