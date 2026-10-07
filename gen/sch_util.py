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
kisch.POWER_LIB = LIB

G = 2.54
NOTE = (255, 255, 194)
S = None                 # the sheet being drawn
REFS = {}                # ref -> part key, across every sheet (one panel, one netlist)
_flags = None


_n = {}
_base = 0
ROLES = {}               # role -> ref: what each part is for, for the placement (gen/placement.py)
_tag = None


def tag(name):
    """Name the role of the next part placed (part(), down(), up(), series()...)."""
    global _tag
    assert name not in ROLES, "role %s used twice" % name
    _tag = name


def begin(sch, ref_base=0):
    """Start drawing `sch`; its automatically numbered references (R, C, D, TP) start
    after ref_base (0 for the base board, 100 for the tree, 200 for the perch...)."""
    global S, _flags, _base
    S = sch
    _flags = iter("#FLG_%s%02d" % (sch.filename.split(".")[0], i) for i in range(1, 99))
    _base = ref_base
    _n.clear()


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
    global _tag
    if _tag:
        ROLES[_tag] = ref
        _tag = None
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


# ---- drawing helpers every sheet uses ----------------------------------------------
def nref(prefix):
    """The next free reference of a kind (R, C, D, TP), in the order the sheet is drawn,
    after this board's base (begin())."""
    _n[prefix] = _n.get(prefix, _base) + 1
    while "%s%d" % (prefix, _n[prefix]) in REFS:
        _n[prefix] += 1
    return "%s%d" % (prefix, _n[prefix])


def kind(key):
    return "C" if key.startswith("C") else "L" if key.startswith("L") else "R"


def down(key, x, y, net="GND", text="right", ref=None, drop=G, fsize=1.0):
    """A two-pin part hanging from the node (x, y): a short drop, the part, then ground
    (or `net`'s flag, or nothing when net is None).  Returns (reference, bottom pin)."""
    ref = ref or nref(kind(key))
    t, b = vpart(key, ref, x, y + drop + 3.81, fsize=fsize, text=text)
    W((x, y), t)
    if net:
        gnd(*b, net=net)
    return ref, b


def up(key, x, y, rail, text="right", ref=None, rise=G, fsize=1.0):
    """A two-pin part standing on the node (x, y), `rail`'s flag on top (a pull-up)."""
    ref = ref or nref(kind(key))
    t, b = vpart(key, ref, x, y - rise - 3.81, fsize=fsize, text=text)
    W(b, (x, y))
    flag(rail, *t)
    return ref, t


def series(key, xc, y, ref=None, above=True, fsize=1.0):
    """A two-pin part lying on a horizontal line, its name and value stacked above it
    (or below); returns (left, right)."""
    ref = ref or nref(kind(key))
    if above:
        return hpart(key, ref, xc, y, ref_at=(xc, y - 4.3), val_at=(xc, y - 3.9), fsize=fsize, justify="center")
    return hpart(key, ref, xc, y, ref_at=(xc, y + 3.9), val_at=(xc, y + 4.3), fsize=fsize, justify="center")


def tp(x, y, value, ref=None, key="TP"):
    """A test pad at (x, y), labelled with what it reads."""
    ref = ref or nref("TP")
    part(key, ref, x, y, value=value, ref_at=(x + 1.5, y - 3.6), val_at=(x + 1.5, y - 1.9), fsize=1.0)
    return ref


def line(y, xs):
    """A horizontal wire through the points xs on row y (pins, taps)."""
    xs = sorted(set(round(x, 3) for x in xs))
    for a, b in zip(xs, xs[1:]):
        W((a, y), (b, y))


def vline(x, ys):
    ys = sorted(set(round(y, 3) for y in ys))
    for a, b in zip(ys, ys[1:]):
        W((x, a), (x, b))


def diode(key, ref, xc, y):
    """A diode lying on a horizontal line, anode on the left; returns (anode, cathode)."""
    d = part(key, ref, xc, y, rot=180, ref_at=(xc, y - 3.0), val_at=(xc, y + 3.3), fsize=1.0)
    return d.pin("2"), d.pin("1")
