"""The base board's sheet (A1): power, the RP2354A, the LED driver and its LEDs, the
sensors, the coil bridges and coils, the perch drivers, the mux, the theremin, the
audio, and the tree's socket.

Layout.  Power runs along the top, left to right: the 12 V jack and its protection, the
4.8 V buck, then the OR of 4.8 V and USB (VSYS) and the 3.3 V regulator.  The RP2354A
stands in the middle with its supplies above it (Raspberry Pi's circuit, as on
GPiBridge).  To its left: the audio and the theremin at the top, then USB, the crystal,
the debug connectors and the buttons (GPiBridge's arrangement), and at the bottom the I2C
bus running left to the sensors and the LED driver with its columns of LEDs.  To its
right: the four DRV8874 coil bridges stacked (levitation on top), each with its coil and
current sense; the mux; the two perch bridges; and the tree's socket at the bottom right,
which the I2C bus and the Hall sensor's line reach by running under the RP2354A.

Every signal is a wire; only power and ground are flags (CLAUDE_PCB.md section 4).  The
pins' order on each side of the RP2354A (gen/symbols.py) is chosen so that its lines
leave it without crossing, and everything hangs off those pins, so moving a signal to
another GPIO (gen/pins.py) moves its whole line.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import sch_util as U
from sch_util import (G, part, hpart, vpart, gnd, flag, W, J, pwr_flag, label, note, title, box, nref, down,
                      up, series, tp, line, vline, diode)
import symbols as SYMB
import pins as PINS
import leds as LEDS

UX, UY = 419.1, 266.7                  # the RP2354A's centre
U4 = None


def pin(num):
    return U4.pin(num)


def gpin(net):
    return str(SYMB.GPIO_PIN[PINS.GPIO_OF[net]])


def gp(net):
    """Where the RP2354A's pin carrying `net` ends."""
    return pin(gpin(net))


# ======================================================================================
# Power: the 12 V input, its protection, the 4.8 V buck, VSYS and the 3.3 V regulator
# ======================================================================================
Y12 = 55.88                                         # the 12 V line


def power_in():
    title(17.78, 33.02, "12 V IN")
    j1 = part("JACK", "J1", 27.94, Y12 + G, ref_at=(20.32, Y12 - 6.0), val_at=(20.32, Y12 + 10.5))
    tip, sleeve, swp = j1.pin("1"), j1.pin("2"), j1.pin("3")
    xg = sleeve[0] + 5.08
    W(swp, (xg, swp[1]))
    W(sleeve, (xg, sleeve[1]))
    vline(xg, [swp[1], sleeve[1], sleeve[1] + G])
    gnd(xg, sleeve[1] + G)
    W((xg, sleeve[1] + G), (xg + 5.08, sleeve[1] + G))
    pwr_flag(xg + 5.08, sleeve[1] + G)
    # F1, then Q1 (drain toward the jack, source toward the load, gate below)
    xf = tip[0] + 12.7
    fl, fr = hpart("PTC5A", "F1", xf, Y12, ref_at=(xf, Y12 - 3.0), val_at=(xf, Y12 + 3.3))
    W(tip, fl)
    xq = fr[0] + 11.43
    q1 = part("AO4407A", "Q1", xq, Y12 + G, rot=90, mirror="y", ref_at=(xq - 1.0, Y12 - 4.3),
              val_at=(xq + 3.2, Y12 - 4.3), fsize=1.0)
    d, s, g_ = q1.pin("5"), q1.pin("1"), q1.pin("4")
    W(fr, d)
    yg = g_[1] + G
    W(g_, (g_[0], yg))
    down("R100K", g_[0], yg, text="left", ref="R1")
    xz = s[0] + 5.08
    z = part("BZT52C10", "D1", xz, yg - 3.81, rot=270, ref_at=(xz + 2.2, yg - 4.4), val_at=(xz + 2.2, yg - 3.2),
             fsize=1.0)
    W(z.pin("2"), (g_[0], yg))
    W(z.pin("1"), (xz, Y12))
    # the +12V line: Q1's source, D1, the TVS, the bulk capacitor, 10 uF, the flag, the pad
    x2, xb, xc, xfl, xt = xz + 15.24, xz + 30.48, xz + 45.72, xz + 55.88, xz + 60.96
    tv = part("SMBJ15A", "D2", x2, Y12 + G + 3.81, rot=270, ref_at=(x2 + 2.2, Y12 + 5.8),
              val_at=(x2 + 2.2, Y12 + 7.0), fsize=1.0)
    W((x2, Y12), tv.pin("1"))
    gnd(*tv.pin("2"))
    down("C470U", xb, Y12, ref="C1")
    down("C10U", xc, Y12, ref="C2")
    line(Y12, [s[0], xz, x2, xb, xc, xfl, xt])
    flag("+12V", xfl, Y12)
    W((xfl, Y12), (xfl, Y12 + G))
    pwr_flag(xfl, Y12 + G, rot=180)
    tp(xt, Y12, "+12V", ref="TP1")
    note(17.78, 82.55,
         "12 V, 5 A adapter (5.5 x 2.1 mm plug, centre positive; ORDER_LIST.md). "
         "F1 resets itself after a short: it holds 5 A and trips by 10 A. "
         "Q1 conducts only when the plug is the right way round: its body diode lifts the "
         "source, then the gate, pulled to ground by R1, turns it fully on (9.5 mOhm: 0.15 W "
         "at 4 A). D1 keeps the gate within 10 V of the source. Plugged in backwards, Q1 "
         "blocks. D2 clamps the ringing of a long cable at plug-in (up to twice the supply, "
         "Linear Technology AN88); C1's resistance damps it.", cols=50)
    return xt


def buck(x0):
    """TPS54302: 12 V to 4.8 V."""
    title(x0 + 2.54, 33.02, "4.8 V BUCK")
    xu = x0 + 60.96
    yu = Y12 + G
    u1 = part("TPS54302", "U1", xu, yu, ref_at=(xu - 3.8, yu - 7.0), val_at=(xu + 4.0, yu - 7.0))
    vin, en, ug = u1.pin("3"), u1.pin("5"), u1.pin("1")
    sw, boot, fb = u1.pin("2"), u1.pin("6"), u1.pin("4")
    gnd(*ug)
    # input: the +12V flag, 10 uF and 100 nF, the EN divider
    xf, xc1, xc2, xr = x0 + 5.08, x0 + 12.7, x0 + 25.4, x0 + 38.1
    flag("+12V", xf, Y12)
    line(Y12, [xf, xc1, xc2, xr, vin[0]])
    down("C10U", xc1, Y12)
    down("C100N", xc2, Y12)
    _, b2 = down("R100K", xr, Y12, net=None)
    down("R22K", xr, b2[1])
    xe = en[0] - G
    W(b2, (xe, b2[1]), (xe, en[1]), en)
    J(*b2)
    # BOOT capacitor from BOOT to SW, then the inductor
    xs = sw[0] + 10.16
    yb = boot[1] - 7.62
    W(boot, (boot[0] + G, boot[1]), (boot[0] + G, yb), (xs, yb))
    t, b = vpart("C100N", nref("C"), xs, yb + 3.81, fsize=1.0)
    W(b, (xs, sw[1]))
    l1, r1 = hpart("L10U", "L1", xs + 10.16, sw[1], ref_at=(xs + 10.16, sw[1] - 3.0),
                   val_at=(xs + 10.16, sw[1] + 3.3))
    line(sw[1], [sw[0], xs, l1[0]])
    # output: the feedback divider first (its wire to FB runs under the inductor), then
    # 2 x 22 uF, the +5V flag and the test pad
    xfb, x5a, x5b, xflag, xtp = r1[0] + 5.08, r1[0] + 15.24, r1[0] + 27.94, r1[0] + 38.1, r1[0] + 43.18
    line(sw[1], [r1[0], xfb, x5a, x5b, xflag, xtp])
    _, b4 = down("R36K", xfb, sw[1], net=None)
    down("R5K1", xfb, b4[1])
    xfw = fb[0] + 5.08
    W(fb, (xfw, fb[1]), (xfw, b4[1]), b4)
    J(*b4)
    down("C22U", x5a, sw[1])
    down("C22U", x5b, sw[1])
    flag("+5V", xflag, sw[1])
    W((xflag, sw[1]), (xflag, sw[1] + G))
    pwr_flag(xflag, sw[1] + G, rot=180)
    tp(xtp, sw[1], "+4.8V")
    note(x0 + 2.54, 82.55,
         "U1, TPS54302: 12 V to 4.8 V, 3 A, 400 kHz. "
         "4.8 V, not 5: 0.596 V x (1 + 36k/5.1k) = 4.80 V from a Preferred and a Basic "
         "resistor, and it keeps the audio amplifier (5.25 V absolute maximum) clear of its "
         "limit. The rail is called +5V; it runs the LEDs, the perch drivers, the audio "
         "amplifier and the tree. EN through 100k/22k: the buck starts above 6.7 V (EN may "
         "not see 12 V).", cols=46)
    return xtp


