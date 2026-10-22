import sys, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg
Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
ZB = Z4[-1]
ps = np.array([[0, 0, ZB - 0.6e-3]])
g0 = 8.5370e-3
bat = lambda g: mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,ZB-g-1e-3), axis=(0,0,-1), nz=8, nseg=48)
def try_coil(turns, r_out, r_in, zl, label):
    coil = mg.multilayer_coil(turns, r_out*1e-3, r_in*1e-3, zl, per_turn=64)
    CA, CB = mg.segments(coil)
    B = mg.bfield(CA, CB, 1.0, ps)[0,2]*1e3
    F0 = mg.force_torque(bat(g0), coil, 1.0)[0][2]*1e3
    F1 = mg.force_torque(bat(1.5e-3), coil, 1.0)[0][2]*1e3
    print(f"{label:34s} Bcoil {B:7.4f}  kc(g0) {F0:8.4f}  kc(1.5mm) {F1:8.4f}")
print("committed:                       Bcoil  3.1118  kc(g0) -20.410  kc(1.5mm) 75.553 (sign +)")
try_coil(11, 15, 4, Z4, "4L 11t r4-15 (old def)")
try_coil(11, 15, 4, Z4[:3], "3L 11t r4-15")
try_coil(14, 15, 4, Z4[:3], "3L 14t r4-15 (current def)")
# drawn coil: F.Cu 14.5 turns, In1/In2 ~14.07, track centres 14.75..4.25
zl = Z4[:3]
lay = []
lay.append(mg.spiral(14.5, 14.75e-3, 4.25e-3, zl[0], 64, inward=True))
lay.append(mg.spiral(14.07, 4.25e-3, 14.75e-3, zl[1], 64, inward=False))
lay.append(mg.spiral(14.07, 14.75e-3, 4.25e-3, zl[2], 64, inward=True))
CA, CB = mg.segments(lay)
B = mg.bfield(CA, CB, 1.0, ps)[0,2]*1e3
F0 = mg.force_torque(bat(g0), lay, 1.0)[0][2]*1e3
F1 = mg.force_torque(bat(1.5e-3), lay, 1.0)[0][2]*1e3
print(f"{'drawn coil (14.5/14.07/14.07)':34s} Bcoil {B:7.4f}  kc(g0) {F0:8.4f}  kc(1.5mm) {F1:8.4f}")
