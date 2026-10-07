#!/usr/bin/env python3
"""Make hardware/lib/: every symbol, footprint and 3D model the boards use, so the
project opens and builds on a machine whose KiCad has no libraries (CLAUDE_PCB.md
section 2).

    hardware/lib/OWL.kicad_sym     KiCad's symbols (flattened) + ours (gen/symbols.py)
    hardware/lib/OWL.pretty/       KiCad's footprints, Raspberry Pi's (gen/rpi_minimal),
                                   and the ones drawn in gen/footprints.py
    hardware/lib/OWL.3dshapes/     KiCad's 3D models, plus GPiBridge's drawn ones
                                   (gen/models/: the RP2354A's QFN-60, the AOTA
                                   inductor, the HRO USB-C)
    hardware/sym-lib-table, fp-lib-table

KiCad's own libraries are read from the KiCad install (tools/kienv.py).  They are
CC-BY-SA 4.0 with an exception for designs that use them.  JLCPCB's (EasyEDA's) land
patterns are NOT copied here: they are fetched into a git-ignored cache only to check
our footprints against (mfg/footprint_check.py), as on GPiBridge.

    python3 gen/library.py
"""
import os, re, shutil, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import kienv, kisch
from sexp import parse, head, kids, kid, val, ser
import symbols
import footprints
from parts import PARTS, LIB
kisch.POWER_LIB = LIB          # power symbols live in our library: OWL:PWR_+5V

HW = os.path.join(ROOT, "hardware")
LIBDIR = os.path.join(HW, "lib")
PRETTY = os.path.join(LIBDIR, LIB + ".pretty")
SHAPES = os.path.join(LIBDIR, LIB + ".3dshapes")
MODEL_PATH = "${KIPRJMOD}/lib/" + LIB + ".3dshapes/"

# symbol name in our library -> KiCad's stock lib_id
STOCK_SYMBOLS = {
    "R": "Device:R", "C": "Device:C", "C_Polarized": "Device:C_Polarized", "L": "Device:L",
    "LED": "Device:LED", "D_Schottky": "Device:D_Schottky", "D_TVS": "Device:D_TVS", "D_Zener": "Device:D_Zener",
    "Polyfuse": "Device:Polyfuse", "Antenna": "Device:Antenna", "Crystal_GND24": "Device:Crystal_GND24", "Speaker": "Device:Speaker",
    "SW_Push": "Switch:SW_Push", "SW_SPDT": "Switch:SW_SPDT",
    "USB_C_Receptacle_USB2.0_16P": "Connector:USB_C_Receptacle_USB2.0_16P",
    "Barrel_Jack_Switch": "Connector:Barrel_Jack_Switch",
    "Conn_02x08_Odd_Even": "Connector_Generic:Conn_02x08_Odd_Even",
    "Conn_01x03": "Connector_Generic:Conn_01x03",
    "TestPoint": "Connector:TestPoint", "MountingHole": "Mechanical:MountingHole", "PWR_FLAG": "power:PWR_FLAG",
    "XC6206P332MR": "Regulator_Linear:XC6206PxxxMR", "TPS54302": "Regulator_Switching:TPS54302",
    "74HC4051": "74xx:74HC4051", "74LVC1G14": "74xGxx:74LVC1G14", "LP5036": "Driver_LED:LP5036",
    "LTR-303ALS-01": "Sensor_Optical:LTR-303ALS-01",
    "DRV5055": "Sensor_Magnetic:DRV5055A1xDBZxQ1",
}

# Raspberry Pi's footprints (gen/rpi_minimal/rpi.pretty) -> our name, 3D model, model's KiCad library
RPI_FOOTPRINTS = {
    "rpi_rp2350a_vias": ("RP2350A_QFN-60_7x7mm_P0.4mm_RPi", "QFN-60-1EP_7x7mm_P0.4mm.wrl", None),
    "abracon_aota-b201610s3r3-101-t": ("L_Abracon_AOTA-B201610_RPi", "L_Abracon_AOTA-B201610.wrl", None),
    "generic_capc1005x50_wide": ("C_0402_RPi_wide", "C_0402_1005Metric.step", "Capacitor_SMD"),
    "generic_capc1005x50": ("C_0402_RPi", "C_0402_1005Metric.step", "Capacitor_SMD"),
    "generic_resc1005x35": ("R_0402_RPi", "R_0402_1005Metric.step", "Resistor_SMD"),
}
# 3D models for the footprints drawn in gen/footprints.py: the nearest stock model
GEN_MODELS = {
    "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.55x2.46mm_TI_PWP0016J": ("HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm.step", "Package_SO"),
    "BarrelJack_XKB_DC-005-5A-2.0_Horizontal": ("BarrelJack_Horizontal.step", "Connector_BarrelJack"),
    "LED_LiteOn_LTST-S270_SideView": ("LED_0603_1608Metric.step", "LED_SMD"),
    "Speaker_GSPK2307P_D23mm_P10mm": (None, None),      # none in KiCad's set: a speaker is a disc on the render
}
DRAWN_MODELS = os.path.join(HERE, "models")   # GPiBridge's drawn models (QFN-60, AOTA, HRO USB-C)

