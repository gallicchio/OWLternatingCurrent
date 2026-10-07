#!/usr/bin/env python3
"""Can the perch's levitation coil light the floating bat's LEDs by induction?

TX: the perch coil (the canonical 4-layer spiral, 31.5 uH), driven by its DRV8874
(PWM <= 100 kHz), so the carrier is at 90 kHz.  RX: a fine-pitch 4-layer spiral in
the bat PCB round its magnet (r 6-11 mm, 0.2/0.2 mm track/gap: 12 turns a layer),
with a C0G capacitor across it (parallel resonance) and two LED pairs across that:
orange side-view eyes and violet belly LEDs, each pair anti-parallel.
The bat's magnet (10 x 2 mm) floats 8.5 mm below the perch's bottom copper, and the
bat's top copper is 2 mm below that (the magnet's thickness).

Also reports the carrier's eddy loss in the magnet.  Writes results/bat_power.json.
"""
import json, os
import numpy as np
import magnetics as mg
from familiar import simulate

HERE = os.path.dirname(os.path.abspath(__file__))
Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
OZ4 = [1, 1, 1, 1]           # 1 oz inner copper (Jason, 2026-10-07)

TX = dict(n=12, r_out=15e-3, r_in=3e-3, w=0.6e-3)
RX = dict(n=12, r_out=11e-3, r_in=6.2e-3, w=0.2e-3)


def L_of(c):
    return mg.L_multilayer(c["n"], c["r_out"], c["r_in"], Z4)


def R_of(c, f):
    turn = 2 * np.pi * 0.5 * (c["r_out"] + c["r_in"]) * c["n"]
    return 1.3 * sum(mg.R_trace(turn, c["w"], oz * mg.OZ, f) for oz in OZ4)


def M_of(dz):
    rt = np.linspace(TX["r_out"], TX["r_in"], TX["n"])
    rr = np.linspace(RX["r_out"], RX["r_in"], RX["n"])
    M = 0.0
    for zt in Z4:
        for zr in Z4:
            d = dz + (Z4[-1] - zt) + (0 - zr)        # TX bottom copper to RX top copper = dz
            M += sum(mg.mutual_coaxial_loops(a, b, d) for a in rt for b in rr)
    return M


f = 90e3
L1, L2 = L_of(TX), L_of(RX)
R1, R2 = R_of(TX, f), R_of(RX, f)
dz = 8.5e-3 + 2e-3
M = M_of(dz)
k = M / np.sqrt(L1 * L2)
Q2 = 2 * np.pi * f * L2 / R2
C2 = 1 / ((2 * np.pi * f) ** 2 * L2)
print(f"perch L1 {L1*1e6:.1f} uH R1 {R1:.2f} ohm; bat coil L2 {L2*1e6:.1f} uH R2 {R2:.1f} ohm Q2 {Q2:.1f}; "
      f"C2 {C2*1e9:.1f} nF; M {M*1e6:.2f} uH k {k:.3f} at {dz*1e3:.1f} mm")
rows = []
for I1 in (0.2, 0.3, 0.4, 0.5):
    io, iv, vp = simulate(f, f, I1, M, L2, R2, cycles=300, vf_o=1.85, r_o=9 + 33, vf_v=2.85, r_v=14 + 33)
    rows.append(dict(I1=I1, orange_mA=io * 1e3, violet_mA=iv * 1e3, vpk=vp))
    print(f"carrier {I1:.1f} A: eyes {io*1e3:5.1f} mA, belly {iv*1e3:5.1f} mA (tank {vp:.1f} V peak)")
# carrier the bridge can make: square 12 V across L1 at 90 kHz -> triangle; fundamental amplitude
Ipp = 12 / (4 * f * L1)          # bipolar square, 50 %: I_pp = V T / (2 L) ... (V/L)(T/2)/2 per half
fund = 8 / np.pi ** 2 * Ipp / 2
print(f"a 12 V bipolar square at 90 kHz gives {Ipp:.2f} A pp, fundamental {fund:.2f} A amplitude")
# eddy loss in the 10 x 2 magnet: B at the magnet from the coil, per amp, on axis
CA, CB = mg.segments(mg.multilayer_coil(12, 15e-3, 3e-3, Z4, per_turn=64))
Bmag = mg.bfield(CA, CB, 1.0, np.array([[0, 0, Z4[-1] - 8.5e-3 - 1e-3]]))[0, 2]
sigma, a, h = 7.1e5, 5e-3, 2e-3
for I1 in (0.3, 0.5):
    B = Bmag * I1
    P = sigma * (2 * np.pi * f) ** 2 * (B ** 2 / 2) * np.pi * h * a ** 4 / 8
    print(f"eddy loss in the bat's magnet at {I1} A carrier: {P*1e3:.1f} mW (B {B*1e3:.2f} mT at the magnet)")
json.dump(dict(f=f, L1=L1, L2=L2, R2=R2, Q2=Q2, C2=C2, M=M, k=k, rows=rows, Bmag_per_A=Bmag),
          open(os.path.join(HERE, "results", "bat_power.json"), "w"), indent=1)