def vsys_ldo(x0):
    """VSYS = 4.8 V or USB through two Schottky diodes; the 3.3 V regulator after it."""
    title(x0 + 2.54, 33.02, "VSYS AND 3.3 V")
    yv = Y12
    a3, k3 = diode("B5819W", "D3", x0 + 12.7, yv)
    flag("+5V", a3[0] - 5.08, yv)
    W((a3[0] - 5.08, yv), a3)
    yb = yv + 10.16
    a4, k4 = diode("B5819W", "D4", x0 + 12.7, yb)
    flag("VBUS", a4[0] - 5.08, yb)
    W((a4[0] - 5.08, yb), a4)
    xn = k3[0] + 5.08
    W(k4, (xn, yb), (xn, yv))
    xu = xn + 25.4
    u2 = part("XC6206", "U2", xu, yv, ref_at=(xu - 6.0, yv - 4.0), val_at=(xu + 2.0, yv + 7.0))
    vi, vo = u2.pin("3"), u2.pin("2")
    gnd(*u2.pin("1"))
    xf, xc = xn + 5.08, xn + 10.16
    line(yv, [k3[0], xn, xf, xc, vi[0]])
    flag("VSYS", xf, yv)
    W((xf, yv), (xf, yv + G))
    pwr_flag(xf, yv + G, rot=180)
    down("C1U", xc, yv)
    xo, xfl, xt = vo[0] + 5.08, vo[0] + 15.24, vo[0] + 20.32
    line(yv, [vo[0], xo, xfl, xt])
    down("C1U", xo, yv)
    flag("+3V3", xfl, yv)
    tp(xt, yv, "+3V3")
    tp(xn, yv - 7.62, "VSYS")
    W((xn, yv), (xn, yv - 7.62))
    note(x0 + 2.54, 82.55,
         "VSYS is 4.8 V less a Schottky drop, or USB's 5 V less one: so the RP2354A, the "
         "sensors and the LED drivers' logic run from USB alone (to program the board "
         "without the adapter), while USB never feeds the 4.8 V rail and its loads. U2, "
         "XC6206: 3.3 V, 200 mA, stable with ceramic capacitors; the logic draws about "
         "110 mA. Dropout 0.25 V: VSYS may sag to 3.6 V.", cols=44)


# ======================================================================================
# The RP2354A, its supplies, USB, crystal, debug and buttons (GPiBridge's, copied)
# ======================================================================================
def mcu():
    global U4
    hw = (len(SYMB.RP_TOP) + 1) * SYMB.RP_TOP_PITCH / 2
    hh = max(len(SYMB.RP_LEFT), len(SYMB.RP_RIGHT)) * G / 2 + G / 2
    U4 = part("RP2354A", "U4", UX, UY, ref_at=(UX - hw, UY - hh - 1.2), val_at=(UX - hw, UY + hh + 1.2))
    xs = {p[0]: pin(p[0])[0] for p in SYMB.RP_TOP}
    ytop = pin("46")[1]
    Y33, Y11, Yj = ytop - 27.94, ytop - 20.32, ytop - 15.24

    def decap(num, key="C100N"):
        """The capacitor hangs beside its pin's wire; its name and value sit centred
        under its ground, between the wires."""
        x = xs[num]
        W((x, Yj), (x + G, Yj))
        t, b = vpart(key, nref("C"), x + G, Yj + 3.81, fsize=1.0, justify="center",
                     ref_at=(x + G, ytop - 2.0), val_at=(x + G, ytop - 2.0))
        gnd(*b)
        J(x, Yj)

    x = xs["46"]                                    # VREG_AVDD: 33 R and 4.7 uF (Raspberry Pi's R3, C9)
    t, b = vpart("R33_RPI", nref("R"), x, Y33 + 3.81, fsize=1.0)
    W(b, (x, ytop))
    W((x, b[1] + G), (x - G, b[1] + G))
    J(x, b[1] + G)
    pwr_flag(x - G, b[1] + G)
    decap("46", "C4U7_RPI")
    W((xs["49"], Y33), (xs["49"], ytop))            # VREG_VIN: 4.7 uF
    decap("49", "C4U7_RPI_WIDE")
    yL = ytop - 5.08                               # VREG_LX through L2 to the 1.1 V node
    W((xs["48"], ytop), (xs["48"], yL))
    xm = (xs["48"] + xs["50"]) / 2
    part("L3U3", "L2", xm, yL, rot=270, ref_at=(xm - 3.0, yL - 1.7), val_at=(xm - 3.0, yL + 1.5), fsize=1.0)
    W((xs["50"], ytop), (xs["50"], Y11))            # VREG_FB senses it
    J(xs["50"], yL)
    decap("50", "C4U7_RPI_WIDE")
    dv = [p[0] for p in SYMB.RP_TOP if p[1] == "DVDD"]
    W((xs["50"], Y11), (xs[dv[-1]], Y11))
    for n in dv:
        W((xs[n], Y11), (xs[n], ytop))
        if n != dv[-1]:
            J(xs[n], Y11)
        decap(n)
    flag("+1V1", xs["50"], Y11)
    J(xs[dv[0]] + 3.81, Y11)
    pwr_flag(xs[dv[0]] + 3.81, Y11)
    io = [p[0] for p in SYMB.RP_TOP if p[1] in ("IOVDD", "QSPI_IOVDD", "USB_OTP_VDD", "ADC_AVDD")]
    for n in io:
        W((xs[n], Y33), (xs[n], ytop))
        decap(n)
        if n != io[-1]:
            J(xs[n], Y33)
    xf3 = xs["46"] - 7.62
    W((xf3, Y33), (xs[io[-1]], Y33))
    flag("+3V3", xf3, Y33)
    J(xs["46"], Y33)
    J(xs["49"], Y33)
    for n in ("47", "61"):
        gnd(*pin(n))
    x11 = xs[dv[-1]] - 3.81
    tp(x11, Y11, "+1V1")
    J(x11, Y11)
    note(xs["46"] - 3.0, Y33 - 21.0,
         "Core regulator (1.1 V): Raspberry Pi's parts and layout, copied exactly "
         "(gen/rpi_minimal), as on GPiBridge. L2 is polarity-marked: its dot must sit as "
         "their footprint shows.", cols=44)
    note(xs["1"] - 3.0, Y33 - 21.0,
         "3.3 V and 1.1 V: one 100 nF at every supply pin. ADC_AVDD shares the 3.3 V: the "
         "ADC reads currents and a Hall sensor to 1 %, not microvolts.", cols=44)


