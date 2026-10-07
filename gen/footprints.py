"""Footprints drawn for OWLternating Current (the rest are KiCad's own, vendored).

Each is drawn from its maker's drawing, cited below.  JLCPCB's own land pattern
for each part (EasyEDA's, fetched into a git-ignored cache by
mfg/footprint_check.py) is compared with these before a release, and predicts the
rotation JLCPCB will place each part at.

The PCB coils are footprints too, generated rather than drawn: gen/coils.py makes each
spiral the footprint's own copper, a net tie between its two pads.
"""

MODELS = []          # 3D models drawn here: none (gen/models3d.py would add them)


def _hdr(name, descr, attr="smd", tags=""):
    return ['(footprint "%s"' % name, '\t(version 20240108)', '\t(generator "owl_gen")',
            '\t(layer "F.Cu")', '\t(descr "%s")' % descr.replace('"', "'"), '\t(tags "%s")' % tags,
            '\t(property "Reference" "REF**" (at 0 -3 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
            '\t(property "Value" "%s" (at 0 3 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % name,
            '\t(attr %s)' % attr]


def _line(x0, y0, x1, y1, layer, w=0.15):
    return '\t(fp_line (start %.4f %.4f) (end %.4f %.4f) (stroke (width %.3f) (type solid)) (layer "%s"))' % (
        x0, y0, x1, y1, w, layer)


def _rect(x0, y0, x1, y1, layer, w=0.15):
    return '\t(fp_rect (start %.4f %.4f) (end %.4f %.4f) (stroke (width %.3f) (type solid)) (fill none) (layer "%s"))' % (
        x0, y0, x1, y1, w, layer)


def _circle(cx, cy, r, layer, w=0.15):
    return '\t(fp_circle (center %.4f %.4f) (end %.4f %.4f) (stroke (width %.3f) (type solid)) (fill none) (layer "%s"))' % (
        cx, cy, cx + r, cy, w, layer)


def _smd(num, x, y, w, h, shape="roundrect", paste=True, rot=0):
    layers = '"F.Cu" "F.Mask"' + (' "F.Paste"' if paste else "")
    rr = ' (roundrect_rratio 0.25)' if shape == "roundrect" else ""
    return '\t(pad "%s" smd %s (at %.4f %.4f %g) (size %.4f %.4f) (layers %s)%s)' % (
        num, shape, x, y, rot, w, h, layers, rr)


def _tht(num, x, y, w, h, drill, shape="circle", rot=0, drill_oval=None):
    d = ("(drill oval %.4f %.4f)" % drill_oval) if drill_oval else "(drill %.4f)" % drill
    return '\t(pad "%s" thru_hole %s (at %.4f %.4f %g) (size %.4f %.4f) %s (layers "*.Cu" "*.Mask") (remove_unused_layers no))' % (
        num, shape, x, y, rot, w, h, d)


def _close(out):
    out.append(')')
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------------------------------
def drv8874_pwp():
    """TI DRV8874PWPR, PWP0016J PowerPAD HTSSOP-16 (datasheet, package drawing and example
    board layout).  Body 5.0 x 4.4 mm, 0.65 mm pitch, leads to 6.4 mm; thermal pad up to
    3.55 x 2.46 mm (JLCPCB's own pattern for C1855818 uses exactly 3.55 x 2.46).  The pad
    is ground (datasheet: "Thermal pad. Connect to system ground"), with six 0.3 mm vias
    on a 1.2 mm x 0.9 mm grid into the inner ground plane, and window-pane paste."""
    name = "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.55x2.46mm_TI_PWP0016J"
    out = _hdr(name, "TI PWP0016J PowerPAD HTSSOP-16 (DRV8874PWPR): 0.65 mm pitch, thermal pad 3.55 x 2.46 mm, 6 vias",
               tags="HTSSOP PowerPAD DRV8874")
    for i in range(8):
        x = -2.275 + i * 0.65
        out.append(_smd(str(i + 1), x, 2.85, 0.40, 1.50))            # pins 1-8 along the bottom, left to right
        out.append(_smd(str(16 - i), x, -2.85, 0.40, 1.50))          # 16-9 along the top
    # thermal pad, no paste on the pad itself; four paste windows (~60 %)
    out.append('\t(pad "17" smd rect (at 0 0) (size 3.55 2.46) (layers "F.Cu" "F.Mask"))')
    for px in (-0.85, 0.85):
        for py in (-0.58, 0.58):
            out.append('\t(pad "" smd rect (at %.3f %.3f) (size 1.35 0.92) (layers "F.Paste"))' % (px, py))
    for vx in (-1.2, 0.0, 1.2):
        for vy in (-0.45, 0.45):
            out.append('\t(pad "17" thru_hole circle (at %.3f %.3f) (size 0.6 0.6) (drill 0.3) (layers "*.Cu") (remove_unused_layers no))' % (vx, vy))
    out.append(_rect(-2.5, -2.2, 2.5, 2.2, "F.Fab", 0.1))
    out.append(_line(-2.5, -2.2, -2.5, 2.2, "F.SilkS"))
    out.append(_circle(-2.9, 3.55, 0.15, "F.SilkS", 0.3))            # pin 1 dot
    out.append(_rect(-3.0, -3.85, 3.0, 3.85, "F.CrtYd", 0.05))
    return name, _close(out)


