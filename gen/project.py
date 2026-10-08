#!/usr/bin/env python3
"""The KiCad project file: design rules at least as strict as JLCPCB's for the
JLC04161H-7628 4-layer stack-up, the net classes, and the ERC settings.

    python3 gen/project.py      writes hardware/OWLternatingCurrent.kicad_pro and .kicad_dru

JLCPCB's limits for 4-layer boards (capabilities page): track and space 0.09 mm, via
0.15 mm hole in a 0.25 mm pad, hole to hole 0.2 mm, copper to a routed edge 0.2 mm.
Ours are stricter everywhere (GPiBridge's rules).

Track widths for current (CLAUDE_PCB.md section 15; IPC-2152, 1 oz outer copper, 10 C
rise): 1 A needs 0.3 mm, 2 A 0.75 mm, 3.5 A 1.5 mm.  The 12 V path carries up to 5 A and
is drawn as zones; its class asks for 2.5 mm where a track is used.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import board_info as BI

LIMITS = {
    "min_clearance": 0.127,
    "min_track_width": 0.127,
    "min_via_diameter": 0.45,
    "min_through_hole_diameter": 0.25,       # Raspberry Pi's exposed-pad and regulator vias: 0.25 mm in 0.6 mm
    "min_via_annular_width": 0.1,
    "min_microvia_diameter": 0.3,
    "min_microvia_drill": 0.1,
    "min_hole_clearance": 0.2,
    "min_hole_to_hole": 0.25,
    "min_silk_clearance": 0.0,
    "min_text_height": 0.8,
    "min_text_thickness": 0.15,
    "min_copper_edge_clearance": 0.3,
    # (no minimum connection width: the check finds a ground via just touching a pour's
    # edge, which every ground via and pad also reaches through the In2 plane)
    "min_connection": 0.0,
    "min_resolved_spokes": 1,                # a small passive's ground pad between tracks may keep one spoke
    "solder_mask_clearance": 0.0,
    "solder_mask_min_width": 0.0,
}

# name, track, clearance, via dia, via drill, diff-pair width, diff-pair gap
CLASSES = [
    ("Default", 0.15, 0.15, 0.45, 0.25, 0.15, 0.15),
    ("Logic_Power", 0.4, 0.15, 0.6, 0.3, 0.4, 0.2),     # 3.3 V, 1.1 V, VSYS, VBUS: under 0.2 A
    # (clearance 0.15 mm on every class: IPC-2221 asks 0.1 mm between outer-layer copper
    # at up to 15 V, and the router keeps 0.16 mm everywhere; width is what current needs)
    ("Power_5V", 0.8, 0.15, 0.6, 0.3, 0.8, 0.2),        # the 4.8 V rail: LEDs, perch drivers, audio, the tree
    ("Power_12V", 2.5, 0.15, 0.8, 0.4, 2.5, 0.25),      # the input and the coil bridges' supply: 5 A
    ("Coil", 1.5, 0.15, 0.8, 0.4, 1.5, 0.25),           # bridge outputs to coils: 3.3 A peaks
    ("USB", 0.2, 0.15, 0.45, 0.25, 0.2, 0.15),          # full speed forgives the impedance
    ("GND", 0.5, 0.15, 0.6, 0.3, 0.5, 0.2),
]
PATTERNS = [
    ("GND", "GND"), ("GND", "GND_T"), ("GND", "GND_P"),
    ("Logic_Power", "+3V3"), ("Logic_Power", "+1V1"), ("Logic_Power", "VSYS"), ("Logic_Power", "VBUS"),
    ("Logic_Power", "+3V3_T"), ("Logic_Power", "+3V3_P"),
    ("Power_5V", "+5V"), ("Power_5V", "+5V_T"), ("Power_5V", "+5V_P"),
    ("Power_12V", "+12V"), ("Power_12V", "/Net-\\((J1|F1|Q1)-/"),
    ("Coil", "/^(LEV|PEND[123]|OWL|CAT)_[ABC]$/"), ("Coil", "/^(LEV|PEND)_[AB]_[TP]$/"),
    ("USB", "/USB_D[PM+-]$/"),
]

DRU = '''(version 1)
# Written by gen/project.py.  Edit that, not this.
# (no silk_clearance rule: KiCad 10 then reports every designator against Fab
#  text and courtyards as a silkscreen overlap; its built-in silk checks stay on)
(rule "USB pair skew"
    (constraint skew (max 1.0mm))
    (condition "A.NetClass == 'USB' && B.NetClass == 'USB'"))
'''


def write(hw):
    path = os.path.join(hw, BI.NAME + ".kicad_pro")
    pro = {}
    if os.path.exists(path):
        try:
            pro = json.load(open(path))
        except Exception:
            pro = {}
    pro["meta"] = {"filename": BI.NAME + ".kicad_pro", "version": 3}
    board = pro.setdefault("board", {})
    ds = board.setdefault("design_settings", {})
    ds.setdefault("defaults", {})
    ds["rules"] = LIMITS
    sev = ds.setdefault("rule_severities", {})
    for k in ("silk_over_copper", "silk_overlap", "silk_edge_clearance", "text_height", "text_thickness",
              "copper_edge_clearance", "holes_co_located", "solder_mask_bridge", "courtyards_overlap",
              "duplicate_footprints", "missing_footprint", "extra_footprint", "unresolved_variable",
              "net_conflict", "invalid_outline", "malformed_outline", "through_hole_pad_without_hole",
              "lib_footprint_mismatch"):
        sev[k] = "error"
    for k in ("lib_footprint_issues", "footprint_symbol_mismatch", "footprint_type_mismatch", "padstack"):
        sev[k] = "ignore"
    sev["isolated_copper"] = "warning"
    ds["drc_exclusions"] = []
    net = pro.setdefault("net_settings", {})
    net["classes"] = [{"name": n, "track_width": tw, "clearance": cl, "via_diameter": vd, "via_drill": vdr,
                       "diff_pair_width": dw, "diff_pair_gap": dg, "diff_pair_via_gap": dg, "bus_width": 12,
                       "wire_width": 6, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                       "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                       "priority": 2147483647 if n == "Default" else 0, "tuning_profile": ""}
                      for n, tw, cl, vd, vdr, dw, dg in CLASSES]
    net["netclass_patterns"] = [{"netclass": c, "pattern": p} for c, p in PATTERNS]
    net.setdefault("meta", {"version": 4})
    sch = pro.setdefault("schematic", {})
    sch.setdefault("meta", {"version": 1})
    erc = sch.setdefault("erc", {})
    erc.setdefault("rule_severities", {})
    pro.setdefault("libraries", {"pinned_footprint_libs": [], "pinned_symbol_libs": []})
    pro.setdefault("pcbnew", {"last_paths": {}, "page_layout_descr_file": ""})
    pro.setdefault("sheets", [])
    pro["text_variables"] = {"REV": BI.REV, "DATE": BI.DATE}
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)
    with open(os.path.join(hw, BI.NAME + ".kicad_dru"), "w") as f:
        f.write(DRU)
    return path


if __name__ == "__main__":
    print(write(os.path.join(ROOT, "hardware")))
