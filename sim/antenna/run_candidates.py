#!/usr/bin/env python3
"""
run_candidates.py -- the character antennas, coarse first, then the winners refined.

Every case sits at the middle of the 100 mm edge of a 100 x 80 mm via-stitched ground
plane, on an FR4 tab (all copper layers cleared under it), 1.6 mm FR4, er 4.4,
tan d 0.02, fed by a 50-ohm lumped port at the ground edge.

  stage A   coarse (0.5 mm) scan: bat-IFA span, bat dipole span, ghost size
  stage B   tune the bat-IFA match (feed-short spacing, body height) at 0.35 mm
  stage C   the tuned candidates at 0.25 mm (the production mesh)

usage:  NPAR=5 em-env python run_candidates.py A
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import antsim  # noqa: E402
import runner  # noqa: E402
import shapes  # noqa: E402

COARSE = dict(res_fine=0.5, nz=4)
MID = dict(res_fine=0.35, nz=5)
FINE = dict(res_fine=0.25, nz=5)


def stage_A():
    J = []
    for span in (36.0, 44.0, 52.0):
        J.append((f"A_batifa_span{span:g}", shapes.bat("ifa", span=span), COARSE))
    for span in (40.0, 46.0, 52.0):
        J.append((f"A_batdip_span{span:g}", shapes.bat("dipole", span=span, yb=16.0), COARSE))
    for R in (8.0, 9.5):
        J.append((f"A_ghost_R{R:g}", shapes.ghost(R=R, yc=R + 6.0), COARSE))
    return J


def stage_B():
    """Single-ended ways to drive the bat's dipole mode, and a better-fed ghost (0.5 mm)."""
    J = []
    for span in (46.0, 50.0):
        J.append((f"B_splitifa_span{span:g}", shapes.bat("split_ifa", span=span), COARSE))
        J.append((f"B_legfed_span{span:g}", shapes.bat("legfed", span=span), COARSE))
    J.append(("B_batmono_span46", shapes.bat("ifa", span=46.0, short=False), COARSE))
    J.append(("B_batifa_scale0.62", shapes.bat("ifa", span=44.0, scale=0.62), COARSE))
    J.append(("B_ghost_R8_stub0.3_fw1.8", shapes.ghost(R=8.0, yc=14.0, stub=0.3, fw=1.8), COARSE))
    J.append(("B_ghost_R8.5_stub0.3_fw2.4", shapes.ghost(R=8.5, yc=14.5, stub=0.3, fw=2.4),
              COARSE))
    return J


def stage_B2():
    """The bat as a planar monopole (no legs: tail point on a short wide stub), 0.5 mm."""
    J = []
    for span in (36.0, 44.0, 52.0):
        J.append((f"B2_batpm_span{span:g}", shapes.bat("pm", span=span, yb=8.0, bh=6.0), COARSE))
    J.append(("B2_batpm_span44_yb10", shapes.bat("pm", span=44.0, yb=10.0, bh=7.0, ytip=1.5),
              COARSE))
    J.append(("B2_ghost_R8_stub0_fw2.4", shapes.ghost(R=8.0, yc=14.0, stub=0.0, fw=2.4), COARSE))
    J.append(("B2_splitifa_span48_yb7", shapes.bat("split_ifa", span=48.0, yb=7.0), COARSE))
    return J


def stage_B3():
    """Pull the ghost's in-band resistance from ~73 ohm toward 50: flatter bottom (0.5 mm)."""
    J = []
    for fl in (0.30, 0.15):
        J.append((f"B3_ghost_R8_flat{fl:g}", shapes.ghost(R=8.0, yc=14.0, stub=0.0, fw=2.4, flat=fl),
                  COARSE))
    J.append(("B3_ghost_R7.5_flat0.3", shapes.ghost(R=7.5, yc=13.5, stub=0.0, fw=2.4, flat=0.3),
              COARSE))
    J.append(("B3_ghost_R8_flat0.3_fw3.2", shapes.ghost(R=8.0, yc=14.0, stub=0.0, fw=3.2, flat=0.3),
              COARSE))
    return J


# the tuned designs (production mesh); the sensitivity study reuses these
GHOST = dict(R=7.0, yc=13.0, stub=0.0, fw=2.4, flat=0.30)
BAT_SPLIT = dict(kind="split_ifa", span=50.0)
BAT_DIPOLE = dict(kind="dipole", span=47.0, yb=16.0)
BAT_T = dict(kind="ifa", span=44.0)            # the solid bat: feet = feed + short
BAT_PM = dict(kind="pm", span=44.0, yb=8.0, bh=6.0)   # the legless bat: tail on the feed


def ghost_design(**kw):
    P = dict(GHOST)
    P.update(kw)
    return shapes.ghost(**P)


def bat_design(base, **kw):
    P = dict(base)
    P.update(kw)
    kind = P.pop("kind")
    return shapes.bat(kind, **P)


def stage_C():
    """The candidates on the production mesh (0.25 mm), with current maps."""
    FH = dict(FINE, hdump=True)
    return [
        ("C_ghost", ghost_design(), FH),
        ("C_bat_split", bat_design(BAT_SPLIT), FH),
        ("C_bat_dipole", bat_design(BAT_DIPOLE), FH),
        # TI's DN007 copied as-is onto this board (1.6 mm, 100 x 80 mm, centred)
        ("C_dn007_onboard", shapes.dn007(h=1.6, gnd_l=80.0, gnd_left=50 - 12.8,
                                         gnd_right=50 - 12.8), FINE),
    ]


def stage_B4():
    """Last ghost trim (0.5 mm)."""
    return [
        ("B4_ghost_R7_flat0.3", shapes.ghost(R=7.0, yc=13.0, stub=0.0, fw=2.4, flat=0.3), COARSE),
        ("B4_ghost_R7.5_flat0.15", shapes.ghost(R=7.5, yc=13.5, stub=0.0, fw=2.4, flat=0.15),
         COARSE),
    ]


def stage_Cbat():
    return [j for j in stage_C() if not j[0].startswith("C_ghost")]


def stage_Ct():
    return [("C_bat_t", bat_design(BAT_T), dict(FINE, hdump=True))]


def stage_Cpm():
    return [("C_bat_pm", bat_design(BAT_PM), dict(FINE, hdump=True))]


def stage_Cg():
    return [j for j in stage_C() if j[0].startswith("C_ghost")]


def stage_B5():
    """The legless (planar-monopole) bat: a wider, lower tail; a smaller span (0.5 mm)."""
    return [
        ("B5_batpm_span44_fw3.5", shapes.bat("pm", span=44.0, yb=8.0, bh=6.0, fw=3.5, ytip=0.6),
         COARSE),
        ("B5_batpm_span40", shapes.bat("pm", span=40.0, yb=8.0, bh=6.0), COARSE),
    ]


STAGES = {"A": stage_A, "B": stage_B, "B2": stage_B2, "B3": stage_B3, "B4": stage_B4, "B5": stage_B5,
          "C": stage_C, "Cbat": stage_Cbat, "Ct": stage_Ct, "Cg": stage_Cg,
          "Cpm": stage_Cpm}

if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "A"
    jobs = STAGES[st]()
    res = runner.run_many(jobs, npar=int(os.environ.get("NPAR", 5)), threads=int(os.environ.get("THREADS", 6)))
    print()
    for name, _, _ in jobs:
        if name in res:
            print(antsim.fmt(res[name]))
