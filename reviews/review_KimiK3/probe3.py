import sys, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg
Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
ZB = Z4[-1]
ps = np.array([[0, 0, ZB - 0.6e-3]])
g0 = 8.5370e-3
bat = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,ZB-g0-1e-3), axis=(0,0,-1), nz=8, nseg=48)
def try_coil(turns, r_out, r_in, zl, label):
    coil = mg.multilayer_coil(turns, r_out*1e-3, r_in*1e-3, zl, per_turn=64)
    CA, CB = mg.segments(coil)
    B = mg.bfield(CA, CB, 1.0, ps)[0,2]*1e3
    F = mg.force_torque(bat, coil, 1.0)[0][2]*1e3
    print(f"{label:36s} Bcoil {B:7.4f} mT/A  kc {F:8.4f} mN/A")
print("committed:                             Bcoil  3.1118 mT/A  kc -20.410 mN/A")
try_coil(14, 15, 4, Z4[:3], "3L 14t r4-15 (true coil)")
try_coil(14, 15, 4, [Z4[1],Z4[2],Z4[3]], "3L 14t r4-15 layers 2-4")
try_coil(12, 15, 3, Z4, "4L 12t r3-15 canonical")
try_coil(14, 15, 4, Z4, "4L 14t r4-15")
try_coil(15, 15, 4, Z4[:3], "3L 15t r4-15")
try_coil(14, 15, 3, Z4[:3], "3L 14t r3-15")
try_coil(15, 15, 3, Z4[:3], "3L 15t r3-15")
try_coil(13, 15, 3, Z4[:3], "3L 13t r3-15")
