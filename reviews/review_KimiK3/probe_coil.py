import sys, numpy as np
sys.path.insert(0, '.')
import magnetics as mg
from levitation import Z, ZB

# candidate coil definitions
cands = {
    "3L_layers123_14t_r4-15": mg.multilayer_coil(14, 15e-3, 4e-3, Z[:3], per_turn=64),
    "4L_allZ_14t_r4-15":      mg.multilayer_coil(14, 15e-3, 4e-3, Z, per_turn=64),
    "4L_allZ_12t_r3-15(canonical)": mg.multilayer_coil(12, 15e-3, 3e-3, Z, per_turn=64),
}
ps = np.array([[0, 0, ZB - 0.6e-3]])
# bat magnet at float gap 8.537 mm
bat = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0, 0, ZB - 8.537e-3 - 1e-3), axis=(0,0,-1), nz=8, nseg=48)
for name, coil in cands.items():
    CA, CB = mg.segments(coil)
    B = mg.bfield(CA, CB, 1.0, ps)[0, 2]
    F = mg.force_torque(bat, coil, 1.0)[0][2]
    L = None
    print(f"{name:32s} B_sensor {B*1e3:+7.4f} mT/A   F_bat {F*1e3:+8.4f} mN/A")
print("committed: BCOIL +3.1118 mT/A (lifting sense); KCOIL 20.410 mN/A; onemagnet-canonical sim: 21.2 mN/A, loop sim 3.69 mT/A")
