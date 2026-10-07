"""The small boards' sheets: the tree, the perch, the bat, and the two familiar tokens.

Each board is its own piece of the panel, so each sheet is one board, with its own
reference numbers (tree 101+, perch 201+, bat 301+, owl 401+, cat 501+) and its own
power nets (+5V_T, GND_P...): the boards' nets meet only through mated connectors
(gen/connectors.py), never in the netlist.  The bat and the tokens have no power at
all: each is a coil, a capacitor and LEDs, lit by the field of the coil under it.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import sch_util as U
from sch_util import (G, part, hpart, vpart, gnd, flag, W, J, pwr_flag, label, note, title, nref, down, up,
                      series, line, vline, tag)
import leds as LEDS
import connectors as CONN
from parts import COILS

KEY = {"violet": "LED_VIOLET", "purple": "LED_PURPLE", "amber5050": "LED_AMBER5050", "orange": "LED_ORANGE"}


def S():
    return U.S


def joint_pins(conn, table):
    """Check a drawn connector's pins against its table: every pin is used."""
    assert sorted(table) == list(range(1, 17))
    return {p: conn.pin(str(p)) for p in table}


# ======================================================================================
# The tree
# ======================================================================================
def build_tree(sch):
    U.begin(sch, ref_base=100)
    sch.text(17.78, 20.32, "OWLternating Current: the tree", size=3.5, bold=True)
    gt, v3, v5 = "GND_T", "+3V3_T", "+5V_T"
    # ---- the two plugs: J101 into the base (bottom edge), J102 into the perch (top edge)
    yj = 95.25
    j1 = part("HEADER2x8RA", "J101", 195.58, yj, value="BASE", ref_at=(190.0, yj - 11.0), val_at=(196.5, yj - 11.0))
    j2 = part("HEADER2x8RA", "J102", 256.54, yj, value="PERCH", mirror="y", ref_at=(251.0, yj - 11.0),
              val_at=(257.5, yj - 11.0))
    p1, p2 = joint_pins(j1, CONN.BASE_TREE), joint_pins(j2, CONN.TREE_PERCH)
    # the even pins match: the coil's lines run straight across; the supplies get flags
    for p in (8, 10, 14, 16):
        W(p1[p], p2[p])
    xm = (p1[8][0] + p2[8][0]) / 2
    for a, b, name in ((8, 10, "LEV_B"), (14, 16, "LEV_A")):
        W((xm, p1[a][1]), (xm, p1[b][1]))
        J(xm, p1[a][1]); J(xm, p1[b][1])
        label(p1[a][0] + 2.0, p1[a][1], name)
    for p, net in ((2, v3), (4, v5)):
        for q, side in ((p1[p], +1), (p2[p], -1)):
            x = q[0] + side * G
            W(q, (x, q[1]))
            flag(net, x, q[1], rot=90 if side > 0 else 270)
    for p in (6, 12):
        for q, side in ((p1[p], +1), (p2[p], -1)):
            x = q[0] + side * G
            W(q, (x, q[1]))
            S().power(gt, x, q[1], rot=90 if side > 0 else 270)
    # J101's odd pins: the Hall line (on over the top to J102), the bus, grounds
    xh1, yh = p1[1][0] - G, 69.85
    xh2 = p2[1][0] + G
    W(p1[1], (xh1, p1[1][1]), (xh1, yh), (xh2, yh), (xh2, p2[1][1]), p2[1])
    label(xh1 + 2.0, yh, "HALL")
    xg = p1[7][0] - 5.08
    for p in (7, 9, 11, 13, 15):
        W(p1[p], (xg, p1[p][1]))
    vline(xg, [p1[p][1] for p in (7, 9, 11, 13, 15)])
    gnd(xg, p1[15][1], net=gt)
    W((xg, p1[13][1]), (xg - G, p1[13][1]))
    pwr_flag(xg - G, p1[13][1])                  # ground arrives through J101
    # J102's odd pins: grounds (one flag, sideways), and the perch's two downlights
    xg2 = p2[3][0] + 5.08
    for p in (3, 5, 7, 9, 11):
        W(p2[p], (xg2, p2[p][1]))
    vline(xg2, [p2[p][1] for p in (3, 5, 7, 9, 11)])
    W((xg2, p2[3][1]), (xg2 + G, p2[3][1]))
    S().power(gt, xg2 + G, p2[3][1], rot=90)

    # ---- U101, the LP5036 (mirrored: outputs left to the LEDs, the bus on its right) ---
    xu, yu = 124.46, 130.81
    u = part("LP5036", "U101", xu, yu, mirror="y", ref_at=(xu - 9.0, yu - 49.0), val_at=(xu + 2.0, yu + 46.5))
    sda, scl = u.pin("41"), u.pin("42")
    W(p1[3], sda)                                   # straight across
    xs = scl[0] + 20.32
    W(p1[5], (xs, p1[5][1]), (xs, scl[1]), scl)     # the one crossing: the plug has SDA above SCL
    label(sda[0] + 24.0, sda[1], "SDA"); label(xs + 4.0, p1[5][1], "SCL")
    # EN high; ADDR1 high, ADDR0 low: address 0x32
    en, a0, a1 = u.pin("43"), u.pin("38"), u.pin("39")
    W(en, (en[0] + G, en[1])); flag(v3, en[0] + G, en[1], rot=90)
    W(a0, (a0[0] + G, a0[1])); S().power(gt, a0[0] + G, a0[1], rot=90)
    W(a1, (a1[0] + G, a1[1])); flag(v3, a1[0] + G, a1[1], rot=90)
    vcc = u.pin("40")
    yr = vcc[1] - 12.7
    W(vcc, (vcc[0], yr))
    flag(v3, vcc[0], yr)
    line(yr, [vcc[0], vcc[0] + 5.08, vcc[0] + 15.24])
    tag("u101:cvcc"); down("C1U", vcc[0] + 5.08, yr, net=gt)
    tag("u101:cvcc_hf"); down("C100N", vcc[0] + 15.24, yr, net=gt)
    W((vcc[0], yr + 5.08), (vcc[0] - G, yr + 5.08))
    J(vcc[0], yr + 5.08)
    pwr_flag(vcc[0] - G, yr + 5.08)             # 3.3 V arrives through J101
    vcap, iref = u.pin("45"), u.pin("44")
    W(vcap, (vcap[0] + 10.16, vcap[1]))
    tag("u101:cvcap"); down("C1U", vcap[0] + 10.16, vcap[1], net=gt)
    W(iref, (iref[0] + G, iref[1]))
    tag("u101:riref"); down("R3K3", iref[0] + G, iref[1], net=gt)
    gnd(*u.pin("37"), net=gt)
    # the LEDs: two staggered columns, anodes to 4.8 V
    xo = u.pin("1")[0]
    downs = {}
    for (drv, ch), (name, colour, where) in sorted(LEDS.LEDS.items()):
        if drv != "TREE":
            continue
        out = u.pin(str(ch + 1))
        if name.startswith("PERCH_DOWN"):
            downs[name] = out
            continue
        xc = xo - 16.51 - 35.56 * (ch % 2)
        tag("led:%s" % name)
        d = part(KEY[colour], nref("D"), xc, out[1], rot=180, value=colour,
                 ref_at=(xc - 15.24, out[1] - 0.3), val_at=(xc - 15.24, out[1] + 0.3), justify="right", fsize=1.0)
        k, a = d.pin("1"), d.pin("2")
        W(k, out)
        flag(v5, *a, rot=270)
        label(k[0] + 1.0, out[1], name, size=0.9)
    used = {ch for (drv, ch) in LEDS.LEDS if drv == "TREE"}
    for ch in range(36):
        if ch not in used:
            S().nc(*u.pin(str(ch + 1)))
    # the perch's downlights: the driver's last two outputs, down under everything and up
    # into J102
    o33, o34 = downs["PERCH_DOWN0"], downs["PERCH_DOWN1"]
    yb0, yb1 = 193.04, 190.5
    xc0, xc1 = p2[13][0] + 12.7, p2[13][0] + 10.16
    W(o33, (o33[0] - 5.08, o33[1]), (o33[0] - 5.08, yb0), (xc0, yb0), (xc0, p2[13][1]), p2[13])
    W(o34, (o34[0] - G, o34[1]), (o34[0] - G, yb1), (xc1, yb1), (xc1, p2[15][1]), p2[15])
    label(o33[0] + 60.0, yb0, "DOWN0"); label(o33[0] + 60.0, yb1, "DOWN1")
    # 4.8 V: 10 uF at the plug
    xc = 220.98
    tag("tree:c5v"); t, b = vpart("C10U", nref("C"), xc, 140.97, fsize=1.0)
    flag(v5, *t)
    gnd(*b, net=gt)
    W(t, (t[0] - 5.08, t[1]))
    pwr_flag(t[0] - 5.08, t[1])                  # 4.8 V arrives through J101
    note(17.78, 200.66,
         "The tree stands in the base's socket (J101, a right-angle header: its pins point "
         "down) and carries the perch on its top (J102, the same part pointing up). Both "
         "joints follow gen/connectors.py. The levitation coil's current (LEV_A, LEV_B, "
         "3.3 A at most) and the Hall sensor's line pass straight up the trunk; the tree "
         "has its own LP5036 (U101, I2C 0x32) for the owls' eyes, the stars, the wisps and "
         "the perch's two downlights.", cols=60)
    note(160.02, 200.66,
         "Owls A, B, C: an orange eye pair each, one bank each (OUT0-1, 3-4, 6-7), so each "
         "owl's eyes open together. Stars OUT9-14 (violet), wisps OUT18-21 (purple). "
         "R on IREF: 22 mA at most per output.", cols=48)
    return sch


