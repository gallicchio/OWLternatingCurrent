#!/usr/bin/env python3
"""Write firmware/src/led_map.h from gen/leds.py: every LED's driver, channel,
name, colour, board and position, so the light show and the board cannot
disagree about which channel lights what.

    python3 gen/firmware_leds.py

Positions come from the placement, once there is one: the board generator writes
hardware/checks/led_positions.json, which this reads if it exists.  Accepted forms
(millimetres, KiCad board coordinates: x right, y down):

    {"STAR0": {"x_mm": 12.5, "y_mm": 40.0}, ...}           # by LED name
    {"STAR0": [12.5, 40.0], ...}
    [{"name": "STAR0", "x_mm": 12.5, "y_mm": 40.0}, ...]

An LED the file does not mention (or every LED, without the file) gets x = y = 0,
and the header says how many are still unplaced (LED_UNPLACED).  The scenes do not
depend on positions yet; they use the order of each group (left to right).

The header also carries, for each named group (STAR, PUMPKIN, WISP, ...), the
LEDs' indices in order, and for each driver the channel -> LED table.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import leds as LEDS            # noqa: E402
import board_info as BI        # noqa: E402

OUT = os.path.join(ROOT, "firmware", "src", "led_map.h")
POSITIONS = os.path.join(ROOT, "hardware", "checks", "led_positions.json")

DRIVERS = ("BASE", "TREE")             # index 0 and 1 in the firmware
CHANNELS = 36                          # LP5036
COLOURS = ("orange", "amber5050", "violet", "purple")


def load_positions():
    if not os.path.exists(POSITIONS):
        return {}, "no %s yet" % os.path.relpath(POSITIONS, ROOT)
    data = json.load(open(POSITIONS))
    pos = {}
    items = data.items() if isinstance(data, dict) else ((d["name"], d) for d in data)
    for name, v in items:
        if isinstance(v, dict):
            pos[name] = (float(v["x_mm"]), float(v["y_mm"]))
        else:
            pos[name] = (float(v[0]), float(v[1]))
    return pos, "from %s" % os.path.relpath(POSITIONS, ROOT)


def board_of(driver, name, where):
    if "perch" in where.lower() or name.startswith("PERCH"):
        return "PERCH"
    return "BASE" if driver == "BASE" else "TREE"


def group_of(name):
    """STAR3 -> STAR, OWLA_L -> OWLEYE, PERCH_DOWN1 -> PERCH_DOWN."""
    if re.match(r"OWL[A-Z]_[LR]$", name):
        return "OWLEYE"
    return re.sub(r"\d+$", "", name)


def main():
    pos, pos_src = load_positions()
    entries = sorted(LEDS.LEDS.items(), key=lambda kv: (DRIVERS.index(kv[0][0]), kv[0][1]))
    for (drv, ch), (name, colour, where) in entries:
        assert drv in DRIVERS and 0 <= ch < CHANNELS and colour in COLOURS, (drv, ch, name, colour)
    names = [v[0] for _, v in entries]
    assert len(set(names)) == len(names), "duplicate LED names"
    assert set(LEDS.DRIVER_ADDR) == set(DRIVERS)

    L = ["/* led_map.h: every LED on %s rev %s: driver, channel, name, colour, board, position." % (BI.TITLE, BI.REV),
         " * WRITTEN BY gen/firmware_leds.py FROM gen/leds.py (and the placement's",
         " * hardware/checks/led_positions.json, when it exists): edit those, not this. */",
         "#pragma once",
         "#include <stdint.h>",
         "",
         "enum { LED_DRV_BASE = 0, LED_DRV_TREE = 1, LED_DRIVERS = 2 };",
         "#define LED_DRIVER_CHANNELS %d   /* LP5036: 12 banks of 3 */" % CHANNELS,
         "#define LED_DRIVER_BANKS    %d" % (CHANNELS // 3),
         "static const uint8_t LED_DRIVER_ADDR[LED_DRIVERS] = {0x%02X, 0x%02X};" % (
             LEDS.DRIVER_ADDR["BASE"], LEDS.DRIVER_ADDR["TREE"]),
         "",
         "/* colours (gen/leds.py's docstring has the parts) */",
         "enum { %s, LED_COLOURS };" % ", ".join("LED_COL_%s = %d" % (c.upper(), i) for i, c in enumerate(COLOURS)),
         "enum { LED_BOARD_BASE = 0, LED_BOARD_TREE = 1, LED_BOARD_PERCH = 2 };",
         "",
         "typedef struct {",
         "    uint8_t driver;      /* LED_DRV_* */",
         "    uint8_t channel;     /* OUTn, 0-35; its bank is channel / 3 */",
         "    const char *name;",
         "    uint8_t colour;      /* LED_COL_* */",
         "    float x_mm, y_mm;    /* on its board (KiCad coordinates); 0, 0 until placed */",
         "    uint8_t board;       /* LED_BOARD_* */",
         "} led_info;",
         "",
         "#define LED_COUNT %d" % len(entries)]
    unplaced = sum(1 for n in names if n not in pos)
    L.append("#define LED_UNPLACED %d   /* positions %s%s */" % (
        unplaced, pos_src, "" if not unplaced else "; TODO: x/y = 0 until the placement writes them"))
    L.append("")
    L.append("enum {")
    for i, n in enumerate(names):
        L.append("    LED_%s = %d," % (n, i))
    L.append("};")
    L.append("")
    L.append("static const led_info LED_MAP[LED_COUNT] = {")
    for (drv, ch), (name, colour, where) in entries:
        x, y = pos.get(name, (0.0, 0.0))
        L.append('    {LED_DRV_%s, %2d, "%s", LED_COL_%s, %.2ff, %.2ff, LED_BOARD_%s},   /* %s */' % (
            drv, ch, name, colour.upper(), x, y, board_of(drv, name, where), where.replace("*/", "* /")))
    L.append("};")
    L.append("")

    # channel -> LED index per driver (-1: unused output)
    L.append("/* each driver's outputs: the LED on OUTn, or -1 */")
    L.append("static const int8_t LED_OF_CHANNEL[LED_DRIVERS][LED_DRIVER_CHANNELS] = {")
    for drv in DRIVERS:
        row = []
        for ch in range(CHANNELS):
            idx = next((i for i, ((d, c), _) in enumerate(entries) if d == drv and c == ch), -1)
            row.append(str(idx))
        L.append("    {%s},   /* %s */" % (", ".join(row), drv))
    L.append("};")
    L.append("")

    # groups, in the order of their names' numbers (left to right, as gen/leds.py lists
    # them).  The table itself is in channel order, and the channels were reassigned for
    # the routing, so a group must be sorted by the number in each name: in table order
    # the arc ran STAR3, 2, 1, 0, 8, 7, ... and the theremin's meter filled in that order
    # (seen on the bench, 2026-11-07).  The owl eyes: by owl letter, then L before R.
    def member_key(i):
        n = names[i]
        m = re.search(r"(\d+)$", n)
        if m:
            return (int(m.group(1)), n)
        m = re.match(r"OWL([A-Z])_([LR])$", n)
        if m:
            return (ord(m.group(1)) * 2 + (m.group(2) == "R"), n)
        return (0, n)
    groups = {}
    for i, n in enumerate(names):
        groups.setdefault(group_of(n), []).append(i)
    for idx in groups.values():
        idx.sort(key=member_key)
    L.append("/* named groups, in order (the scenes walk these) */")
    for gname, idx in groups.items():
        L.append("#define LED_N_%-12s %d" % (gname, len(idx)))
        L.append("static const uint8_t LED_GROUP_%s[LED_N_%s] = {%s};" % (
            gname, gname, ", ".join(str(i) for i in idx)))
    L.append("")
    tmp = OUT + ".tmp"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(tmp, "w") as f:
        f.write("\n".join(L))
    os.replace(tmp, OUT)
    print("wrote %s: %d LEDs, %d groups, %d unplaced (%s)" % (
        os.path.relpath(OUT, ROOT), len(entries), len(groups), unplaced, pos_src))


if __name__ == "__main__":
    main()
