"""The symbols drawn for OWLternating Current (the rest are KiCad's, vendored by
gen/library.py).  Each is drawn the way the schematic flows: inputs on the left,
outputs to the right, supplies on top, grounds below.

Pin numbers come from the datasheets' pin tables and figures, cited per symbol.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, HERE)
import kisch
from kisch import _hdr, _pin, _rect, _poly
import pins as PINS

G = 2.54
B, I, O, PI, PO, PA, NC, OC = ("bidirectional", "input", "output", "power_in", "power_out", "passive",
                               "no_connect", "open_collector")


def _close(out):
    out += ['(embedded_fonts no)', ')']
    return "\n".join(out)


def _hidden(pin_text):
    """A pin stacked under a visible one: KiCad's (hide yes) after its length."""
    i = pin_text.index("(length ")
    j = pin_text.index(")", i) + 1
    return pin_text[:j] + " (hide yes)" + pin_text[j:]


def box_symbol(name, ref, left, right, top, bottom, w, keywords="", value=None,
               top_pitch=G, top_x=None, extra=(), bottom_x=None):
    """A rectangle `w` wide.  left/right: lists of (number, name, type) or None for a
    gap, top to bottom.  top/bottom: (number, name, type) left to right."""
    rows = max(len(left), len(right))
    hh = rows * G / 2.0 + G / 2.0
    hw = w / 2.0
    out = _hdr(name, ref, value or name, hh + 3.81, keywords=keywords)
    out.append('(symbol "%s_0_1"' % name)
    out.append(_rect(-hw, hh, hw, -hh))
    out.extend(extra)
    out.append(')')
    out.append('(symbol "%s_1_1"' % name)
    y0 = hh - G
    for i, p in enumerate(left):
        if p:
            out.append(_pin(p[0], p[1], -hw - 5.08, y0 - i * G, 0, 5.08, p[2]))
    for i, p in enumerate(right):
        if p:
            out.append(_pin(p[0], p[1], hw + 5.08, y0 - i * G, 180, 5.08, p[2]))
    xs = top_x or [-(len(top) - 1) * top_pitch / 2.0 + i * top_pitch for i in range(len(top))]
    for x, p in zip(xs, top):
        out.append(_pin(p[0], p[1], x, hh + 5.08, 270, 5.08, p[2]))
    bx = bottom_x or [-(len(bottom) - 1) * G + i * 2 * G for i in range(len(bottom))]
    for x, p in zip(bx, bottom):
        out.append(_pin(p[0], p[1], x, -hh - 5.08, 90, 5.08, p[2]))
    out.append(')')
    return _close(out), dict(hw=hw, hh=hh, top_x=xs)


# ---------------------------------------------------------------------------------
# RP2354A: RP2350 datasheet, Table 1674 (QFN-60 numbers) and its pinout figure; the
# same numbers as GPiBridge's symbol, which was checked against the datasheet in code
# (tools/check_pins.py there).  The QSPI data pins and SCLK reach the flash inside the
# package; only QSPI_SS is used outside (BOOTSEL).
_gp = {0: 2, 1: 3, 2: 4, 3: 5, 4: 7, 5: 8, 6: 9, 7: 10, 8: 12, 9: 13, 10: 14, 11: 15, 12: 16, 13: 17,
       14: 18, 15: 19, 16: 27, 17: 28, 18: 29, 19: 31, 20: 32, 21: 33, 22: 34, 23: 35, 24: 36,
       25: 37, 26: 40, 27: 41, 28: 42, 29: 43}
GPIO_PIN = dict(_gp)        # GPIO number -> QFN-60 pin number


def _g(n):
    nm = "GPIO%d" % n + ("/ADC%d" % (n - 26) if n >= 26 else "")
    kind = {"out": O, "in": I, "adc": I}.get(PINS.GPIO[n][1], B)
    return (str(_gp[n]), nm, kind)


_FIXED = {"USB_DP": ("52", "USB_DP", B), "USB_DM": ("51", "USB_DM", B), "XIN": ("21", "XIN", I),
          "XOUT": ("22", "XOUT", O), "SWCLK": ("24", "SWCLK", I), "SWDIO": ("25", "SWDIO", B),
          "RUN": ("26", "RUN", I), "QSPI_SS": ("60", "~{QSPI_SS}", B), "QSPI_SCLK": ("56", "QSPI_SCLK", B),
          "QSPI_SD0": ("57", "QSPI_SD0", B), "QSPI_SD1": ("59", "QSPI_SD1", B),
          "QSPI_SD2": ("58", "QSPI_SD2", B), "QSPI_SD3": ("55", "QSPI_SD3", B)}