# ======================================================================================
# The perch
# ======================================================================================
def build_perch(sch):
    U.begin(sch, ref_base=200)
    sch.text(17.78, 20.32, "OWLternating Current: the perch", size=3.5, bold=True)
    gp_, v3, v5 = "GND_P", "+3V3_P", "+5V_P"
    yj = 100.33
    j = part("SOCKET2x8", "J201", 127.0, yj, value="TREE", ref_at=(121.5, yj - 11.0), val_at=(128.0, yj - 11.0))
    p = joint_pins(j, CONN.TREE_PERCH)
    # the levitation coil on the even side
    xl = p[8][0] + 22.86
    L = part("COIL_LEV", "L201", xl, (p[8][1] + p[16][1]) / 2, rot=270, value="29uH coil",
             ref_at=(xl + 2.5, (p[8][1] + p[16][1]) / 2 - 0.4), val_at=(xl + 2.5, (p[8][1] + p[16][1]) / 2 + 0.4),
             fsize=1.0)
    la, lb = L.pin("1"), L.pin("2")
    xa = p[8][0] + 7.62
    for a, b in ((8, 10), (14, 16)):
        W(p[a], (xa, p[a][1])); W(p[b], (xa, p[b][1]))
        vline(xa, [p[a][1], p[b][1]])
    W((xa, p[8][1]), (xa + 7.62, p[8][1]), (xa + 7.62, la[1]), la)
    W((xa, p[14][1]), (xa + 10.16, p[14][1]), (xa + 10.16, lb[1]), lb)
    J(xa, p[8][1]); J(xa, p[14][1])
    label(p[8][0] + 1.0, p[8][1], "LEV_B"); label(p[14][0] + 1.0, p[14][1], "LEV_A")
    for q, net in ((p[2], v3), (p[4], v5)):
        W(q, (q[0] + G, q[1])); flag(net, q[0] + G, q[1], rot=90)
    for n in (6, 12):
        W(p[n], (p[n][0] + G, p[n][1])); S().power(gp_, p[n][0] + G, p[n][1], rot=90)
    # odd side: grounds
    xg = p[3][0] - 5.08
    for n in (3, 5, 7, 9, 11):
        W(p[n], (xg, p[n][1]))
    vline(xg, [p[n][1] for n in (3, 5, 7, 9, 11)])
    W((xg, p[3][1]), (xg - G, p[3][1]))
    S().power(gp_, xg - G, p[3][1], rot=270)
    W((xg, p[11][1]), (xg - G, p[11][1]))
    pwr_flag(xg - G, p[11][1], rot=180)          # ground arrives through J201
    # the Hall sensor at the coil's centre, its line filtered where it starts
    xu = 30.48
    u = part("DRV5055", "U201", xu, p[1][1], ref_at=(xu + 2.0, p[1][1] - 12.5), val_at=(xu + 3.0, p[1][1] + 9.0))
    out = u.pin("2")
    tag("perch:rhall"); l, r = series("R1K", out[0] + 10.16, out[1])
    W(out, l)
    xc = r[0] + 7.62
    W(r, (xc, out[1]), p[1])
    tag("perch:chall"); down("C10N", xc, out[1], net=gp_)
    label(xc + 2.0, out[1], "HALL")
    vcc = u.pin("1")
    yr = vcc[1] - 7.62
    W(vcc, (vcc[0], yr))
    flag(v3, vcc[0], yr)
    W((vcc[0], yr), (vcc[0] - 7.62, yr))
    tag("perch:cvcc"); down("C100N", vcc[0] - 7.62, yr, net=gp_, text="left")
    J(vcc[0], yr)
    W((vcc[0], yr + G), (vcc[0] + G, yr + G))
    J(vcc[0], yr + G)
    pwr_flag(vcc[0] + G, yr + G)                 # 3.3 V arrives through J201
    gnd(*u.pin("3"), net=gp_)
    # the two downlights onto the bat: standing on their lines, anodes up to 4.8 V
    for n, name, dx in ((13, "DOWN0", 25.4), (15, "DOWN1", 45.72)):
        q = p[n]
        xd = q[0] - dx
        tag("led:PERCH_" + name)
        d = part("LED_VIOLET", nref("D"), xd, q[1] - 3.81, rot=90, value="violet",
                 ref_at=(xd + 2.2, q[1] - 4.1), val_at=(xd + 2.2, q[1] - 3.5), fsize=1.0)
        W(d.pin("1"), q)
        flag(v5, *d.pin("2"))
        label(xd + 3.0, q[1], name)
    tag("perch:c5v"); t, b = vpart("C1U", nref("C"), 78.74, 76.2, fsize=1.0)
    flag(v5, *t)
    gnd(*b, net=gp_)
    W(t, (t[0] + 5.08, t[1]))
    pwr_flag(t[0] + 5.08, t[1])                  # 4.8 V arrives through J201
    note(17.78, 140.97,
         "The perch lies across the top of the tree (J201, a socket on its underside). "
         "L201: the levitation coil, 11 turns on each of 4 layers round a 4 mm hole (about "
         "29 uH, 2 ohm). The printed owl clips over it and holds the bias magnet 14 mm above; "
         "the bat floats 8.5 mm under it. U201, DRV5055A4 (7.5 mV/mT at 3.3 V, ratiometric), at the "
         "coil's centre on the underside, reads the bat's magnet; 1k and 10n at its output "
         "keep the coil's switching off the long line down the tree. D201 and D202 light "
         "the bat from above.", cols=56)
    return sch


