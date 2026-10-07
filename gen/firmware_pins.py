#!/usr/bin/env python3
"""Write firmware/src/board_pins.h from gen/pins.py, so the firmware and the
board cannot disagree about which GPIO is which.

    python3 gen/firmware_pins.py

Everything the C needs is derived here, never typed twice:
  * PIN_<NET> for every GPIO, with its job as a comment;
  * each bridge's PWM slice, checked: IN1 / leg A on the slice's A output,
    IN2 / leg B on its B output (RP2350: GPIO n is slice (n >> 1) & 7,
    channel n & 1);
  * the ADC inputs (GPIO26-29 are ADC0-3 on the QFN-60);
  * the 74HC4051's channels, and the sense dividers' ratios, read from the
    descriptions ("through 100 k / 22 k");
  * the I2C addresses;
  * the pins the board holds with its own 10 k resistors (the descriptions
    say "pull-up" or "pull-down"), for the safe state and for RP2350-E9.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pins as PINS            # noqa: E402
import board_info as BI        # noqa: E402

OUT = os.path.join(ROOT, "firmware", "src", "board_pins.h")

BRIDGES_DRV = ("PEND1", "PEND2", "PEND3", "LEV")      # DRV8874s: IN1 = A, IN2 = B
BRIDGES_FAM = ("FAM1", "FAM2")                        # UCC27524 legs: A, B
ADC_FIRST_GPIO = 26                                   # QFN-60: GPIO26-29 = ADC0-3


def slice_of(gpio):
    return (gpio >> 1) & 7


def chan_of(gpio):
    return gpio & 1


def divider(desc):
    """'through 100 k / 22 k' -> (100e3, 22e3); the ratio is bottom / (top + bottom)."""
    m = re.search(r"through\s+([\d.]+)\s*k\s*/\s*([\d.]+)\s*k", desc)
    assert m, "no 'through R1 k / R2 k' divider in %r" % desc
    return float(m.group(1)) * 1e3, float(m.group(2)) * 1e3


def c_comment(s):
    return s.replace("*/", "* /")


def main():
    g = PINS.GPIO_OF
    L = ["/* board_pins.h: which RP2354A GPIO does what on %s rev %s." % (BI.TITLE, BI.REV),
         " * WRITTEN BY gen/firmware_pins.py FROM gen/pins.py: edit that, not this. */",
         "#pragma once", ""]

    L.append("/* ---- every GPIO ---------------------------------------------------------- */")
    for n in sorted(PINS.GPIO):
        net, direction, what = PINS.GPIO[n]
        L.append("#define PIN_%-16s %2d   /* %s: %s */" % (net, n, direction, c_comment(what)))
    L.append("")

    L.append("/* ---- the coil bridges: one PWM slice each, IN1/leg A = channel A -------------- */")
    for b in BRIDGES_DRV:
        a, bb = g[b + "_IN1"], g[b + "_IN2"]
        assert slice_of(a) == slice_of(bb), "%s: IN1 and IN2 on different PWM slices" % b
        assert chan_of(a) == 0 and chan_of(bb) == 1, "%s: IN1 must be channel A, IN2 channel B" % b
        assert a < 16, "%s: GPIO16 and up share slices 0-6 with GPIO0-13" % b
        L.append("#define PWM_SLICE_%-6s %d   /* GPIO%d (IN1) = A, GPIO%d (IN2) = B */" % (b, slice_of(a), a, bb))
    for b in BRIDGES_FAM:
        a, bb = g[b + "_A"], g[b + "_B"]
        assert slice_of(a) == slice_of(bb) and chan_of(a) == 0 and chan_of(bb) == 1, b
        L.append("#define PWM_SLICE_%-6s %d   /* GPIO%d (leg A) = A, GPIO%d (leg B) = B */" % (b, slice_of(a), a, bb))
    au = g["AUDIO"]
    assert chan_of(au) == 0, "AUDIO must be a slice's A output"
    L.append("#define PWM_SLICE_AUDIO  %d   /* GPIO%d = A */" % (slice_of(au), au))
    used = {slice_of(g[b + "_IN1"]) for b in BRIDGES_DRV} | {slice_of(g[b + "_A"]) for b in BRIDGES_FAM}
    used.add(slice_of(au))
    # a slice no output uses: the 10 kHz control tick (its counter only, no pin)
    free = [s for s in range(8) if s not in used]
    assert free, "no PWM slice left for the control tick"
    tick = free[0]
    pins_on_tick = [n for n in range(16) if slice_of(n) == tick]
    L.append("#define PWM_SLICE_TICK   %d   /* no PWM output: GPIO%s carry %s */" % (
        tick, " and GPIO".join(str(p) for p in pins_on_tick), " and ".join(PINS.GPIO[p][0] for p in pins_on_tick)))
    L.append("")

    L.append("/* ---- the ADC inputs ---------------------------------------------------- */")
    for net in ("HALL", "LEV_IPROPI", "MUX_OUT"):
        n = g[net]
        assert ADC_FIRST_GPIO <= n <= 29, net
        L.append("#define ADC_CH_%-12s %d   /* GPIO%d */" % (net, n - ADC_FIRST_GPIO, n))
    L.append("")

    L.append("/* ---- the 74HC4051 (S0-S2 on PIN_MUX_S0..S2) ------------------------------ */")
    s0, s1, s2 = g["MUX_S0"], g["MUX_S1"], g["MUX_S2"]
    assert s1 == s0 + 1 and s2 == s0 + 2, "the mux select pins must be adjacent (one masked write)"
    L.append("#define MUX_SEL_SHIFT    %d" % s0)
    L.append("#define MUX_SEL_MASK     (7u << MUX_SEL_SHIFT)")
    for ch in sorted(PINS.MUX):
        net, what = PINS.MUX[ch]
        L.append("#define MUX_CH_%-14s %d   /* %s */" % (net, ch, c_comment(what)))
    L.append("#define MUX_CHANNELS     %d" % len(PINS.MUX))
    for ch in sorted(PINS.MUX):
        net, what = PINS.MUX[ch]
        if net.endswith("_SENSE") and "through" in what:
            top, bot = divider(what)
            L.append("#define %-20s %.6ff   /* sense voltage / rail: %.0f k over %.0f k */" % (
                net.replace("_SENSE", "_DIVIDER"), bot / (top + bot), top / 1e3, bot / 1e3))
    L.append("")

    L.append("/* ---- I2C0 (7-bit addresses) ------------------------------------------------- */")
    for name, addr in PINS.I2C.items():
        L.append("#define I2C_ADDR_%-12s 0x%02X" % (name, addr))
    L.append("")

    # the board's own resistors ("4.7 k pull-down") and the pins that need the pad's
    # own pull-up ("internal pull-up"); RP2350-E9 rules out relying on a pad pull-down
    up, down, internal_up = [], [], []
    for n in sorted(PINS.GPIO):
        net, _, what = PINS.GPIO[n]
        if re.search(r"[\d.]+\s*k\s+pull-up", what):
            up.append(net)
        if re.search(r"[\d.]+\s*k\s+pull-down", what):
            down.append(net)
        # the RP2354A pad's own ("internal pull-up"), not another chip's ("their internal pull-ups")
        if re.search(r"(?<!their )internal pull-up(?!s)", what):
            internal_up.append(net)
        assert not re.search(r"internal pull-down", what), "%s relies on a pad pull-down (RP2350-E9)" % net
    L += ["/* ---- what the board's own resistors hold while the RP2354A is in reset ---- */",
          "#define BOARD_PULL_UP_MASK    (%s)" % (" | ".join("(1u << PIN_%s)" % n for n in up) or "0u"),
          "#define BOARD_PULL_DOWN_MASK  (%s)" % (" | ".join("(1u << PIN_%s)" % n for n in down) or "0u"),
          "/* the pins that rely on the pad's own pull-up (pull-ups are not hit by RP2350-E9) */",
          "#define MCU_PULL_UP_MASK      (%s)" % (" | ".join("(1u << PIN_%s)" % n for n in internal_up) or "0u"),
          ""]
    assert "DRV_nSLEEP" in down and "FAM_EN" in down, "the bridges' enables must be pulled off in reset"

    bridge_pins = ["%s_IN1" % b for b in BRIDGES_DRV] + ["%s_IN2" % b for b in BRIDGES_DRV] + \
                  ["%s_A" % b for b in BRIDGES_FAM] + ["%s_B" % b for b in BRIDGES_FAM]
    L += ["/* every pin that drives a coil bridge: low = off (DRV8874 coast, UCC27524 output low) */",
          "#define BRIDGE_PIN_MASK  (%s)" % " | \\\n                          ".join(
              "(1u << PIN_%s)" % n for n in bridge_pins),
          ""]
    open_tmp = OUT + ".tmp"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(open_tmp, "w") as f:
        f.write("\n".join(L))
    os.replace(open_tmp, OUT)
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
