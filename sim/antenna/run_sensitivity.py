#!/usr/bin/env python3
"""
run_sensitivity.py -- how far do the two finalists move with the things a hobby build
does not control?

  scale +/-5 %      the whole shape about its feed point (artwork / fab / a re-draw)
  er 4.2 / 4.6      JLCPCB FR4 lot-to-lot, 7628 prepreg vs core (nominal 4.4)
  PLA lid           2 mm PLA (er 2.7, tan d 0.01) lying directly on the copper
  hand              a palm-sized tissue block (er 40, sigma 1.5 S/m) 15 mm over it
  conductor loss    the antenna copper as a 35 um, 5.8e7 S/m sheet instead of PEC
  mesh              0.35 / 0.25 / 0.18 mm on the nominal design (convergence)

Differences are computed at 0.35 mm (the systematic mesh error is common to both
sides of a difference and cancels); the absolute numbers come from the 0.25 mm
stage-C runs and the 0.18 mm convergence run.

usage:  NPAR=6 THREADS=4 em-env python run_sensitivity.py ghost|bat [subset...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import antsim  # noqa: E402
import runner  # noqa: E402
from run_candidates import BAT_PM, bat_design, ghost_design  # noqa: E402

MID = dict(res_fine=0.35, nz=5)
COARSE = dict(res_fine=0.5, nz=4)


def family(which):
    if which == "ghost":
        return "ghost", ghost_design
    if which == "bat":
        return "batpm", lambda **kw: bat_design(BAT_PM, **kw)
    raise ValueError(which)


def jobs(which, subset=None):
    tag, mk = family(which)
    # the bat is ~2.5x the ghost's area: its differences are taken on the 0.5 mm mesh,
    # with 0.35 mm as the extra convergence point (0.25 mm is the stage-C run)
    MESH = MID if which == "ghost" else COARSE
    base = mk()
    p = base["params"]
    keep = dict(tab_w=p["tab_w"], tab_h=p["tab_h"])     # same FR4 tab for every variant
    J = [(f"S_{tag}_nominal", base, MESH)]
    for sc in (0.95, 1.05):
        J.append((f"S_{tag}_scale{sc:g}", mk(scale=sc, **keep), MESH))
    for er in (4.2, 4.6):
        J.append((f"S_{tag}_er{er:g}", mk(er=er, **keep), MESH))
    J.append((f"S_{tag}_pla2mm", mk(cover=dict(gap=0.0, t=2.0, er=2.7, tand=0.01), **keep),
              MESH))
    hand = mk(**keep)
    hand["blocks"] = [dict(x0=-40.0, x1=40.0, y0=-60.0, y1=p["tab_h"] + 20.0,
                           z0=hand["h"] + 15.0, z1=hand["h"] + 35.0, er=40.0, sigma=1.5)]
    J.append((f"S_{tag}_hand15mm", hand, MESH))
    J.append((f"S_{tag}_culoss", base, dict(MESH, cu_loss=True)))
    if which == "ghost":
        J.append((f"S_{tag}_mesh0.18", base, dict(res_fine=0.18, nz=7)))
    else:
        J.append((f"S_{tag}_mesh0.35", base, MID))
    if subset:
        J = [j for j in J if any(w in j[0] for w in subset)]
    return J


if __name__ == "__main__":
    which = sys.argv[1]
    J = jobs(which, sys.argv[2:])
    res = runner.run_many(J, npar=int(os.environ.get("NPAR", 6)),
                          threads=int(os.environ.get("THREADS", 4)))
    print()
    for name, _, _ in J:
        if name in res:
            print(antsim.fmt(res[name]))
