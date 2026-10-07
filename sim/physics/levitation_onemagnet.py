#!/usr/bin/env python3
"""One magnet size for everything: bias = bat magnet = 10 x 2 mm N52 disc.

Jason should have to buy one kind of magnet.  The bias magnet is the same disc as
the bat's, lifted higher above the perch (in its printed cap) so that its pull
at the bat's float gap equals the bat's weight.  For each lift: the float gap,
the negative stiffness there, the coil's grip, the sideways stiffness, and what
the Hall sensor at the coil centre (on the perch's underside) sees.

Bat mass: PCB bat ~2.0 g (FR4 1.6 mm, ~45 x 25 mm of wing, LEDs, coil, caps)
+ magnet 1.18 g + printed cap 0.4 g = ~3.6 g.

Writes results/levitation_onemagnet.json.
"""
import json, os
import numpy as np
import magnetics as mg
from levitation import force_between, COIL, ZB

HERE = os.path.dirname(os.path.abspath(__file__))
G = 9.81
M_BAT = 3.6e-3
DOWN = (0, 0, -1)


def bias(lift):
    return mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0, 0, lift + 1e-3), axis=DOWN, nz=8, nseg=64)


def bat(gap, x=0.0):
    return mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(x, 0, ZB - gap - 1e-3), axis=DOWN, nz=8, nseg=48)


rows = []
ps = np.array([[0, 0, ZB - 0.6e-3]])
CA, CB = mg.segments(COIL)
for lift in (8e-3, 10e-3, 12e-3, 14e-3, 16e-3, 18e-3, 20e-3):
    b = bias(lift)
    gaps = np.linspace(3e-3, 25e-3, 45)
    Fz = np.array([force_between(b, bat(g))[2] for g in gaps])
    W = M_BAT * G
    i = np.where(np.diff(np.sign(Fz - W)))[0]
    if not len(i):
        print(f"lift {lift*1e3:.0f} mm: no equilibrium ({Fz.min()*1e3:.1f}..{Fz.max()*1e3:.1f} mN)")
        continue
    j = i[0]
    g0 = gaps[j] + (W - Fz[j]) * (gaps[j + 1] - gaps[j]) / (Fz[j + 1] - Fz[j])
    kneg = -(Fz[j + 1] - Fz[j]) / (gaps[j + 1] - gaps[j])
    Fc = mg.force_torque(bat(g0), COIL, 1.0)[0][2]
    klat = -force_between(b, bat(g0, x=0.5e-3))[0] / 0.5e-3
    Bb = b.field(ps)[0, 2]
    Bt = bat(g0).field(ps)[0, 2]
    dB = (bat(g0 + 0.1e-3).field(ps)[0, 2] - bat(g0 - 0.1e-3).field(ps)[0, 2]) / 0.2e-3
    wc = 2 * np.pi * 10
    Kp = (M_BAT * wc ** 2 + kneg) / abs(Fc)
    r = dict(lift_mm=lift * 1e3, gap_mm=g0 * 1e3, k_neg=kneg, coil_mN_per_A=Fc * 1e3, k_lat=klat,
             hall_bias_mT=Bb * 1e3, hall_bat_mT=Bt * 1e3, hall_mT_per_mm=dB, Kp_A_per_mm_10Hz=Kp * 1e-3)
    rows.append(r)
    print(f"lift {lift*1e3:4.0f} mm: bat floats {g0*1e3:5.1f} mm down; k_neg {kneg:5.1f} N/m; coil {Fc*1e3:6.1f} mN/A; "
          f"lateral {klat:+5.1f} N/m; Hall bias {Bb*1e3:6.1f} + bat {Bt*1e3:6.1f} mT, {dB:5.1f} mT/mm; "
          f"Kp(10 Hz) {Kp*1e-3:.2f} A/mm")
json.dump(rows, open(os.path.join(HERE, "results", "levitation_onemagnet.json"), "w"), indent=1)
