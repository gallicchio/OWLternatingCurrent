#!/usr/bin/env python3
"""Size the familiar coin's LED series resistors (uses familiar.py's model).

Goal: at the normal maximum drive (0.2 A in the perch coil) each LED gets at most
~20 mA, and at a firmware fault (0.4 A) neither passes its ~30 mA absolute maximum.
Writes results/familiar_resistors.json.
"""
import json, os
import numpy as np
from familiar import coil, R_at, mutual, simulate, RX, TX

HERE = os.path.dirname(os.path.abspath(__file__))
L2, _ = coil(RX)
M = mutual(3.0e-3)
out = []
for f in (150e3, 330e3):
    R2 = R_at(RX, f)
    for Rs in (0, 22, 47, 68, 100):
        row = dict(f=f, R_series=Rs)
        for I1 in (0.1, 0.2, 0.4):
            io, iv, vp = simulate(f, f, I1, M, L2, R2, r_o=9.0 + Rs, r_v=14.0 + Rs)
            row[f"{I1:.1f}A"] = dict(orange_mA=round(io * 1e3, 1), violet_mA=round(iv * 1e3, 1), vpk=round(vp, 2))
        out.append(row)
        print(f"{f/1e3:3.0f} kHz, R = {Rs:3d} ohm: " + "  ".join(
            f"I1 {k}: orange {v['orange_mA']:5.1f} / violet {v['violet_mA']:5.1f} mA"
            for k, v in row.items() if k.endswith("A")))
json.dump(out, open(os.path.join(HERE, "results", "familiar_resistors.json"), "w"), indent=1)
