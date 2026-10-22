import sys, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg
Z = [0.0, -0.21e-3, -1.275e-3]
# drawn COIL_LEV: copper edges 15/4 mm, 0.5 mm track; ~14.07-14.5 turns/layer
L = mg.L_multilayer(14.2, 15e-3, 4e-3, Z)
print(f"L_multilayer(14.2t, r 4-15, 3 layers) = {L*1e6:.1f} uH  (config.h claims 30.1 uH)")
# R: mean spiral length * rho / (w t), 1 oz copper
for turns in (14.07, 14.5):
    L1 = mg.polyline_length(mg.spiral(turns, 14.75e-3, 4.25e-3, 0.0, 64))
    print(f"layer length ({turns} t): {L1:.3f} m")
Rtot = 3 * mg.R_trace(0.84, 0.5e-3, mg.OZ)
print(f"R ~ {Rtot:.2f} ohm + vias/leads (config.h claims 2.56)")
# canonical 4-layer coil for contrast (levitation_loop.py's L_COIL)
Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
print(f"L_multilayer(12t, r 3-15, 4 layers) = {mg.L_multilayer(12, 15e-3, 3e-3, Z4)*1e6:.1f} uH (loop sim uses 31.5 uH, R 3.35)")