def _row(n):
    if n is None:
        return None
    if n in _FIXED:
        return _FIXED[n]
    return _g(PINS.GPIO_OF[n])


# Left: the USB, the crystal, the debug port, RUN and BOOTSEL, the unused QSPI pins, the
# UART, then the I2C bus and its interrupt, which go left to the sensors and the LED
# driver.  Right, top to bottom in the order the blocks stand to the right of the chip:
# the four DRV8874 bridges, the two perch bridges, then the analog inputs and the mux,
# the audio and the theremin.  Gaps leave room for each block's parts.
RP_LEFT_NETS = ["USB_DP", "USB_DM", None, "XIN", "XOUT", None, "SWCLK", "SWDIO", "RUN", "QSPI_SS", None,
                "QSPI_SCLK", "QSPI_SD0", "QSPI_SD1", "QSPI_SD2", "QSPI_SD3", None, "UART_TX", "UART_RX", None,
                "SDA", "SCL", "IMU_INT", None, "BUTTON"]
RP_RIGHT_NETS = ["PEND1_IN1", "PEND1_IN2", "PEND2_IN1", "PEND2_IN2", "PEND3_IN1", "PEND3_IN2",
                 "LEV_IN1", "LEV_IN2", "DRV_nSLEEP", "DRV_nFAULT", None,
                 "FAM1_A", "FAM1_B", "FAM2_A", "FAM2_B", "FAM_EN", None,
                 "HALL", "LEV_IPROPI", "MUX_OUT", "MUX_S0", "MUX_S1", "MUX_S2", None,
                 "AUDIO", "THEREMIN_PITCH", "THEREMIN_VOL"]
RP_LEFT = [_row(n) for n in RP_LEFT_NETS]
RP_RIGHT = [_row(n) for n in RP_RIGHT_NETS]
RP_TOP = [("46", "VREG_AVDD", PI), ("49", "VREG_VIN", PI), ("48", "VREG_LX", PO), ("50", "VREG_FB", PI),
          ("6", "DVDD", PI), ("23", "DVDD", PI), ("39", "DVDD", PI),
          ("1", "IOVDD", PI), ("11", "IOVDD", PI), ("20", "IOVDD", PI), ("30", "IOVDD", PI),
          ("38", "IOVDD", PI), ("45", "IOVDD", PI),
          ("54", "QSPI_IOVDD", PI), ("53", "USB_OTP_VDD", PI), ("44", "ADC_AVDD", PI)]
RP_BOTTOM = [("47", "VREG_PGND", PI), ("61", "GND", PI)]
RP_TOP_PITCH = 7.62
_all = {p[0] for p in RP_LEFT + RP_RIGHT + RP_TOP + RP_BOTTOM if p}
assert len(_all) == 61 and _all == {str(i) for i in range(1, 62)}, sorted(_all)


def rp2354a():
    w = (len(RP_TOP) + 1) * RP_TOP_PITCH
    return box_symbol("RP2354A", "U", RP_LEFT, RP_RIGHT, RP_TOP, RP_BOTTOM, w,
                      keywords="Raspberry Pi RP2354A: RP2350 with 2 MB flash in the package, QFN-60",
                      top_pitch=RP_TOP_PITCH)


# ---------------------------------------------------------------------------------
# TI DRV8874 (PWP0016J, datasheet "Pin Functions"): 1 EN/IN1, 2 PH/IN2, 3 nSLEEP,
# 4 nFAULT, 5 VREF, 6 IPROPI, 7 IMODE, 8 OUT1, 9 PGND, 10 OUT2, 11 VM, 12 VCP, 13 CPH,
# 14 CPL, 15 GND, 16 PMODE, 17 thermal pad (ground).  Logic in on the left, the bridge
# outputs and the current sense out on the right, VM and the charge pump on top.
def drv8874():
    left = [("1", "IN1", I), ("2", "IN2", I), ("3", "~{SLEEP}", I), ("4", "~{FAULT}", OC), None,
            ("16", "PMODE", I), ("7", "IMODE", I), ("5", "VREF", I)]
    right = [("8", "OUT1", O), ("10", "OUT2", O), None, None, ("6", "IPROPI", O)]
    top = [("13", "CPH", PA), ("14", "CPL", PA), ("12", "VCP", PA), ("11", "VM", PI)]
    bottom = [("9", "PGND", PI), ("15", "GND", PI), ("17", "PAD", PI)]
    return box_symbol("DRV8874", "U", left, right, top, bottom, 17.78,
                      keywords="TI DRV8874 H-bridge, 37 V 6 A, PWM to 100 kHz, IPROPI current mirror (450 uA/A)",
                      top_pitch=G * 2, bottom_x=[-G * 2, 0.0, G * 2])


