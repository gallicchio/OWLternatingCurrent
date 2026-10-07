#!/usr/bin/env python3
"""Check the exported netlist against the design's tables, pin by pin.

    python3 tools/net_check.py          (after tools/sch_check.py has exported the netlist)

  * every RP2354A GPIO carries the net gen/pins.py gives it;
  * every mux input carries the net gen/pins.py's MUX table gives it;
  * every pin of the four board-to-board connectors carries gen/connectors.py's net;
  * every LED driver output carries the LED gen/leds.py puts there, in its colour;
  * the LED drivers' address straps give gen/pins.py's I2C addresses.

Exit status 1 on any mismatch.  Writes hardware/checks/net_check.txt.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
from sexp import parse, kids, kid, val
import pins as PINS
import symbols as SYMB
import connectors as CONN
import leds as LEDS
import board_info as BI

MUX_PIN = {0: "13", 1: "14", 2: "15", 3: "12", 4: "1", 5: "5", 6: "2", 7: "4"}   # 74HC4051: A0..A7
# which part on which sheet, and how its power nets are named there
JOINTS = [("J3", CONN.BASE_TREE, ""), ("J101", CONN.BASE_TREE, "_T"), ("J102", CONN.TREE_PERCH, "_T"),
          ("J201", CONN.TREE_PERCH, "_P")]
DRIVERS = {"BASE": ("U3", ""), "TREE": ("U101", "_T")}
COLOUR_MPN = {"violet": "HL-A-3528S7VC", "purple": "GL0603PU01", "orange": "XL-1608UOC", "amber5050": "HL-AF-5060S22OC"}


def load(path):
    t = parse(open(path).read())[0]
    pinnet, comps = {}, {}
    for c in kids(kid(t, "components"), "comp"):
        ref = val(kid(c, "ref"))
        fields = {}
        fl = kid(c, "fields")
        if fl:
            for f in kids(fl, "field"):
                name = val(kid(f, "name"))
                fields[name] = f[-1][1] if isinstance(f[-1], tuple) else ""
        comps[ref] = dict(value=val(kid(c, "value")), fields=fields)
    for n in kids(kid(t, "nets"), "net"):
        name = val(kid(n, "name"))
        for nd in kids(n, "node"):
            pinnet[(val(kid(nd, "ref")), val(kid(nd, "pin")))] = name
    return pinnet, comps


def short(net):
    """'/Base/SDA' -> 'SDA'; power nets ('+3V3_T') stay as they are."""
    return net.split("/")[-1] if net else net


def main():
    pinnet, comps = load(BI.NETLIST)
    bad, lines = [], []

    def check(what, got, want):
        ok = got == want
        lines.append("%-4s %-40s %-24s %s" % ("ok" if ok else "BAD", what, got, "" if ok else "want " + want))
        if not ok:
            bad.append(what)

    for g, (net, _, _) in sorted(PINS.GPIO.items()):
        check("U4 GPIO%d (pin %s)" % (g, SYMB.GPIO_PIN[g]), short(pinnet.get(("U4", str(SYMB.GPIO_PIN[g])))), net)
    for ch, (net, _) in sorted(PINS.MUX.items()):
        check("U11 A%d (pin %s)" % (ch, MUX_PIN[ch]), short(pinnet.get(("U11", MUX_PIN[ch]))), net)
    for ref, table, suffix in JOINTS:
        for p, net in sorted(table.items()):
            want = net + suffix if (net.startswith("+") or net == "GND") and suffix else net
            check("%s pin %d" % (ref, p), short(pinnet.get((ref, str(p)))), want)
    for (drv, ch), (name, colour, _) in sorted(LEDS.LEDS.items()):
        u, _ = DRIVERS[drv]
        net = short(pinnet.get((u, str(ch + 1))))
        if name.startswith("PERCH_DOWN"):
            check("%s OUT%d" % (u, ch), net, "DOWN" + name[-1])
            continue
        check("%s OUT%d" % (u, ch), net, name)
        # the LED on that net is the right colour
        leds = [r for (r, pn), n in pinnet.items() if pinnet[(r, pn)] == pinnet.get((u, str(ch + 1)))
                and r.startswith("D")]
        mpns = {comps[r]["fields"].get("MPN", "") for r in leds}
        check("%s OUT%d colour" % (u, ch), "yes" if any(COLOUR_MPN[colour] in m for m in mpns) else "no", "yes")
    for drv, (u, suffix) in DRIVERS.items():
        a0, a1 = short(pinnet.get((u, "38"))), short(pinnet.get((u, "39")))
        addr = 0x30 | (2 if a1.startswith("+3V3") else 0) | (1 if a0.startswith("+3V3") else 0)
        want = PINS.I2C["LP5036_" + drv]
        check("%s I2C address" % u, "0x%02X" % addr, "0x%02X" % want)
    out = os.path.join(BI.CHECKS, "net_check.txt")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("net check: %d checks, %d mismatches -> %s" % (len(lines), len(bad), os.path.relpath(out, ROOT)))
    for b in bad:
        print("   ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