# The HRO USB-C's silkscreen is trimmed behind the board edge (GPiBridge, learned on the
# Lorenz board: board edge = upper shell tab + 5.79 mm; JLCPCB pulls silk 0.2 mm back).
USBC_EDGE_Y = -3.13 + 5.79
USBC_SILK_LIMIT = USBC_EDGE_Y - 0.45


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ------------------------------------------------------------------------------------------
def _rename_symbol(node, old, new):
    node = list(node)
    node[1] = ("str", new)
    out = []
    for c in node:
        if isinstance(c, list) and head(c) == "symbol":
            c = list(c)
            c[1] = ("str", val(c).replace(old, new, 1))
        out.append(c)
    return out


def _set_prop(node, name, value):
    for c in node:
        if isinstance(c, list) and head(c) == "property" and val(c) == name:
            c[2] = ("str", value)


def build_symbols(share):
    entries = []
    for name, stock_id in sorted(STOCK_SYMBOLS.items()):
        node = kisch.SYMS.stock(stock_id, os.path.join(share, "symbols"))
        node = _rename_symbol(node, stock_id.split(":")[1], name)
        entries.append((name, node))
    for name, fn in sorted(symbols.CUSTOM.items()):
        text, _ = fn()
        entries.append((name, parse(text)[0]))
    for net, down in sorted(symbols.RAILS.items()):
        lib_id = kisch.power_lib_id(net)
        kisch.make_power(lib_id, net, down=down)
        node, _ = kisch.SYMS.get(lib_id)
        entries.append((lib_id.split(":", 1)[1], node))
    for name, node in entries:
        _set_prop(node, "Footprint", "")
    write(os.path.join(LIBDIR, LIB + ".kicad_sym"), kisch.library_text(entries))
    return len(entries)


# ------------------------------------------------------------------------------------------
def _set_model(node, model):
    rest = [c for c in node if not (isinstance(c, list) and head(c) == "model")]
    node[:] = rest
    if model:
        node.append([("atom", "model"), ("str", MODEL_PATH + model),
                     [("atom", "offset"), [("atom", "xyz"), ("atom", "0"), ("atom", "0"), ("atom", "0")]],
                     [("atom", "scale"), [("atom", "xyz"), ("atom", "1"), ("atom", "1"), ("atom", "1")]],
                     [("atom", "rotate"), [("atom", "xyz"), ("atom", "0"), ("atom", "0"), ("atom", "0")]]])


def _stock_model(node):
    m = kid(node, "model")
    return os.path.basename(val(m)) if m else None


def _trim_usbc_silk(node):
    keep = []
    for c in node:
        if isinstance(c, list) and head(c) == "fp_line" and val(kid(c, "layer")) in ("F.SilkS", "F.Silkscreen"):
            s, e = kid(c, "start"), kid(c, "end")
            ys = [float(val(s, 2)), float(val(e, 2))]
            if min(ys) >= USBC_SILK_LIMIT:
                continue
            for p in (s, e):
                if float(val(p, 2)) > USBC_SILK_LIMIT:
                    p[2] = ("atom", "%.2f" % USBC_SILK_LIMIT)
            if abs(float(val(s, 1)) - float(val(e, 1))) + abs(float(val(s, 2)) - float(val(e, 2))) < 0.3:
                continue
        keep.append(c)
    node[:] = keep


RPI_DESCR = "From Raspberry Pi's RP2350A Minimal design (MIT licence), so their regulator layout can be copied exactly"


def _clean_rpi(node):
    keep = []
    for c in node:
        if isinstance(c, list) and head(c) == "property" and val(c) not in ("Reference", "Value", "Datasheet"):
            continue
        if isinstance(c, list) and head(c) == "property" and val(c) == "Datasheet":
            c[2] = ("str", "")
        if isinstance(c, list) and head(c) in ("embedded_files", "embedded_fonts", "descr"):
            continue
        keep.append(c)
    at = next(i for i, c in enumerate(keep) if isinstance(c, list) and head(c) == "layer") + 1
    keep.insert(at, [("atom", "descr"), ("str", RPI_DESCR)])
    node[:] = keep


