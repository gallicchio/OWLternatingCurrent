"""Which RP2354A GPIO does what: the one source of truth.

The schematic draws these nets at these pins, the firmware's board_pins.h is
generated from this file (gen/firmware_pins.py), and docs/PINOUT.md too.

Constraints that shaped it (RP2350 datasheet, GPIO function table, section 9.4):
  * On the 60-pin RP2354A, GPIO16-29 reuse PWM slices 0-6, so only 8 slices are
    independent.  Each coil bridge gets a whole slice (its two inputs are the
    slice's A and B outputs: same frequency, independent duty), on GPIO0-11; the
    audio gets slice 7 (GPIO14); everything on GPIO16 and up is non-PWM.
  * The theremin's two oscillators are counted by PIO, not by a PWM slice.
  * GPIO26-29 are the only ADC inputs: the levitation loop's two fast signals
    (Hall sensor, coil current) get their own; the slow ones share ADC2 through
    an 8:1 multiplexer.
  * RP2350-E9: an input's internal pull-down is unreliable, so every pin that must
    rest at a level has an external resistor; nothing here relies on a pull-down.
"""

# GPIO -> (net, direction, what it is)
GPIO = {
    0: ("PEND1_IN1", "out", "pendulum coil 1 bridge (DRV8874 U5) IN1; PWM0 A"),
    1: ("PEND1_IN2", "out", "pendulum coil 1 bridge IN2; PWM0 B"),
    2: ("PEND2_IN1", "out", "pendulum coil 2 bridge (U6) IN1; PWM1 A"),
    3: ("PEND2_IN2", "out", "pendulum coil 2 bridge IN2; PWM1 B"),
    4: ("PEND3_IN1", "out", "pendulum coil 3 bridge (U7) IN1; PWM2 A"),
    5: ("PEND3_IN2", "out", "pendulum coil 3 bridge IN2; PWM2 B"),
    6: ("LEV_IN1", "out", "levitation coil bridge (U8) IN1; PWM3 A"),
    7: ("LEV_IN2", "out", "levitation coil bridge IN2; PWM3 B"),
    8: ("FAM1_A", "out", "owl perch bridge, leg A (UCC27524 U9, channel A); PWM4 A"),
    9: ("FAM1_B", "out", "owl perch bridge, leg B (U9, channel B); PWM4 B"),
    10: ("FAM2_A", "out", "cat perch bridge, leg A (UCC27524 U10, channel A); PWM5 A"),
    11: ("FAM2_B", "out", "cat perch bridge, leg B (U10, channel B); PWM5 B"),
    12: ("UART_TX", "out", "UART0 TX to the debug connector J5 (console, 115200)"),
    13: ("UART_RX", "in", "UART0 RX from J5"),
    14: ("AUDIO", "out", "audio PWM to the class-D amplifier through an RC filter; PWM7 A"),
    15: ("IMU_INT", "in", "LSM6DS3TR-C INT1: taps, tilt, free fall"),
    16: ("SDA", "io", "I2C0 SDA: LED drivers, IMU, light sensor, 3-axis Hall; the tree's LED driver"),
    17: ("SCL", "out", "I2C0 SCL"),
    18: ("THEREMIN_PITCH", "in", "pitch oscillator (moon antenna), counted by PIO"),
    19: ("THEREMIN_VOL", "in", "volume oscillator (pumpkin antenna), counted by PIO"),
    20: ("MUX_S0", "out", "74HC4051 select bit 0"),
    21: ("MUX_S1", "out", "74HC4051 select bit 1"),
    22: ("MUX_S2", "out", "74HC4051 select bit 2"),
    23: ("DRV_nSLEEP", "out", "all four DRV8874s: low = asleep (4.7 k pull-down keeps them asleep in reset)"),
    24: ("DRV_nFAULT", "in", "all four DRV8874s' nFAULT, wired-OR, 10 k pull-up"),
    25: ("FAM_EN", "out", "both UCC27524s' four enables (4.7 k pull-down beats their internal pull-ups: off in reset)"),
    26: ("HALL", "adc", "ADC0: the perch's DRV5055 Hall sensor (via the tree)"),
    27: ("LEV_IPROPI", "adc", "ADC1: levitation coil current (DRV8874 IPROPI)"),
    28: ("MUX_OUT", "adc", "ADC2: the 74HC4051's output (slow signals, below)"),
    29: ("BUTTON", "in", "the SPELL button, low when pressed (internal pull-up: RP2350-E9 affects only pull-downs)"),
}

# The 74HC4051's inputs (MUX channel -> net, what).  The order is the drawing's: each line
# reaches its input without crossing another.  After switching channels, wait 10 us before
# sampling (the dividers have no capacitor; 18 k x 10 pF settles in 2 us).
MUX = {
    0: ("PEND3_IPROPI", "pendulum coil 3 current"),
    1: ("PEND2_IPROPI", "pendulum coil 2 current"),
    2: ("PEND1_IPROPI", "pendulum coil 1 current"),
    3: ("FAM2_ISENSE", "cat perch bridge's supply current (filtered): rises when the cat sits on it"),
    4: ("FAM1_ISENSE", "owl perch bridge's supply current (filtered): rises when the owl sits on it"),
    5: ("V12_SENSE", "+12V through 100 k / 22 k (12 V reads 2.16 V)"),
    6: ("V5_SENSE", "+5V through 10 k / 10 k (5 V reads 2.5 V)"),
    7: ("VBUS_SENSE", "USB VBUS through 10 k / 10 k: plugged into USB?"),
}

# I2C0 addresses (7-bit)
I2C = {
    "LP5036_BASE": 0x30,     # ADDR0 = ADDR1 = GND
    "LP5036_TREE": 0x31,     # ADDR0 = VCC, ADDR1 = GND (on the tree board)
    "LSM6DS3TR_C": 0x6A,     # SA0 = GND
    "LTR_303ALS": 0x29,      # fixed
    "TMAG5273A2": 0x35,      # factory address of the A2 (the B2 is 0x22): datasheet table 6-2
}

GPIO_OF = {net: n for n, (net, _, _) in GPIO.items()}
NET_OF = {n: net for n, (net, _, _) in GPIO.items()}
