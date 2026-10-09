#!/usr/bin/env python3
"""The JLCPCB release for OWLternating Current's panel: everything to upload, in one folder.

    python3 mfg/make_release.py [--panels N] [--assembled N] [--refresh]

--panels is the number of bare panels ordered (JLCPCB's minimum, 5) and --assembled
how many of them JLCPCB assembles (2).  --refresh asks JLCPCB's parts API again
instead of using answers cached within the last 24 hours (tools/jlc_api.py).

One panel carries all six boards (gen/layout.py: base, tree, perch, bat, owl and cat
tokens) and is assembled on BOTH sides, so the BOM is the whole netlist and every
quantity is per panel.

Writes mfg/release/:
    OWLternatingCurrent_gerbers.zip  Gerbers (4 copper layers, both masks, both silks,
                                     both pastes, edge cuts) and Excellon drill, all
                                     measured from the drill/place origin; gerbers/ holds
                                     the same files unzipped
    BOM_JLCPCB.csv                   Comment, Designator, Footprint, LCSC: one line per
                                     LCSC code, only the parts JLCPCB places
    OWLternatingCurrent_cpl_jlcpcb_upload.csv   the one to upload: Designator, Mid X, Mid Y, Layer, Rotation, with
                                     JLCPCB's conventions: the bottom-side mirror and
                                     each part's correction (mfg/jlc_rotation.py, read in
                                     a preview or predicted from JLCPCB's own drawing),
                                     and each part moved to where JLCPCB's drawing has its
                                     origin (mfg/footprint_check.py's datum)
    OWLternatingCurrent_cpl_kicad_native.csv    KiCad's own positions and angles, for reference
    PLACEMENT_CHECKS.txt             what to look at in JLCPCB's placement preview
    FOOTPRINT_CHECK.txt              does each ordered part fit its copper?
    COST_ESTIMATE.md                 the order's price, fee by fee, and the parts' stock
    ORDER_SETTINGS.md                what to choose on JLCPCB's order page, in its order
    excluded_from_assembly.csv       what is on the panel but not placed, and why
    hand_solder_bom.csv              the parts soldered at home (HAND_SOLDER below), with their codes
    OWLternatingCurrent_assembly_top.pdf, _bottom.pdf   designators, from the fab layers

Gates: the release stops, and leaves mfg/release/ as it was, if any of these fails
(CLAUDE_PCB.md section 10):
  * every component of the netlist is a part JLCPCB places (an LCSC code), or one
    gen/parts.py says is not a part (coils are copper; test pads, antenna pads, holes);
  * every code is in gen/parts.py, the schematic's MPN is the table's, and JLCPCB's own
    description of the code carries every one of the part's `match` words, the
    schematic's value and package, and the MPN as JLCPCB's model;
  * every code is in stock for the order, attrition included;
  * the board: 4 copper layers, 1.6 mm, filled zones, DRC clean and newer than the
    board file, every netlist component on it with the same footprint, nothing coded on
    it that the netlist lacks, bottom footprints stored as KiCad's own flip stores them;
  * no ordered part wants a hole the board lacks (FOOTPRINT_CHECK.txt);
  * the CPL agrees with KiCad's own position export, and JLCPCB's drawing of each chip,
    placed as the CPL tells JLCPCB to place it, lands on our pads pin for pin, on both
    sides;
  * no output names a place on this machine (relative paths only).

Until gen/board.py has written the board file, only the board-free half runs: the BOM,
its checks and the parts' cost.  The script then exits with status 3 and says so.
--bom-only does the same while the board exists but is not finished.

Testing on another board (never a release): --pcb FILE --out DIR [--skip-drc]
[--accept-hole LCSC].
"""
import argparse
import collections
import csv
import datetime
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, os.path.join(ROOT, "tools"), os.path.join(ROOT, "gen")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import kienv                                  # noqa: E402
import jlc_api                                # noqa: E402
import jlc_rotation                           # noqa: E402
import footprint_check as FC                  # noqa: E402
import board_info as BI                       # noqa: E402
import layout as LAYOUT                       # noqa: E402
from parts import PARTS                       # noqa: E402
from sexp import parse, kids, kid, val        # noqa: E402

NAME = BI.NAME
COPPER = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
GERBER_LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
GERBER_FILES = ["F_Cu", "In1_Cu", "In2_Cu", "B_Cu", "F_Paste", "B_Paste", "F_Silkscreen", "B_Silkscreen",
                "F_Mask", "B_Mask", "Edge_Cuts"]
LIBDIR = os.path.join(ROOT, "hardware", "lib", "OWL.pretty")
# a place on one machine (CLAUDE_PCB.md section 2), spelt with character classes so that
# the repository's own path audit (git grep before every commit) does not flag this line
FORBIDDEN = re.compile(rb"/hom[e]/|/User[s]/|/tm[p]/|/mn[t]/|[A-Za-z]:\\{1,2}User[s]")
EXIT_NO_BOARD = 3

# ---------------------------------------------------------------------------------------
# JLCPCB's prices.  Parts come live from their API; everything else is their published
# list price on the date given, to be checked against the cart and updated here (the
# estimate says which numbers are which).
# ---------------------------------------------------------------------------------------
FEES = dict(
    # Standard PCBA (purple on 4 layers rules out Economic), from JLCPCB's assembly price
    # list, https://jlcpcb.com/help/article/pcb-assembly-price (updated 2026-09-09, read
    # 2026-10-07).  Prices move with the exchange rate.
    source="jlcpcb.com/help/article/pcb-assembly-price, updated 2026-09-09",
    setup={1: 25.56, 2: 51.12},       # one side, both sides
    stencil={1: 8.21, 2: 16.42},      # a stencil for each side; it stays at JLCPCB
    feeder=1.53,                      # Standard: EVERY distinct part needs a feeder loaded,
                                      # Basic and Extended alike (Economic: $3.07, Extended only)
    economic_extended=3.07,
    smt_joint=0.0016,                 # per SMD joint, 1-50,000 joints
    tht_joint=0.0164,                 # manual assembly, per through-hole joint
    tht_labour=3.58,                  # hand-soldering labour, per order
    designs=8.21,                     # "Panel (applicable when the number of panelized designs > 1)"
    packing=(0.50, 0.00003),          # $0.50 + $0.00003 per cm2 of board
    large=(650.0, 57.46),             # above 650 cm2 of board: a large-size fee
)
# The bare panels.  JLCPCB publishes no formula for a 4-layer board this size and its
# quote API needs a logged-in session, so this is a model with a range, and the cart's
# number replaces it once Jason has one: PCB_QUOTE = dict(date=..., price=...) for the
# order's `panels` panels.
PCB_QUOTE = None
GPIBRIDGE_CART = dict(date="2026-10-06", w=60.0, h=25.5, boards=5, price=24.80)   # 4 layers, ENIG, green
PCB_MODEL = dict(
    # JLCPCB's own 4-layer board charge, $70.6 per square metre (news, 2024-03-06; a 100-piece
    # order): the floor for the area part
    per_m2_low=70.6,
    # an assumption for a small order of large boards, five times that floor
    per_m2_high=350.0,
    # unpublished extras, as allowances: each further design on the panel, and 1 oz inner copper
    per_extra_design=(0.0, 6.0),
    inner_1oz=(0.0, 25.0),
)


# A HOLE finding (FOOTPRINT_CHECK.txt: JLCPCB's drawing of a part wants a hole where the
# board has no drill) stops the release.  Accept one here only after a person has put
# the maker's drawing beside JLCPCB's and decided the part seats as the board is drawn,
# and say who and why:  "C431540": "Jason, 2026-10-08: ..."
HOLE_ACCEPTED = {}


def draft():
    """Why this release is a DRAFT (CLAUDE_PCB.md section 10, gate 10), or None."""
    if getattr(BI, "FOR_NAME", None) is None:
        return ("gen/board_info.py FOR_NAME (the dedication printed on the back) is not decided yet, so the "
                "board carries a placeholder")
    return None


# the placement files (CLAUDE_PCB.md section 8): the name says which one goes to JLCPCB
CPL_UPLOAD = BI.NAME + "_cpl_jlcpcb_upload.csv"
CPL_NATIVE = BI.NAME + "_cpl_kicad_native.csv"


class Gate(Exception):
    """A release gate failed: say why, change nothing."""


# ---------------------------------------------------------------------------------------
# the netlist and the parts table
# ---------------------------------------------------------------------------------------
def read_netlist(path):
    doc = parse(open(path, encoding="utf-8").read())[0]
    comps = []
    for c in kids(kid(doc, "components"), "comp"):
        fields = {}
        fl = kid(c, "fields")
        for f in kids(fl, "field") if fl else []:
            fields[val(kid(f, "name"))] = val(f, 2) if len(f) > 2 and isinstance(f[2], tuple) else ""
        props = {val(kid(p, "name")): (val(kid(p, "value")) if kid(p, "value") else "") for p in kids(c, "property")}
        lib = kid(c, "libsource")
        fp = kid(c, "footprint")
        comps.append(dict(ref=val(kid(c, "ref")), value=val(kid(c, "value")),
                          fp=(val(fp) if fp else "").split(":")[-1], lcsc=fields.get("LCSC", "").strip(),
                          mpn=fields.get("MPN", "").strip(), sym=val(kid(lib, "part")) if lib else "",
                          sheet=props.get("Sheetname", ""), dnp="dnp" in props,
                          no_bom="exclude_from_bom" in props, no_board="exclude_from_board" in props))
    return comps


def refkey(ref):
    m = re.match(r"([A-Za-z_#]+)(\d*)", ref)
    return (m.group(1), int(m.group(2) or 0)) if m else (ref, 0)


def not_a_part(c):
    """The gen/parts.py entry saying that this code-less component is not a part JLCPCB
    places (a coil is copper; a test pad, antenna pad or hole is bare board), or None.
    Where several match (three kinds of coil on one net tie), the one whose value the
    schematic's value names."""
    keys = [k for k, p in PARTS.items() if not p.get("lcsc") and p["fp"].split(":")[-1] == c["fp"]
            and p["sym"].split(":")[-1] == c["sym"]]
    named = [k for k in keys if PARTS[k].get("value") and c["value"].split()[0] == PARTS[k]["value"]]
    return (named or keys or [None])[0]


