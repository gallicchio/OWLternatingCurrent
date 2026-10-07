#!/usr/bin/env python3
"""
run_validation.py -- does the openEMS set-up get known answers right?

V1  A 58 x 1 mm strip dipole in vacuum, at three meshes, against the thin-wire MoM in
    mom_dipole.py (a = w/4).  An answer that cannot be wrong: resonance, resistance,
    and -- because the copper is PEC and there is no dielectric -- the radiation
    efficiency must come out 100 %, which tests the NF2FF/port power bookkeeping.

V2  TI DN007 (SWRU120D) inverted-F replica on 1.0 mm FR4, against TI's measured S11
    (minimum about -24 dB near 2.42 GHz; better than -10 dB over > 300 MHz).  The
    reference board's ground plane is not documented, so two plausible ground
    planes bracket it.  Also: the same antenna on 1.6 mm FR4, and a finer mesh.

usage:  NPAR=5 em-env python run_validation.py
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import antsim  # noqa: E402
import mom_dipole  # noqa: E402
import runner  # noqa: E402
import shapes  # noqa: E402


def jobs():
    J = []
    d = shapes.dipole_freespace()
    for r in (0.5, 0.25, 0.125):
        J.append((f"dipole_fs_r{r}", d, dict(res_fine=r, margin=45.0)))
    # DN007: ground as drawn in SWRU120 (antenna spans the board end), and a larger one
    J.append(("dn007_h1.0_g29x60", shapes.dn007(h=1.0, gnd_l=60.0), dict(res_fine=0.25)))
    J.append(("dn007_h1.0_g50x80", shapes.dn007(h=1.0, gnd_l=80.0, gnd_right=50 - 25.58 - 1.6),
              dict(res_fine=0.25)))
    J.append(("dn007_h1.6_g29x60", shapes.dn007(h=1.6, gnd_l=60.0), dict(res_fine=0.25)))
    J.append(("dn007_h1.0_g29x60_r0.18", shapes.dn007(h=1.0, gnd_l=60.0),
              dict(res_fine=0.18, nz=6)))
    return J


if __name__ == "__main__":
    res = runner.run_many(jobs(), npar=int(os.environ.get("NPAR", 5)), threads=6)
    # MoM reference for V1
    f = np.linspace(2.30e9, 2.55e9, 51)
    rows = []
    for n in (61, 121):
        Z = mom_dipole.sweep(58e-3, 0.25e-3, f, n)
        fr, rr = mom_dipole.resonance(f, Z)
        rows.append(dict(case=f"MoM nseg={n}", f_res=fr / 1e9, r_res=rr))
    for k in sorted(res):
        r = res[k]
        rows.append(dict(case=k, f_res=r["f_res"] / 1e9, r_res=r["r_res"], f_min=r["f_min"] / 1e9,
                         s11_min=r["s11_min_db"], bw_lo=r["bw_lo"] / 1e9, bw_hi=r["bw_hi"] / 1e9,
                         eta=r["eta_rad"][1], D=r["Dmax_dBi"][1], cells=r["cells"],
                         t_min=r["t_run"] / 60))
    fn = os.path.join(antsim.RESULTS, "validation.csv")
    cols = ["case", "f_res", "r_res", "f_min", "s11_min", "bw_lo", "bw_hi", "eta", "D", "cells",
            "t_min"]
    with open(fn, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: (f"{r[c]:.4f}" if isinstance(r.get(c), float) else r.get(c, ""))
                        for c in cols})
    for r in rows:
        print(r)
