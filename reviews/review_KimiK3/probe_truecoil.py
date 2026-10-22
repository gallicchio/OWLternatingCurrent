import sys, re, numpy as np
sys.path.insert(0, '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/sim/physics')
import magnetics as mg

Z = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
ZB = Z[-1]
ps = np.array([[0, 0, ZB - 0.6e-3]])
# the drawn COIL_LEV: F.Cu 14.5 turns, In1/In2 ~14.07, track centres 14.75 -> 4.25 mm
lay = [mg.spiral(14.5,  14.75e-3, 4.25e-3, Z[0], 64, inward=True),
       mg.spiral(14.07, 4.25e-3, 14.75e-3, Z[1], 64, inward=False),
       mg.spiral(14.07, 14.75e-3, 4.25e-3, Z[2], 64, inward=True)]
CA, CB = mg.segments(lay)
Bcoil = mg.bfield(CA, CB, 1.0, ps)[0, 2]
print(f"true drawn coil: Bcoil {Bcoil*1e3:.4f} mT/A")
gaps = np.round(np.arange(1.0e-3, 25.0e-3 + 1e-9, 0.1e-3), 7)
Fc = []
for k, g in enumerate(gaps):
    bat = mg.cylinder_magnet(5e-3, 2e-3, 1.43, center=(0, 0, ZB - g - 1e-3), axis=(0, 0, -1), nz=8, nseg=48)
    Fc.append(mg.force_torque(bat, lay, 1.0)[0][2])
    if k % 60 == 0: print(f"  {k}/{len(gaps)}", flush=True)
Fc = np.array(Fc)
g0 = 8.5369827e-3
print(f"kc at g0: {np.interp(g0, gaps, Fc)*1e3:.4f} mN/A (committed -20.410)")
# patch the copy's lev_plant.h
p = '/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/review_KimiK3/project/firmware/test/lev_plant.h'
src = open(p).read()
def carr(vals, per_line=5):
    out = []
    for i in range(0, len(vals), per_line):
        out.append("    " + ", ".join("%.7e" % v for v in vals[i:i+per_line]) + ",")
    return "\n".join(out) + "\n"
new_arr = "static const double PLANT_FCOIL_N_PER_A[241] = {\n" + carr(Fc) + "};"
src = re.sub(r"static const double PLANT_FCOIL_N_PER_A\[241\] = \{.*?\};", new_arr, src, flags=re.S)
src = re.sub(r"#define PLANT_BCOIL_T_PER_A 3.1118359e-03", "#define PLANT_BCOIL_T_PER_A %.7e" % Bcoil, src)
open(p, 'w').write(src)
print("patched", p)
