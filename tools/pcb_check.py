#!/usr/bin/env python3
"""Run KiCad's DRC on the board at every severity, with schematic parity,
and summarise it by kind.

    python3 tools/pcb_check.py [--list KIND] [--max N]

Writes drc.json beside the netlist (hardware/checks/, the Lite's in
hardware/checks/lite/; GPIBRIDGE_VARIANT=lite selects it).  Exit status 1 if anything is reported.
--list KIND prints each item of that kind (e.g. clearance) with where it is,
in board millimetres from the top-left corner.
"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kienv
import board_info as BI

PCB = BI.PCB
OUT = os.path.join(BI.CHECKS, "drc.json")
ORIGIN = (100.0, 100.0)                  # gen/board.py puts the board's corner here


def main():
    args = sys.argv[1:]
    kienv.run_cli(["pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "--schematic-parity",
                   "-o", OUT, PCB], ok=(0, 5))
    d = json.load(open(OUT))
    items = []
    for key in ("violations", "unconnected_items", "schematic_parity"):
        for v in d.get(key, []):
            v["_group"] = key
            items.append(v)
    kinds = collections.Counter(v.get("type", "?") for v in items)
    for k, n in kinds.most_common():
        print("  %-32s %d" % (k, n))
    if "--list" in args:
        want = args[args.index("--list") + 1]
        nmax = int(args[args.index("--max") + 1]) if "--max" in args else 40
        for v in [v for v in items if v.get("type") == want][:nmax]:
            where = []
            for it in v.get("items", []):
                p = it.get("pos", {})
                where.append("(%.2f, %.2f) %s" % (p.get("x", 0) - ORIGIN[0], p.get("y", 0) - ORIGIN[1],
                                                  it.get("description", "")[:70]))
            print("   - %s" % v.get("description", ""))
            for w in where:
                print("       %s" % w)
    print("DRC: %d items (%d violations, %d unconnected, %d parity)"
          % (len(items), sum(1 for v in items if v["_group"] == "violations"),
             sum(1 for v in items if v["_group"] == "unconnected_items"),
             sum(1 for v in items if v["_group"] == "schematic_parity")))
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main())
