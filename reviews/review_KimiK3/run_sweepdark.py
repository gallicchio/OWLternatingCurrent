#!/usr/bin/env python3
"""Review check: token tank voltage during the firmware's sweep (V1 = 0.575 V max
fundamental, at the token's own resonance), with the built 150 ohm LED legs.
LEDs glimmer if the tank peak passes the orange Vf ~1.85 V."""
import sys, numpy as np
sys.path.insert(0, "/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics")
from familiar import coil, R_at, mutual, simulate, RX, TX

L1, _ = coil(TX); L2, _ = coil(RX); M = mutual(3.0e-3)
V1 = 4 / np.pi * 4.8 * np.sin(np.pi * 0.030)          # sweep's upper duty: 0.575 V
for f in (142e3, 303e3):
    R1 = R_at(TX, f); R2 = R_at(RX, f)
    wM = 2 * np.pi * f * M
    Zl = np.hypot(2 * np.pi * f * L1, R1 + wM * wM / R2)   # token at resonance, LEDs dark (Q high)
    I1 = V1 / Zl
    io, iv, vp = simulate(f, f, I1, M, L2, R2, r_o=159.0, r_v=164.0, cycles=250)
    print(f"{f/1e3:.0f} kHz sweep point: V1 {V1:.3f} V, |Z| {Zl:.1f} ohm, I1 {I1*1e3:.1f} mA -> "
          f"tank Vpk {vp:.2f} V, orange {io*1e3:.2f} mA, violet {iv*1e3:.2f} mA")
# and the strongest harmonic hit: 3rd harmonic of a ~101 kHz sweep point lands on the cat
f = 303e3
V3 = 4 / (3 * np.pi) * 4.8 * np.sin(3 * np.pi * 0.030)
R1 = R_at(TX, f); R2 = R_at(RX, f); wM = 2 * np.pi * f * M
Zl = np.hypot(2 * np.pi * f * L1, R1 + wM * wM / R2)
I3 = V3 / Zl
io, iv, vp = simulate(f, f, I3, M, L2, R2, r_o=159.0, r_v=164.0, cycles=250)
print(f"cat hit by 3rd harmonic of a 101 kHz sweep point: V3 {V3:.3f} V, I3 {I3*1e3:.2f} mA -> Vpk {vp:.2f} V")
