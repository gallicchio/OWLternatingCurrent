"""Which RP2354A GPIO does what: the one source of truth.

The schematic draws these nets at these pins, the firmware's board_pins.h is
generated from this file (gen/firmware_pins.py), and docs/PINOUT.md too.

Constraints that shaped it (RP2350 datasheet, GPIO function table, section 9.4):
  * On the 60-pin RP2354A, GPIO16-29 reuse PWM slices 0-6, so only 8 slices are
    independent.  Each coil bridge gets a whole slice (its two inputs are the
    slice's A and B outputs: same frequency, independent duty), on GPIO0-11; the
    audio gets slice 7 (GPIO14); everything on GPIO16 and up is non-PWM.  That last
    rule is a choice, not the chip's: PWM is legal on GPIO16-29 too, and gen/assign.py
    could cut the ring crossings from 84 to about 60 by using them (review 2026-10-09).
    It is kept because GPIO16-29 share the chip's back edge with the ADC pins (26-29)
    that carry the levitation loop's two signals: no 100 kHz bridge PWM beside them.
  * The theremin's two oscillators are counted by PIO, not by a PWM slice.
  * GPIO26-29 are the only ADC inputs: the levitation loop's two fast signals
    (Hall sensor, coil current) get their own; the slow ones share ADC2 through
    an 8:1 multiplexer.
  * RP2350-E9: an input's internal pull-down is unreliable, so every pin that must
    rest at a level has an external resistor; nothing here relies on a pull-down.
"""

# The hand-written table, in GPIO order: GPIO -> (net, direction, what it is).  The board's
# own order is chosen by gen/assign.py from the placement (which pin each line reaches
# first, so that the lines leave the chip without crossing) and kept in
# gen/assignment.json; GPIO below is that order.  The PWM slice and ADC channel in each
# description follow the GPIO number, so they are added below, not written here.
DEFAULT = {
    0: ("PEND1_IN1", "out", "pendulum coil 1 bridge (DRV8874 U5) IN1"),
    1: ("PEND1_IN2", "out", "pendulum coil 1 bridge IN2"),
    2: ("PEND2_IN1", "out", "pendulum coil 2 bridge (U6) IN1"),
    3: ("PEND2_IN2", "out", "pendulum coil 2 bridge IN2"),
    4: ("PEND3_IN1", "out", "pendulum coil 3 bridge (U7) IN1"),
    5: ("PEND3_IN2", "out", "pendulum coil 3 bridge IN2"),
    6: ("LEV_IN1", "out", "levitation coil bridge (U8) IN1"),
    7: ("LEV_IN2", "out", "levitation coil bridge IN2"),
    8: ("FAM1_A", "out", "owl perch bridge, leg A (UCC27524 U9, channel A)"),
    9: ("FAM1_B", "out", "owl perch bridge, leg B (U9, channel B)"),
    10: ("FAM2_A", "out", "cat perch bridge, leg A (UCC27524 U10, channel A)"),
    11: ("FAM2_B", "out", "cat perch bridge, leg B (U10, channel B)"),
    12: ("UART_TX", "out", "UART0 TX to the debug connector J5 (console, 115200)"),
    13: ("UART_RX", "in", "UART0 RX from J5"),
    14: ("AUDIO", "out", "audio PWM to the class-D amplifier through an RC filter"),
    15: ("IMU_INT", "in", "LSM6DS3TR-C INT1: taps, tilt, free fall"),
    16: ("SDA", "io", "I2C0 SDA: LED drivers, IMU, light sensor, 3-axis Hall; the tree's LED driver"),
    17: ("SCL", "out", "I2C0 SCL"),
    18: ("THEREMIN_PITCH", "in", "pitch oscillator (moon antenna), counted by PIO"),
    19: ("THEREMIN_VOL", "in", "volume oscillator (ghost antenna), counted by PIO"),
    20: ("MUX_S0", "out", "74HC4051 select bit 0"),
    21: ("MUX_S1", "out", "74HC4051 select bit 1"),
    22: ("MUX_S2", "out", "74HC4051 select bit 2"),
    23: ("DRV_nSLEEP", "out", "all four DRV8874s: low = asleep (4.7 k pull-down keeps them asleep in reset)"),
    24: ("DRV_nFAULT", "in", "all four DRV8874s' nFAULT, wired-OR, 10 k pull-up"),
    25: ("FAM_EN", "out", "both UCC27524s' four enables (4.7 k pull-down beats their internal pull-ups: off in reset)"),
    26: ("HALL", "adc", "the perch's DRV5055 Hall sensor (via the tree)"),
    27: ("LEV_IPROPI", "adc", "levitation coil current (DRV8874 IPROPI)"),
    28: ("MUX_OUT", "adc", "the 74HC4051's output (slow signals, below)"),
    29: ("BUTTON", "in", "the SPELL button, low when pressed (internal pull-up: RP2350-E9 affects only pull-downs)"),
}
PWM_NETS = ("PEND1_IN1", "PEND1_IN2", "PEND2_IN1", "PEND2_IN2", "PEND3_IN1", "PEND3_IN2", "LEV_IN1",
            "LEV_IN2", "FAM1_A", "FAM1_B", "FAM2_A", "FAM2_B", "AUDIO")

