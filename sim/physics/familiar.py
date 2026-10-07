#!/usr/bin/env python3
"""A familiar's receiver, in the time domain, with real LED thresholds.

The familiar coin: a 4-layer spiral (it rides on the base board's 4-layer panel),
a C0G capacitor across it (parallel resonance, so Q steps the induced EMF up),
and an orange and a violet LED in anti-parallel across the tank: the orange LED
lights on one half-cycle, the violet on the other, and the violet (3.1 eV
photons) needs more voltage than the orange (2.0 eV), so as the drive rises the
colour goes from orange to orange-and-violet.

The perch coil is driven with a sinusoidal current of amplitude I1 (the
H-bridge's square wave, filtered by the coil: the fundamental is what couples).

Questions answered:
  1. LED currents against perch-coil current, for the owl tuned to f_owl.
  2. Cross-talk: the cat (tuned to f_cat) on the same perch while the board
     drives f_owl, and vice versa.
  3. The perch coil current the H-bridge must supply.

Writes results/familiar.json and results/familiar.png.
"""
import json, os
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import magnetics as mg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)

Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
OZ4 = [1, 0.5, 0.5, 1]
# perch (TX) coil on the base board, and the familiar coin (RX)
TX = dict(n=10, r_out=15e-3, r_in=5e-3, w=0.6e-3)
RX = dict(n=7, r_out=11.5e-3, r_in=4.5e-3, w=0.6e-3)


def coil(c):
    L = mg.L_multilayer(c["n"], c["r_out"], c["r_in"], Z4)
    turn = 2 * np.pi * 0.5 * (c["r_out"] + c["r_in"]) * c["n"]
    return L, turn


def R_at(c, f):
    _, turn = coil(c)
    return 1.3 * sum(mg.R_trace(turn, c["w"], oz * mg.OZ, f) for oz in OZ4)


def mutual(gap):
    rt = np.linspace(TX["r_out"], TX["r_in"], TX["n"])
    rr = np.linspace(RX["r_out"], RX["r_in"], RX["n"])
    M = 0.0
    for zt in Z4:
        for zr in Z4:
            d = gap + (zr - Z4[-1]) - zt
            M += sum(mg.mutual_coaxial_loops(a, b, d) for a in rt for b in rr)
    return M


def led_i(v, vf, rs):
    return np.where(v > vf, (v - vf) / rs, 0.0)


def simulate(f_drive, f_tune, I1, M, L2, R2, cycles=400, vf_o=1.85, r_o=9.0, vf_v=2.85, r_v=14.0):
    """Return mean orange and violet LED currents (A) in steady state."""
    C2 = 1 / ((2 * np.pi * f_tune) ** 2 * L2)
    w = 2 * np.pi * f_drive

    def rhs(t, y):
        i, v = y
        e = M * I1 * w * np.cos(w * t)                 # e = M dI1/dt
        il = led_i(v, vf_o, r_o) - led_i(-v, vf_v, r_v)
        return [(e - R2 * i - v) / L2, (i - il) / C2]

    T = 1 / f_drive
    tt = np.linspace((cycles - 40) * T, cycles * T, 4000)
    sol = solve_ivp(rhs, (0, cycles * T), [0.0, 0.0], t_eval=tt, max_step=T / 60, rtol=1e-6, atol=1e-9)
    v = sol.y[1]
    return float(np.mean(led_i(v, vf_o, r_o))), float(np.mean(led_i(-v, vf_v, r_v))), float(np.max(np.abs(v)))


def main():
    L1, _ = coil(TX)
    L2, _ = coil(RX)
    gap = 3.0e-3            # 2 mm printed floor + 1 mm air/mask
    M = mutual(gap)
    k = M / np.sqrt(L1 * L2)
    f_owl, f_cat = 150e3, 330e3
    print(f"perch L1 = {L1*1e6:.1f} uH, coin L2 = {L2*1e6:.2f} uH, M = {M*1e6:.2f} uH (k = {k:.2f}) at {gap*1e3:.0f} mm")
    for f in (f_owl, f_cat):
        R2 = R_at(RX, f)
        print(f"  coin at {f/1e3:.0f} kHz: R2 = {R2:.2f} ohm, Q2 = {2*np.pi*f*L2/R2:.1f}, "
              f"C2 = {1/((2*np.pi*f)**2*L2)*1e9:.1f} nF")
    res = dict(L1_uH=L1 * 1e6, L2_uH=L2 * 1e6, M_uH=M * 1e6, k=k, gap_mm=gap * 1e3,
               f_owl=f_owl, f_cat=f_cat, sweep=[])
    I1s = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4]
    rows = []
    for I1 in I1s:
        r = {"I1": I1}
        for name, fd, ft in (("owl_on", f_owl, f_owl), ("cat_on", f_cat, f_cat),
                             ("cat_when_owl_driven", f_owl, f_cat), ("owl_when_cat_driven", f_cat, f_owl)):
            R2 = R_at(RX, fd)
            io, iv, vp = simulate(fd, ft, I1, M, L2, R2)
            r[name] = dict(orange_mA=io * 1e3, violet_mA=iv * 1e3, vpk=vp)
        rows.append(r)
        print(f"I1 {I1:.2f} A: owl@own f orange {r['owl_on']['orange_mA']:5.1f} mA violet {r['owl_on']['violet_mA']:5.1f} mA "
              f"(Vpk {r['owl_on']['vpk']:.2f}) | cat@own f orange {r['cat_on']['orange_mA']:5.1f} violet {r['cat_on']['violet_mA']:5.1f} | "
              f"cross-talk: cat while owl driven {r['cat_when_owl_driven']['orange_mA']:.2f}/{r['cat_when_owl_driven']['violet_mA']:.2f} mA, "
              f"owl while cat driven {r['owl_when_cat_driven']['orange_mA']:.2f}/{r['owl_when_cat_driven']['violet_mA']:.2f} mA")
    res["sweep"] = rows
    # perch drive: the H-bridge sees the perch coil's impedance at f (non-resonant drive)
    for f in (f_owl, f_cat):
        X = 2 * np.pi * f * L1
        R1 = R_at(TX, f)
        V1 = 0.2 * np.hypot(X, R1)
        print(f"perch at {f/1e3:.0f} kHz: |Z| = {np.hypot(X, R1):.1f} ohm -> 0.2 A needs {V1:.1f} V amplitude "
              f"(a 12 V full bridge's fundamental is {4/np.pi*12:.1f} V)")
    json.dump(res, open(os.path.join(OUT, "familiar.json"), "w"), indent=1)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for key, lab, ls in (("owl_on", "owl (150 kHz), driven at 150 kHz", "-"),
                         ("cat_on", "cat (330 kHz), driven at 330 kHz", "-"),
                         ("cat_when_owl_driven", "cat, while the owl's 150 kHz is on", ":"),
                         ("owl_when_cat_driven", "owl, while the cat's 330 kHz is on", ":")):
        ax.plot(I1s, [r[key]["orange_mA"] for r in rows], "o" + ls, color="#ff8a1f", label="orange: " + lab)
        ax.plot(I1s, [r[key]["violet_mA"] for r in rows], "s" + ls, color="#9b4dff", label="violet: " + lab)
    ax.set(xlabel="perch coil current amplitude (A)", ylabel="mean LED current (mA)",
           title=f"Familiar coins on a perch, {gap*1e3:.0f} mm gap")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=6.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "familiar.png"), dpi=120)


if __name__ == "__main__":
    main()
