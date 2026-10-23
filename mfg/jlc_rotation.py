#!/usr/bin/env python3
"""How a KiCad placement becomes a JLCPCB CPL rotation.  THE SOURCE OF TRUTH.

Import this; do not re-derive it.  It is the accumulated result of reading
JLCPCB's "Confirm parts placement" preview on real uploads, and every number
in it cost somebody a look at a screenshot.

    from jlc_rotation import cpl_rotation
    rot = cpl_rotation(native_degrees, side, footprint_name, lcsc_code)

TWO INDEPENDENT THINGS, APPLIED IN THIS ORDER:

  1. the bottom-side mirror, a property of how JLCPCB reads the BOARD;
  2. a correction, a property of JLCPCB's PARTS LIBRARY: per part
     (JLC_ROTATION_BY_PART, by LCSC code) where there is one, else per
     footprint (JLC_ROTATION).

Order matters and is not arbitrary -- see BOTTOM_FLIP.  Getting it backwards
moves parts that are known good.

(Copied into GPiBridge from the ECP5-2ADC-2DAC and Icepi Zero boards, where
every reading in JLC_ROTATION was made.  GPiBridge's corrections are in
JLC_ROTATION_BY_PART: predicted from JLCPCB's own drawings, then read in the
preview of GPiBridge rev A on 2026-10-06, all eleven right.)

ROTATION IS NOT THE WHOLE STORY: POSITION TOO.  JLCPCB puts THEIR library
part's origin where the CPL says.  Where their origin is not KiCad's, the
part lands off its pads by the difference, whatever the rotation.  Every
USB-C so far has: 1.3-1.6 mm towards its pad row, so the preview showed it
hanging off the board until Jason moved it by hand.  mfg/footprint_check.py
measures that offset for every part from their land pattern (its "datum"),
and mfg/make_release.py moves the JLCPCB CPL by it.
"""

import sys