# NS4150B (Nsiway datasheet, "pin description"): 1 CTRL (low = shutdown), 2 Bypass (1 uF
# to ground), 3 INP, 4 INN, 5 VoN, 6 VCC, 7 GND, 8 VoP.
def ns4150b():
    left = [("3", "INP", I), ("4", "INN", I), None, ("1", "CTRL", I), ("2", "BYPASS", PA)]
    right = [("8", "VOP", O), ("5", "VON", O)]
    return box_symbol("NS4150B", "U", left, right, [("6", "VCC", PI)], [("7", "GND", PI)], 12.7,
                      keywords="Nsiway NS4150B 3 W class-D mono speaker amplifier; CTRL low = shutdown",
                      top_x=[0.0], bottom_x=[0.0])


# TI TMAG5273 (SOT-23-6, datasheet table 4-1): 1 SCL, 2 GND, 3 GND (TI test pin: ground
# it), 4 VCC, 5 INT, 6 SDA.
def tmag5273():
    left = [("6", "SDA", B), ("1", "SCL", I), ("5", "~{INT}", OC)]
    return box_symbol("TMAG5273", "U", left, [], [("4", "VCC", PI)], [("2", "GND", PI), ("3", "TEST", PI)], 12.7,
                      keywords="TI TMAG5273 3-axis linear Hall sensor, I2C; A2: +-133/266 mT, address 0x35",
                      top_x=[0.0], bottom_x=[-G, G])


# AO4407A (SOIC-8, Alpha & Omega datasheet): 1, 2, 3 source; 4 gate; 5-8 drain.  Drawn as
# one P-MOSFET, the extra source and drain pins stacked and hidden on the visible ones.
def q_pmos_sssgdddd():
    name = "Q_PMOS_SSSGDDDD"
    out = _hdr(name, "Q", name, 6.35, keywords="P-channel MOSFET, SO-8: pins 1-3 source, 4 gate, 5-8 drain")
    out.append('(symbol "%s_0_1"' % name)
    out.append(_poly([(0.254, 0.0), (-2.54, 0.0)]))                          # gate lead
    out.append(_poly([(0.254, 1.905), (0.254, -1.905)], width=0.254))        # gate plate
    for y in (1.27, 0.0, -1.27):
        out.append(_poly([(0.762, y + 0.508), (0.762, y - 0.508)], width=0.254))
    out.append(_poly([(0.762, 1.27), (2.54, 1.27), (2.54, 2.54)]))
    out.append(_poly([(0.762, -1.27), (2.54, -1.27), (2.54, -2.54)]))
    out.append(_poly([(0.762, 0.0), (2.54, 0.0), (2.54, -1.27)]))
    out.append(_poly([(1.524, 0.0), (1.016, 0.381), (1.016, -0.381), (1.524, 0.0)], fill="outline"))  # P: arrow out
    out.append(')')
    out.append('(symbol "%s_1_1"' % name)
    out.append(_pin("4", "G", -5.08, 0.0, 0, 2.54, I))
    for k, n in enumerate(("1", "2", "3")):
        p = _pin(n, "S", 2.54, 5.08, 270, 2.54, PA)
        out.append(p if k == 0 else _hidden(p))
    for k, n in enumerate(("5", "6", "7", "8")):
        p = _pin(n, "D", 2.54, -5.08, 90, 2.54, PA)
        out.append(p if k == 0 else _hidden(p))
    out.append(')')
    return _close(out), {}