def mcu_left():
    """USB, crystal, SWD, RUN/BOOT, the unused QSPI pins, UART, the SPELL button: the
    blocks GPiBridge validated, at the same distances from the pins."""
    xL = pin("51")[0]

    def ry(num):
        return pin(num)[1]

    # ---- USB-C -------------------------------------------------------------------------
    J2x = xL - 110.49
    J2 = part("USBC", "J2", J2x, ry("51"), ref_at=(J2x - 10.16, ry("51") - 19.1), val_at=(J2x - 10.16, ry("51") + 26.4))
    xst = J2.pin("A7")[0] + G
    for a, b in (("A7", "B7"), ("A6", "B6")):
        W(J2.pin(a), (xst, J2.pin(a)[1]), (xst, J2.pin(b)[1]), J2.pin(b))
    ydm, ydp = J2.pin("B7")[1], J2.pin("A6")[1]
    J(xst, ydm); J(xst, ydp)
    l, r = hpart("R27", nref("R"), xL - 17.78, ydm)
    W((xst, ydm), l); W(r, pin("51"))
    label(xst + 3.0, ydm, "USB_D-"); label(r[0] + 1.0, ydm, "USB_DM")
    l, r = hpart("R27", nref("R"), xL - 30.48, ydp, ref_at=(xL - 34.29, ydp + 3.0), val_at=(xL - 30.48, ydp + 1.6))
    W((xst, ydp), l); W(r, pin("52"))
    label(xst + 3.0, ydp, "USB_D+"); label(r[0] + 1.0, ydp, "USB_DP")
    note(xL - 52.0, ydp + 4.6, "USB 2.0 full speed, 12 Mbit/s. 27 R at the chip (RP2350 datasheet).", cols=40)
    cc1, cc2 = J2.pin("A5"), J2.pin("B5")
    l, r = hpart("R5K1", nref("R"), cc2[0] + 7.62, cc2[1], ref_at=(cc2[0] + 3.2, cc2[1] + 3.0),
                 val_at=(cc2[0] + 3.2, cc2[1] + 3.0))
    W(cc2, l); gnd(*r)
    l, r = hpart("R5K1", nref("R"), cc1[0] + 20.32, cc1[1], ref_at=(cc1[0] + 15.24, cc1[1] - 1.6),
                 val_at=(cc1[0] + 21.6, cc1[1] - 2.9))
    W(cc1, l); gnd(*r)
    note(cc1[0] + 27.0, cc1[1] + 1.4, "CC1, CC2: 5.1 k to ground say 'device'; the host then gives 5 V.", cols=32)
    for n in ("A8", "B8"):
        S().nc(*J2.pin(n))
    W(J2.pin("SH"), J2.pin("A1"))
    gnd(*J2.pin("A1"))
    vb = J2.pin("A4")
    xvb, yvb = vb[0] + 5.08, vb[1] - 12.7
    W(vb, (xvb, vb[1]), (xvb, yvb))
    W((xvb, vb[1]), (xvb + G, vb[1]))
    pwr_flag(xvb + G, vb[1])
    flag("VBUS", xvb, yvb)
    line(yvb, [xvb, xvb + 7.62, xvb + 15.24])
    down("C10U", xvb + 7.62, yvb)
    tp(xvb + 15.24, yvb, "VBUS")
    note(J2x - 20.0, ry("51") + 31.0, "USB-C: programming and the console. It powers the logic (about "
         "110 mA), never the LEDs or coils.", cols=36)

    # ---- crystal ----------------------------------------------------------------------
    yi, yo = ry("21"), ry("22")
    Xc = xL - 33.02
    yc = (yi + yo) / 2
    Y1 = part("Y12M", "Y1", Xc, yc, rot=270, ref_at=(Xc + 4.4, yc - 0.3), val_at=(Xc + 4.4, yc + 0.3))
    W(pin("21"), (Xc, yi), Y1.pin("1"))
    l, r = hpart("R1K", nref("R"), xL - 15.24, yo)
    W(pin("22"), r); W(l, (Xc, yo), Y1.pin("3"))
    for yy in (yi, yo):
        l, r = hpart("C15P", nref("C"), Xc - 7.62, yy, ref_at=(Xc - 12.7, yy - 2.6), val_at=(Xc - 5.6, yy - 2.6))
        W(r, (Xc, yy)); gnd(*l)
        J(Xc, yy)
    gnd(*Y1.pin("2"))
    note(Xc - 24.0, yo + 6.4, "ABM8-272-T3, 12 MHz, 10 pF load: the crystal Raspberry Pi specifies, with "
         "their 15 pF loads and the 1 k that limits its drive.", cols=40)

    # ---- SWD --------------------------------------------------------------------------
    ysc, ysd = ry("24"), ry("25")
    J4x = J2x
    J4 = part("JSTSH3", "J4", J4x, ysd, value="SWD", sym="Conn_SWD", ref_at=(J4x - 3.81, ysd - 6.4),
              val_at=(J4x + 4.6, ysd - 6.4))
    l, r = hpart("R100", nref("R"), xL - 15.24, ysc)
    W(J4.pin("1"), l); W(r, pin("24"))
    l, r = hpart("R100", nref("R"), xL - 27.94, ysd, ref_at=(xL - 32.2, ysd + 3.0), val_at=(xL - 26.4, ysd + 1.6))
    W(J4.pin("3"), l); W(r, pin("25"))
    gnd(*J4.pin("2")); gnd(*J4.pin("MP"))
    note(J4x - 18.0, ysd + 14.5, "Raspberry Pi debug connector (JST-SH 3-pin): the Debug Probe's 'D' "
         "cable. 100 R in each line, at the connector. 3.3 V logic.", cols=34)

    # ---- RUN and BOOT -----------------------------------------------------------------
    yb = ry("60")
    S().nc(*pin("26"))
    l, r = hpart("R1K", nref("R"), xL - 15.24, yb)
    W(pin("60"), r)
    sw = part("BUTTON", "SW1", xL - 33.02, yb, value="BOOT", ref_at=(xL - 38.1, yb - 3.3), val_at=(xL - 30.48, yb - 3.3))
    W(l, sw.pin("2"))
    gnd(*sw.pin("1"))
    note(xL - 98.0, yb + 4.0, "BOOT: hold it while plugging in to start the RP2354A's USB bootloader. Rarely "
         "needed: 'picotool reboot -f -u' gets there from software. RUN stays open: it has its own "
         "pull-up inside the RP2354A, and the Debug Probe resets the chip over SWD.", cols=40)
    for n in ("56", "57", "59", "58", "55"):
        S().nc(*pin(n))
    note(xL - 52.0, ry("57") - 1.0, "The 2 MB flash is inside the RP2354A; these stay open.", cols=24)

    # ---- UART -------------------------------------------------------------------------
    yrx, ytx = ry(gpin("UART_RX")), ry(gpin("UART_TX"))
    J5 = part("JSTSH3", "J5", J4x, ytx, value="UART", sym="Conn_UART", ref_at=(J4x - 3.81, ytx - 6.4),
              val_at=(J4x + 4.6, ytx - 6.4))
    l, r = hpart("R100", nref("R"), xL - 15.24, yrx)
    W(J5.pin("1"), l); W(r, pin(gpin("UART_RX")))
    l, r = hpart("R100", nref("R"), xL - 27.94, ytx, ref_at=(xL - 32.2, ytx + 3.0), val_at=(xL - 26.4, ytx + 1.6))
    W(J5.pin("3"), l); W(r, pin(gpin("UART_TX")))
    gnd(*J5.pin("2")); gnd(*J5.pin("MP"))
    note(J4x - 18.0, ytx + 14.5, "UART0 console, 115200 baud: the Debug Probe's 'U' cable. Works when USB "
         "does not.", cols=34)

    # ---- the SPELL button ---------------------------------------------------------------
    ybt = ry(gpin("BUTTON"))
    l, r = hpart("R1K", nref("R"), xL - 15.24, ybt)
    W(pin(gpin("BUTTON")), r)
    sw2 = part("BUTTON", "SW2", xL - 33.02, ybt, value="SPELL", ref_at=(xL - 38.1, ybt - 3.3),
               val_at=(xL - 30.48, ybt - 3.3))
    W(l, sw2.pin("2"))
    gnd(*sw2.pin("1"))
    for name, num in (("XIN", "21"), ("SWCLK", "24"), ("SWDIO", "25"), ("QSPI_SS", "60"),
                      ("UART_RX", gpin("UART_RX")), ("UART_TX", gpin("UART_TX")), ("BUTTON", gpin("BUTTON"))):
        x, y = pin(num)
        label(x - 11.5, y, name)
    label(pin("22")[0] - 7.5, ry("22"), "XOUT")


