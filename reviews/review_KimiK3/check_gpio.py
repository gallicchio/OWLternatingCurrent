#!/usr/bin/env python3
"""Static checks of the RP2354A GPIO binding against the RP2350 datasheet
(function table verified in datasheets/RP2354A.pdf = RP2350 datasheet release 8,
section 1.2.3 "GPIO functions (Bank 0)" and the QFN-60 pinout figure).

Datasheet facts used here (read off the table by hand):
  * PWM: GPIO n -> PWM slice (n>>1)&7, channel "AB"[n&1]; slices repeat every
    16 GPIOs: GPIO16/17 = PWM0 A/B ... GPIO28/29 = PWM6 A/B. PWM also exists
    on GPIO26-29.
  * ADC: exactly GPIO26/27/28/29 = ADC0/1/2/3 (QFN-60 pinout figure).
  * I2C0 SDA on GPIO 0,4,8,12,16,20,24,28 ; SCL on 1,5,9,13,17,21,25,29.
  * UART0 TX on GPIO 0,12,16,28 ; RX on 1,13,17,29.
  * PIO0/1/2 available on every GPIO 0-29.
Reads only; writes nothing.
"""
import json, re, sys

ROOT = "/home/jason/stuff/mudd/pcbs/OWLternatingCurrent"
A = json.load(open(ROOT + "/gen/assignment.json"))["gpio"]
HDR = open(ROOT + "/firmware/src/board_pins.h").read()
SDK = open(ROOT + "/firmware/boards/owlternating.h").read()

BRIDGES = [("PEND1_IN1", "PEND1_IN2"), ("PEND2_IN1", "PEND2_IN2"), ("PEND3_IN1", "PEND3_IN2"),
           ("LEV_IN1", "LEV_IN2"), ("FAM1_A", "FAM1_B"), ("FAM2_A", "FAM2_B")]
ADC_NETS = ("HALL", "LEV_IPROPI", "MUX_OUT")
I2C0 = {(4 * k, 4 * k + 1) for k in range(8)}
UART0 = {(0, 1), (12, 13), (16, 17), (28, 29)}

fails = []
def check(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)

# --- 30 nets, unique pins, exactly GPIO0-29 -------------------------------
check(len(A) == 30, "30 nets assigned (got %d)" % len(A))
check(sorted(A.values()) == list(range(30)), "GPIOs 0-29 each used exactly once")

# --- PWM: bridges on (even, even+1), distinct slices, mod-8 slice math -----
slices = {}
for x, y in BRIDGES:
    g = A[x]
    check(g % 2 == 0 and A[y] == g + 1, "%s/%s on adjacent pair (%d,%d)" % (x, y, g, A[y]))
    s = (g >> 1) & 7
    check(s not in slices, "%s slice PWM%d not shared" % (x, s))
    slices[s] = x
au = A["AUDIO"]
check(au % 2 == 0, "AUDIO on even GPIO%d (channel A)" % au)
check(((au >> 1) & 7) not in slices, "AUDIO slice PWM%d free of bridges" % ((au >> 1) & 7))
slices[(au >> 1) & 7] = "AUDIO"
check(slices.get(0) is None, "slice 0 left for the firmware tick (PWM_SLICE_TICK)")

# --- ADC ------------------------------------------------------------------
for n in ADC_NETS:
    check(26 <= A[n] <= 29, "%s on ADC-capable GPIO%d" % (n, A[n]))
for n, ch in (("HALL", 1), ("LEV_IPROPI", 2), ("MUX_OUT", 3)):
    m = re.search(r"ADC_CH_%s\s+(\d+)" % n, HDR)
    check(m and int(m.group(1)) == A[n] - 26 == ch - 1 + 1 - 1 or (m and int(m.group(1)) == A[n] - 26),
          "board_pins.h ADC_CH_%s == GPIO-26" % n)

# --- I2C0 / UART0 ----------------------------------------------------------
check((A["SDA"], A["SCL"]) in I2C0, "I2C0 SDA/SCL on (%d,%d): allowed" % (A["SDA"], A["SCL"]))
check((A["UART_TX"], A["UART_RX"]) in UART0, "UART0 TX/RX on (%d,%d): allowed" % (A["UART_TX"], A["UART_RX"]))

# --- mux selects consecutive ----------------------------------------------
check(A["MUX_S1"] == A["MUX_S0"] + 1 and A["MUX_S2"] == A["MUX_S0"] + 2,
      "MUX_S0..S2 consecutive: %d,%d,%d" % (A["MUX_S0"], A["MUX_S1"], A["MUX_S2"]))
m = re.search(r"MUX_SEL_SHIFT\s+(\d+)", HDR)
check(m and int(m.group(1)) == A["MUX_S0"], "board_pins.h MUX_SEL_SHIFT == MUX_S0")

# --- board_pins.h matches assignment.json for every net --------------------
pins = dict(re.findall(r"#define\s+PIN_(\w+)\s+(\d+)", HDR))
mismatch = [n for n, g in A.items() if n not in pins or int(pins[n]) != g]
check(not mismatch, "board_pins.h PIN_* == assignment.json for all 30 nets %s" % (mismatch or ""))

# --- PWM slice defines in board_pins.h -------------------------------------
for name, net in (("PEND1", "PEND1_IN1"), ("PEND2", "PEND2_IN1"), ("PEND3", "PEND3_IN1"),
                  ("LEV", "LEV_IN1"), ("FAM1", "FAM1_A"), ("FAM2", "FAM2_A"), ("AUDIO", "AUDIO")):
    m = re.search(r"PWM_SLICE_%s\s+(\d+)" % name, HDR)
    want = (A[net] >> 1) & 7
    check(m and int(m.group(1)) == want, "PWM_SLICE_%s == %d (GPIO%d)" % (name, want, A[net]))

# --- SDK board header matches ----------------------------------------------
for macro, net in (("PICO_DEFAULT_UART_TX_PIN", "UART_TX"), ("PICO_DEFAULT_UART_RX_PIN", "UART_RX"),
                   ("PICO_DEFAULT_I2C_SDA_PIN", "SDA"), ("PICO_DEFAULT_I2C_SCL_PIN", "SCL")):
    m = re.search(macro + r"\s+(\d+)", SDK)
    check(m and int(m.group(1)) == A[net], "owlternating.h %s == GPIO%d" % (macro, A[net]))
# stale comments in the SDK header?
c = re.findall(r"/\* (UART0|I2C0) on GPIO(\d+)/(\d+)", SDK)
print("NOTE  SDK header comments say:", c, " actual defines: TX/RX=%d/%d SDA/SCL=%d/%d"
      % (A["UART_TX"], A["UART_RX"], A["SDA"], A["SCL"]))

# --- PIO pins (any GPIO is PIO-capable on RP2350) ---------------------------
for n in ("THEREMIN_PITCH", "THEREMIN_VOL"):
    check(0 <= A[n] <= 29, "%s on GPIO%d: PIO input OK (all GPIOs are PIO pins)" % (n, A[n]))

print("\n%d FAILURES" % len(fails))
sys.exit(1 if fails else 0)
