#!/usr/bin/env python3
"""Review check: token LED currents with the BUILT 150 ohm series resistors,
at the perch currents the 4.8 V bridge can actually make."""
import sys, numpy as np
sys.path.insert(0, "/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics")
from familiar import coil, R_at, mutual, simulate, RX, TX

L1, _ = coil(TX)
L2, _ = coil(RX)
M = mutual(3.0e-3)
print(f"L1 {L1*1e6:.2f} uH, L2 {L2*1e6:.2f} uH, M {M*1e6:.2f} uH")

# the 4.8 V bridge's largest possible fundamental: 4/pi*4.8 = 6.11 V at duty 0.5
V1MAX = 4 / np.pi * 4.8
for f, ft, tag in ((142e3, 142e3, "owl as built (142 kHz, 100 nF on 12.5uH?)"),
                   (150e3, 150e3, "owl as simulated (150 kHz)"),
                   (303e3, 303e3, "cat as built (303 kHz, 22 nF)"),
                   (330e3, 330e3, "cat as simulated (330 kHz)")):
    R1 = R_at(TX, f)
    R2 = R_at(RX, f)
    X1 = 2 * np.pi * f * L1
    Zempty = np.hypot(X1, R1)
    # token at resonance: reflected (wM)^2/R2 in series with the perch coil
    wM = 2 * np.pi * f * M
    Zres = np.hypot(X1, R1 + wM * wM / R2)
    i_empty = V1MAX / Zempty
    i_res = V1MAX / Zres
    print(f"{tag}: empty-perch |Z| {Zempty:.1f} ohm -> I1 max {i_empty:.3f} A; "
          f"token at resonance |Z| {Zres:.1f} ohm -> I1 {i_res:.3f} A")
    for I1 in (0.2, i_empty):
        io, iv, vp = simulate(f, ft, I1, M, L2, R2, r_o=9.0 + 150.0, r_v=14.0 + 150.0, cycles=250)
        print(f"   150 ohm legs, I1 = {I1:.3f} A: orange {io*1e3:5.1f} mA, violet {iv*1e3:5.1f} mA, tank Vpk {vp:.2f} V")

# also: what the LED sees peak instantaneous (peak tank V over 150+9 ohm)
io, iv, vp = simulate(142e3, 142e3, 0.225, M, L2, R_at(RX, 142e3), r_o=159.0, r_v=164.0, cycles=250)
print(f"owl worst case (I1 0.225 A): Vpk {vp:.2f} -> orange peak {(vp-1.85)/159*1e3:.1f} mA, violet peak {(vp-2.85)/164*1e3:.1f} mA")
