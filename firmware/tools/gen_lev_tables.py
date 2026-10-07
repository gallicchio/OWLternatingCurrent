#!/usr/bin/env python3
"""Write the levitation tables from the field computations in sim/physics/.

    python3 firmware/tools/gen_lev_tables.py      (about half a minute; numpy, scipy)

Two headers, both committed so that the firmware builds without Python:

  firmware/src/lev_table.h    the firmware's nominal calibration: the bat's field at
                              the Hall sensor against the gap (to turn a reading into
                              a gap), the bias attraction and the coil's grip against
                              the gap (for the catch and the gains), and the constants
  firmware/test/lev_plant.h   the plant for test/test_lev.c, on a finer grid

The geometry is the one-magnet design (sim/physics/levitation_onemagnet.py, PLAN.md
section 2): the bias magnet and the bat's magnet are the same 10 x 2 mm N52 disc
(gen/mech.py MAGNET_D, MAGNET_T); the bias magnet's bottom face is OWL_LIFT above the
perch's top copper; the bat (mass M_BAT from levitation_onemagnet.py) hangs below the
perch coil (levitation.py's COIL, the canonical 4-layer spiral); the DRV5055 sits on
the coil's axis 0.6 mm below the bottom copper (ZB).  levitation_onemagnet.py runs its
whole sweep when imported, so its two magnet definitions are repeated here (bias(),
bat()) and checked against the result it wrote (results/levitation_onemagnet.json).

Sign conventions, as in the simulations: z is up; "gap" is from the perch's bottom
copper down to the top face of the bat's magnet; a positive force lifts the bat
(attraction toward the perch); fields are B_z in tesla; the coil's current is positive
in its polyline's sense (counter-clockwise seen from above).  With these, both
magnets' fields at the sensor point down (negative), a positive coil current makes
an upward field there and pushes the bat down.  The firmware works in its own frame
(lev_ctrl.c): fields counted positive along the bat's own field at the sensor, and
current counted positive when it lifts the bat.
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
ROOT = os.path.dirname(FW)
SIM = os.path.join(ROOT, "sim", "physics")
sys.path.insert(0, SIM)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import magnetics as mg                                   # noqa: E402
from levitation import force_between, COIL, ZB          # noqa: E402
import mech                                             # noqa: E402

G = 9.81
BR = 1.43                       # N52, as every simulation here
DOWN = (0, 0, -1)
SENSOR = np.array([[0.0, 0.0, ZB - 0.6e-3]])

OUT_FW = os.path.join(FW, "src", "lev_table.h")
OUT_PLANT = os.path.join(FW, "test", "lev_plant.h")


def m_bat():
    """The bat's mass, from levitation_onemagnet.py's source (importing it runs its sweep)."""
    src = open(os.path.join(SIM, "levitation_onemagnet.py")).read()
    m = re.search(r"^M_BAT\s*=\s*([0-9.eE+-]+)", src, re.M)
    assert m, "M_BAT not found in levitation_onemagnet.py"
    return float(m.group(1))


R_MAG = mech.MAGNET_D / 2 * 1e-3
T_MAG = mech.MAGNET_T * 1e-3
LIFT = mech.OWL_LIFT * 1e-3


def bias():
    """As levitation_onemagnet.bias(lift): bottom face LIFT above the top copper, N down."""
    return mg.cylinder_magnet(R_MAG, T_MAG, BR, center=(0, 0, LIFT + T_MAG / 2), axis=DOWN, nz=8, nseg=64)


def bat(gap):
    """As levitation_onemagnet.bat(gap): top face `gap` below the bottom copper, N down."""
    return mg.cylinder_magnet(R_MAG, T_MAG, BR, center=(0, 0, ZB - gap - T_MAG / 2), axis=DOWN, nz=8, nseg=48)


def tables(gaps):
    b = bias()
    Fb, Fc, Bb = [], [], []
    for g in gaps:
        bm = bat(g)
        Fb.append(force_between(b, bm)[2])
        Fc.append(mg.force_torque(bm, COIL, 1.0)[0][2])
        Bb.append(bm.field(SENSOR)[0, 2])
    CA, CB = mg.segments(COIL)
    Bcoil = mg.bfield(CA, CB, 1.0, SENSOR)[0, 2]
    Bbias = b.field(SENSOR)[0, 2]
    return np.array(Fb), np.array(Fc), np.array(Bb), Bbias, Bcoil


def carr(name, vals, fmt, per_line=6, ctype="float"):
    s = ["static const %s %s[%d] = {" % (ctype, name, len(vals))]
    for i in range(0, len(vals), per_line):
        s.append("    " + ", ".join(fmt % v for v in vals[i:i + per_line]) + ",")
    s.append("};")
    return s


def main():
    M = m_bat()
    W = M * G
    # the plant: a fine grid; the firmware: every other point of it
    gaps = np.round(np.arange(1.0e-3, 25.0e-3 + 1e-9, 0.1e-3), 7)
    print("computing %d gaps ..." % len(gaps), flush=True)
    Fb, Fc, Bb, Bbias, Bcoil = tables(gaps)

    # the float point: where the bias alone carries the weight
    i = int(np.where(np.diff(np.sign(Fb - W)))[0][0])
    g0 = gaps[i] + (W - Fb[i]) * (gaps[i + 1] - gaps[i]) / (Fb[i + 1] - Fb[i])
    dF = np.gradient(Fb, gaps)
    k_neg = -float(np.interp(g0, gaps, dF))
    kc0 = float(np.interp(g0, gaps, Fc))
    dB = float(np.interp(g0, gaps, np.gradient(Bb, gaps)))
    Bb0 = float(np.interp(g0, gaps, Bb))
    print("float gap %.3f mm, k_neg %.2f N/m, coil %.2f mN/A, Hall: bias %.2f mT, bat %.2f mT, "
          "%.2f mT/mm, coil %.3f mT/A" % (g0 * 1e3, k_neg, kc0 * 1e3, Bbias * 1e3, Bb0 * 1e3, dB, Bcoil * 1e3))

    # the same design as levitation_onemagnet.py found (its 14 mm row)
    ref = os.path.join(SIM, "results", "levitation_onemagnet.json")
    if os.path.exists(ref):
        row = [r for r in json.load(open(ref)) if abs(r["lift_mm"] - mech.OWL_LIFT) < 1e-6]
        if row:
            r = row[0]
            assert abs(r["gap_mm"] - g0 * 1e3) < 0.1, (r["gap_mm"], g0 * 1e3)
            assert abs(r["coil_mN_per_A"] - kc0 * 1e3) < 0.03 * abs(kc0 * 1e3), r
            assert abs(r["hall_bias_mT"] - Bbias * 1e3) < 0.03 * abs(Bbias * 1e3), r
            assert abs(r["hall_bat_mT"] - Bb0 * 1e3) < 0.03 * abs(Bb0 * 1e3), r
            assert abs(r["k_neg"] - k_neg) < 0.15 * k_neg, (r["k_neg"], k_neg)   # its was a 0.5 mm difference
            print("agrees with %s (lift %.0f mm)" % (os.path.relpath(ref, ROOT), mech.OWL_LIFT))

    # monotonic field: the firmware inverts it
    assert np.all(np.diff(np.abs(Bb)) < 0), "the bat's field must fall with the gap"
    stamp = ("one-magnet design: two %.0f x %.0f mm N52 discs, bias %.1f mm above the perch, bat %.2f g"
             % (mech.MAGNET_D, mech.MAGNET_T, mech.OWL_LIFT, M * 1e3))

    # ---- the firmware's table: the bat-positive, lift-positive frame of lev_ctrl.c ----
    fw = slice(5, None, 2)               # 1.5 mm .. 25.0 mm every 0.2 mm
    gf = gaps[fw]
    L = ["/* lev_table.h: the levitation's nominal calibration, from the field computations.",
         " * WRITTEN BY firmware/tools/gen_lev_tables.py FROM sim/physics/ AND gen/mech.py: rerun that.",
         " * %s." % stamp,
         " *",
         " * The firmware's frame (lev_ctrl.c): a field counts positive along the bat's own field at",
         " * the Hall sensor; a current counts positive when it lifts the bat; force up is positive.",
         " * The gap runs from the perch's bottom copper to the top of the bat's magnet. */",
         "#pragma once",
         "",
         "#define LEV_TAB_N          %d" % len(gf),
         "#define LEV_TAB_GAP0_MM    %.4ff   /* first gap of the tables */" % (gf[0] * 1e3),
         "#define LEV_TAB_STEP_MM    %.4ff   /* uniform step */" % ((gf[1] - gf[0]) * 1e3),
         "#define LEV_MASS_KG        %.6ff   /* the bat, levitation_onemagnet.py */" % M,
         "#define LEV_G0_MM          %.4ff   /* where the bias magnet alone carries the bat */" % (g0 * 1e3),
         "#define LEV_KNEG_N_PER_M   %.4ff   /* -dF_bias/dgap there: the instability */" % k_neg,
         "#define LEV_KCOIL_N_PER_A  %.6ff   /* the coil's lift per amp there */" % abs(kc0),
         "#define LEV_DB_MT_PER_MM   %.4ff   /* the bat's field at the sensor per mm of gap there */" % abs(dB),
         "#define LEV_BBIAS_MT       %.4ff   /* the bias magnet's field at the sensor (same sense as the bat's) */"
         % (abs(Bbias) * 1e3),
         "#define LEV_BCOIL_MT_PER_A %.4ff   /* the coil's field at the sensor per lifting amp: aligned with the bat's */"
         % (abs(Bcoil) * 1e3),
         ""]
    # sanity of the frame: a lifting current's field is along the bat's field
    assert np.sign(Bbias) == np.sign(Bb0), "the two magnets' fields at the sensor must agree in sense"
    assert np.sign(Bcoil) != np.sign(Bb0) and kc0 < 0, \
        "frame check: a positive (sim) current must push the bat down and oppose its field at the sensor"
    L += ["/* the bat's field at the sensor (mT, falling with the gap) */"]
    L += carr("LEV_TAB_BBAT_MT", np.abs(Bb[fw]) * 1e3, "%.4ff")
    L += ["", "/* the bias magnet's pull on the bat (N, up) */"]
    L += carr("LEV_TAB_FBIAS_N", Fb[fw], "%.6ff")
    L += ["", "/* the coil's lift on the bat per lifting amp (N/A) */"]
    L += carr("LEV_TAB_KCOIL_N_PER_A", np.abs(Fc[fw]), "%.6ff")
    L.append("")
    open(OUT_FW, "w").write("\n".join(L))
    print("wrote", os.path.relpath(OUT_FW, ROOT))

    # ---- the plant: the simulation's own frame ----
    P = ["/* lev_plant.h: the levitating bat's vertical axis, for test/test_lev.c.",
         " * WRITTEN BY firmware/tools/gen_lev_tables.py FROM sim/physics/ AND gen/mech.py: rerun that.",
         " * %s." % stamp,
         " *",
         " * The simulations' frame: z up, gap from the perch's bottom copper to the bat's magnet,",
         " * force positive upward, B_z in tesla at the Hall sensor, coil current positive in",
         " * levitation.py's polyline sense (which pushes the bat down). */",
         "#pragma once",
         "",
         "#define PLANT_N            %d" % len(gaps),
         "#define PLANT_GAP0_M       %.7e" % gaps[0],
         "#define PLANT_STEP_M       %.7e" % (gaps[1] - gaps[0]),
         "#define PLANT_MASS_KG      %.7e" % M,
         "#define PLANT_G0_M         %.7e   /* the float point */" % g0,
         "#define PLANT_BBIAS_T      %.7e   /* the bias magnet's field at the sensor */" % Bbias,
         "#define PLANT_BCOIL_T_PER_A %.7e  /* the coil's field at the sensor per amp */" % Bcoil,
         ""]
    P += ["/* the bias magnet's force on the bat (N, + up) */"]
    P += carr("PLANT_FBIAS_N", Fb, "%.7e", 5, "double")
    P += ["", "/* the coil's force on the bat per amp (N/A, + up) */"]
    P += carr("PLANT_FCOIL_N_PER_A", Fc, "%.7e", 5, "double")
    P += ["", "/* the bat's field at the sensor (T, B_z) */"]
    P += carr("PLANT_BBAT_T", Bb, "%.7e", 5, "double")
    P.append("")
    open(OUT_PLANT, "w").write("\n".join(P))
    print("wrote", os.path.relpath(OUT_PLANT, ROOT))


if __name__ == "__main__":
    main()