# The pumpkins' LED: HONGLITRONIC HL-AF-5060S22OC, three orange dice in a PLCC-6 (its
# drawing: anodes 4, 5, 6; cathodes 3, 2, 1, each die from 4-3, 5-2, 6-1).  Drawn as one
# LED with the dice paralleled: anodes stacked, cathodes stacked.
def led_3die():
    name = "LED_3die"
    out = _hdr(name, "D", name, 3.81, keywords="three LED dice in one package, driven in parallel")
    out.append('(symbol "%s_0_1"' % name)
    out.append(_poly([(-1.27, -1.27), (-1.27, 1.27)], width=0.254))         # cathode bar
    out.append(_poly([(1.27, -1.27), (1.27, 1.27), (-1.27, 0.0), (1.27, -1.27)], width=0.254))
    out.append(_poly([(-2.54, 0.0), (2.54, 0.0)]))
    for x in (-0.3, 0.6):
        out.append(_poly([(x, 1.6), (x + 0.9, 2.5)]))
        out.append(_poly([(x + 0.9, 2.5), (x + 0.4, 2.3), (x + 0.7, 2.0), (x + 0.9, 2.5)], fill="outline"))
    out.append(')')
    out.append('(symbol "%s_1_1"' % name)
    for k, n in enumerate(("4", "5", "6")):
        p = _pin(n, "A", 5.08, 0.0, 180, 2.54, PA)
        out.append(p if k == 0 else _hidden(p))
    for k, n in enumerate(("1", "2", "3")):
        p = _pin(n, "K", -5.08, 0.0, 0, 2.54, PA)
        out.append(p if k == 0 else _hidden(p))
    out.append(')')
    return _close(out), {}


# A PCB coil: an inductor drawn with a spiral, whose footprint is KiCad's net tie (the
# spiral itself is tracks and vias drawn by gen/coils.py).  Pin 1 is where the spiral
# starts (outermost turn, top layer); pin 2 where it ends.
def coil():
    name = "Coil"
    out = _hdr(name, "L", name, 3.81, keywords="PCB spiral coil (copper, not a part); footprint is a net tie")
    out.append('(symbol "%s_0_1"' % name)
    for k in range(4):                                                        # four bumps
        x0 = -2.54 + k * 1.27
        out.append('(arc (start %.3f 0) (mid %.3f 0.635) (end %.3f 0) (stroke (width 0.254) (type default)) (fill (type none)))'
                   % (x0 + 1.27, x0 + 0.635, x0))
    out.append(_poly([(-3.0, -1.2), (3.0, -1.2)], width=0.15))
    out.append(')')
    out.append('(symbol "%s_1_1"' % name)
    out.append(_pin("1", "1", -5.08, 0.0, 0, 2.54, PA))
    out.append(_pin("2", "2", 5.08, 0.0, 180, 2.54, PA))
    out.append(')')
    return _close(out), {}


def debug_conn(name, pins, keywords):
    """A 3-pin JST-SH (Raspberry Pi debug connector) with its two mounting pads; pins on
    the right, pointing at the chip it serves (as on GPiBridge)."""
    hh, hw = 5.08, 3.81
    out = _hdr(name, "J", name.replace("Conn_", ""), hh + 1.27, keywords=keywords)
    out.append('(symbol "%s_0_1"' % name)
    out.append(_rect(-hw, hh, hw, -hh))
    out.append(')')
    out.append('(symbol "%s_1_1"' % name)
    for i, (num, nm, t) in enumerate(pins):
        out.append(_pin(num, nm, hw + 5.08, hh - G * (i + 1), 180, 5.08, t))
    out.append(_pin("MP", "", 0, -hh - 5.08, 90, 5.08, PA))
    out.append(')')
    return _close(out), {}


def conn_swd():
    # Raspberry Pi 3-pin debug connector specification: 1 SC, 2 GND, 3 SD
    return debug_conn("Conn_SWD", [("1", "SWCLK", PA), ("3", "SWDIO", PA), ("2", "GND", PA)],
                      "Raspberry Pi 3-pin debug connector, serial wire debug: 1 SC, 2 GND, 3 SD")


def conn_uart():
    # the same specification, UART: 1 RX (into the target), 2 GND, 3 TX
    return debug_conn("Conn_UART", [("1", "RX", PA), ("3", "TX", PA), ("2", "GND", PA)],
                      "Raspberry Pi 3-pin debug connector, UART: 1 RX (into this board), 2 GND, 3 TX")


CUSTOM = {"RP2354A": rp2354a, "DRV8874": drv8874, "NS4150B": ns4150b, "TMAG5273": tmag5273,
          "Q_PMOS_SSSGDDDD": q_pmos_sssgdddd, "LED_3die": led_3die, "Coil": coil,
          "Conn_SWD": conn_swd, "Conn_UART": conn_uart}

# Rails, each with its own power symbol; the sub-boards have their own grounds and rails
# (their nets must not merge with the base's: they meet only through mated connectors).
RAILS = {"+12V": False, "+12V_IN": False, "+5V": False, "+3V3": False, "+1V1": False, "VBUS": False,
         "GND": True,
         "+5V_T": False, "+3V3_T": False, "GND_T": True,          # the tree
         "+3V3_P": False, "+5V_P": False, "GND_P": True}           # the perch