# ---------------------------------------------------------------------------
# JLCPCB placement rotation.  KiCad's zero for a footprint and JLCPCB's zero
# for the same part in their feeder are different things, and the offset is a
# property of THEIR library: it cannot be derived from anything here.  The
# only authority is their "Confirm parts placement" preview.
#
# So this table is SHORT on purpose.  It holds corrections that were read off
# a real preview, and nothing else.  The GPSDO board took its numbers from a
# third-party table instead and got two wrong, one of them on 59 placements.
# Everything not listed goes into PLACEMENT_CHECKS.txt to be looked at.
# Positive is counter-clockwise, which is both KiCad's sign and JLCPCB's.
# "90 clockwise" therefore lands here as 270.
#
#   footprint: (correction, confidence, who said so and what they saw)
JLC_ROTATION = {
    "SOT-23-5":
        (180, "sure", "GPSDO board's preview, where this footprint appears 59 "
              "times.  Not contradicted on this board: it was already "
              "corrected in the CPL Jason uploaded and he did not flag it"),
    # Zero, and checked.  All eight of these are on the bottom and all eight
    # were read in the preview: the vertical ones were right and the
    # horizontal ones were wrong, which is what identified BOTTOM_FLIP.  The
    # footprint itself needs no correction -- the error was the placement
    # frame, not JLCPCB's part.
    "D_SOD-523":
        (0, "read-twice", "Jason, bottom preview: \"The ones oriented "
            "vertically are correct: D10 D11 D13.  The horizontal ones are "
            "incorrect: D6 D7 D8 D9 D12\".  Fixed by BOTTOM_FLIP, not by a "
            "correction here"),
    "VSSOP-8_2.3x2mm_P0.5mm":
        (180, "sure", "Jason, JLCPCB placement preview: \"U6 needs an "
              "additional 180 degree rotation\""),
    "Texas_DRT-3":
        (270, "sure-on-top", "Jason: \"U7,U8 need 90 clockwise\".  U7 and U8 "
              "are the TOP-side pair.  U5 and U10 are the same footprint on "
              "the BOTTOM and were not in view -- see PLACEMENT_CHECKS"),
    "TSOP-II-54_22.2x10.16mm_P0.8mm":
        (270, "sure", "Jason: \"U11 needs 90 clockwise\""),
    "QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm":
        # 180 on the first reading, then +90 CCW more on the second.  The
        # board wants U9's pin 1 at the SOUTH-WEST corner -- pad 1 is 1.00 mm
        # west and 1.94 mm south of centre, and the library's own triangle is
        # 2.28 west and 2.11 south, so both agree.  With 180 applied JLCPCB's
        # preview still showed their pin 1 at the north-west.  Adding to the
        # rotation walks pin 1 counter-clockwise, SE -> NE -> NW -> SW, so
        # NW needs one more quarter turn to reach SW.
        (270, "read-twice", "Jason, second preview: \"rotate U9 an additional "
              "90 degrees CCW so that the purple dot will line up with the "
              "silkscreen triangle in the SW\".  First reading was 180"),
    "SOIC-8_5.3x5.3mm_P1.27mm":
        (270, "sure", "Jason, first preview: \"U12 probably needs 90 "
              "clockwise if its pin 1 is supposed to be NE\".  Confirmed on "
              "the second: \"U12, the SOIC8, now looks right\""),
    # ZERO, and listed rather than left out.  Absent from this table means
    # nobody has looked; a zero here means somebody looked twice and it needs
    # nothing.  First reading was "seems to need 90 counter clockwise, but
    # it's hard to tell with all of the dots" -- there were thirteen dots
    # then and there is one now.  Second reading, with the correction
    # applied: "should still be rotated 90 CW more", and 90 CCW then 90 CW is
    # where it started.  It agrees with the geometry: pin 1 is Y1's
    # south-west corner, the preview showed their dot at the south-east, and
    # south-east turned a quarter clockwise is south-west.
    "Oscillator_SMD_SiT_PQFN-4Pin_2.5x2.0mm":
        (0, "read-twice", "Jason, second preview: \"Y1 seems wrong like it "
            "should still be rotated 90 CW more than it is in the corrected "
            "CPL\".  First reading was 90 CCW; the two cancel"),
}
# The HRO USB-C's ROTATION needs nothing: right on Jason's Lorenz attractor board,
# built by JLCPCB, and in GPiBridge's preview.  Its
# POSITION did: in both previews it hung off the board edge and its pads
# missed ours ("they put the USB low and I have to tell them to move it up",
# Lorenz; "sticking too far off the board ... This has been true for every
# USB-C connector", GPiBridge, 2026-10-06).  The Lorenz board's answer, that
# nothing in a CPL can address their model's origin, was wrong: their origin
# for C165948 is 1.572 mm from KiCad's, towards the pad row, and the JLCPCB
# CPL now puts the part there (make_release.py, from footprint_check.py's datum).
JLC_ROTATION["USB_C_Receptacle_HRO_TYPE-C-31-M-12"] = (
    0, "built", "Lorenz board and GPiBridge's preview: the rotation right; the position needs the "
       "datum shift, 1.572 mm, which the JLCPCB CPL now carries")

