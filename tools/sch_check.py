#!/usr/bin/env python3
"""Bring the generated schematic to KiCad 10's own format, run ERC at every
severity and export the netlist the board is made from.

    python3 tools/sch_check.py        (GPIBRIDGE_VARIANT=lite for the Lite)

Writes erc.json and netlist.net in hardware/checks/ (the Lite's in
hardware/checks/lite/).  Exit status 1 if ERC reports anything.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kienv
import board_info as BI

SCH = BI.SCH
CHECKS = BI.CHECKS


def relative_source(net):
    """kicad-cli writes the schematic's absolute path into the netlist's header.
    Make it relative to the netlist, so that the committed file names no machine."""
    s = open(net).read()
    s = re.sub(r'\(source "(/[^"]*)"\)',
               lambda m: '(source "%s")' % os.path.relpath(m.group(1), os.path.dirname(net)), s)
    open(net, "w").write(s)


def main():
    os.makedirs(CHECKS, exist_ok=True)
    # the writer emits an older file version; upgrading makes KiCad 10 open it without asking
    kienv.run_cli(["sch", "upgrade", "--force", SCH])
    erc = os.path.join(CHECKS, "erc.json")
    kienv.run_cli(["sch", "erc", "--format", "json", "--severity-all", "--units", "mm", "-o", erc, SCH], ok=(0, 5))
    net = os.path.join(CHECKS, "netlist.net")
    kienv.run_cli(["sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, SCH])
    relative_source(net)
    d = json.load(open(erc))
    items = [v for s in d.get("sheets", []) for v in s.get("violations", [])]
    for v in items[:40]:
        print("   ERC %s %s: %s" % (v.get("severity"), v.get("type"), v.get("description")))
    print("schematic checks: %d ERC items; netlist -> %s" % (len(items), os.path.relpath(net, ROOT)))
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main())