def dc005():
    """XKB DC-005-5A-2.0 barrel jack (its drawing, 'PCB layout top view'): pin 1 = centre
    pin (+), pin 2 = sleeve (-), pin 3 = the plug-detect switch.  Pins 1 and 2 are slots
    1.0 x 3.5 mm across the jack's axis, 7.7 mm (pin 2) and 13.6 mm (pin 1) behind the
    front face; pin 3 is a slot along the axis, 10.6 mm behind the front face and 4.7 mm to
    the side of the other two.  Origin: midway between the slots' centres; the plug
    enters from -x; the front face is at x = -10.65.  Body 9.0 x 14.4 mm, 11 mm tall."""
    name = "BarrelJack_XKB_DC-005-5A-2.0_Horizontal"
    out = _hdr(name, "XKB DC-005-5A-2.0 5.5x2.1 mm barrel jack, 5 A; pin 1 centre (+), 2 sleeve, 3 switch; plug enters from -x",
               attr="through_hole", tags="barrel jack DC-005")
    out.append(_tht("1", 2.95, -2.35, 1.9, 4.4, None, "oval", drill_oval=(1.0, 3.5)))
    out.append(_tht("2", -2.95, -2.35, 1.9, 4.4, None, "oval", drill_oval=(1.0, 3.5)))
    out.append(_tht("3", 0.0, 2.35, 4.4, 1.9, None, "oval", drill_oval=(3.5, 1.0)))
    x0, x1, y0, y1 = -10.65, 3.75, -4.5, 4.5
    out.append(_rect(x0, y0, x1, y1, "F.Fab", 0.1))
    out.append(_line(x0, y0, x1, y0, "F.SilkS"))
    out.append(_line(x0, y1, x1, y1, "F.SilkS"))
    out.append(_line(x1, y0, x1, y1, "F.SilkS"))
    out.append(_rect(x0 - 0.25, y0 - 0.5, x1 + 0.5, y1 + 0.5, "F.CrtYd", 0.05))
    return name, _close(out)


def ltst_s270():
    """Lite-On LTST-S270KFKT side-looking LED (datasheet p.1 package, p.8 'Suggest
    Soldering Pad Dimensions': two 1.10 x 1.10 mm pads, 0.90 mm apart).  Body 1.65 x 0.60,
    1.15 tall.  Pad 1 is the cathode (the end with the cathode mark); it shines out of its
    long side, toward -y here (the board edge goes there)."""
    name = "LED_LiteOn_LTST-S270_SideView"
    out = _hdr(name, "Lite-On LTST-S270 side-view LED: pads 1.1 x 1.1 mm, 0.9 mm apart; pad 1 cathode; emits toward -y",
               tags="LED side view")
    out.append(_smd("1", -1.0, 0.0, 1.1, 1.1))
    out.append(_smd("2", 1.0, 0.0, 1.1, 1.1))
    out.append(_rect(-0.83, -0.3, 0.83, 0.85, "F.Fab", 0.1))
    out.append(_line(-1.75, 0.75, -1.75, -0.75, "F.SilkS"))          # cathode bar
    out.append(_line(-0.3, -1.0, 0.3, -1.0, "F.SilkS"))             # light goes this way
    out.append(_line(0.0, -1.0, 0.0, -1.35, "F.SilkS"))
    out.append(_rect(-1.8, -1.45, 1.8, 0.85, "F.CrtYd", 0.05))
    return name, _close(out)


def gspk2307p():
    """G-SPK GSPK2307P-8R1W (LCSC C530531), 23 mm round speaker, 6.8 mm tall, with
    two PCB pins 10.0 mm apart (JLCPCB's pattern for C530531: 1.1 mm drills, 2.5 mm pads).
    The cone faces up; the back has a vent, so it stands on the board."""
    name = "Speaker_GSPK2307P_D23mm_P10mm"
    out = _hdr(name, "G-SPK GSPK2307P-8R1W 23 mm 8 ohm 1 W speaker, PCB pins 10 mm apart", attr="through_hole",
               tags="speaker")
    out.append(_tht("1", -5.0, 0.0, 2.5, 2.5, 1.1, "rect"))
    out.append(_tht("2", 5.0, 0.0, 2.5, 2.5, 1.1))
    out.append(_circle(0, 0, 11.5, "F.Fab", 0.1))
    out.append(_circle(0, 0, 11.6, "F.SilkS"))
    out.append(_circle(0, 0, 11.85, "F.CrtYd", 0.05))
    return name, _close(out)


DRAWN = [drv8874_pwp, dc005, ltst_s270, gspk2307p]


def generated():
    return {name: text for name, text in (fn() for fn in DRAWN)}
