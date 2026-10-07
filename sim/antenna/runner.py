#!/usr/bin/env python3
"""
runner.py -- run many antsim cases at once.

openEMS is memory-bandwidth bound and stops scaling at 4-8 threads, so the 32 cores
are used as several independent solves (FIELD_SOLVER.md, section 7).  Each case is
cached by antsim.run() under out/<name>_<hash>/, so re-running a study only
computes what changed.
"""
import os
import sys
import time
import traceback
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import antsim  # noqa: E402


def _job(args):
    name, design, sim = args
    t0 = time.time()
    try:
        r = antsim.run(design, sim, name=name)
        return name, r, None, time.time() - t0
    except Exception:
        return name, None, traceback.format_exc(), time.time() - t0


def run_many(jobs, npar=None, threads=None):
    """jobs: list of (name, design, sim).  Returns {name: summary}."""
    npar = npar or int(os.environ.get("NPAR", 5))
    if threads:
        jobs = [(n, d, dict(s or {}, threads=threads)) for (n, d, s) in jobs]
    out = {}
    ctx = get_context("fork")
    with ctx.Pool(npar, maxtasksperchild=1) as pool:
        for name, r, err, dt in pool.imap_unordered(_job, jobs):
            if err:
                print(f"[FAIL] {name} ({dt/60:.1f} min)\n{err}", flush=True)
            else:
                out[name] = r
                print(antsim.fmt(r), flush=True)
    return out