# ======================================================================================
# The bat and the two familiar tokens: a coil, a capacitor, LEDs
# ======================================================================================
def tank(sch, base, title_, coil_key, coil_val, cap_key, leds, text, who):
    """A receiver: the coil and the capacitor in parallel (resonant at the drive's
    frequency), and LEDs across them, each direction through its own resistor."""
    U.begin(sch, ref_base=base)
    sch.text(17.78, 20.32, "OWLternating Current: " + title_, size=3.5, bold=True)
    yt, yb = 76.2, 101.6
    xl, xc = 45.72, 66.04
    L = part(coil_key, "L%d" % (base + 1), xl, (yt + yb) / 2, rot=270, value=coil_val,
             ref_at=(xl - 2.5, (yt + yb) / 2 - 0.4), val_at=(xl - 2.5, (yt + yb) / 2 + 0.4), justify="right",
             fsize=1.0)
    W(L.pin("1"), (xl, yt)); W(L.pin("2"), (xl, yb))
    tag("%s:ctank" % who); t, b = vpart(cap_key, nref("C"), xc, (yt + yb) / 2, fsize=1.0)
    W(t, (xc, yt)); W(b, (xc, yb))
    x = xc + 20.32
    xs = [xl, xc]
    for k, (key, colour, rkey, down_) in enumerate(leds):
        xd = x + 15.24 * k
        rr = nref("R")
        U.ROLES["%s:r%d" % (who, k + 1)] = rr
        t2, b2 = vpart(rkey, rr, xd, yt + 6.35, fsize=1.0)
        tag("%s:led%d" % (who, k + 1))
        d = part(key, nref("D"), xd, yb - 6.35, rot=90 if down_ else 270, value=colour,
                 ref_at=(xd + 2.2, yb - 6.65), val_at=(xd + 2.2, yb - 6.05), fsize=1.0)
        W((xd, yt), t2)
        top, bot = sorted([d.pin("1"), d.pin("2")], key=lambda q: q[1])
        W(b2, top); W(bot, (xd, yb))
        xs.append(xd)
    line(yt, xs); line(yb, xs)
    note(17.78, 116.84, text, cols=64)
    return sch


