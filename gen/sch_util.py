"""Helpers every sheet's generator uses (after GPiBridge's gen/schematic.py).

A sheet module calls begin(sch) and then places parts with part()/hpart()/vpart(),
draws wires with W(), and puts notes at nodes with note().  Coordinates are
millimetres, x right, y DOWN, on the 1.27 mm grid.

Reference designators are numbered by board, so the silkscreen says which board a
part belongs to: base 1-99, tree 101-199, perch 201-299, bat 301-399, the owl token
401-499, the cat token 501-599.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import kisch
from parts import PARTS, LIB

G = 2.54
NOTE = (255, 255, 194)
S = None                 # the sheet being drawn
REFS = {}                # ref -> part key, across every sheet (one panel, one netlist)
_flags = None


def begin(sch):
    global S, _flags
    S = sch
    _flags = iter("#FLG%s%02d" % (sch.filename.split(".")[0][-2:], i) for i in range(1, 99))


def part(key, ref, x, y, rot=0, unit=1, value=None, mirror=None, text="auto", fsize=1.27, sym=None, **kw):
    """Place PARTS[key] as `ref`.  text: "auto" (reference above, value below), "right"
    (both to the right of a vertical part), "left", or "hide"."""
    assert ref not in REFS or REFS[ref] == key, "reference %s used twice" % ref
    p = dict(PARTS[key])
    if sym:
        p["sym"] = LIB + ":" + sym
    fields = {"MPN": p["mpn"]} if p.get("mpn") else {}
    value = p["value"] if value is None else value
    if text == "right":
        dx = 2.8 if p["sym"].endswith(":C") or p["sym"].endswith(":C_Polarized") else 1.9
        kw.setdefault("ref_at", (x + dx, y - 0.3))
        kw.setdefault("val_at", (x + dx, y + 0.3))
    elif text == "left":
        dx = 2.8 if p["sym"].endswith(":C") or p["sym"].endswith(":C_Polarized") else 1.9
        kw.setdefault("ref_at", (x - dx, y - 0.3))
        kw.setdefault("val_at", (x - dx, y + 0.3))
        kw.setdefault("justify", "right")
    elif text == "hide":
        kw["hide_ref"] = kw["hide_value"] = True
    pl = S.sym(p["sym"], x, y, rot=rot, ref=ref, value=value, footprint=p["fp"], unit=unit, mirror=mirror,
               lcsc=p["lcsc"], fields=fields, fsize=fsize, **kw)
    REFS[ref] = key
    return pl


def _pins(pl):
    _, pins = kisch.SYMS.get(pl.lib_id)
    seen, out = set(), []
    for p in pins:
        if p["unit"] in (0, pl.unit):
            xy = pl.pin(p["num"])
            if xy not in seen:
                seen.add(xy)
                out.append(xy)
    return out


def hpart(key, ref, xc, y, **kw):
    """A two-pin part lying on a horizontal line; returns (left, right)."""
    pl = part(key, ref, xc, y, rot=90, **kw)
    a, b = sorted(_pins(pl), key=lambda q: q[0])
    return a, b


def vpart(key, ref, x, yc, **kw):
    """A two-pin part standing on a vertical line; returns (top, bottom)."""
    kw.setdefault("text", "right")
    pl = part(key, ref, x, yc, **kw)
    a, b = sorted(_pins(pl), key=lambda q: q[1])
    return a, b


def gnd(x, y, net="GND"):
    return S.power(net, x, y)


def flag(net, x, y, **kw):
    return S.power(net, x, y, **kw)


def W(*pts):
    S.wires(*pts)


def J(x, y):
    S.junction(x, y)


def pwr_flag(x, y, rot=0):
    return S.sym(PARTS["PWR_FLAG"]["sym"], x, y, rot=rot, ref=next(_flags), value="PWR_FLAG", footprint="",
                 in_bom=False, on_board=False, hide_ref=True, hide_value=True)


def label(x, y, name, size=1.0):
    """A net name on a wire (the wire carries on: nothing disappears)."""
    S.label(x, y, name, size=size)


def note(x, y, text, cols=44, size=1.0):
    return S.note(x, y, text, size=size, cols=cols, color=NOTE)


def title(x, y, text, size=2.0):
    return S.text(x, y, text, size=size, bold=True)


def box(x, y, w, h):
    """A dashed box round a block."""
    S.rect(x, y, w, h, style="dash", width=0.2)


def decouple(xpin, ypin, caps, refs, rail, gnd_net="GND", side=+1, dy=7.62):
    """Decoupling at a supply pin that points UP: a short riser to a junction, the rail's
    flag above, and each capacitor hanging to one side of the riser to its own ground.
    caps: part keys, nearest first; refs: their references; side: +1 right, -1 left."""
    yj = ypin - dy
    W((xpin, ypin), (xpin, yj))
    flag(rail, xpin, yj - 2.54)
    W((xpin, yj), (xpin, yj - 2.54))
    x = xpin
    for k, (key, ref) in enumerate(zip(caps, refs)):
        x2 = xpin + side * (k + 1) * 5.08
        W((x, yj), (x2, yj))
        x = x2
        t, b = vpart(key, ref, x2, yj + 3.81, fsize=1.0, text="right" if side > 0 else "left")
        gnd(*b, net=gnd_net)
    J(xpin, yj)
    return yj