# ======================================================================================
# The audio and the theremin, above-left of the RP2354A
# ======================================================================================
def audio_theremin():
    """AUDIO, PITCH and VOL leave the top of the RP2354A's left side, rise, run left over
    the USB block, and drop into their blocks: the audio chain (which runs on to the left,
    away from the chip) at the top, the two theremin oscillators below it."""
    xa_col, xp_col, xv_col = 346.71, 344.17, 341.63         # rising columns by the chip
    ya, yp, yv = 140.97, 143.51, 146.05                      # their rows over the USB block
    xa_dn, xp_dn, xv_dn = 210.82, 213.36, 215.9              # where they drop
    pa, pp, pv = gp("AUDIO"), gp("THEREMIN_PITCH"), gp("THEREMIN_VOL")
    W(pa, (xa_col, pa[1]), (xa_col, ya), (xa_dn, ya))
    W(pp, (xp_col, pp[1]), (xp_col, yp), (xp_dn, yp))
    W(pv, (xv_col, pv[1]), (xv_col, yv), (xv_dn, yv))
    for (x, y, nm) in ((xa_col, ya, "AUDIO"), (xp_col, yp, "THEREMIN_PITCH"), (xv_col, yv, "THEREMIN_VOL")):
        label(x - 30.0, y, nm)

    # ---- audio: RC, RC, coupling, the amplifier, the speaker, the sound switch --------------
    y_in = 175.26                                            # the audio line
    title(22.86, y_in - 27.94, "AUDIO")
    W((xa_dn, ya), (xa_dn, y_in))
    x = xa_dn
    l1, r1 = series("R1K", x - 7.62, y_in)
    xc1 = l1[0] - 5.08
    l2, r2 = series("R1K", xc1 - 7.62, y_in)
    xc2 = l2[0] - 5.08
    l3, r3 = series("C22N", xc2 - 7.62, y_in)
    l4, r4 = series("R100K", l3[0] - 7.62, y_in)
    line(y_in, [x, r1[0]])
    line(y_in, [l1[0], xc1, r2[0]])
    line(y_in, [l2[0], xc2, r3[0]])
    W(l3, r4)
    down("C10N", xc1, y_in)
    down("C10N", xc2, y_in)
    # U14 mirrored: inputs on its right, outputs on its left; INP on the audio line
    xu = l4[0] - G - 11.43
    yu = y_in + G
    u14 = part("NS4150B", "U14", xu, yu, mirror="y", ref_at=(xu - 3.0, yu - 10.0), val_at=(xu + 5.5, yu - 10.0))
    inn, inp, ctrl, byp = u14.pin("4"), u14.pin("3"), u14.pin("1"), u14.pin("2")
    vop, von = u14.pin("8"), u14.pin("5")
    W(inp, l4)
    # INN: the same 100k and 22n, to ground, rising away from the signal line
    yn = inn[1] - 10.16
    W(inn, (inn[0] + G, inn[1]), (inn[0] + G, yn))
    l5, r5 = series("R100K", inn[0] + G + 6.35, yn)
    l6, r6 = series("C22N", r5[0] + 6.35, yn)
    W((inn[0] + G, yn), l5); W(r5, l6)
    gnd(*r6)
    # supply: 4.8 V, 10 uF and 1 uF
    vcc = u14.pin("6")
    yr = vcc[1] - 5.08
    W(vcc, (vcc[0], yr))
    flag("+5V", vcc[0], yr)
    line(yr, [vcc[0], vcc[0] - 7.62, vcc[0] - 20.32])
    down("C10U", vcc[0] - 7.62, yr, text="left")
    down("C1U", vcc[0] - 20.32, yr, text="left")
    gnd(*u14.pin("7"))
    # BYPASS: 1 uF; CTRL: the sound switch through 10k, held low by 100k between
    xb = byp[0] + 5.08
    W(byp, (xb, byp[1]))
    down("C1U", xb, byp[1])
    xcv = ctrl[0] + 15.24
    ys = ctrl[1] + 22.86
    W(ctrl, (xcv, ctrl[1]), (xcv, ys))
    down("R100K", xcv, ys, text="left")
    l7, r7 = series("R10K", xcv + 8.89, ys)
    W((xcv, ys), l7)
    sw3 = part("SLIDE", "SW3", r7[0] + 10.16, ys, value="SOUND", ref_at=(r7[0] + 7.6, ys - 5.0),
               val_at=(r7[0] + 7.6, ys + 4.5))
    W(r7, sw3.pin("2"))
    a, c = sw3.pin("1"), sw3.pin("3")
    W(a, (a[0] + G, a[1]), (a[0] + G, a[1] - G))
    flag("+5V", a[0] + G, a[1] - G)
    W(c, (c[0] + G, c[1]))
    gnd(c[0] + G, c[1])
    J(xcv, ys)
    # the speaker, its two pins facing the outputs
    ls = part("SPEAKER", "LS1", vop[0] - 15.24, vop[1], mirror="y", ref_at=(vop[0] - 22.0, vop[1] - 6.0),
              val_at=(vop[0] - 22.0, vop[1] + 8.5))
    W(vop, ls.pin("1")); W(von, ls.pin("2"))
    note(22.86, y_in - 22.86,
         "AUDIO is PWM at about 150 kHz. Two RC stages (1k, 10n: 16 kHz each) leave the "
         "tone and take the carrier down 38 dB; 22n and 100k pass 72 Hz and up. U14, "
         "NS4150B: class D, gain 240k/100k = 2.4. Full scale is about 0.5 W in the 8 ohm, "
         "23 mm speaker, more than a bedroom needs: the firmware sets the volume. "
         "SW3 off (or no 12 V adapter) shuts U14 down: no sound at all, whatever the "
         "firmware does.", cols=48)

    # ---- the theremin's two oscillators ------------------------------------------------
    def osc(ref, ydst, xdn, ycol, name, antenna):
        """A Schmitt-trigger RC oscillator whose capacitor is a copper shape on the board:
        a hand near the shape adds capacitance and lowers the frequency."""
        xo = xdn - 40.64
        u = part("LVC1G14", ref, xo, ydst, ref_at=(xo + 1.0, ydst - 12.5), val_at=(xo + 1.0, ydst + 13.5))
        i, o = u.pin("2"), u.pin("4")
        S().nc(*u.pin("1"))
        gnd(*u.pin("3"))
        vcc = u.pin("5")
        yr = vcc[1] - 5.08
        W(vcc, (vcc[0], yr))
        flag("+3V3", vcc[0], yr)
        W((vcc[0], yr), (vcc[0] + 7.62, yr))
        down("C100N", vcc[0] + 7.62, yr)
        # output through 33 R to the RP2354A
        lo, ro = series("R33", o[0] + 7.62, ydst, above=False)
        xn = o[0] + 2.54
        line(ydst, [o[0], xn, lo[0]])
        W(ro, (xdn, ydst), (xdn, ycol))
        # feedback 100k from the output back to the input, under the chip
        yf = ydst + 15.24
        xi = i[0] - 5.08
        W((xn, ydst), (xn, yf))
        lf, rf = series("R100K", (xn + xi) / 2, yf, above=False)
        W((xn, yf), rf); W(lf, (xi, yf), (xi, ydst))
        W(i, (xi, ydst))
        # the timing capacitor and the antenna (the copper shape) on the input
        xa = xi - 7.62
        W((xi, ydst), (xa, ydst))
        down("C15P", xa, ydst)
        ant = part("ANTENNA", "AE1" if name == "PITCH" else "AE2", xa - 7.62, ydst - 5.08,
                   value=antenna, ref_at=(xa - 11.0, ydst - 7.0), val_at=(xa - 11.0, ydst - 7.0), justify="right")
        W((xa, ydst), ant.pin("1"))
        J(xi, ydst); J(xa, ydst); J(xn, ydst)
        label(ro[0] + 2.0, ydst, "THEREMIN_" + name)

    title(22.86, 220.98, "THEREMIN")
    osc("U12", 238.76, xp_dn, yp, "PITCH", "moon")
    osc("U13", 281.94, xv_dn, yv, "VOL", "ghost")
    note(22.86, 226.06,
         "Each oscillator: a 74LVC1G14 with 100k feedback; its capacitor is 15 pF plus a gold "
         "copper shape (the moon, the ghost: their pads AE1 and AE2), about 500 kHz. A hand "
         "10 cm away adds a fraction of a picofarad and lowers the frequency by a few "
         "kHz; the RP2354A's PIO counts each for 10 ms (100 Hz resolution), 100 times a "
         "second. Pitch from the moon, volume from the ghost. The two run about 20 % "
         "apart (different shapes), so they do not lock to each other.", cols=48)