# The 74HC4051's inputs, hand-written (MUX channel -> net, what); MUX below is the board's
# order (gen/assignment.json).  After switching channels, wait 10 us before sampling (the
# dividers have no capacitor; 18 k x 10 pF settles in 2 us).
MUX_DEFAULT = {
    0: ("PEND3_IPROPI", "pendulum coil 3 current"),
    1: ("PEND2_IPROPI", "pendulum coil 2 current"),
    2: ("PEND1_IPROPI", "pendulum coil 1 current"),
    3: ("FAM2_ISENSE", "cat perch bridge's supply current, 1 ms average, x20.6 on 0.5 R: 10.3 V/A; rises when the cat sits on it"),
    4: ("FAM1_ISENSE", "owl perch bridge's supply current, 1 ms average, x20.6 on 0.5 R: 10.3 V/A; rises when the owl sits on it"),
    5: ("V12_SENSE", "+12V through 100 k / 22 k (12 V reads 2.16 V)"),
    6: ("V5_SENSE", "+5V through 10 k / 10 k (5 V reads 2.5 V)"),
    7: ("VBUS_SENSE", "USB VBUS through 10 k / 10 k: plugged into USB?"),
}


def _assigned():
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assignment.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def _what(net, g, what):
    if net in PWM_NETS:
        what += "; PWM%d %s" % ((g >> 1) & 7, "AB"[g & 1])
    if g >= 26 and DEFAULT_DIR[net] == "adc":
        what = "ADC%d: %s" % (g - 26, what)
    return what


DEFAULT_DIR = {net: d for net, d, _ in DEFAULT.values()}
_A = _assigned()
_GPIO_OF = _A.get("gpio") or {net: g for g, (net, _, _) in DEFAULT.items()}
assert sorted(_GPIO_OF) == sorted(DEFAULT_DIR), "gen/assignment.json and pins.DEFAULT name different nets"
GPIO = {}
for _g, (_net, _d, _w) in DEFAULT.items():
    GPIO[_GPIO_OF[_net]] = (_net, _d, _what(_net, _GPIO_OF[_net], _w))
GPIO = dict(sorted(GPIO.items()))
_MUX_OF = _A.get("mux") or {net: ch for ch, (net, _) in MUX_DEFAULT.items()}
MUX = dict(sorted((_MUX_OF[net], (net, what)) for ch, (net, what) in MUX_DEFAULT.items()))

# I2C0 addresses (7-bit)
I2C = {
    "LP5036_BASE": 0x30,     # ADDR0 = ADDR1 = GND
    "LP5036_TREE": 0x32,     # ADDR1 = VCC, ADDR0 = GND (on the tree board)
    "LSM6DS3TR_C": 0x6A,     # SA0 = GND
    "LTR_303ALS": 0x29,      # fixed
    "TMAG5273A2": 0x35,      # factory address of the A2 (the B2 is 0x22): datasheet table 6-2
}

GPIO_OF = {net: n for n, (net, _, _) in GPIO.items()}
NET_OF = {n: net for n, (net, _, _) in GPIO.items()}