# Parts JLCPCB does not fit, soldered at home after the panel is snapped apart: the tree's
# two right-angle headers would hang past its edges over the rail and over the perch,
# below the panel, and the perch's socket is a through-hole part on the second side.
# Three parts, 48 joints, ten minutes with an iron; bought loose (ORDER_LIST.md).
HAND_SOLDER = {"J101": "right-angle header off the tree's foot: its pins would hang over the panel's rail",
               "J102": "right-angle header off the tree's top: its pins would hang over the perch",
               "J201": "through-hole socket on the perch's underside: keeps the line's through-hole work on one side"}


def classify(comps):
    """placed: JLCPCB fits it (it has an LCSC code); hand: soldered at home (HAND_SOLDER);
    none: not a part; dnp: marked do-not-place or excluded from the BOM; nocode: a gate
    failure."""
    for c in comps:
        if c["dnp"] or c["no_bom"]:
            c["cls"], c["why"] = "dnp", "marked do-not-populate or excluded from the BOM in the schematic"
        elif c["ref"] in HAND_SOLDER:
            c["cls"], c["why"] = "hand", "hand-soldered at home: " + HAND_SOLDER[c["ref"]]
        elif c["lcsc"]:
            c["cls"], c["why"] = "placed", ""
        else:
            k = not_a_part(c)
            if k:
                c["cls"], c["why"] = "none", "%s: %s" % (k, PARTS[k].get("note") or "not a part")
            else:
                c["cls"], c["why"] = "nocode", ""
    return comps


def parts_for(code):
    return [(k, p) for k, p in PARTS.items() if p.get("lcsc") == code]


# ---------------------------------------------------------------------------------------
# JLCPCB's description of each code against the parts table and the schematic
# ---------------------------------------------------------------------------------------
PKG = re.compile(r"_(0201|0402|0603|0805|1206|1210|1812|2010|2512)_")
SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6}


def _qty(text, unit):
    """Every quantity in `text` with that unit (Ω, F, H, V), in SI."""
    out = set()
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([pnuµmkKM]?)" + unit + r"(?![a-zA-Z])", text):
        out.add(round(float(m.group(1)) * SI[m.group(2)], 15))
    return out


def schematic_value(c):
    """What the schematic's value says, as (kind, number in SI, extra words): '4.7u' on a
    capacitor is ('F', 4.7e-6, []); '22n C0G' adds 'C0G'; '10u 25V' adds 25 V; '0.5' on
    a resistor is 0.5 ohm.  None when the value is not a number (a part name)."""
    kind = {"R": "Ω", "C": "F", "L": "H"}.get(c["sym"][:1]) if c["sym"] in ("R", "C", "C_Polarized", "L") else None
    if not kind:
        return None
    words = c["value"].replace("µ", "u").split()
    m = re.match(r"^(\d+(?:\.\d+)?)([pnumkKM]?)(?:F|H|R|Ω)?$", words[0]) if words else None
    if not m:
        return None
    return kind, round(float(m.group(1)) * SI[m.group(2)], 15), words[1:]


def check_code(code, comps, p):
    """Problems with one code: JLCPCB's record `p` against gen/parts.py and the schematic."""
    bad = []
    desc = " ".join(str(p.get(k) or "") for k in ("describe", "componentModelEn", "componentSpecificationEn",
                                                  "componentTypeEn", "componentBrandEn"))
    low = desc.lower().replace("µ", "u")
    entries = parts_for(code)
    if not entries:
        return ["%s (%s) is in the schematic but not in gen/parts.py" % (code, ", ".join(c["ref"] for c in comps))]
    for key, e in entries:
        missing = [w for w in e["match"] if w.lower().replace("µ", "u") not in low]
        if missing:
            bad.append("%s %s: JLCPCB's description lacks %s: %s" % (code, key, missing, desc[:110]))
    mpns = {e["mpn"] for _, e in entries}
    model = re.sub(r"\s+", "", (p.get("componentModelEn") or "")).upper()
    for c in comps:
        if c["mpn"] not in mpns:
            bad.append("%s on %s: the schematic says MPN %r, gen/parts.py %s" % (code, c["ref"], c["mpn"], sorted(mpns)))
        if re.sub(r"\s+", "", c["mpn"]).upper() != model:
            bad.append("%s on %s: MPN %r but JLCPCB's model is %r" % (code, c["ref"], c["mpn"], p.get("componentModelEn")))
        fps = {e["fp"].split(":")[-1] for _, e in entries}
        if c["fp"] not in fps:
            bad.append("%s on %s: footprint %s, but gen/parts.py gives %s" % (code, c["ref"], c["fp"], sorted(fps)))
    seen = set()
    for c in comps:
        sv = schematic_value(c)
        if sv and (c["value"], c["fp"]) not in seen:
            seen.add((c["value"], c["fp"]))
            kind, number, extra = sv
            have = _qty(desc.replace("µ", "u"), kind)
            if kind in ("Ω", "F") and number not in have:
                bad.append("%s on %s: value %s, but JLCPCB's description says %s" % (code, c["ref"], c["value"], desc[:110]))
            elif kind == "H" and have and number not in have:
                bad.append("%s on %s: value %s, but JLCPCB's description says %s" % (code, c["ref"], c["value"], desc[:110]))
            for w in extra:
                if w.upper().endswith("V"):
                    if float(w[:-1]) not in _qty(desc, "V"):
                        bad.append("%s on %s: rated %s, JLCPCB says %s" % (code, c["ref"], w, desc[:110]))
                elif w.lower() not in low:
                    bad.append("%s on %s: %s not in JLCPCB's description %s" % (code, c["ref"], w, desc[:110]))
        m = PKG.search("_" + c["fp"] + "_") or PKG.search(c["fp"] + "_")
        if m and m.group(1) not in desc:
            bad.append("%s on %s: footprint %s, JLCPCB's package is %s" % (code, c["ref"], c["fp"],
                                                                         p.get("componentSpecificationEn")))
    return sorted(set(bad))


def parts_report(placed, assembled, refresh):
    """Ask JLCPCB about every code; return (rows by code, failures, notes)."""
    by = collections.OrderedDict()
    for c in sorted(placed, key=lambda c: refkey(c["ref"])):
        by.setdefault(c["lcsc"], []).append(c)
    rows, bad, thin = [], [], []
    for code, comps in by.items():
        try:
            p, ts = jlc_api.by_code(code, refresh=refresh)
        except Exception as e:                                    # noqa: BLE001
            bad.append("%s: JLCPCB's parts API did not answer (%s); run again when online" % (code, e))
            continue
        if not p:
            bad.append("%s (%s): JLCPCB does not know this code" % (code, ", ".join(c["ref"] for c in comps)))
            continue
        bad += check_code(code, comps, p)
        n = len(comps)
        need = n * assembled
        order = jlc_api.order_qty(p, need)
        stock = int(p.get("stockCount") or 0)
        if stock < order:
            bad.append("%s %s: %d in stock, the order needs %d (%d a panel x %d panels, plus %d attrition)"
                       % (code, p.get("componentModelEn"), stock, order, n, assembled, order - need))
        elif stock < max(10 * order, 100):
            thin.append(code)
        rows.append(dict(code=code, comps=comps, n=n, need=need, order=order, stock=stock, part=p, asked=ts,
                         lib=jlc_api.library_type(p), unit=jlc_api.unit_price(p, order),
                         model=p.get("componentModelEn") or "", pkg=p.get("componentSpecificationEn") or ""))
    return rows, bad, thin