# PER PART, by LCSC code.  JLCPCB's library is drawn part by part, so two
# parts on one KiCad footprint can need different corrections, and on this
# board they do: JLCPCB draws the SN75161B upright, as KiCad does, and the
# SN75160B lying down.
#
# These were PREDICTED, then read: Jason checked GPiBridge rev A's preview on
# 2026-10-06, "For the standard release, all of the rotations were correct":
# 12 placements of these 11 part numbers.  The prediction: JLCPCB's own
# drawing of each part (its EasyEDA land pattern, which
# mfg/footprint_check.py fetches) is turned until it lies on our footprint;
# the correction is minus that turn.  Turned
# by PIN NUMBER where the numbers mean the same thing (chips, transistors,
# connectors), and by the POLARITY MARK drawn on it where JLCPCB numbers the
# pads its own way: their yellow and green LEDs call the cathode pad 2, and
# their inductor has its dot at pad 2 where Raspberry Pi's has it at pad 1.
#
# The method was tested (2026-10-06) against the top-side corrections in
# JLC_ROTATION, which Jason read off the Icepi Zero and GPSDO previews:
# Texas_DRT-3 270, SOT-23-5 180, VSSOP-8 180, QFN-20 270, TSOP-II-54 270,
# SOIC-8 270, the SiT oscillator 0.  It reproduced every one, for each of the
# 14 part numbers that use those 7 footprints on the Icepi Zero, GPSDO and
# ECP5-2ADC-2DAC boards.  It is untested on the bottom side, where GPiBridge
# places nothing.  The preview is still the authority: when somebody has looked,
# change "predicted" to what they saw.
#
#   LCSC code: (correction, confidence, the part and why)
JLC_ROTATION_BY_PART = {
    "C41378174": (0, "read", "RP2354A, U1: all 61 pads line up by number; their pin-1 dot is at pin 1"),
    "C2671348": (0, "read", "SN75161B, U3: JLCPCB draws it upright, pin 1 top left, as KiCad does"),
    "C882412": (270, "read", "SN75160B, U2: JLCPCB draws it lying down (pin 1 bottom left), a quarter "
                                  "turn from KiCad's; the same footprint as U3 and NOT the same correction"),
    "C15127": (180, "read", "AO3401A, Q1: JLCPCB's pin 1 is bottom right where KiCad's is top left; "
                                 "their dot is at pin 1"),
    "C8545": (180, "read", "2N7002, Q2: as Q1"),
    "C5446": (180, "read", "XC6206, U4: as Q1"),
    "C160389": (180, "read", "BM03B, J3 and J4: JLCPCB's pin 1 is at the right where KiCad's is at the "
                                  "left; their dot is at pin 1"),
    "C42411119": (180, "read", "AOTA inductor, L1, by its polarity dot: JLCPCB draws the dot at their "
                                    "pad 2, Raspberry Pi's footprint at pad 1.  By pad number it would be 0, "
                                    "with the dot at the wrong end"),
    "C2296": (0, "read", "yellow LED, D1, by the cathode mark: on the left in both drawings.  JLCPCB "
                              "numbers the cathode pad 2, so a fit by pad number says 180, which would "
                              "reverse it"),
    "C2297": (0, "read", "green LED, D2: as D1"),
    "C84256": (0, "read", "red LED, D3: cathode mark and pad 1 on the left in both drawings"),

    # OWLternating Current (2026-10-07): PREDICTED by the polarity mark in JLCPCB's own
    # drawing (the EasyEDA footprint record's png, read by eye), for the two-pad parts a
    # fit by pin number cannot judge, and for the through-hole headers, whose hole
    # pattern is the same turned round.  JLCPCB marks a diode's cathode "-" (C2296 above,
    # read right in GPiBridge's preview, is the calibration: "-" on the left, correction
    # 0).  KiCad's LED and diode footprints put the cathode at pad 1, on the left at 0;
    # its polarized capacitors put "+" at pad 1, on the left.
    "C965800": (0, "predicted", "XL-1608UOC-06 orange 0603 LED: JLCPCB's '-' (their pad 2) on the left at 0, "
                                "where our pad 1, the cathode, is"),
    "C51933300": (0, "predicted", "GL0603PU01 purple 0603 LED: '-' on the left, as C965800"),
    "C516136": (0, "predicted", "HL-A-3528S7VC violet 3528 LED: '-' (their pad 1), the cathode bar and the "
                                "corner mark on the left at 0, where our pad 1 is"),
    "C160472": (0, "predicted", "LTST-S270KFKT side-view LED: '-' (their pad 1) on the left and the lens "
                                "toward -y at 0, as our footprint (pad 1 cathode, light toward -y) and the "
                                "datasheet's top view (cathode left when the lens faces up)"),
    "C173431": (0, "predicted", "BZT52C10 SOD-123: '-' and the cathode bar on the left"),
    "C8598": (0, "predicted", "B5819W SOD-123: '-' and the cathode bar on the left (ECP5 read the same mark)"),
    "C19077569": (0, "predicted", "SMBJ15A SMB: '-' and the cathode bar on the left"),
    "C46550472": (0, "read", "470 uF polymer capacitor, C1: '+' and the bevelled corners on the left, where our "
                             "pad 1 (+12V) is, '-' on the right at pad 2 (GND).  Asked and settled: JLCPCB's "
                             "engineers queried C1's polarity on OWL rev A (2026-10-22, with a placement snapshot, "
                             "kept in mfg/jlcpcb_order/); their '+' was on the left pad, and Jason said proceed"),
    "C530531": (0, "read", "GSPK2307P speaker, LS1: '+' and the pin-1 dot on the left, where our pad 1 (square, "
                           "the NS4150B's VOP) is, '-' on the right at pad 2 (VON); either way sounds the same.  "
                           "Asked and settled: JLCPCB's engineers queried LS1's 3D orientation on OWL rev A "
                           "(2026-10-23, snapshot kept in mfg/jlcpcb_order/)"),
    "C2894988": (90, "predicted", "PZ254-2-08-W right-angle 2x8 header: JLCPCB draws the body and the bent pins "
                                  "toward +y at 0; our footprint's go toward +x, a quarter turn counter-clockwise. "
                                  "The hole pattern is the same turned half round, so only the drawing says which "
                                  "way the pins point: in the preview they must point off the board's edge"),
    "C2897409": (90, "predicted", "PM254-2-08-Z vertical 2x8 socket: JLCPCB draws its rows along x, ours along y; "
                                  "either quarter turn fits the holes and the part is the same turned half round"),
}

