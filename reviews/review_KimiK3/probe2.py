import sys, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg

G_ACC = 9.81; W = 3.6e-3 * G_ACC
# Hypothesis: committed tables were generated with a 3-layer Z where Z[-1] is treated
# as the bottom copper (ZB = -1.275 mm instead of -1.485 mm)
Z3 = [0.0, -0.21e-3, -1.275e-3]
def run(Z, coilZ, label):
    ZB = Z[-1]
    coil = mg.multilayer_coil(14, 15e-3, 4e-3, coilZ, per_turn=64)
    ps = np.array([[0, 0, ZB - 0.6e-3]])
    bias = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,14e-3+1e-3), axis=(0,0,-1), nz=8, nseg=64)
    bat = lambda g: mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,ZB-g-1e-3), axis=(0,0,-1), nz=8, nseg=48)
    gaps = np.arange(1e-3, 25e-3+1e-9, 0.1e-3)
    Fb = np.array([mg.force_torque(bat(g), bias.loops, bias.currents[0])[0][2] for g in gaps])
    i = int(np.where(np.diff(np.sign(Fb - W)))[0][0])
    g0 = gaps[i] + (W - Fb[i])*(gaps[i+1]-gaps[i])/(Fb[i+1]-Fb[i])
    dF = np.gradient(Fb, gaps); k_neg = -float(np.interp(g0, gaps, dF))
    kc0 = mg.force_torque(bat(g0), coil, 1.0)[0][2]
    CA, CB = mg.segments(coil)
    Bcoil = mg.bfield(CA, CB, 1.0, ps)[0,2]
    Bbias = bias.field(ps)[0,2]
    Bb0 = bat(g0).field(ps)[0,2]
    print(f"{label:34s} g0 {g0*1e3:7.4f} mm  k_neg {k_neg:6.4f}  kc {kc0*1e3:8.4f} mN/A  Bcoil {Bcoil*1e3:7.4f} mT/A  Bbias {Bbias*1e3:7.4f}  Bbat {Bb0*1e3:8.4f} mT")

print("committed:   g0 8.5370 mm  k_neg 5.0080  kc 20.410 mN/A  Bcoil 3.1118 mT/A  Bbias 6.3638  Bbat ~33.67")
run(Z3, Z3, "3L Z=[0,-.21,-1.275], coil on all 3")
Z4 = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
run(Z4, Z4[:3], "4L stack, coil layers 1-3, ZB=-1.485")