def build_footprints(share, models_needed):
    if os.path.isdir(PRETTY):
        shutil.rmtree(PRETTY)
    os.makedirs(PRETTY)
    done = set()
    gen = footprints.generated()
    rpi_by_name = {v[0]: (k, v[1], v[2]) for k, v in RPI_FOOTPRINTS.items()}
    for key, p in sorted(PARTS.items()):
        src = p.get("fp_src")
        name = p["fp"].split(":", 1)[1]
        if not src or not name or name in done:
            continue
        if src.startswith("stock:"):
            lib = src.split(":", 1)[1]
            path = os.path.join(share, "footprints", lib + ".pretty", name + ".kicad_mod")
            node = parse(open(path, encoding="utf-8").read())[0]
            model = _stock_model(node)
            if name.startswith("USB_C_Receptacle_HRO"):
                _trim_usbc_silk(node)
                model, lib = "USB_C_Receptacle_HRO_TYPE-C-31-M-12.wrl", None
            _set_model(node, model)
            if model:
                models_needed[model] = lib
            write(os.path.join(PRETTY, name + ".kicad_mod"), ser(node) + "\n")
        elif src == "rpi":
            src_name, model, mlib = rpi_by_name[name]
            path = os.path.join(HERE, "rpi_minimal", "rpi.pretty", src_name + ".kicad_mod")
            node = parse(open(path, encoding="utf-8").read())[0]
            node[1] = ("str", name)
            _clean_rpi(node)
            _set_model(node, model)
            models_needed[model] = mlib
            write(os.path.join(PRETTY, name + ".kicad_mod"), ser(node) + "\n")
        elif src == "gen":
            node = parse(gen[name])[0]
            model, mlib = GEN_MODELS.get(name, (None, None))
            _set_model(node, model)
            if model:
                models_needed[model] = mlib
            write(os.path.join(PRETTY, name + ".kicad_mod"), ser(node) + "\n")
        else:
            raise SystemExit("unknown footprint source %r for %s" % (src, key))
        done.add(name)
    return len(done)


def copy_models(share, models_needed):
    if os.path.isdir(SHAPES):
        shutil.rmtree(SHAPES)
    os.makedirs(SHAPES)
    have, missing = 0, []
    for model, lib in sorted(models_needed.items()):
        base = os.path.splitext(model)[0]
        if lib is None:                                   # drawn (GPiBridge's): wrl + step
            for ext in (".wrl", ".step"):
                src = os.path.join(DRAWN_MODELS, base + ext)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(SHAPES, base + ext))
            have += 1
            continue
        found = False
        for m in (model, base + ".step", base + ".wrl"):
            src = os.path.join(share, "3dmodels", lib + ".3dshapes", m)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(SHAPES, os.path.basename(m)))
                found = True
        have += found
        if not found:
            missing.append("%s/%s" % (lib, model))
    return have, missing


LIB_README = """# hardware/lib: everything the boards are drawn with

Made by `gen/library.py`; do not edit by hand.

- `OWL.kicad_sym`: KiCad's own symbols (flattened), plus the ones drawn for this board
  in `gen/symbols.py` (RP2354A, DRV8874, NS4150B, TMAG5273, the SO-8 P-MOSFET, the
  three-die LED, the PCB coil, the debug connectors, the power symbols).
- `OWL.pretty/`: KiCad's own footprints; Raspberry Pi's QFN-60, inductor and 0402
  footprints (`gen/rpi_minimal/`, MIT licence), so their regulator layout is copied
  exactly; and four drawn in `gen/footprints.py` from their makers' drawings.
- `OWL.3dshapes/`: KiCad's 3D models, plus three drawn for GPiBridge (`gen/models/`).

Licences: KiCad's libraries are CC-BY-SA 4.0 with the KiCad libraries' exception (using
them in a design does not put the design under CC-BY-SA).  Raspberry Pi's footprints
are MIT licensed (`gen/rpi_minimal/LICENSE.txt`).  The rest is this project's (`LICENSE`).
"""


def lib_tables():
    write(os.path.join(HW, "sym-lib-table"),
          '(sym_lib_table\n\t(version 7)\n\t(lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/lib/%s.kicad_sym") '
          '(options "") (descr "Every symbol OWLternating Current uses"))\n)\n' % (LIB, LIB))
    write(os.path.join(HW, "fp-lib-table"),
          '(fp_lib_table\n\t(version 7)\n\t(lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/lib/%s.pretty") '
          '(options "") (descr "Every footprint OWLternating Current uses"))\n)\n' % (LIB, LIB))
    write(os.path.join(LIBDIR, "README.md"), LIB_README)


def fixed_uuids(directory):
    """KiCad's upgrade gives every item a fresh random UUID on every run; replace them with
    ones derived from the file name and the item's order, so rebuilding the library
    changes nothing that git can see unless a footprint really changed."""
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".kicad_mod"):
            continue
        path = os.path.join(directory, name)
        text = open(path).read()
        n = iter(range(10 ** 6))
        text = re.sub(r'\(uuid "[0-9a-f-]+"\)',
                      lambda m: '(uuid "%s")' % uuid.uuid5(uuid.NAMESPACE_URL, "owl/%s/%d" % (name, next(n))), text)
        write(path, text)


def main():
    share = kienv.share()
    ns = build_symbols(share)
    models = {}
    nf = build_footprints(share, models)
    have, missing = copy_models(share, models)
    lib_tables()
    # bring every footprint to KiCad 10's own format (ours are written as KiCad 8)
    kienv.run_cli(["fp", "upgrade", "--force", PRETTY])
    fixed_uuids(PRETTY)
    print("library: %d symbols, %d footprints, %d 3D models%s"
          % (ns, nf, have, ("; MISSING 3D models: " + ", ".join(missing)) if missing else ""))
    return 0          # missing 3D models only affect renders: drawn later (PLAN.md work list)


if __name__ == "__main__":
    sys.exit(main())
