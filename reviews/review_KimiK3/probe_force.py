import sys, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg

ZB = -1.485e-3
LIFT = 14.0e-3
G0 = 8.537e-3
W = 3.6e-3 * 9.81

# --- mesh convergence of the equilibrium force/fields (design mesh: nz=8, nseg=64/48) ---
for nz, nseg in ((8, 64), (16, 128), (40, 256)):
    bias = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,LIFT+1e-3), axis=(0,0,-1), nz=nz, nseg=nseg)
    bat  = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0,0,ZB-G0-1e-3), axis=(0,0,-1), nz=nz, nseg=nseg)
    F = mg.force_torque(bat, bias.loops, bias.currents[0])[0][2]
    ps = np.array([[0,0,ZB-0.6e-3]])
    Bb = bat.field(ps)[0,2]
    print(f"nz={nz:3d} nseg={nseg:3d}: F_bias(g0) = {F*1e3:8.3f} mN (weight {W*1e3:.3f}), B_bat at sensor {Bb*1e3:8.3f} mT")

# --- independent path: force = I1 I2 dM/dz summed over the magnets' loop pairs (elliptic M) ---
nz, nseg = 24, 8   # nseg irrelevant here: use analytic loops -> take loop radii/heights directly
zs = -1e-3 + (2e-3/nz)*(np.arange(nz)+0.5)
M = 1.43/mg.MU0
Ic = M*(2e-3/nz)
def F_dMdz(d_faces):
    zb = LIFT                      # bias bottom face
    zt = zb - d_faces              # bat top face (below bias)
    tot = 0.0
    dd = 1e-6
    for z1 in zb + 1e-3 + zs:      # bias loop heights
        for z2 in zt - 1e-3 + zs:         # bat loop heights (both centred)
            d = z1 - z2
            tot += (mg.mutual_coaxial_loops(5e-3, 5e-3, d+dd) - mg.mutual_coaxial_loops(5e-3, 5e-3, d-dd))/(2*dd)
    return Ic*Ic*tot
sep = LIFT + 1.485e-3 + G0         # face-to-face separation at the float point
print(f"\nface-to-face separation at float: {sep*1e3:.2f} mm")
print(f"F via I1 I2 dM/dz at float sep:  {F_dMdz(sep)*1e3:.3f} mN  (Lorentz path gave ~35.3)")
print(f"F via I1 I2 dM/dz at 5.55 mm sep: {F_dMdz(5.55e-3)*1e3:.1f} mN  ({F_dMdz(5.55e-3)/W:.1f} x bat weight)")
# where would equilibrium be if separation really were 14.05-8.5=5.55 mm?