# ======================================================================================
# The I2C bus, the sensors, the LED driver and its LEDs (bottom left)
# ======================================================================================
# the corner columns where the bus leaves the RP2354A's bottom-left pins
X_HALL, X_SDA, X_SCL = 346.71, 344.17, 341.63
# their rows under the chip, on the way right to the tree's socket
Y_HALL_U, Y_SDA_U, Y_SCL_U = 356.87, 359.41, 361.95
# the columns down to the socket's row, right of the chip
XB_HALL, XB_SDA, XB_SCL = 497.84, 495.3, 492.76


def bus_left():
    pi, pc, pd, ph = gp("IMU_INT"), gp("SCL"), gp("SDA"), gp("HALL")
    yi, yc, yd = pi[1], pc[1], pd[1]
    # down the corner and under the chip (to the tree's socket)
    W(ph, (X_HALL, ph[1]), (X_HALL, Y_HALL_U), (XB_HALL, Y_HALL_U))
    W(pd, (X_SDA, yd), (X_SDA, Y_SDA_U), (XB_SDA, Y_SDA_U))
    W(pc, (X_SCL, yc), (X_SCL, Y_SCL_U), (XB_SCL, Y_SCL_U))
    J(X_SDA, yd); J(X_SCL, yc)
    label(X_HALL + 6.0, Y_HALL_U, "HALL"); label(X_SDA + 6.0, Y_SDA_U, "SDA"); label(X_SCL + 6.0, Y_SCL_U, "SCL")

    # ---- U3, the LP5036 (mirrored: outputs left to the LEDs, the bus on its right) ------
    xl = 170.18
    yl = yc + 43.18
    u3 = part("LP5036", "U3", xl, yl, mirror="y", ref_at=(xl - 6.0, yl - 49.0), val_at=(xl + 2.0, yl + 46.5))
    xr = u3.pin("42")[0]
    assert abs(u3.pin("42")[1] - yc) < 0.01 and abs(u3.pin("41")[1] - yd) < 0.01
    # the bus, left from the chip's corner to U3; pull-ups near U3
    xpc, xpd = xr + 12.7, xr + 20.32
    line(yc, [xr, xpc, X_SCL])
    line(yd, [xr, xpd, X_SDA])
    up("R2K2", xpc, yc, "+3V3")
    up("R2K2", xpd, yd, "+3V3", rise=5.08)
    label(xr + 25.0, yc, "SCL"); label(xr + 25.0, yd, "SDA")
    # EN high; ADDR0 = ADDR1 = ground: address 0x30
    en, a0, a1 = u3.pin("43"), u3.pin("38"), u3.pin("39")
    W(en, (en[0] + G, en[1]))
    flag("+3V3", en[0] + G, en[1], rot=90)
    W(a0, (a0[0] + G, a0[1]), (a0[0] + G, a1[1]), a1)
    gnd(a0[0] + G, a1[1])
    # VCC, VCAP, IREF
    vcc = u3.pin("40")
    yr = vcc[1] - 12.7
    W(vcc, (vcc[0], yr))
    flag("+3V3", vcc[0], yr)
    line(yr, [vcc[0], vcc[0] + 5.08, vcc[0] + 12.7])
    down("C1U", vcc[0] + 5.08, yr)
    down("C100N", vcc[0] + 12.7, yr)
    vcap, iref = u3.pin("45"), u3.pin("44")
    W(vcap, (vcap[0] + 15.24, vcap[1]))
    down("C1U", vcap[0] + 15.24, vcap[1])
    W(iref, (iref[0] + 5.08, iref[1]))
    down("R3K3", iref[0] + 5.08, iref[1])
    gnd(*u3.pin("37"))
    # the LEDs: three staggered columns, each LED on its output's row, anode to 4.8 V
    xo = u3.pin("1")[0]
    for (drv, ch), (name, colour, where) in sorted(LEDS.LEDS.items()):
        if drv != "BASE":
            continue
        out = u3.pin(str(ch + 1))
        c = ch % 3
        xc = xo - 16.51 - 35.56 * c
        key = {"violet": "LED_VIOLET", "purple": "LED_PURPLE", "amber5050": "LED_AMBER5050",
               "orange": "LED_ORANGE"}[colour]
        dref = nref("D")
        d = part(key, dref, xc, out[1], rot=180, value={"amber5050": "orange x3"}.get(colour, colour),
                 ref_at=(xc - 15.24, out[1] - 0.3), val_at=(xc - 15.24, out[1] + 0.3), justify="right", fsize=1.0)
        k, a = d.pin("1"), d.pin("4") if key == "LED_AMBER5050" else d.pin("2")
        W(k, out)
        flag("+5V", *a, rot=270)
        label(k[0] + 1.0, out[1], name, size=0.9)
    for ch in range(36):
        if ("BASE", ch) not in LEDS.LEDS:
            S().nc(*u3.pin(str(ch + 1)))

    # ---- the sensors, hanging from the bus ------------------------------------------------
    # U15, LSM6DS3TR-C: the IMU (SA0 low: 0x6A); its interrupt ends the IMU_INT line
    x15, y15 = 312.42, 375.92
    u15 = part("LSM6DS3", "U15", x15, y15, ref_at=(x15 - 8.0, y15 + 12.5), val_at=(x15 + 6.0, y15 + 19.5))
    scl, sda, int1 = u15.pin("13"), u15.pin("14"), u15.pin("4")
    W(scl, (scl[0] + G, scl[1]), (scl[0] + G, yc))
    W(sda, (sda[0] + 5.08, sda[1]), (sda[0] + 5.08, yd))
    W(int1, (int1[0] + 7.62, int1[1]), (int1[0] + 7.62, yi), pi)
    label(int1[0] + 9.0, yi, "IMU_INT")
    S().nc(*u15.pin("9"))
    cs = u15.pin("12")
    W(cs, (cs[0] - G, cs[1]))
    flag("+3V3", cs[0] - G, cs[1], rot=270)
    sa0, sdx, scx = u15.pin("1"), u15.pin("2"), u15.pin("3")
    xg = sa0[0] - G
    W(sa0, (xg, sa0[1])); W(sdx, (xg, sdx[1])); W(scx, (xg, scx[1]))
    vline(xg, [sa0[1], sdx[1], scx[1]])
    gnd(xg, scx[1])
    for n in ("10", "11"):
        S().nc(*u15.pin(n))
    vdd, vio = u15.pin("8"), u15.pin("5")
    ys = vdd[1] - 10.16
    W(vdd, (vdd[0], ys)); W(vio, (vio[0], ys))
    line(ys, [vio[0], vdd[0], vdd[0] - 7.62, vdd[0] - 15.24, vdd[0] - 22.86])
    flag("+3V3", vdd[0] - 22.86, ys)
    down("C100N", vdd[0] - 7.62, ys)
    down("C100N", vdd[0] - 15.24, ys, text="left")
    for n in ("6", "7"):
        gnd(*u15.pin(n))
    # U16, LTR-303ALS: ambient light (0x29)
    x16, y16 = 264.16, 375.92
    u16 = part("LTR303", "U16", x16, y16, mirror="y", ref_at=(x16 - 6.0, y16 + 12.5), val_at=(x16 + 2.0, y16 + 12.5))
    sda, scl = u16.pin("6"), u16.pin("4")
    W(sda, (sda[0] + G, sda[1]), (sda[0] + G, yd))
    W(scl, (scl[0] + 5.08, scl[1]), (scl[0] + 5.08, yc))
    S().nc(*u16.pin("5")); S().nc(*u16.pin("2"))
    vdd = u16.pin("1")
    ys = vdd[1] - 5.08
    W(vdd, (vdd[0], ys - G))
    flag("+3V3", vdd[0], ys - G)
    W((vdd[0], ys), (vdd[0] - 10.16, ys))
    down("C1U", vdd[0] - 10.16, ys, text="left")
    J(vdd[0], ys)
    gnd(*u16.pin("3"))
    # U17, TMAG5273A2: the 3-axis Hall sensor under the pendulum (0x35)
    x17, y17 = 223.52, 375.92
    u17 = part("TMAG5273", "U17", x17, y17, mirror="y", ref_at=(x17 - 6.0, y17 + 16.5), val_at=(x17 + 2.0, y17 + 16.5))
    sda, scl = u17.pin("6"), u17.pin("1")
    W(sda, (sda[0] + G, sda[1]), (sda[0] + G, yd))
    W(scl, (scl[0] + 5.08, scl[1]), (scl[0] + 5.08, yc))
    S().nc(*u17.pin("5"))
    vcc = u17.pin("4")
    ys = vcc[1] - 5.08
    W(vcc, (vcc[0], ys - G))
    flag("+3V3", vcc[0], ys - G)
    W((vcc[0], ys), (vcc[0] - 10.16, ys))
    down("C100N", vcc[0] - 10.16, ys, text="left")
    J(vcc[0], ys)
    gnd(*u17.pin("2")); gnd(*u17.pin("3"))
    note(212.09, 403.86,
         "I2C at 400 kHz, 3.3 V, 2.2k pull-ups; on it: U3 (LP5036, 0x30), the tree's LP5036 "
         "(0x31, through the socket), U15 (LSM6DS3TR-C, 0x6A: taps and tilt), U16 (LTR-303, "
         "0x29: the owls wake at dusk), U17 (TMAG5273A2, 0x35: times the pendulum's kicks). "
         "Interrupts the firmware does not use stay open.", cols=48)
    note(17.78, 431.8,
         "U3, LP5036: 36 current sinks, 12-bit PWM at 29 kHz (no flicker a camera or an eye "
         "can see), in 12 banks of 3 that share a brightness. R3K3 on IREF sets the most any "
         "output can sink: 105 x 0.7 V / 3.3k = 22 mA, under every LED's 30 mA, whatever "
         "the firmware asks. The LEDs' anodes are on 4.8 V; the names on the wires are "
         "gen/leds.py's, which the firmware's light show uses.", cols=56)