def build_bat(sch):
    return tank(sch, 300, "the bat", "COIL_BAT", "36uH coil", "C100N_C0G",
                [("LED_SIDE_ORANGE", "orange", "R33", True), ("LED_SIDE_ORANGE", "orange", "R33", False)],
                "The bat floats under the perch (or swings on its thread over the pendulum coils). "
                "L301: 10 turns on each of 4 layers, 0.2 mm track and gap, round the magnet (r 7 to 11 "
                "mm), 36 uH; with C301 (100 nF C0G) it resonates at 84 kHz, where the levitation "
                "bridge adds its carrier. The two eyes (side-view orange LEDs at the head's edge) "
                "light on alternate half-cycles: about 4 mA each at 0.4 A of carrier, 7 mA at "
                "0.5 A (sim/physics/bat_power.py). No battery, no wires: the magnet in the printed "
                "cap holds it up, the field lights it.", "bat")


def build_owl(sch):
    return tank(sch, 400, "the owl token", "COIL_TOKEN", "11.5uH coil", "C100N_C0G",
                [("LED_ORANGE", "orange", "R150", True), ("LED_VIOLET", "violet", "R150", False)],
                "The owl familiar: put it on the owl's perch and it lights. L401 (7 turns on each "
                "of 4 layers, 11.5 uH) with C401 (100 nF C0G) resonates at 148 kHz; the owl perch "
                "drives there. Orange lights first; violet joins as the drive rises (its photons "
                "carry 3.1 eV against orange's 2.0). 150 R in each leg: the 4.8 V bridge cannot "
                "push either LED past about 20 mA, whatever the firmware does. At the cat's "
                "frequency (316 kHz) this tank shrinks the voltage and stays dark.", "owl")


def build_cat(sch):
    return tank(sch, 500, "the cat token", "COIL_TOKEN", "11.5uH coil", "C22N_C0G",
                [("LED_ORANGE", "orange", "R150", True), ("LED_VIOLET", "violet", "R150", False)],
                "The cat familiar: the same coil, tuned higher: C501 (22 nF C0G) with L501 resonates "
                "at 316 kHz, where the cat's perch drives. Below about 0.2 A of perch current the "
                "other familiar stays completely dark, so each perch lights only its own token "
                "(sim/physics/README.md).", "cat")