# POSITIONS read in a preview, by LCSC code.  The CPL moves a part to where JLCPCB's
# drawing has its origin (make_release.py datum_shift, from footprint_check.py's fit of
# their drawing on our pads); where the preview then still showed it off its pads, the
# reading goes here, and PLACEMENT_CHECKS.txt prints it under the part.  There is no
# number to apply yet: a reading with a measurement becomes a correction in datum_shift.
JLC_DATUM_READINGS = {
    "C431540": ("MSK12C02 slide switch, SW3, OWL rev A preview (Jason, 2026-10-09): with the CPL's shift of "
                "+0.251 mm north (the drawing's fit) it still sat a little south of its pads and was nudged north "
                "by eye, amount not measured; the order went with his nudge.  JLCPCB's part is their SW-TH_MSK12C02: "
                "its origin may be the pegs', not the pads'.  Next preview: measure how far, and put it here"),
}

# BOTTOM-SIDE PLACEMENTS ARE MIRRORED: rot -> 180 - rot, and it is CONFIRMED.
#
# KiCad reports a bottom footprint's angle in the board's top-view frame.
# JLCPCB wants it the other way up.  The transform is not a negation, which
# is what I guessed first and what the diodes refuted: it is 180 - rot, whose
# fixed points are 90 and 270 rather than 0 and 180.
#
# It is the unique transform consistent with every bottom-side observation
# anybody has made on this board, and there are ten of them:
#
#   must change by 180   D6 180, D7 0, D8 0, D9 180, D12 0   Jason: the
#                        horizontal diodes are the wrong ones
#   must NOT change      D10 90, D11 90, D13 270             the vertical
#                        ones are right
#   must NOT change      U5 270, U10 90                      confirmed good
#                        earlier, and they carry a +270 footprint correction
#
# Negation fits none of it.  Adding 180 fits none of it.  180 - rot fits all
# ten, and only when it is applied to the NATIVE angle BEFORE the per-
# footprint correction -- applied afterwards it moves U5 and U10, which are
# known good.  That ordering is also the one that makes sense: the mirror is
# a property of how bottom-side geometry maps into their frame, and the
# footprint correction is a property of their parts library.  Coordinate
# first, library offset on top.
#
# My prediction was the exact opposite of what Jason saw, which is worth more
# than a confirmation would have been: a negation and a flip are
# indistinguishable on 0 and 180, and every bottom part checked before the
# diodes happened to sit there.
BOTTOM_FLIP = True