# ======================================================================================
# The four coil bridges (DRV8874), stacked to the right of the RP2354A
# ======================================================================================
XD = 584.2                                       # the DRV8874s' centres
YD = [50.8, 109.22, 167.64, 226.06]              # levitation, pendulum 1, 2, 3
X_COL0 = 497.84                                  # the first rising column
X_LEV_IPROPI = 650.24
X_PEND_IPROPI = {1: 688.34, 2: 683.26, 3: 678.18}  # down to the mux, PEND3's innermost
X_LEV_A, X_LEV_B = 820.42, 815.34                # down the right edge to the tree's socket


def drv_tiles():
    nets = ["LEV_IN1", "LEV_IN2", "PEND1_IN1", "PEND1_IN2", "PEND2_IN1", "PEND2_IN2", "PEND3_IN1", "PEND3_IN2",
            "DRV_nSLEEP", "DRV_nFAULT"]
    refs = ["U8", "U5", "U6", "U7"]
    tiles = []
    for k in range(4):
        tiles.append(part("DRV8874", refs[k], XD, YD[k], ref_at=(XD - 12.7, YD[k] + 14.0),
                          val_at=(XD + 5.0, YD[k] + 14.0)))
    # the columns: each line rises from its pin to its bridge's row, the upper pins on the
    # inner columns, so that nothing crosses
    for s_, net in enumerate(nets):
        x = X_COL0 + G * s_
        p = gp(net)
        if s_ < 8:
            u = tiles[s_ // 2]
            q = u.pin("1" if s_ % 2 == 0 else "2")
            W(p, (x, p[1]), (x, q[1]), q)
        else:
            num = "3" if net == "DRV_nSLEEP" else "4"
            qs = [u.pin(num) for u in tiles]
            W(p, (x, p[1]), (x, qs[0][1]), qs[0])
            for q in qs[1:]:
                W((x, q[1]), q)
                J(x, q[1])
        label(p[0] + 1.0, p[1], net)
    # nSLEEP: 4.7k to ground keeps the bridges asleep through a reset; nFAULT: 10k up
    xs8, xs9 = X_COL0 + G * 8, X_COL0 + G * 9
    yj = 187.96
    W((xs8, yj), (535.94, yj))
    J(xs8, yj)
    down("R4K7", 535.94, yj)
    yk = 210.82
    W((xs9, yk), (546.1, yk))
    J(xs9, yk)
    up("R10K", 546.1, yk, "+3V3")
    for k, u in enumerate(tiles):
        tile(u, YD[k], k)
    note(701.04, 58.42,
         "U8, U5-U7: DRV8874 H-bridges from 12 V. PMODE high: PWM mode (IN1 and IN2 drive the "
         "bridge; both low: coast). IMODE to ground: fixed off-time chopping at ITRIP = 3.3 V / "
         "(450 uA/A x 2.2k) = 3.3 A, so no coil ever carries more. IPROPI mirrors the low-side "
         "current, 450 uA per amp: 2.2k makes 1 V per amp, then 1k and 10n filter it. "
         "nSLEEP, shared, latches PMODE and IMODE when it rises; 4.7k holds the bridges asleep "
         "through a reset. nFAULT, shared and open-drain, goes low on overcurrent, overheating "
         "or undervoltage.", cols=40)
    note(701.04, 121.92,
         "U8 drives the levitation coil on the perch (LEV_A, LEV_B: up the right edge to the "
         "tree's socket). L3-L5: the pendulum coils under the bat's swing, 12 turns on each of "
         "4 layers, 31 uH, 2 ohm (copper on this board, gen/coils.py).", cols=40)


def tile(u, yd, k):
    """One DRV8874: its straps, charge pump, supply, grounds, and current sense; a
    pendulum coil, or (k = 0) the lines up to the levitation coil on the perch."""
    pm, vr, im = u.pin("16"), u.pin("5"), u.pin("7")
    xj = pm[0] - 5.08
    W(pm, (xj, pm[1]), (xj, vr[1]), vr)
    flag("+3V3", xj, pm[1], rot=270)
    W(im, (im[0] - G, im[1]))
    gnd(im[0] - G, im[1])
    # charge pump: 22n CPH-CPL, 100n VCP-VM
    cph, cpl, vcp, vm = u.pin("13"), u.pin("14"), u.pin("12"), u.pin("11")
    yc = cph[1] - 5.08
    l, r = series("C22N", (cph[0] + cpl[0]) / 2, yc)
    W(cph, l); W(cpl, r)
    l, r = series("C100N", (vcp[0] + vm[0]) / 2, yc)
    W(vcp, l)
    yr = yc - 5.08
    W(vm, r, (vm[0], yr))
    J(*r)
    flag("+12V", vm[0], yr)
    line(yr, [vm[0], vm[0] + 7.62, vm[0] + 17.78])
    down("C100N", vm[0] + 7.62, yr)
    down("C10U", vm[0] + 17.78, yr)
    for n in ("9", "15", "17"):
        gnd(*u.pin(n))
    # the coil, or the lines to the perch
    o1, o2, ip = u.pin("8"), u.pin("10"), u.pin("6")
    if k == 0:
        W(o1, (X_LEV_A, o1[1]))
        W(o2, (X_LEV_B, o2[1]))
        label(o1[0] + 3.0, o1[1], "LEV_A"); label(o2[0] + 3.0, o2[1], "LEV_B")
    else:
        xl = o1[0] + 27.94
        L = part("COIL_PEND", "L%d" % (2 + k), xl, yd - 7.62, rot=270, value="31uH coil",
                 ref_at=(xl + 2.5, yd - 8.0), val_at=(xl + 2.5, yd - 7.2), fsize=1.0)
        W(o1, (xl - 5.08, o1[1]), (xl - 5.08, L.pin("1")[1]), L.pin("1"))
        W(o2, (xl - 10.16, o2[1]), (xl - 10.16, L.pin("2")[1]), L.pin("2"))
        label(o1[0] + 1.0, o1[1], "PEND%d_A" % k, size=0.9)
        label(o2[0] + 1.0, o2[1], "PEND%d_B" % k, size=0.9)
    # current sense: 2.2k to ground (ITRIP), then 1k and 10n to the ADC or the mux
    xr = ip[0] + 7.62
    down("R2K2", xr, ip[1], text="left")
    l, r = series("R1K", ip[0] + 15.24, ip[1], above=False)
    xc = r[0] + 3.81
    down("C10N", xc, ip[1])
    line(ip[1], [ip[0], xr, l[0]])
    if k == 0:
        W(r, (xc, ip[1]), (X_LEV_IPROPI, ip[1]))
        dst = gp("LEV_IPROPI")
        W((X_LEV_IPROPI, ip[1]), (X_LEV_IPROPI, dst[1]), dst)
        label(r[0] + 6.0, ip[1], "LEV_IPROPI")
    else:
        W(r, (xc, ip[1]), (X_PEND_IPROPI[k], ip[1]))
        label(r[0] + 12.0, ip[1], "PEND%d_IPROPI" % k)


# ======================================================================================
# The mux and the rail dividers
# ======================================================================================
XM = 660.4


def mux():
    s0 = gp("MUX_S0")
    ym = s0[1] + G
    u = part("HC4051", "U11", XM, ym, ref_at=(XM - 8.0, ym - 14.0), val_at=(XM - 6.0, ym + 18.5))
    for net, num in (("MUX_S0", "11"), ("MUX_S1", "10"), ("MUX_S2", "9")):
        W(gp(net), u.pin(num))
    po, a = gp("MUX_OUT"), u.pin("3")
    W(po, (a[0] - 7.62, po[1]), (a[0] - 7.62, a[1]), a)
    ne = u.pin("6")
    W(ne, (ne[0] - G, ne[1]))
    gnd(ne[0] - G, ne[1])
    vee, gn = u.pin("7"), u.pin("8")
    W(vee, gn)
    gnd(*gn)
    vcc = u.pin("16")
    yr = vcc[1] - 7.62
    W(vcc, (vcc[0], yr))
    flag("+3V3", vcc[0], yr)
    l, r = series("C100N", vcc[0] + 5.08, vcc[1] - G)
    W((vcc[0], vcc[1] - G), l)
    J(vcc[0], vcc[1] - G)
    gnd(*r)
    for net in ("MUX_OUT", "MUX_S0", "MUX_S1", "MUX_S2"):
        p = gp(net)
        label(p[0] + 1.0, p[1], net)
    # inputs: the pendulum currents from above, the perch currents from below, the dividers
    for k, num in ((3, "13"), (2, "14"), (1, "15")):
        q = u.pin(num)
        x = X_PEND_IPROPI[k]
        W((x, YD[k] + 1.27), (x, q[1]), q)
    xr = u.pin("13")[0]
    # A5 (pin 5, top row) takes the outer column and the lowest tap, A7 (pin 4) the inner
    # column and the highest, so that none crosses another
    taps = [("4", "VBUS", 671.83, 335.28, 664.21, "R10K", "R10K"),
            ("2", "+5V", 674.37, 355.6, 651.51, "R10K", "R10K"),
            ("5", "+12V", 676.91, 375.92, 638.81, "R100K", "R22K")]
    names = {"4": "VBUS_SENSE", "2": "V5_SENSE", "5": "V12_SENSE"}
    for num, rail, xcol, yt, xt, rtop, rbot in taps:
        q = u.pin(num)
        W(q, (xcol, q[1]), (xcol, yt), (xt, yt))
        up(rtop, xt, yt, rail, text="left")
        down(rbot, xt, yt, text="left")
        J(xt, yt)
        label(xt + 1.0, yt, names[num])
    return u


# ======================================================================================
# The perch bridges (UCC27524), below the mux
# ======================================================================================
XU = 563.88
YU = {1: 401.32, 2: 462.28}                       # the owl's perch, the cat's
X_ISENSE = {1: 698.5, 2: 703.58}


def bridges(u11):
    cols = {"FAM1_A": 535.94, "FAM1_B": 533.4, "FAM2_A": 530.86, "FAM2_B": 528.32, "FAM_EN": 525.78}
    us = {}
    for k in (1, 2):
        us[k] = part("UCC27524", "U%d" % (8 + k), XU, YU[k], ref_at=(XU - 7.0, YU[k] + 10.5),
                     val_at=(XU + 1.0, YU[k] + 10.5))
    for k in (1, 2):
        u = us[k]
        for leg, num in (("A", "2"), ("B", "4")):
            net = "FAM%d_%s" % (k, leg)
            p, q, x = gp(net), u.pin(num), cols[net]
            W(p, (x, p[1]), (x, q[1]), q)
            label(p[0] + 1.0, p[1], net)
        ena, enb = u.pin("1"), u.pin("8")
        xj = ena[0] - G
        W(ena, (xj, ena[1]), (xj, enb[1]), enb)
        J(xj, enb[1])
    pe = gp("FAM_EN")
    xe = cols["FAM_EN"]
    e1, e2 = us[1].pin("8"), us[2].pin("8")
    W(pe, (xe, pe[1]), (xe, e1[1]), (e1[0] - G, e1[1]))
    W((xe, e1[1]), (xe, e2[1]), (e2[0] - G, e2[1]))
    J(xe, e1[1])
    label(pe[0] + 1.0, pe[1], "FAM_EN")
    J(xe, e2[1])
    down("R4K7", xe, e2[1], text="left")
    for k in (1, 2):
        bridge(us[k], YU[k], k, u11)


def bridge(u, yu, k, u11):
    """One UCC27524 as a full bridge: channel A drives one end of the perch coil, channel
    B the other, through a 10 uF capacitor that blocks DC (a stuck output cannot pass
    current), from 4.8 V.  Its ground returns through 0.5 R, whose filtered voltage tells
    the firmware how much power the coil delivers: more when a token sits on it."""
    vdd = u.pin("6")
    yr = vdd[1] - 12.7
    W(vdd, (vdd[0], yr))
    flag("+5V", vdd[0], yr)
    line(yr, [vdd[0], vdd[0] + 7.62, vdd[0] + 17.78])
    down("C1U", vdd[0] + 7.62, yr)
    down("C100N", vdd[0] + 17.78, yr)
    oa, ob = u.pin("7"), u.pin("5")
    l, r = series("C10U", oa[0] + 8.89, oa[1])
    W(oa, l)
    xl = r[0] + 5.08
    L = part("COIL_PERCH", "L%d" % (5 + k), xl, oa[1] + 5.08, rot=270, value="28uH coil",
             ref_at=(xl + 2.5, oa[1] + 4.6), val_at=(xl + 2.5, oa[1] + 5.4), fsize=1.0)
    W(r, L.pin("1"))
    xb = ob[0] + G
    W(L.pin("2"), (xb, L.pin("2")[1]), (xb, ob[1]), ob)
    who = "OWL" if k == 1 else "CAT"
    label(oa[0] + 0.6, oa[1], who + "_A", size=0.9)
    label(xb + 1.0, L.pin("2")[1], who + "_B", size=0.9)
    label(r[0] + 0.6, r[1], who + "_C", size=0.9)
    # the return: 0.5 R to ground, then 10k and 100n to the mux
    g = u.pin("3")
    yn = g[1] + G
    W(g, (g[0], yn))
    down("R0R5", g[0], yn, text="left")
    W((g[0], yn), (g[0] - 5.08, yn))
    pwr_flag(g[0] - 5.08, yn)               # the chip's ground: GND through 0.5 R
    l, r = series("R10K", g[0] + 8.89, yn, above=False)
    xc = r[0] + 5.08
    W((g[0], yn), l)
    J(g[0], yn)
    down("C100N", xc, yn)
    # x 20.6 (U18, OPA2333, zero drift): 0.5 R x 20.6 = 10.3 V per amp, 80 uA a count, so
    # the firmware's low-duty sweep sees a token's 0.2-0.5 mA
    xa = xc + 20.32
    amp = part("OPA2333", "U18", xa, yn + G, unit=k, ref_at=(xa - 14.5, yn - 4.8), val_at=(xa - 14.5, yn - 4.4))
    pp, pn, po = amp.pin("3" if k == 1 else "5"), amp.pin("2" if k == 1 else "6"), amp.pin("1" if k == 1 else "7")
    W(r, (xc, yn), pp)
    xo, yf, xn = po[0] + G, pn[1] + 5.08, pn[0] - G
    l2, r2 = series("R100K", (xn + xo) / 2, yf, above=False)
    W(po, (xo, po[1]), (xo, yf), r2)
    W(l2, (xn, yf), (xn, pn[1]), pn)
    J(xo, po[1])
    down("R5K1", xn, yf, text="left")
    J(xn, yf)
    x = X_ISENSE[k]
    W((xo, po[1]), (x, po[1]))
    q = u11.pin("12" if k == 2 else "1")
    W((x, po[1]), (x, q[1]), q)
    label(xo + 3.0, po[1], "FAM%d_ISENSE" % k)
    label(xc + 1.5, yn, "FAM%d_IAVG" % k, size=0.9)
    if k == 1:
        xp, yp = xa + 33.02, yn + 25.4
        pw = part("OPA2333", "U18", xp, yp, unit=3, ref_at=(xp + 1.0, yp - 1.0), val_at=(xp + 1.0, yp + 1.0))
        vp, vn = pw.pin("8"), pw.pin("4")
        W(vp, (vp[0], vp[1] - G))
        flag("+3V3", vp[0], vp[1] - G)
        W((vp[0], vp[1] - G), (vp[0] - 7.62, vp[1] - G))
        J(vp[0], vp[1] - G)
        down("C100N", vp[0] - 7.62, vp[1] - G, text="left")
        gnd(*vn)


# ======================================================================================
# The tree's socket (bottom right)
# ======================================================================================
def tree_socket():
    xj, yj = 774.7, 520.7
    j3 = part("SOCKET2x8", "J3", xj, yj, value="TREE", ref_at=(xj - 3.0, yj - 10.5), val_at=(xj + 3.5, yj - 10.5))
    # left column: the Hall line and the bus from under the RP2354A, then grounds
    for num, xb, yu in (("1", XB_HALL, Y_HALL_U), ("3", XB_SDA, Y_SDA_U), ("5", XB_SCL, Y_SCL_U)):
        q = j3.pin(num)
        W((xb, yu), (xb, q[1]), q)
    xg = j3.pin("7")[0] - G
    for num in ("7", "9", "11", "13", "15"):
        W(j3.pin(num), (xg, j3.pin(num)[1]))
    vline(xg, [j3.pin(n)[1] for n in ("7", "9", "11", "13", "15")])
    gnd(xg, j3.pin("15")[1])
    # right column: 3.3 V, 4.8 V, grounds, and the levitation coil's two ends, two pins each
    for num, net in (("2", "+3V3"), ("4", "+5V")):
        q = j3.pin(num)
        W(q, (q[0] + G, q[1]))
        flag(net, q[0] + G, q[1], rot=90)
    for num in ("6", "12"):
        q = j3.pin(num)
        W(q, (q[0] + G, q[1]))
        S().power("GND", q[0] + G, q[1], rot=90)
    xs = j3.pin("8")[0] + 5.08
    for (a, b), xcol in ((("8", "10"), X_LEV_B), (("14", "16"), X_LEV_A)):
        pa, pb = j3.pin(a), j3.pin(b)
        W((xcol, YD[0] - 8.89 if xcol == X_LEV_A else YD[0] - 6.35), (xcol, pa[1]), pa)
        W((xs, pa[1]), (xs, pb[1]), pb)
        J(xs, pa[1])
    note(xj - 5.08, yj + 15.24,
         "J3: the tree stands here (its right-angle header). Pins 8, 10: LEV_B; 14, 16: "
         "LEV_A (3.3 A at most, two pins each); 1 HALL; 3 SDA; 5 SCL; 2 3.3 V; 4 4.8 V; "
         "the rest ground, between the coil's pins and the signals.", cols=30)


def S():
    return U.S


def build(sch):
    U.begin(sch, ref_base=0)
    sch.text(17.78, 20.32, "OWLternating Current: the base board", size=3.5, bold=True)
    xt = power_in()
    xb = buck(xt + 7.62)
    vsys_ldo(xb + 7.62)
    mcu()
    mcu_left()
    audio_theremin()
    bus_left()
    drv_tiles()
    u11 = mux()
    bridges(u11)
    tree_socket()
    return sch
