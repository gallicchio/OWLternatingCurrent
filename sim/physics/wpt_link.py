#!/usr/bin/env python3
"""Inductive power to a 'familiar': a figurine whose LEDs light with no battery.

Base board: a 4-layer PCB spiral (the 'perch' coil).  Familiar: a small 2-layer
PCB spiral in the figurine's base, a few mm above (PLA floor + air).

For each frequency this computes the coils' L, R and Q, the coupling k against
the gap, the best-case link efficiency k^2 Q1 Q2 / (1+sqrt(1+k^2 Q1 Q2))^2, and
the TX coil current needed to deliver P_LED to a matched load.  It also checks
how far apart two familiars' resonant frequencies must be for the base to light
one without the other (frequency-division addressing).

Writes results/wpt_link.json and results/wpt_link.png.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import magnetics as mg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)

# --- geometry -----------------------------------------------------------------
# TX: 4 layers of JLC04161H-7628 (L1-L2 0.21 mm, L2-L3 1.065 mm, L3-L4 0.21 mm),
# 1 oz outer / 0.5 oz inner unless 2 oz is ordered.
TX = dict(r_out=16e-3, r_in=6e-3, n=10, w=0.6e-3,
          z=[0.0, -0.21e-3, -1.275e-3, -1.485e-3], t=[mg.OZ, mg.OZ / 2, mg.OZ / 2, mg.OZ])
# RX: 2-layer 0.8 mm board inside the figurine's base, 1 oz both sides.
RX = dict(r_out=12e-3, r_in=4e-3, n=8, w=0.5e-3, z=[0.0, -0.8e-3], t=[mg.OZ, mg.OZ])


def coil_props(c, f):
    L = mg.L_multilayer(c["n"], c["r_out"], c["r_in"], c["z"])
    turn_len = 2 * np.pi * 0.5 * (c["r_out"] + c["r_in"]) * c["n"]
    R = sum(mg.R_trace(turn_len, c["w"], t, f) for t in c["t"])
    R *= 1.3          # proximity effect between turns, a typical allowance at these spacings
    return L, R, 2 * np.pi * f * L / R


def mutual(gap):
    """TX top layer at z=0; RX bottom layer 'gap' above it."""
    rt = np.linspace(TX["r_out"], TX["r_in"], TX["n"])
    rr = np.linspace(RX["r_out"], RX["r_in"], RX["n"])
    M = 0.0
    for zt in TX["z"]:
        for zr in RX["z"]:
            d = gap + (zr - RX["z"][-1]) - zt
            M += sum(mg.mutual_coaxial_loops(a, b, d) for a in rt for b in rr)
    return M


def main():
    freqs = [150e3, 400e3, 1e6, 2e6, 6.78e6]
    gaps = np.array([2, 3, 4, 6, 8, 10, 15]) * 1e-3
    res = {"tx": {k: v for k, v in TX.items()}, "rx": {k: v for k, v in RX.items()}, "rows": []}
    Ltx, _, _ = coil_props(TX, 1e5)
    Lrx, _, _ = coil_props(RX, 1e5)
    Ms = np.array([mutual(g) for g in gaps])
    ks = Ms / np.sqrt(Ltx * Lrx)
    print(f"L_tx = {Ltx*1e6:.2f} uH, L_rx = {Lrx*1e6:.2f} uH")
    for g, M, k in zip(gaps, Ms, ks):
        print(f"  gap {g*1e3:4.1f} mm: M = {M*1e6:6.3f} uH, k = {k:.3f}")
    P_led = 0.15     # W into the familiar's LEDs (e.g. 4 LEDs at 15 mA, ~2.5 V)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for f in freqs:
        _, R1, Q1 = coil_props(TX, f)
        _, R2, Q2 = coil_props(RX, f)
        eta = [mg.link_eta_max(k, Q1, Q2) for k in ks]
        # matched series-series link: optimum load R_L = R2*sqrt(1+k^2 Q1 Q2);
        # P_L = (w M I1)^2 R_L / (R2+R_L)^2  ->  I1 needed
        I1 = []
        for M, k in zip(Ms, ks):
            x = k * k * Q1 * Q2
            RL = R2 * np.sqrt(1 + x)
            w = 2 * np.pi * f
            I1.append(np.sqrt(P_led * (R2 + RL) ** 2 / RL) / (w * M))
        row = dict(f=f, R_tx=R1, Q_tx=Q1, R_rx=R2, Q_rx=Q2,
                   eta=[float(e) for e in eta], I_tx=[float(i) for i in I1])
        res["rows"].append(row)
        print(f"f={f/1e3:7.0f} kHz: R_tx={R1:.2f} ohm Q_tx={Q1:5.1f}  R_rx={R2:.2f} Q_rx={Q2:5.1f}  "
              + "  ".join(f"{g*1e3:.0f}mm: eta={e*100:4.1f}% I1={i:.2f}A" for g, e, i in zip(gaps, eta, I1)))
        ax[0].plot(gaps * 1e3, np.array(eta) * 100, "o-", label=f"{f/1e6:g} MHz")
        ax[1].semilogy(gaps * 1e3, I1, "o-", label=f"{f/1e6:g} MHz")
    ax[0].set(xlabel="gap TX top copper to RX bottom copper (mm)", ylabel="best link efficiency (%)",
              title="Familiar link: efficiency vs gap")
    ax[1].set(xlabel="gap (mm)", ylabel=f"TX coil current for {P_led*1e3:.0f} mW to LEDs (A rms)",
              title="TX current needed")
    for a in ax:
        a.grid(True, alpha=0.3)
        a.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "wpt_link.png"), dpi=120)
    res["L_tx"], res["L_rx"] = Ltx, Lrx
    res["gaps"] = gaps.tolist()
    res["M"] = Ms.tolist()
    res["k"] = ks.tolist()

    # Frequency-division addressing: two familiars, each a series-resonant RX
    # loaded by its LEDs (loaded Q_L).  Power ratio delivered off-resonance.
    print("\nfrequency addressing (series RX, loaded Q):")
    sel = []
    for QL in (3, 5, 8, 12):
        for ratio in (1.25, 1.5, 2.0, 3.0):
            u = ratio - 1 / ratio
            att = 1 / (1 + (QL * u) ** 2)
            sel.append(dict(QL=QL, f_ratio=ratio, power_ratio=att))
        print(f"  Q_L={QL:2d}: power leaked at f2/f1=1.25,1.5,2,3: "
              + ", ".join(f"{s['power_ratio']*100:5.1f}%" for s in sel[-4:]))
    res["fdm"] = sel
    json.dump(res, open(os.path.join(OUT, "wpt_link.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