# Two-terminal and unpolarised: which way round is not a question.
ROTATION_NA = ("R_0402_1005Metric", "R_0201_0603Metric", "C_0402_1005Metric",
               "C_0603_1608Metric", "L_0805_2012Metric",
               # the ECP5-2ADC-2DAC board's two-terminal and electrically symmetric parts (a 3225 crystal's pads 1/3
               # are the crystal and 2/4 the case either way round; the 4030 inductor and the 1812 fuse have two)
               "R_0603_1608Metric", "C_0402_1005Metric_BGA", "C_0805_2012Metric", "C_1206_3216Metric",
               "L_0603_1608Metric", "Fuse_1812_4532Metric", "IND-SMD_L4.0-W4.0", "Crystal_SMD_3225-4Pin_3.2x2.5mm",
               "SW-SMD_L3.9-W3.0-P4.45",
               # GPiBridge's: two-terminal parts, Raspberry Pi's 0402 footprints, and the BOOT button
               # (two pads, the same either way round)
               "R_0402_RPi", "C_0402_RPi", "C_0402_RPi_wide", "SW_SPST_TS-1088-xR020",
               # OWLternating Current's: the shunts, the PTC fuse and the buck's molded inductor
               # have two pads and no polarity
               "R_1206_3216Metric", "Fuse_2920_7451Metric", "L_Changjiang_FXL0630")

def correction(footprint, code=None):
    """(degrees, confidence, why) for one part: per part first, then per footprint."""
    if code in JLC_ROTATION_BY_PART:
        return JLC_ROTATION_BY_PART[code]
    return JLC_ROTATION.get(footprint, (0, "none", ""))


def cpl_rotation(native_deg, side, footprint, code=None, predicted=None):
    """The number that goes in JLCPCB's CPL for one placement.

    `native_deg` is KiCad's own footprint orientation (as KiCad's own flip
    stores it for the bottom side: pads mirrored top-to-bottom), `side` is
    "top" or "bottom", `footprint` is the footprint's short name, `code` its
    LCSC code.  `predicted` is the correction read off JLCPCB's own drawing of
    the part (mfg/make_release.py, from footprint_check.py's fit); it is used
    only where nobody has read the part in a preview.
    """
    rot = float(native_deg) % 360.0
    if BOTTOM_FLIP and side == "bottom":
        rot = (180.0 - rot) % 360.0
    corr, conf, _ = correction(footprint, code)
    if conf == "none" and predicted is not None:
        corr = predicted
    rot = (rot + corr) % 360.0
    return round(rot, 4)


def checked(footprint, code=None):
    """Has anybody looked at this part in a placement preview?"""
    if code in JLC_ROTATION_BY_PART:
        return JLC_ROTATION_BY_PART[code][1] not in ("predicted", "none")
    return footprint in JLC_ROTATION or footprint in ROTATION_NA


# The ten bottom-side readings BOTTOM_FLIP was derived from, kept so the rule
# can be re-checked rather than re-believed.  (ref, native, side, must_move)
EVIDENCE = [
    ("D6", 180, "bottom", True), ("D7", 0, "bottom", True),
    ("D8", 0, "bottom", True), ("D9", 180, "bottom", True),
    ("D12", 0, "bottom", True), ("D10", 90, "bottom", False),
    ("D11", 90, "bottom", False), ("D13", 270, "bottom", False),
    ("U5", 270, "bottom", False), ("U10", 90, "bottom", False),
]
EVIDENCE_FP = {"D6": "D_SOD-523", "D7": "D_SOD-523", "D8": "D_SOD-523",
               "D9": "D_SOD-523", "D12": "D_SOD-523", "D10": "D_SOD-523",
               "D11": "D_SOD-523", "D13": "D_SOD-523",
               "U5": "Texas_DRT-3", "U10": "Texas_DRT-3"}


def self_test():
    """Re-check the rule against every reading it was derived from."""
    bad = 0
    for ref, native, side, must_move in EVIDENCE:
        fp = EVIDENCE_FP[ref]
        before = (float(native) + (JLC_ROTATION.get(fp, (0,))[0])) % 360.0
        after = cpl_rotation(native, side, fp)
        moved = round((after - before) % 360.0) == 180
        if moved != must_move:
            print("  %-5s expected %s, got %s" %
                  (ref, "a 180 flip" if must_move else "no change",
                   "a 180 flip" if moved else "no change"))
            bad += 1
    print("%d of %d bottom-side readings still satisfied"
          % (len(EVIDENCE) - bad, len(EVIDENCE)))
    return bad


if __name__ == "__main__":
    sys.exit(1 if self_test() else 0)