def write_bom(rows, out):
    """JLCPCB's BOM: one line per LCSC code (two lines for one code make JLCPCB's
    'multiple lines matched to the same part', GPSDO P32)."""
    path = os.path.join(out, "BOM_JLCPCB.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for r in sorted(rows, key=lambda r: (-r["n"], r["code"])):
            values = list(dict.fromkeys(c["value"] for c in r["comps"]))
            fps = list(dict.fromkeys(c["fp"] for c in r["comps"]))
            w.writerow(["/".join(values), ",".join(c["ref"] for c in r["comps"]), fps[0], r["code"]])
    return path


def write_excluded(comps, extra, out):
    with open(os.path.join(out, "excluded_from_assembly.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Value", "Footprint", "Why JLCPCB does not place it"])
        for c in sorted((c for c in comps if c["cls"] in ("none", "dnp", "hand")), key=lambda c: refkey(c["ref"])):
            w.writerow([c["ref"], c["value"], c["fp"], c["why"]])
        for ref, value, fp, why in extra:
            w.writerow([ref, value, fp, why])
    with open(os.path.join(out, "hand_solder_bom.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Value", "Footprint", "LCSC (to order loose)", "MPN", "Why"])
        for c in sorted((c for c in comps if c["cls"] == "hand"), key=lambda c: refkey(c["ref"])):
            w.writerow([c["ref"], c["value"], c["fp"], c["lcsc"], c["mpn"], HAND_SOLDER[c["ref"]]])


# ---------------------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------------------
def library_pads(short):
    """The project library's own pads for a footprint: {number: [(x, y)]}, or None."""
    path = os.path.join(LIBDIR, short + ".kicad_mod")
    if not os.path.exists(path):
        return None
    node = FC.sexp(open(path, encoding="utf-8").read())[0]
    out = collections.defaultdict(list)
    for p in FC.kids(node, "pad"):
        at = FC.nums(FC.kid(p, "at"), 2)
        out[p[1]].append((at[0], at[1]))
    return out


def library_footprint(short):
    """A footprint from the project library, in the shape read_board_full gives the
    board's (for counting joints before the board exists), or None."""
    path = os.path.join(LIBDIR, short + ".kicad_mod")
    if not os.path.exists(path):
        return None
    node = FC.sexp(open(path, encoding="utf-8").read())[0]
    pads = [dict(number=p[1], type=p[2]) for p in FC.kids(node, "pad")]
    return dict(short=short, pads=pads)


def bottom_storage(fp):
    """How the board file stores a bottom-side footprint: 'kicad' (KiCad's own flip:
    pads mirrored top-to-bottom, y negated), 'x-mirrored' (left-to-right: the same part
    then carries an angle 180 from KiCad's), or None when the library cannot tell."""
    lib = library_pads(fp["short"])
    if not lib:
        return None

    def err(sx, sy):
        worst = 0.0
        for p in fp["pads"]:
            cands = lib.get(p["number"])
            if not cands:
                return None
            worst = max(worst, min(math.hypot(p["x"] - sx * x, p["y"] - sy * y) for x, y in cands))
        return worst
    e_k, e_x = err(1, -1), err(-1, 1)
    if e_k is not None and e_k < 0.005:
        return "kicad"
    if e_x is not None and e_x < 0.005:
        return "x-mirrored"
    return None


def board_parts(pcb, comps):
    """The board's footprints, checked against the netlist.  Returns (by ref, extra
    footprints, failures)."""
    B = FC.read_board_full(pcb)
    fps = {}
    bad, extra = [], []
    for fp in B["fps"]:
        if fp["ref"] in fps:
            bad.append("two footprints on the board are called %s" % fp["ref"])
        fps[fp["ref"]] = fp
    net = {c["ref"]: c for c in comps}
    for c in comps:
        fp = fps.get(c["ref"])
        if c["no_board"]:
            continue
        if fp is None:
            bad.append("%s (%s) is in the netlist but not on the board" % (c["ref"], c["value"]))
            continue
        if fp["short"] != c["fp"]:
            bad.append("%s: the board has footprint %s, the schematic %s" % (c["ref"], fp["short"], c["fp"]))
        if c["cls"] == "placed":
            code = fp["props"].get("LCSC", "")
            if code and code != c["lcsc"]:
                bad.append("%s: the board's LCSC field says %s, the schematic's %s" % (c["ref"], code, c["lcsc"]))
            if fp["dnp"]:
                bad.append("%s: do-not-populate on the board but not in the schematic" % c["ref"])
            if "exclude_from_pos_files" in fp["attrs"]:
                bad.append("%s: an ordered part marked 'exclude from position files' on the board" % c["ref"])
            if fp["layer"] == "B.Cu" and bottom_storage(fp) == "x-mirrored":
                bad.append("%s: stored on the bottom mirrored left-to-right, not as KiCad's own flip stores it "
                           "(FOOTPRINT.Flip or SetLayerAndFlip); every rotation rule here assumes KiCad's" % c["ref"])
    for ref, fp in sorted(fps.items(), key=lambda kv: refkey(kv[0])):
        if ref in net:
            continue
        if fp["props"].get("LCSC"):
            bad.append("%s (%s) carries LCSC code %s on the board but is not in the schematic"
                       % (ref, fp["short"], fp["props"]["LCSC"]))
            continue
        extra.append((ref, fp["value"], fp["short"], "a board feature, not a part (not in the schematic)"))
    return B, fps, extra, bad


def outline_box(B):
    pts = [p for e in B["edges"] for p in e]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def to_cpl(x, y, aux):
    """Board millimetres (y down) to the CPL's and the gerbers' frame: from the
    drill/place origin, y up."""
    ox, oy = aux or (0.0, 0.0)
    return x - ox, oy - y


def kicad_turn(x, y, deg):
    """KiCad's rotation of a footprint-local point: counter-clockwise on screen, y down."""
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def datum_shift(fp, fit):
    """Where JLCPCB's drawing has its origin, relative to ours, in board mm (y down).
    JLCPCB puts THEIR origin where the CPL says (every USB-C so far: 1.3-1.6 mm off).
    footprint_check.py's fit says where it sits in our footprint as the file stores it
    (for the bottom side, already mirrored), so KiCad's own rotation carries it onto the
    board on either side.  Only past DATUM_OK and when the fit is good."""
    if not fit or math.hypot(fit["dx"], fit["dy"]) <= FC.DATUM_OK or fit["worst"] > FC.LAND_OK:
        return 0.0, 0.0
    return kicad_turn(fit["dx"], fit["dy"], fp["at"][2])


def predictions(placed, fps, fits):
    """Per (code, footprint): the correction JLCPCB's own drawing predicts, from the
    quarter turn that laid it on our footprint by pin number (right on every part of
    GPiBridge's preview).  A fit at d degrees predicts 360 - d, on either side: KiCad
    stores a bottom footprint's pads mirrored top-to-bottom, and footprint_check.py
    mirrors JLCPCB's drawing the same way before fitting, so the turn comes out as on
    the top.  Two-pad parts get none: their polarity is a mark, not a pin number."""
    out = {}
    for c in placed:
        fp = fps[c["ref"]]
        key = (c["lcsc"], fp["short"])
        if key in out:
            continue
        cands = []
        for bottom in (False, True):
            fit = fits.get((c["lcsc"], bottom, fp["short"]))
            if fit and fit.get("how") == "by name" and fit.get("n", 0) >= 3 and fit["worst"] <= FC.LAND_WARN:
                cands.append(((360 - fit["deg"]) % 360, "bottom" if bottom else "top", fit))
        if not cands:
            some = fits.get((c["lcsc"], False, fp["short"])) or fits.get((c["lcsc"], True, fp["short"]))
            out[key] = (None, "two pads: polarity is a mark, not a pin number" if some and some.get("n", 0) < 3
                        else "no fit by pin number")
        elif len({cd[0] for cd in cands}) > 1:
            out[key] = (None, "the top-side fit says %d and the bottom-side fit %d: they must agree"
                        % (cands[0][0], cands[1][0]))
        else:
            pred, side, fit = cands[0]
            out[key] = (pred, "JLCPCB's drawing turned %d to lie on ours (%s side, %d pads by number, worst %.2f mm)%s"
                        % (fit["deg"], side, fit["n"], fit["worst"],
                           "; the other side's fit agrees" if len(cands) == 2 else ""))
    return out


def jlc_pads_on_board(lp, row, aux):
    """Where JLCPCB puts the pads of their drawing `lp` for one CPL row, in board mm.
    Top: their drawing, turned counter-clockwise by the CPL's rotation.  Bottom (their
    convention, from the Icepi Zero's preview, jlc_rotation.BOTTOM_FLIP): the board seen
    from below, turned over left-to-right; the part as drawn, turned counter-clockwise
    in that view, then seen through the board from the top (x mirrored)."""
    ox, oy = aux or (0.0, 0.0)
    X, Y = row["X"] + ox, oy - row["Y"]
    out = []
    for p in lp["pads"]:
        u, v = kicad_turn(p["x"], p["y"], row["R"])
        out.append((p["number"], X + (u if row["side"] == "top" else -u), Y + v))
    return out


def simulate(placed, fps, fits, cpl, aux):
    """JLCPCB's drawing of each chip, placed as the CPL says, must land on our pads pin
    for pin.  This is the bottom-side check that needs no preview: it exercises the
    mirror rule, the corrections and the datum shift on both sides at once."""
    bad, ok = [], []
    for c in placed:
        fp = fps[c["ref"]]
        fit = fits.get((c["lcsc"], fp["layer"].startswith("B."), fp["short"]))
        if not fit or fit.get("how") != "by name" or fit.get("n", 0) < 3 or fit["worst"] > FC.LAND_WARN:
            continue
        lp, _ = FC.land_pattern(c["lcsc"])
        ours = collections.defaultdict(list)
        for p in fp["pads"]:
            ours[p["number"]].append(FC.to_board(p["x"], p["y"], fp["at"], fp["layer"]))
        worst, at = 0.0, ""
        for num, x, y in jlc_pads_on_board(lp, cpl[c["ref"]], aux):
            if num not in ours:
                continue
            d = min(math.hypot(x - a, y - b) for a, b in ours[num])
            if d > worst:
                worst, at = d, num
        # the fit's own residual, plus a datum offset too small to move the part for
        unmoved = 0.0 if datum_shift(fp, fit) != (0.0, 0.0) else math.hypot(fit["dx"], fit["dy"])
        if worst > fit["worst"] + unmoved + 0.02:
            bad.append("%s (%s, %s side): JLCPCB's drawing placed by the CPL misses our pad %s by %.2f mm"
                       % (c["ref"], c["lcsc"], cpl[c["ref"]]["side"], at, worst))
        else:
            ok.append(c["ref"])
    return bad, ok


def pos_export_check(pcb, cpl_native, scratch):
    """KiCad's own position export must agree with what this script read."""
    pos = os.path.join(scratch, "pos.csv")
    kienv.run_cli(["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                   "--use-drill-file-origin", "-o", pos, pcb])
    bad, seen = [], set()
    for r in csv.DictReader(open(pos, encoding="utf-8")):
        ref = r["Ref"]
        if ref not in cpl_native:
            continue
        seen.add(ref)
        n = cpl_native[ref]
        if abs(float(r["PosX"]) - n["X"]) > 0.002 or abs(float(r["PosY"]) - n["Y"]) > 0.002 \
                or abs((float(r["Rot"]) - n["R"] + 180) % 360 - 180) > 0.01 or r["Side"] != n["side"]:
            bad.append("%s: KiCad's position file says (%s, %s) %s %s, this script (%.3f, %.3f) %g %s"
                       % (ref, r["PosX"], r["PosY"], r["Rot"], r["Side"], n["X"], n["Y"], n["R"], n["side"]))
    for ref in sorted(set(cpl_native) - seen, key=refkey):
        bad.append("%s: missing from KiCad's position file (excluded from position files?)" % ref)
    return bad


def tht_joints(fp):
    """(SMD pads, through-hole joints) of a footprint.  A plated hole numbered like an
    SMD pad is a via in that pad (an exposed pad's thermal vias), not a lead."""
    smd = {p["number"] for p in fp["pads"] if p["type"] == "smd"}
    return (sum(1 for p in fp["pads"] if p["type"] == "smd" and p["number"]),
            sum(1 for p in fp["pads"] if p["type"] == "thru_hole" and p["number"] not in smd and p["number"]))


def features(B, fps, box, parts=()):
    """What the panel carries for the assembler, against JLCPCB's rules for a customer's
    panel (pcb-capabilities and the edge-rail and tooling-hole articles, 2026-09-09):
    rails of at least 5 mm, 1 mm fiducials with a 2 mm mask opening, three or four, at
    least 3.35 mm from the edge (3.85 suggested); tooling holes of 2 mm (1.152 mm in
    the Economic article); mouse bites 0.5-0.8 mm, 0.2-0.3 mm apart; 2 mm between boards.
    And the order-number text, which JLCPCB now asks NOT to add (May 2026)."""
    x0, y0, x1, y1 = box
    rail = LAYOUT.RAIL

    def edge(x, y):
        return min(x - x0, x1 - x, y - y0, y1 - y)
    fid = []
    for fp in sorted(fps.values(), key=lambda f: refkey(f["ref"])):
        if "fiducial" in fp["short"].lower() or re.match(r"^FID\d+$", fp["ref"]):
            p = fp["pads"][0] if fp["pads"] else dict(w=0.0, mask=None)
            opening = p["w"] + 2 * (p["mask"] if p.get("mask") is not None else 0.0)
            fid.append(dict(ref=fp["ref"], layer=fp["layer"], x=fp["at"][0], y=fp["at"][1], d=p["w"], opening=opening,
                            edge=edge(fp["at"][0], fp["at"][1])))
    npth = []                                   # the panel's own holes: not a part's locating posts
    for fp in sorted(fps.values(), key=lambda f: refkey(f["ref"])):
        if fp["ref"] in parts:
            continue
        for p in fp["pads"]:
            if p["type"] == "np_thru_hole":
                x, y = FC.to_board(p["x"], p["y"], fp["at"], fp["layer"])
                npth.append((fp["ref"], x, y, p["drill"]))
    tooling = [h for h in npth if (abs(h[3] - 1.152) < 0.06 or abs(h[3] - 2.0) < 0.06) and edge(h[1], h[2]) <= rail]
    bites = [h for h in npth if h[3] <= 0.85]
    jlc = [t for t in B["texts"] if "JLCJLCJLCJLC" in t[0]]
    notes = []
    good_fid = [f for f in fid if abs(f["d"] - 1.0) < 0.05 and f["edge"] >= 3.35 - 0.01 and f["edge"] <= rail + 0.01]
    if fid and len(good_fid) < len(fid):
        notes.append("fiducials not as JLCPCB asks (1 mm copper, 2 mm mask opening, on the rail, at least 3.35 mm "
                     "from the panel's edge): " + ", ".join("%s %.2f mm (mask opening %.2f mm), %.2f mm from the edge"
                                                          % (f["ref"], f["d"], f["opening"], f["edge"])
                                                          for f in fid if f not in good_fid))
    if bites:
        sizes = sorted({round(h[3], 2) for h in bites})
        if min(sizes) < 0.5 - 0.01 or max(sizes) > 0.8 + 0.01:
            notes.append("mouse-bite holes of %s mm (JLCPCB: 0.5-0.8 mm)" % sizes)
    if jlc:
        notes.append("the silkscreen carries \"JLCJLCJLCJLC\" (%s): JLCPCB stopped printing order numbers in May 2026 "
                     "and now asks that it NOT be added; it would be printed as it stands" %
                     ", ".join("%s at %.1f, %.1f" % (t[1], t[2], t[3]) for t in jlc))
    return dict(fiducials=fid, fid_ok=good_fid, tooling=tooling, bites=bites, jlc_text=jlc, notes=notes)


# ---------------------------------------------------------------------------------------
# outputs from the board
# ---------------------------------------------------------------------------------------
def export_gerbers(pcb, out):
    gerb = os.path.join(out, "gerbers")
    os.makedirs(gerb)
    kienv.run_cli(["pcb", "export", "gerbers", "-o", gerb, "--layers", GERBER_LAYERS, "--no-protel-ext",
                   "--subtract-soldermask", "--use-drill-file-origin", pcb])
    kienv.run_cli(["pcb", "export", "drill", "-o", gerb + os.sep, "--format", "excellon", "--drill-origin", "plot",
                   "--excellon-units", "mm", "--excellon-zeros-format", "decimal", "--excellon-separate-th",
                   "--generate-map", "--map-format", "gerberx2", pcb])
    files = sorted(os.listdir(gerb))
    stem = os.path.splitext(os.path.basename(pcb))[0]
    missing = [g for g in GERBER_FILES if "%s-%s.gbr" % (stem, g) not in files]
    missing += [d for d in ("PTH.drl",) if "%s-%s" % (stem, d) not in files]
    if missing:
        raise Gate("gerber export is missing %s" % missing)
    zpath = os.path.join(out, NAME + "_gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in files:
            z.write(os.path.join(gerb, fn), fn)
    for side, layers, mirror in (("top", "F.Fab,F.Silkscreen,Edge.Cuts", False),
                                 ("bottom", "B.Fab,B.Silkscreen,Edge.Cuts", True)):
        p = os.path.join(out, "%s_assembly_%s.pdf" % (NAME, side))
        kienv.run_cli(["pcb", "export", "pdf", "-o", p, "--layers", layers, "--mode-single", "--exclude-value"]
                      + (["--mirror"] if mirror else []) + [pcb])
    return zpath, files


def gerber_box(path):
    """The extent of a gerber's coordinates (Edge.Cuts: the panel's outline), in mm."""
    xs, ys = [], []
    scale = 1e-6
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"%FSLAX(\d)(\d)Y(\d)(\d)\*%", line)
        if m:
            scale = 10.0 ** -int(m.group(2))
        for m in re.finditer(r"X(-?\d+)Y(-?\d+)", line):
            xs.append(int(m.group(1)) * scale)
            ys.append(int(m.group(2)) * scale)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def write_cpl(rows, out):
    for name, key in ((CPL_UPLOAD, "jlc"), (CPL_NATIVE, "native")):
        with open(os.path.join(out, name), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            for ref in sorted(rows, key=refkey):
                r = rows[ref][key]
                w.writerow([ref, "%.3fmm" % r["X"], "%.3fmm" % r["Y"], r["side"].capitalize(), "%g" % r["R"]])


LOOK = {
    # what to look for in the preview, by footprint (pad 1 and the library's own marks)
    "RP2350A_QFN-60_7x7mm_P0.4mm_RPi": "pin 1 by the silk dot; JLCPCB's dot on it",
    "VQFN-46-1EP_5x6mm_P0.4mm_EP2.8x3.8mm": "pin 1 by the silk mark; JLCPCB's dot on it",
    "VQFN-46-1EP_5x6mm_P0.4mm_EP2.8x3.8mm_ThermalVias": "pin 1 by the silk mark; JLCPCB's dot on it",
    "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.55x2.46mm_TI_PWP0016J": "pin 1 by the silk mark; JLCPCB's dot on it",
    "SOIC-8_3.9x4.9mm_P1.27mm": "pin 1 by the silk mark (the bevelled edge)",
    "TSSOP-16_4.4x5mm_P0.65mm": "pin 1 by the silk mark",
    "MSOP-8_3x3mm_P0.65mm": "pin 1 by the silk mark",
    "SOT-23": "pin 1 by the silk mark: one pin alone on one side, two on the other",
    "SOT-23-5": "pin 1 by the silk mark: three pins on one side, two on the other",
    "SOT-23-6": "pin 1 by the silk mark",
    "Bosch_LGA-14_3x2.5mm_P0.5mm": "pin 1 by the silk mark",
    "Lite-On_LTR-303ALS-01": "pin 1 by the silk mark",
    "Crystal_SMD_3225-4Pin_3.2x2.5mm": "pin 1 by the silk mark (either half turn works electrically)",
    "LED_0603_1608Metric": "the cathode (pad 1) at the silk bracket's end; JLCPCB marks the cathode",
    "LED_Everlight-SMD3528_3.5x2.8mm_67-21ST": "the cathode (pad 1) by the silk mark; the 3528's notched corner",
    "LED_LiteOn_LTST-S270_SideView": "the cathode (pad 1); the lens must face the board's edge",
    "LED_RGB_5050-6": "pin 1 by the silk mark (the notched corner)",
    "D_SOD-123": "the cathode bar at pad 1",
    "D_SMB": "the cathode bar at pad 1",
    "CP_Elec_10x12.6": "the + (pad 1) by the silk +; the can's black stripe is the minus side",
    "L_Abracon_AOTA-B201610_RPi": "the white dot at pad 1 (+1V1), as on Raspberry Pi's boards",
    "JST_SH_BM03B-SRSS-TB_1x03-1MP_P1.00mm_Vertical": "the opening faces the board's edge; pin 1 by the silk step",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "the receptacle's mouth flush with the board's edge, on its pads",
    "BarrelJack_XKB_DC-005-5A-2.0_Horizontal": "the plug's opening at the board's edge (keyed by its pins)",
    "PinSocket_2x08_P2.54mm_Vertical": "pin 1 by the silk mark (square pad); keyed by nothing but the silk",
    "PinHeader_2x08_P2.54mm_Horizontal": "the pins point off the board's edge; pin 1 at the square pad",
    "Speaker_GSPK2307P_D23mm_P10mm": "on its two pins; the + mark at pad 1 (either way sounds the same)",
    "SW_SPDT_Shouhan_MSK12C02": "the lever over the board's edge, on its locating holes",
}


def placement_checks(out, placed, fps, cpl, preds, moved, sim_ok, sim_bad, aux, B, feat):
    L = ["%s rev %s: PLACEMENT CHECKS for JLCPCB's preview (%s)" % (BI.TITLE, BI.REV, datetime.date.today()), ""]
    L += ["The panel is assembled on BOTH sides.  JLCPCB's preview shows each side; check both.", ""]
    if moved:
        L += ["MOVED in " + CPL_UPLOAD + " to where JLCPCB's library puts the part's origin (their drawing's",
              "zero is not KiCad's; FOOTPRINT_CHECK.txt's 'datum').  In the preview each should sit squarely",
              "on its pads.  If one sits off them by about the same distance the other way, their library has",
              "changed: say so, and it goes into the code.", ""]
        for ref, dx, dy in moved:
            L.append("  %-6s %-10s %-6s %-44s moved (%+.3f, %+.3f) mm (x right, y up)"
                     % (ref, fps[ref]["props"].get("LCSC", ""), cpl[ref]["jlc"]["side"], fps[ref]["short"][:44], dx, dy))
        L.append("")
    L += ["ROTATIONS.  " + CPL_UPLOAD + "'s rotation is KiCad's angle, mirrored for the bottom side",
          "(180 - angle: JLCPCB looks at the bottom from below, the board turned over left-to-right;",
          "jlc_rotation.BOTTOM_FLIP, read on ten bottom-side parts of the Icepi Zero), plus each part's",
          "correction: read in an earlier preview where somebody has looked, else PREDICTED from JLCPCB's",
          "own drawing of the part turned until its pads lie on ours by pin number.  Every part below that",
          "nobody has yet seen right is listed with its prediction: check its pin 1 or polarity mark",
          "(JLCPCB's dot) against the board, write down any that is wrong and by how much, and it goes",
          "into mfg/jlc_rotation.py.", ""]
    L += ["Placed as the CPL says, JLCPCB's own drawing lands pin for pin on our pads for %d chips on"
          % len(sim_ok), "both sides (make_release.py's simulation of their placement)%s." %
          (": " + "; ".join(sim_bad) if sim_bad else ""), ""]
    groups = collections.OrderedDict()
    for c in sorted(placed, key=lambda c: (c["lcsc"], refkey(c["ref"]))):
        groups.setdefault((c["lcsc"], fps[c["ref"]]["short"]), []).append(c)
    unread, read, na = [], [], []
    for (code, short), cs in groups.items():
        corr, conf, why = jlc_rotation.correction(short, code)
        if short in jlc_rotation.ROTATION_NA:
            na.append(short)
        elif jlc_rotation.checked(short, code):
            read.append((code, short, cs, corr, conf, why))
        else:
            unread.append((code, short, cs, corr, conf, why))
    L.append("NOT YET SEEN RIGHT in a preview (%d part numbers, %d placements):"
             % (len(unread), sum(len(g[2]) for g in unread)))
    for code, short, cs, corr, conf, why in unread:
        pred, pwhy = preds.get((code, short), (None, ""))
        tops = [c["ref"] for c in cs if cpl[c["ref"]]["jlc"]["side"] == "top"]
        bots = [c["ref"] for c in cs if cpl[c["ref"]]["jlc"]["side"] == "bottom"]
        L.append("  %-10s %-26s %s" % (code, "/".join(dict.fromkeys(c["value"] for c in cs))[:26], short))
        if tops:
            L.append("      top:    " + " ".join(tops))
        if bots:
            L.append("      bottom: " + " ".join(bots))
        if conf != "none":
            L.append("      correction %d (%s): %s" % (corr, conf, why))
            if pred is not None and pred != corr:
                L.append("      (JLCPCB's drawing by pin number would say %d: %s)" % (pred, pwhy))
        elif pred is not None:
            L.append("      correction %d, predicted: %s" % (pred, pwhy))
        else:
            L.append("      correction 0, NOT PREDICTED (%s): look at it hardest" % pwhy)
        if short in LOOK:
            L.append("      look for: %s" % LOOK[short])
    L += ["", "READ RIGHT in an earlier preview (the same part number, this footprint or its twin):"]
    for code, short, cs, corr, conf, why in read:
        pred, _ = preds.get((code, short), (None, ""))
        agree = "" if pred is None else ("; JLCPCB's drawing agrees" if pred == corr else
                                          "; JLCPCB's drawing says %d: LOOK" % pred)
        L.append("  %-10s %-40s correction %3d (%s)%s: %s" % (code, short[:40], corr, conf, agree,
                                                             " ".join(c["ref"] for c in cs)))
    L += ["", "No orientation to get wrong (two pads, no polarity): " + ", ".join(sorted(set(na))), ""]
    bottom_tall = [c["ref"] for c in placed if cpl[c["ref"]]["jlc"]["side"] == "bottom"
                   and fps[c["ref"]]["short"] in ("CP_Elec_10x12.6", "L_Changjiang_FXL0630", "Speaker_GSPK2307P_D23mm_P10mm",
                                                  "BarrelJack_XKB_DC-005-5A-2.0_Horizontal", "Fuse_2920_7451Metric")]
    if bottom_tall:
        L += ["HEAVY PARTS ON THE BOTTOM (reflowed first, then upside down through the top's reflow; JLCPCB",
              "may glue them): " + " ".join(sorted(bottom_tall, key=refkey)), ""]
    tht = [c["ref"] for c in placed if tht_joints(fps[c["ref"]])[1]]
    if tht:
        L += ["THROUGH-HOLE parts JLCPCB fits by hand (they go in one way by their pins, but look):"]
        for ref in sorted(tht, key=refkey):
            fp = fps[ref]
            L.append("  %-6s %-6s %-46s %d joints%s" % (ref, cpl[ref]["jlc"]["side"], fp["short"][:46], tht_joints(fp)[1],
                                                       ("; " + LOOK[fp["short"]]) if fp["short"] in LOOK else ""))
        L.append("")
    L += ["FRAME: Mid X and Mid Y are millimetres from the drill/place origin %s, y up, the same frame as"
          % ("(%.3f, %.3f) on KiCad's page" % aux if aux else "(not set: KiCad's page origin)"),
          "the gerbers and the drill file.  Bottom-side X is NOT negated (JLCPCB reads both sides from the",
          "top).  KiCad's own position export agrees with every row of " + CPL_NATIVE + ".", ""]
    if feat["fiducials"]:
        L.append("Fiducials: %s." % ", ".join("%s (%s, %.1f mm from the edge)" % (f["ref"], f["layer"], f["edge"])
                                              for f in feat["fiducials"]))
    open(os.path.join(out, "PLACEMENT_CHECKS.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return L


# ---------------------------------------------------------------------------------------
# cost and order settings
# ---------------------------------------------------------------------------------------
def money(x):
    return "$%.2f" % x


def pcb_price(w, h, panels, designs=6):
    """The bare panels: the cart's number when we have one, else (estimate, low, high, how)."""
    if PCB_QUOTE:
        p = PCB_QUOTE["price"]
        return p, p, p, "JLCPCB's cart, %s" % PCB_QUOTE["date"]
    g, M = GPIBRIDGE_CART, PCB_MODEL
    area = w * h / 100.0 * panels                                    # cm2
    fixed = g["price"] - M["per_m2_low"] * g["w"] * g["h"] / 1e6 * g["boards"]   # engineering, ENIG set-up
    lo = fixed + M["per_m2_low"] * area / 1e4 + (designs - 1) * M["per_extra_design"][0] + M["inner_1oz"][0]
    hi = fixed + M["per_m2_high"] * area / 1e4 + (designs - 1) * M["per_extra_design"][1] + M["inner_1oz"][1]
    how = ("ESTIMATE, $%.0f-%.0f: GPiBridge's cart (%s, 4 layers, ENIG: $%.2f for 5 boards of %.0f x %.1f mm) "
           "for the fixed part, plus %.0f cm2 at $%.1f-%.0f per m2 (JLCPCB's published 4-layer board charge, and "
           "five times it for a small order), plus up to $%.0f for each of the %d further designs and $%.0f for "
           "1 oz inner copper (neither is published); purple costs the same as green (JLCPCB)"
           % (lo, hi, g["date"], g["price"], g["w"], g["h"], area, M["per_m2_low"], M["per_m2_high"],
              M["per_extra_design"][1], designs - 1, M["inner_1oz"][1]))
    return (lo + hi) / 2, lo, hi, how


def cost_md(out, rows, fps, panels, assembled, dims, have_board, thin, comps):
    """COST_ESTIMATE.md: the order, fee by fee, and every part's price and stock."""
    F = FEES
    ext = sorted((r for r in rows if r["lib"] == "Extended"), key=lambda r: r["code"])
    pref = [r for r in rows if r["lib"] == "Preferred"]
    basic = [r for r in rows if r["lib"] == "Basic"]
    parts = sum(r["unit"] * r["order"] for r in rows)
    w, h = dims
    designs = len({c["sheet"] for c in comps if c["cls"] == "placed"}) or 1
    if have_board:
        side_of = {c["ref"]: ("bottom" if fps[c["ref"]]["layer"].startswith("B.") else "top")
                   for r in rows for c in r["comps"]}
        sides = set(side_of.values())
        both = [r for r in rows if len({side_of[c["ref"]] for c in r["comps"]}) == 2]
        smd = sum(tht_joints(fps[c["ref"]])[0] for r in rows for c in r["comps"])
        tht = sum(tht_joints(fps[c["ref"]])[1] for r in rows for c in r["comps"])
    else:                                       # before the board: the library's footprints, both sides planned
        sides, both, smd, tht = {"top", "bottom"}, [], 0, 0
        for r in rows:
            for c in r["comps"]:
                lf = library_footprint(c["fp"])
                if lf:
                    s_, t_ = tht_joints(lf)
                    smd, tht = smd + s_, tht + t_
    n = len(sides)
    pcb, pcb_lo, pcb_hi, pcb_how = pcb_price(w, h, panels, designs)
    area = w * h / 100.0
    L_ = dict(setup=F["setup"][n], stencil=F["stencil"][n], feeder=F["feeder"] * len(rows),
              joints=F["smt_joint"] * smd * assembled,
              hand=(F["tht_labour"] + F["tht_joint"] * tht * assembled) if tht else 0.0,
              designs=F["designs"] if designs > 1 else 0.0,
              packing=F["packing"][0] + F["packing"][1] * area * assembled,
              large=F["large"][1] if area > F["large"][0] else 0.0)
    asm = sum(L_.values())
    total = pcb + asm + parts
    L = ["# %s rev %s: cost estimate%s" % (BI.TITLE, BI.REV, " (DRAFT)" if draft() else ""), "",
         "Written by `mfg/make_release.py` on %s.  Parts: JLCPCB's live prices and stock (their parts API, asked at "
         "the times in the table).  Assembly fees: JLCPCB's published list (%s).  The bare panels: %s."
         % (datetime.date.today(), F["source"], "the cart's price" if PCB_QUOTE else "an estimate with a range"), "",
         "**The order:** %d bare panels of %.1f x %.1f mm (%.0f cm2; all %d boards on each), 4 layers, 1.6 mm, purple, "
         "ENIG, 1 oz inner copper; **%d of them assembled, %s** (Standard PCBA)."
         % (panels, w, h, area, designs, assembled, "on both sides" if n == 2 else "on one side"), ""]
    if not have_board:
        L += ["**No released board yet:** the panel's size is gen/layout.py's plan, and the joints are counted from "
              "the library's footprints of the netlist's parts.", ""]
    L += ["| item | how | cost |", "|---|---|--:|",
          "| bare panels | %s | %s |" % (pcb_how, money(pcb)),
          "| assembly setup | Standard PCBA, %s | %s |" % ("both sides" if n == 2 else "one side", money(L_["setup"])),
          "| stencils | %s | %s |" % ("one for each side" if n == 2 else "one", money(L_["stencil"])),
          "| feeder loading | %d distinct parts (BOM lines) x %s: Standard PCBA loads a feeder for every part, Basic "
          "and Extended alike | %s |" % (len(rows), money(F["feeder"]), money(L_["feeder"])),
          "| SMD joints | %d pads a panel x %d panels x $%.4f | %s |" % (smd, assembled, F["smt_joint"], money(L_["joints"])),
          "| through-hole | %s labour an order + %d joints a panel x %d x $%.4f | %s |"
          % (money(F["tht_labour"]), tht, assembled, F["tht_joint"], money(L_["hand"])),
          "| panel of %d designs | JLCPCB's fee for a panel with more than one design | %s |" % (designs, money(L_["designs"])),
          "| packing | $0.50 + $0.00003 per cm2 | %s |" % money(L_["packing"])]
    if L_["large"]:
        L.append("| large board | over %.0f cm2 | %s |" % (F["large"][0], money(L_["large"])))
    L += ["| parts | %d placements a panel on %d BOM lines, for %d panels with JLCPCB's attrition, at the price "
          "break for that quantity | %s |" % (sum(r["n"] for r in rows), len(rows), assembled, money(parts)),
          "| **total before shipping and duty** | | **%s** |" % money(total),
          "| an assembled panel | the total over %d | %s |" % (assembled, money(total / assembled)), "",
          "The range on the bare panels moves the total from %s to %s.  US duty, collected by JLCPCB under DDP at "
          "35 %% of the PCBs and the assembly (their tariff FAQ, 2026-09-09), adds about %s; shipping (UPS Express "
          "Saver DDP to California) is shown at checkout."
          % (money(total - pcb + pcb_lo), money(total - pcb + pcb_hi), money(0.35 * total)), ""]
    L += ["## Per-part fees: Basic, Preferred, Extended", "",
          "| library | distinct parts | placements a panel |", "|---|--:|--:|",
          "| Basic | %d | %d |" % (len(basic), sum(r["n"] for r in basic)),
          "| Preferred | %d | %d |" % (len(pref), sum(r["n"] for r in pref)),
          "| **Extended** | **%d** | %d |" % (len(ext), sum(r["n"] for r in ext)), "",
          "On Standard PCBA every distinct part costs the same %s to load, Basic or Extended (Preferred parts are "
          "exempt only on Economic): %s.  On Economic PCBA, which purple 4-layer boards cannot have, the %d Extended "
          "parts alone would cost %s and Basic and Preferred nothing.%s"
          % (money(F["feeder"]), money(L_["feeder"]), len(ext), money(F["economic_extended"] * len(ext)),
             ("  %d part(s) sit on both sides (%s); if JLCPCB loads them once a side, add %s."
              % (len(both), ", ".join(r["code"] for r in both), money(F["feeder"] * len(both)))) if both else ""), "",
          "The %d distinct Extended parts: %s." % (len(ext), ", ".join("%s (%s)" % (r["code"], r["model"]) for r in ext)), ""]
    flags = []
    if max(w, h) > 250.0:
        flags.append("**The panel is %.1f mm long; JLCPCB recommends at most 250 x 250 mm for an assembled panel** "
                     "(pcb-assembly-capabilities: \"our system allows dimensions beyond the recommended size limits. "
                     "Customers should evaluate the associated manufacturing risks\"): warping in two reflows, and "
                     "perhaps an engineering question" % max(w, h))
    if not PCB_QUOTE:
        flags.append("The bare panels are the least certain line (%s to %s): read the price off JLCPCB's cart and put "
                     "it in `PCB_QUOTE` in `mfg/make_release.py`" % (money(pcb_lo), money(pcb_hi)))
    flags.append("Feeder loading is the largest assembly fee: %s for %d distinct parts.  Each part dropped or merged "
                 "into another value saves %s" % (money(L_["feeder"]), len(rows), money(F["feeder"])))
    for r in sorted(rows, key=lambda r: -r["unit"] * r["order"])[:6]:
        if r["unit"] * r["order"] >= 2.0:
            flags.append("**%s %s** costs %s for the order (%d x %s)"
                         % (r["code"], r["model"], money(r["unit"] * r["order"]), r["order"], money(r["unit"])))
    for code in thin:
        r = next(r for r in rows if r["code"] == code)
        flags.append("**%s %s**: %d in stock against %d for this order: order soon, or it may run out"
                     % (code, r["model"], r["stock"], r["order"]))
    flags.append("Not in the total: baking the moisture-sensitive parts before assembly (JLCPCB recommends it for "
                 "MSL 3 and up, as the LGA-14 accelerometer is; about $7.50), shipping, and duty")
    L += ["## What to look at", ""] + ["- " + f for f in flags] + [""]
    L += ["## Parts (%d BOM lines)" % len(rows), "",
          "| LCSC | part | per panel | ordered | library | unit | line | stock | left after | asked |",
          "|---|---|--:|--:|---|--:|--:|--:|--:|---|"]
    for r in sorted(rows, key=lambda r: (-r["unit"] * r["order"], r["code"])):
        L.append("| %s | %s (%s) | %d | %d | %s | $%.4f | %s | %s | %s | %s |"
                 % (r["code"], r["model"], "/".join(dict.fromkeys(c["value"] for c in r["comps"]))[:24], r["n"],
                    r["order"], r["lib"], r["unit"], money(r["unit"] * r["order"]), "{:,}".format(r["stock"]),
                    "{:,}".format(r["stock"] - r["order"]), r["asked"][:16].replace("T", " ")))
    L += ["", "\"ordered\" is what JLCPCB charges for: the placements on %d panels plus its attrition (`lossNumber`) "
          "or minimum purchase, at the price break for that quantity.  A Preferred part is an Extended part JLCPCB "
          "keeps on its machines." % assembled, ""]
    open(os.path.join(out, "COST_ESTIMATE.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return dict(total=total, pcb=pcb, pcb_lo=pcb_lo, pcb_hi=pcb_hi, parts=parts, ext=ext, fees=L_, smd=smd,
                tht=tht, sides=sides, designs=designs, asm=asm)


def order_md(out, have_board, dims, panels, assembled, feat, B, cost, checks, why_not=""):
    """ORDER_SETTINGS.md: what to choose on JLCPCB's order page, in the order it asks.

    The order and the names are JLCPCB's order page as far as it can be read without a
    browser (2026-10-07: the page's own skeleton, a 2024 printout of it, and 4-layer
    orders written up by others), with the help-centre articles (2026-09-09) for what
    each option does."""
    w, h = dims
    via = min(B["vias"], key=lambda v: v[3]) if B and B["vias"] else None
    tw = min(B["widths"]) if B and B["widths"] else None
    fid = feat.get("fid_ok", [])
    tool = feat.get("tooling", [])
    designs = cost["designs"]
    if via:
        d = via[3]
        via_opt = ("0.3mm/(0.4/0.45mm)" if d >= 0.3 - 1e-6 else "0.25mm/(0.35/0.4mm)" if d >= 0.25 - 1e-6 else
                   "0.2mm/(0.3/0.35mm)" if d >= 0.2 - 1e-6 else "0.15mm/(0.25/0.3mm)")
        via_txt = ("%s | the board's smallest via is %.2f mm in %.2f mm; the page may fill this in from the drill "
                   "file: check that it agrees" % (via_opt, d, via[2]))
    else:
        via_txt = "the default | %s" % ("the board has no vias yet" if have_board else "no board yet")
    L = ["# %s rev %s: JLCPCB order settings%s" % (BI.TITLE, BI.REV, " (DRAFT)" if draft() else ""), ""]
    if draft():
        L += ["**DRAFT:** %s.  Order once the build no longer says DRAFT." % draft(), ""]
    if not have_board:
        L += ["**NOT READY TO ORDER:** %s, so there are no gerbers and no CPL yet; the numbers below that come from "
              "the board are gen/layout.py's plan." % (why_not or "the board is not finished"), ""]
    L += ["Written by `mfg/make_release.py` on %s.  On jlcpcb.com, **Order now**, upload `%s_gerbers.zip`, then "
          "choose, in the order the page asks:" % (datetime.date.today(), NAME), "",
          "## The PCB", "",
          "| field | choose | why |", "|---|---|---|",
          "| Base Material | FR-4 | |",
          "| Layers | 4 | the coils' four spirals; a ground plane under the MCU and the drivers |",
          "| Dimensions | %.1f x %.1f mm | the panel's outline, read from the board file's Edge.Cuts%s |"
          % (w, h, "" if have_board else " (planned)"),
          "| PCB Qty | %d | JLCPCB's minimum; each one is a whole panel of %d boards |" % (panels, designs),
          "| Product Type | Industrial/Consumer electronics | |",
          "| Different Design | %d (type it in: the buttons stop at 4) | base, tree, perch, bat, owl token and cat "
          "token on one panel; with Panel by Customer, JLCPCB takes up to 10 |" % designs,
          "| Delivery Format | Panel by Customer | the panel is ours: rails, tabs and mouse bites are in the gerbers.  "
          "If the page asks for columns and rows, 1 x 1: one panel of six different boards, nothing repeated |",
          "| PCB Thickness | 1.6 mm | the JLC041611-7628 stack-up; the 3D prints (gen/mech.py) are drawn for 1.6 |",
          "| PCB Color | Purple | Halloween.  Purple on 4 layers rules out Economic PCBA, hence Standard below |",
          "| Silkscreen | White | |",
          "| Material Type | FR4-Standard TG 135-140 | the 4-layer default; nothing here runs hot enough to need more |",
          "| Surface Finish | ENIG | the moon and the ghost (the theremin's antennas) are bare gold copper; "
          "lead-free for a child's hands; flat pads for the 0.4 mm QFNs |",
          "| Outer Copper Weight | 1 oz | 5 A in pours is enough at 1 oz (PLAN.md section 4) |",
          "| Inner Copper Weight | 1 oz | halves the coils' inner-layer resistance (3.35 to 2.2 ohm): a third less "
          "heat (PLAN.md section 4) |",
          "| Impedance Control / Layer Stackup | Yes, JLC041611-7628 (no letter after 7628) | the stack-up "
          "gen/project.py's rules and the coils' physics assume: one 7628 prepreg each side of a 1.065 mm core.  "
          "JLCPCB's names read JLC, layers, thickness, outer copper, inner copper, prepreg: JLC04161H-7628 is the "
          "same build with 0.5 oz (H) inner copper, so with 1 oz inner chosen the page lists only the ...11- names; "
          "7628A-H are other core and prepreg layerings.  No line on this board needs a controlled impedance; "
          "'Yes' only brings up the list |",
          "| Via Covering | Tented | the default; the exposed pads' thermal vias wick a little solder, as Raspberry "
          "Pi's layout intends (GPiBridge, built this way) |",
          "| Min via hole size/diameter | %s |" % via_txt,
          "| Board Outline Tolerance | +-0.2mm (Regular) | |",
          "| Confirm Production file | Yes | free: JLCPCB shows the panel as they will make it before production; "
          "check the outline, the slots between the boards and the six designs |",
          "| Mark on PCB | Remove Mark | nothing on the art.  JLCPCB has added no order number by default since "
          "May 2026 and asks that \"JLCJLCJLCJLC\" not be put on the silkscreen (help: How to mark on PCB, "
          "2026-05-22)%s |" % ("; this board still carries it: take it off" if feat.get("jlc_text") else ""),
          "| Electrical Test | Flying Probe Fully Test | |",
          "| Gold Fingers / Castellated Holes / Edge Plating | No | |",
          "| PCB Remark | \"Customer panel of %d different designs joined by mouse bites; keep the rails on; SMD "
          "parts on both sides, through-hole parts on the top side only.\" | |" % designs,
          "| anything else | the default | |", "",
          "## PCB Assembly", "",
          "| field | choose | why |", "|---|---|---|",
          "| PCB Assembly | on | |",
          "| PCBA Type | Standard | purple on 4 layers is Standard only; Standard also does both sides |",
          "| Assembly Side | %s | %s |" % (("Both Sides", "the scene on top; the electronics underneath "
                                          "(gen/layout.py)") if len(cost["sides"]) == 2
                                         else (sorted(cost["sides"])[0].capitalize() + " Side", "")),
          "| PCBA Qty | %d | of the %d panels; the other %d are bare spares |" % (assembled, panels, panels - assembled),
          "| Tooling holes | %s | %s |" % (
              ("(from the board)", "Added by Customer if the panel's rails carry tooling holes, else Added by JLCPCB")
              if not have_board else
              ("Added by Customer", "%d tooling holes on the rails (%s)" % (len(tool), ", ".join(t[0] for t in tool)))
              if len(tool) >= 2 else ("Added by JLCPCB", "the panel's rails carry no tooling holes of their own")),
          "| Edge Rails/Fiducials | %s | %s |" % (
              ("(from the board)", "Added by Customer if the rails carry three fiducials, else Added by JLCPCB")
              if not have_board else
              ("Added by Customer", "%g mm rails with %d fiducials on them (%s)"
               % (LAYOUT.RAIL, len(fid), ", ".join(f["ref"] for f in fid)))
              if len(fid) >= 3 else ("Added by JLCPCB", "the panel lacks three good fiducials on its rails; JLCPCB "
                                     "adds them (and adds or fixes rails and fiducials that are missing or wrong, by "
                                     "default)")),
          "| Confirm Parts Placement | Yes | free.  Some rotations are predicted, not yet seen: "
          "PLACEMENT_CHECKS.txt says what to look at, on both sides |",
          "| Parts Selection | by Customer | every part has its LCSC code in the BOM |",
          "| Stencil / Fixture Storage | No | $4.93 each, for a re-order |",
          "| Bake Components | Yes | JLCPCB recommends it for moisture-sensitive parts (MSL 3 and up: the LGA-14 "
          "accelerometer, the QFNs); about $7.50 |",
          "| Depanel / remove rails | No | JLCPCB ships assembled panels with their rails on; the boards snap out "
          "at the mouse bites at home |",
          "| anything else | the default | |", "",
          "Then upload `BOM_JLCPCB.csv` and `" + CPL_UPLOAD + "` (not `" + CPL_NATIVE + "`).  Every BOM line carries "
          "its LCSC code; nothing should be left unmatched.  In the placement preview, go through "
          "`PLACEMENT_CHECKS.txt` on both sides before confirming.", "",
          "**Shipping:** UPS Express Saver (DDP) or DHL Express Priority (DDP): a US individual must ship DDP, and "
          "JLCPCB collects the duty (about 35 % of the PCBs and assembly).  Lead time: 4-layer PCBs 2-5 days, "
          "Standard assembly at least 4 more (+1 for through-hole parts), then 4-5 business days in the post.", ""]
    L += ["## Numbers behind the choices", "",
          "- Panel %.1f x %.1f mm%s; smallest track %s; %s." % (
              w, h, "" if have_board else " (planned)", ("%.3f mm" % tw) if tw else "(from the board)",
              ("%d vias" % len(B["vias"])) if B and B["vias"] else "vias: from the board"),
          "- Assembly: %d placements a panel on %d BOM lines (%d Extended), %d SMD pads and %d through-hole joints "
          "a panel%s; %s." % (cost["n_place"], cost["n_lines"], len(cost["ext"]), cost["smd"], cost["tht"],
                              "" if have_board else " (from the library's footprints)",
                              " and ".join(sorted(cost["sides"], reverse=True))),
          "- Estimate: %s before shipping and duty (COST_ESTIMATE.md)." % money(cost["total"])]
    if max(w, h) > 250.0:
        L.append("- **The panel is %.1f mm long.** JLCPCB recommends at most 250 x 250 mm for an assembled panel "
                 "and accepts larger at the customer's risk (warping through two reflows).  Expect them to ask."
                 % max(w, h))
    for n_ in feat.get("notes", []):
        L.append("- **Panel:** " + n_ + ".")
    L += checks
    L += ["", "Sources (read 2026-10-07): jlcpcb.com/help/article/pcb-assembly-price (2026-09-09), "
          "/capabilities/pcb-assembly-capabilities, /help/article/How-to-mark-on-PCB (2026-05-22), "
          "/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order, "
          "/help/article/Instructions-for-ordering, /help/article/us-tariff-policy-faq (2026-09-09).  The 4-layer "
          "fields' places on the page come from a 2024 printout of it and from others' 4-layer orders; the page "
          "itself is drawn by JavaScript."]
    open(os.path.join(out, "ORDER_SETTINGS.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


# ---------------------------------------------------------------------------------------
def drc_gate(pcb, skip):
    """DRC must be clean on the shipped file, and newer than it."""
    if skip:
        return "NOT RUN (--skip-drc: a test, not a release)"
    import json
    report = os.path.join(BI.CHECKS, "drc.json")
    if os.path.abspath(pcb) != os.path.abspath(BI.PCB):
        report = os.path.join(BI.SCRATCH, "drc_test.json")
        os.makedirs(BI.SCRATCH, exist_ok=True)
        kienv.run_cli(["pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", report, pcb], ok=(0, 5))
    elif not os.path.exists(report) or os.path.getmtime(report) < os.path.getmtime(pcb):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pcb_check.py")], capture_output=True, text=True)
        sys.stdout.write(r.stdout[-2000:])
    d = json.load(open(report))
    n = {k: len(d.get(k, [])) for k in ("violations", "unconnected_items", "schematic_parity")}
    if any(n.values()):
        raise Gate("DRC is not clean: %d violations, %d unconnected, %d parity (tools/pcb_check.py)"
                   % (n["violations"], n["unconnected_items"], n["schematic_parity"]))
    return "0 violations, 0 unconnected, 0 parity"


def scan_paths(out):
    bad = []
    for dp, _, fns in os.walk(out):
        for fn in fns:
            p = os.path.join(dp, fn)
            data = open(p, "rb").read()
            if fn.endswith(".zip"):
                with zipfile.ZipFile(p) as z:
                    data = b"".join(z.read(n) for n in z.namelist())
            m = FORBIDDEN.search(data)
            if m:
                bad.append("%s names a place on this machine (%r)" % (os.path.relpath(p, out), m.group(0)))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--panels", type=int, default=5)
    ap.add_argument("--assembled", type=int, default=2)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--pcb", default=BI.PCB)
    ap.add_argument("--netlist", default=BI.NETLIST)
    ap.add_argument("--out", default=BI.RELEASE)
    ap.add_argument("--skip-drc", action="store_true", help="testing only")
    ap.add_argument("--accept-hole", action="append", default=[], help="testing only: an LCSC code")
    ap.add_argument("--bom-only", action="store_true",
                    help="only the board-free half (BOM, its checks, the parts' cost), while the board is unfinished")
    a = ap.parse_args(argv)
    test = os.path.abspath(a.pcb) != os.path.abspath(BI.PCB) or os.path.abspath(a.out) != os.path.abspath(BI.RELEASE)
    if (a.skip_drc or a.accept_hole) and not test:
        raise SystemExit("--skip-drc and --accept-hole are for a test board (--pcb, --out), never the release")
    accepted = dict(HOLE_ACCEPTED, **{c: "a test" for c in a.accept_hole})
    stage = os.path.join(BI.SCRATCH, "release_stage") if not test else os.path.abspath(a.out) + ".stage"
    scratch = os.path.join(BI.SCRATCH, "release_scratch")
    for d in (stage, scratch):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    failures = []

    # ---- the rules this release leans on still hold -----------------------------------
    if jlc_rotation.self_test():
        failures.append("mfg/jlc_rotation.py's bottom-side rule no longer satisfies the readings it came from")

    # ---- the netlist and the parts: no board needed --------------------------------
    comps = classify(read_netlist(a.netlist))
    nocode = [c["ref"] for c in comps if c["cls"] == "nocode"]
    if nocode:
        failures.append("components with no LCSC code that gen/parts.py does not call 'not a part': %s"
                        % ", ".join(sorted(nocode, key=refkey)))
    placed = [c for c in comps if c["cls"] == "placed"]
    rows, bad, thin = parts_report(placed, a.assembled, a.refresh)
    failures += bad
    write_bom(rows, stage)
    have_board = os.path.exists(a.pcb) and not a.bom_only
    extra, fps, B, feat, drc = [], {}, None, None, None
    cpl, moved, preds, sim_ok, sim_bad, fp_lines = {}, [], {}, [], [], []
    if failures:
        return finish(failures, stage, a, test)

    if have_board:
        B, fps, extra, bad = board_parts(a.pcb, comps)
        failures += bad
        if B["copper"] != COPPER:
            failures.append("the board's copper layers are %s, not %s" % (B["copper"], COPPER))
        if B["thickness"] is not None and abs(B["thickness"] - 1.6) > 0.01:
            failures.append("the board is %.2f mm thick, not 1.6" % B["thickness"])
        if not B["filled"]:
            failures.append("the board file has no filled zones: the gerbers would ship without the pours")
        box = outline_box(B)
        if not box:
            failures.append("the board has no Edge.Cuts outline")
        if failures:
            return finish(failures, stage, a, test)
        try:
            drc = drc_gate(a.pcb, a.skip_drc)
        except Gate as e:
            return finish([str(e)], stage, a, test)
        dims = (round(box[2] - box[0], 2), round(box[3] - box[1], 2))
        feat = features(B, fps, box, parts={c["ref"] for c in comps})

        # ---- does every ordered part fit its copper? ---------------------------------
        nbad, fp_lines = FC.report(os.path.join(stage, "BOM_JLCPCB.csv"), a.refresh, False, pcb=a.pcb,
                                   bom_label=os.path.join(os.path.basename(a.out), "BOM_JLCPCB.csv"))
        open(os.path.join(stage, "FOOTPRINT_CHECK.txt"), "w", encoding="utf-8").write("\n".join(fp_lines) + "\n")
        holes, code = [], ""
        for l in fp_lines:
            m = re.match(r"  (?:ok|!!) (C\d+)", l)
            if m:
                code = m.group(1)
            if l.startswith("       HOLE") and code not in accepted:
                holes.append("%s: %s" % (code, l.strip()))
        if holes:
            failures.append("a part wants a hole the board does not have (FOOTPRINT_CHECK.txt; once a person has "
                            "compared the maker's drawing with JLCPCB's, HOLE_ACCEPTED in mfg/make_release.py):\n    "
                            + "\n    ".join(holes))
        refs = [l.strip() for l in fp_lines if l.startswith("  ?  ")]
        if refs:
            failures.append("footprint_check.py could not check: " + "; ".join(refs))
        fits = FC.FITS

        # ---- the CPL --------------------------------------------------------------------
        preds = predictions(placed, fps, fits)
        for c in placed:
            fp = fps[c["ref"]]
            side = "bottom" if fp["layer"].startswith("B.") else "top"
            X, Y = to_cpl(fp["at"][0], fp["at"][1], B["aux"])
            native = dict(X=X, Y=Y, side=side, R=round(fp["at"][2] % 360.0, 4))
            fit = fits.get((c["lcsc"], side == "bottom", fp["short"]))
            sx, sy = datum_shift(fp, fit)
            if sx or sy:
                moved.append((c["ref"], round(sx, 3), round(-sy, 3)))
            pred = preds.get((c["lcsc"], fp["short"]), (None, ""))[0]
            R = jlc_rotation.cpl_rotation(fp["at"][2], side, fp["short"], c["lcsc"], predicted=pred)
            cpl[c["ref"]] = dict(native=native, jlc=dict(X=X + sx, Y=Y - sy, side=side, R=R))
        jlc_rows = {ref: v["jlc"] for ref, v in cpl.items()}
        sim_bad, sim_ok = simulate(placed, fps, fits, jlc_rows, B["aux"])
        failures += sim_bad
        failures += pos_export_check(a.pcb, {ref: v["native"] for ref, v in cpl.items()}, scratch)
        if failures:
            return finish(failures, stage, a, test)
        write_cpl(cpl, stage)
        placement_checks(stage, placed, fps, cpl, preds, moved, sim_ok, sim_bad, B["aux"], B, feat)
        try:
            zpath, gfiles = export_gerbers(a.pcb, stage)
        except Gate as e:
            return finish([str(e)], stage, a, test)
        gb = gerber_box(os.path.join(stage, "gerbers", "%s-Edge_Cuts.gbr" % os.path.splitext(os.path.basename(a.pcb))[0]))
        want = (to_cpl(box[0], box[3], B["aux"]), to_cpl(box[2], box[1], B["aux"]))
        if not gb or max(abs(gb[0] - want[0][0]), abs(gb[1] - want[0][1]), abs(gb[2] - want[1][0]),
                         abs(gb[3] - want[1][1])) > 0.05:
            failures.append("the Edge.Cuts gerber spans %s, the board's outline %s in the CPL's frame" % (gb, want))
    else:
        dims = planned_dims()
    write_excluded(comps, extra, stage)
    cost = cost_md(stage, rows, fps, a.panels, a.assembled, dims, have_board, thin, comps)
    cost.update(n_place=len(placed), n_lines=len(rows))
    checks = []
    if have_board:
        checks = ["- Checks passed: DRC %s; %d filled zone polygons; every netlist part on the board; every code "
                  "matched (gen/parts.py's words, the value, the package, the MPN) and in stock; no ordered part wants "
                  "a hole%s; the CPL agrees with KiCad's position export, and JLCPCB's drawings placed by it land on "
                  "our pads (%d chips, both sides)." % (drc, B["filled"], " (accepted: %s)" % ", ".join(sorted(accepted))
                                                       if accepted else "", len(sim_ok))]
    why_not = ("the board file (hardware/%s.kicad_pcb) does not exist yet" % NAME if not os.path.exists(a.pcb)
               else "this is the board-free half of the release (--bom-only): the board is not finished")
    order_md(stage, have_board, dims, a.panels, a.assembled, feat or {}, B, cost, checks, why_not)
    failures += scan_paths(stage)
    return finish(failures, stage, a, test, have_board=have_board, rows=rows, cost=cost)


def planned_dims():
    """gen/layout.py's panel, before the board file exists: the boards' extents plus a
    gap and a rail on every side."""
    L = LAYOUT
    o = L.PANEL_OFFSETS
    x1 = max(o["base"][0] + L.BASE_W, o["tree"][0] + L.TREE_W, o["perch"][0] + L.PERCH_W / 2,
             o["bat"][0] + L.BAT_SPAN / 2, o["owl_token"][0] + L.TOKEN_R, o["cat_token"][0] + L.TOKEN_R)
    y1 = max(o["base"][1] + L.BASE_H, o["tree"][1] + L.TREE_H, o["perch"][1] + L.PERCH_BACK,
             o["bat"][1] + L.BAT_TAIL_Y, o["owl_token"][1] + L.TOKEN_R, o["cat_token"][1] + L.TOKEN_R)
    return round(x1 + L.GAP + L.RAIL, 2), round(y1 + L.GAP + L.RAIL, 2)


def finish(failures, stage, a, test, have_board=None, rows=None, cost=None):
    if failures:
        print("RELEASE FAILED: %d gate(s); %s was not changed" % (len(failures), a.out if test else os.path.relpath(a.out, ROOT)))
        for f in failures:
            print("  - " + f)
        return 1
    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    shutil.move(stage, a.out)
    ext = cost["ext"]
    print("release -> %s%s" % (os.path.relpath(a.out, ROOT) if not test else a.out, "  (TEST)" if test else ""))
    print("  %d BOM lines, %d placements a panel, %d distinct Extended parts: %s"
          % (len(rows), cost["n_place"], len(ext), " ".join(r["code"] for r in ext)))
    print("  estimate %s for %d panels, %d assembled (COST_ESTIMATE.md)" % (money(cost["total"]), a.panels, a.assembled))
    if draft():
        print("  DRAFT: %s" % draft())
    if not have_board:
        print("INCOMPLETE: %s: BOM, parts checks and cost only; no gerbers, CPL or placement checks"
              % ("no board file yet" if not os.path.exists(a.pcb) else "--bom-only"))
        return EXIT_NO_BOARD
    return 0


if __name__ == "__main__":
    sys.exit(main())
