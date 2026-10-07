"""kisch: a small KiCad 9/10 schematic writer, in the Art of Electronics style.

Copied from the ECP5-2ADC-2DAC project (gen/kisch.py), which drew a seven-sheet
board that KiCad 10 opens, ERCs and netlists without complaint; that one was
ported from two earlier boards.  What it keeps, because each was learned the
hard way:

  * the pin transform (library y-up, sheet y-down, placement rotation taken
    clockwise) verified against an exported netlist;
  * junction insertion that SPLITS wires: a junction dot in the interior of an
    unbroken wire breaks connectivity instead of making it;
  * deterministic uuids, so a regenerated project gives a clean git diff;
  * a stock symbol's `extends` parent flattened, because KiCad refuses a file
    whose symbol extends a parent that is absent;
  * checks for accidental connections (a pin landing inside a wire, two rails
    merged) and for text that overlaps text or symbols.

Changed for GPiBridge: symbols come from the project's own library
(hardware/lib/GPiBridge.kicad_sym, made by gen/library.py), so a fresh clone
needs nothing from KiCad's install; KiCad's stock libraries are read only when
a part is vendored into that library.

Schematic coordinates are millimetres, X right, Y DOWN, on a 1.27 mm grid.
Writes format version 20250114 (KiCad 9); the build upgrades it to KiCad 10's
own format with `kicad-cli sch upgrade`.
"""
import hashlib, math, os, re, sys, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, head, kids, kid, val, num, ser

SCH_VERSION = "20250114"
GRID = 1.27

PAPER = {"A4": (297.0, 210.0), "A3": (420.0, 297.0),
         "A2": (594.0, 420.0), "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}


def uuid_for(*parts):
    h = hashlib.sha1(("|".join(str(p) for p in parts)).encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def q(s):
    return '"%s"' % (str(s).replace("\\", "\\\\").replace('"', '\\"')
                     .replace("\n", "\\n").replace("\r", ""))


def snap(v):
    return round(round(float(v) / GRID) * GRID, 4)


def g(v):
    return "%.4f" % snap(v)


def wrap(text, width=60):
    out = []
    for para in str(text).split("\n"):
        out.extend(textwrap.wrap(para, width) if para.strip() else [""])
    return "\n".join(out)


# KiCad's stroke font advances, measured (IcepiZeroADCDAC/common/kicad_sch.py).
_ADV_GROUPS = (
    (0.321, "`"), (0.405, ",I"), (0.410, "!'.:;ij"), (0.457, "l"), (0.514, "^ft"),
    (0.555, "r"), (0.586, "\\"), (0.598, "[]"), (0.600, "()"), (0.602, "{}"),
    (0.655, "~"), (0.695, '"J'), (0.700, "*vy"), (0.705, "T"), (0.740, "k"),
    (0.743, "s"), (0.745, "L"), (0.748, "xz"), (0.762, " _"), (0.790, "?Fce"),
    (0.800, "AVY"), (0.833, "hnu"), (0.836, "Eabdgpq"), (0.838, "o"), (0.857, "|"),
    (0.886, "$015689S"), (0.888, "234"), (0.890, "7XZ"), (0.931, "BDKPR"),
    (0.933, "CG"), (0.943, "#"), (0.948, "/"), (0.976, "HNU"), (0.981, "OQ"),
    (0.986, "w"), (1.071, "M"), (1.076, "%"), (1.081, "W"), (1.167, "+-<=>"),
    (1.169, "&"), (1.219, "@"), (1.262, "m"))
ADV = {c: a for a, chars in _ADV_GROUPS for c in chars}


def text_w(s, size=1.27):
    return max((sum(ADV.get(c, 0.8) for c in line) for line in str(s).split("\n")), default=0) * size


def text_h(s, size=1.27):
    return (str(s).count("\n") + 1) * size * 1.6


# ---------------------------------------------------------------------------
# Symbol library: stock symbols (KiCad 10 ships one .kicad_sym per symbol
# inside Lib.kicad_symdir/), plus symbols we generate.
# ---------------------------------------------------------------------------
class SymCache:
    """Every symbol the sheet can use, by lib_id ("Lib:Name").

    load_library(path, nick) registers each symbol of a .kicad_sym file as
    "nick:Name".  stock(lib_id) reads one of KiCad's own symbols, flattening
    `extends`; only gen/library.py calls it, to vendor parts."""
    def __init__(self):
        self._sym = {}          # lib_id -> (node, pins)

    def load_library(self, path, nick):
        doc = parse(open(path, encoding="utf-8").read())[0]
        syms = {val(s): s for s in kids(doc, "symbol")}
        for name, node in syms.items():
            ext = kid(node, "extends")
            if ext:
                node = self._merge(syms[val(ext)], node, val(ext), name)
            self._sym["%s:%s" % (nick, name)] = (node, _pins_of(node))
        return sorted(syms)

    def stock(self, lib_id, symdir):
        """KiCad's stock symbol `lib_id` from `symdir` (KiCad 10 ships one
        .kicad_sym per symbol inside Lib.kicad_symdir/), flattened."""
        libname, name = lib_id.split(":", 1)

        def load(nm):
            p = os.path.join(symdir, libname + ".kicad_symdir", nm + ".kicad_sym")
            if not os.path.exists(p):
                p = os.path.join(symdir, libname + ".kicad_sym")
            doc = parse(open(p, encoding="utf-8").read())[0]
            syms = {val(s): s for s in kids(doc, "symbol")}
            if nm not in syms:
                raise KeyError("symbol %s not in %s" % (nm, p))
            return syms
        syms = load(name)
        node = syms[name]
        ext = kid(node, "extends")
        if ext:
            parent = syms.get(val(ext)) or load(val(ext))[val(ext)]
            node = self._merge(parent, node, val(ext), name)
        return node

    def get(self, lib_id):
        if lib_id not in self._sym:
            raise KeyError("symbol %s is not in the project library (gen/library.py makes it)" % lib_id)
        return self._sym[lib_id]

    def has(self, lib_id):
        return lib_id in self._sym

    @staticmethod
    def _merge(pnode, node, pname, name):
        """Flatten `extends`: the child's properties over the parent's drawing."""
        def props(nd):
            return {val(c): c for c in kids(nd, "property")}
        merged = props(pnode); merged.update(props(node))
        flags = [c for c in pnode[2:] if isinstance(c, list)
                 and head(c) not in ("property", "symbol", "extends")]
        renamed = []
        for sub in kids(pnode, "symbol"):
            sub = list(sub)
            sub[1] = ("str", val(sub).replace(pname, name, 1))
            renamed.append(sub)
        return [node[0], ("str", name)] + flags + list(merged.values()) + renamed

    def define(self, lib_id, text):
        """Register a generated symbol from its s-expression text."""
        node = parse(text)[0]
        self._sym[lib_id] = (node, _pins_of(node))
        return lib_id

    def emit(self, lib_id):
        node, _ = self.get(lib_id)
        name = lib_id.split(":", 1)[1]
        txt = ser(_strip_v10(node))
        return txt.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)

    def units(self, lib_id):
        node, _ = self.get(lib_id)
        us = set()
        for sub in kids(node, "symbol"):
            m = re.match(r".*_(\d+)_\d+$", val(sub))
            if m:
                us.add(int(m.group(1)))
        return sorted(u for u in us if u > 0) or [1]


def library_text(entries):
    """A .kicad_sym library holding `entries`, a list of (name, node)."""
    out = ['(kicad_symbol_lib', '\t(version 20241209)', '\t(generator "halloween1_gen")',
           '\t(generator_version "10.0")']
    for name, node in entries:
        node = list(node)
        node[1] = ("str", name)
        out.append(ser(_strip_v10(node), 1))
    out.append(")")
    return "\n".join(out) + "\n"


# Tokens KiCad 10 writes into its library symbols that the 20250114 (KiCad 9)
# schematic format does not have.  Dropping them keeps the sheet readable by
# both versions; KiCad 10 simply recreates its defaults.
_V10_ONLY = {"in_pos_files", "duplicate_pin_numbers_are_jumpers", "show_name",
             "do_not_autoplace", "jumper_pin_groups"}


def _strip_v10(node):
    out = []
    for c in node:
        if isinstance(c, list):
            if head(c) in _V10_ONLY:
                continue
            out.append(_strip_v10(c))
        else:
            out.append(c)
    return out


def _pins_of(node):
    pins = []
    for sub in kids(node, "symbol"):
        m = re.match(r".*_(\d+)_(\d+)$", val(sub))
        unit = int(m.group(1)) if m else 0
        for p in kids(sub, "pin"):
            at = kid(p, "at")
            pins.append(dict(num=val(kid(p, "number")), name=val(kid(p, "name")),
                             x=num(at, 1), y=num(at, 2), angle=num(at, 3),
                             etype=val(p, 1), unit=unit))
    return pins


SYMS = SymCache()


def pin_xy(lib_id, at, pin_number, mirror=None, unit=None):
    X, Y, rot = at
    _, pins = SYMS.get(lib_id)
    for p in pins:
        if p["num"] == str(pin_number) and (unit is None or p["unit"] in (0, unit)):
            dx, dy = _xform(p["x"], p["y"], rot, mirror)
            return (snap(X + dx), snap(Y + dy))
    raise KeyError("pin %s not on %s" % (pin_number, lib_id))


# ---------------------------------------------------------------------------
# Generated symbols
# ---------------------------------------------------------------------------
def _eff(size=1.27, hide=False, justify=None):
    s = "(effects (font (size %.2f %.2f))" % (size, size)
    if justify:
        s += " (justify %s)" % justify
    if hide:
        s += " (hide yes)"
    return s + ")"


def _hdr(name, ref, value, top, hide_value=False, keywords=""):
    return ['(symbol "%s"' % name,
            '(pin_names (offset 0.762))',
            '(exclude_from_sim no) (in_bom yes) (on_board yes)',
            '(property "Reference" "%s" (at 0 %.2f 0) %s)' % (ref, top + 2.54, _eff()),
            '(property "Value" "%s" (at 0 %.2f 0) %s)' % (value, -top - 2.54, _eff(hide=hide_value)),
            '(property "Footprint" "" (at 0 0 0) %s)' % _eff(hide=True),
            '(property "Datasheet" "~" (at 0 0 0) %s)' % _eff(hide=True),
            '(property "Description" "%s" (at 0 0 0) %s)' % (keywords, _eff(hide=True))]


def _pin(num, name, x, y, ang, length=3.81, kind="passive", nsize=1.02):
    return ('(pin %s line (at %.2f %.2f %d) (length %.2f) (name "%s" %s) (number "%s" %s))'
            % (kind, x, y, ang, length, name, _eff(nsize), num, _eff(1.02)))


def _poly(pts, fill="none", width=0.254):
    xy = " ".join("(xy %.4f %.4f)" % p for p in pts)
    return '(polyline (pts %s) (stroke (width %.3f) (type default)) (fill (type %s)))' % (xy, width, fill)


def _rect(x0, y0, x1, y1, fill="background", width=0.254):
    return ('(rectangle (start %.2f %.2f) (end %.2f %.2f) (stroke (width %.3f) (type default)) (fill (type %s)))'
            % (x0, y0, x1, y1, width, fill))


def make_box(lib_id, units, ref="U", value=None, keywords=""):
    """A multi-unit rectangular symbol.

    `units` is a list of dicts with keys left/right/top/bottom, each a list of
    (number, name[, etype]) with "" names for gaps, and optional `w` (width).
    Pins on the sides are on a 2.54 mm pitch; the box grows to fit.  Drawn the
    way a chip is drawn by hand: inputs on the left, outputs on the right,
    supplies on top, grounds underneath.
    """
    name = lib_id.split(":", 1)[1]
    out = None
    body = []
    maxtop = 0
    for ui, u in enumerate(units, 1):
        L, R, T, B = (u.get(k, []) for k in ("left", "right", "top", "bottom"))
        rows = max(len(L), len(R), 2)
        cols = max(len(T), len(B), 0)
        hh = rows * 2.54 / 2.0
        names = [r[1] for r in L + R if r and r[1]] or [""]
        w = u.get("w") or max(20.32, (max(len(n) for n in names) + 6) * 1.1 * 1.27 * 2)
        w = max(w, (cols + 1) * 2.54 + 2.54)
        w = math.ceil(w / 2.54) * 2.54
        hw = w / 2.0
        trap = u.get("shape") == "trap"
        if trap:
            # A converter: a trapezoid narrowing left to right, the way a
            # converter (or an amplifier) says which way the signal goes.
            # Each side's pins are centred on that side independently, so a
            # short side sits in the middle of a tall one.  The taper is a
            # full 5 mm; a 1 mm taper reads as a drawing error.
            hh = max(len(L), len(R) + 4, 2) * 2.54 / 2.0
            hh2 = hh - 5.08
        maxtop = max(maxtop, hh + (2.54 if T else 0))
        body.append('(symbol "%s_%d_1"' % (name, ui))
        if trap:
            body.append(_poly([(-hw, hh), (hw, hh2), (hw, -hh2), (-hw, -hh), (-hw, hh)], fill="background"))
            topL = (len(L) - 1) * 2.54 / 2.0
            topR = (len(R) - 1) * 2.54 / 2.0
        else:
            body.append(_rect(-hw, hh, hw, -hh))
            topL = topR = hh - 1.27
        for i, row in enumerate(L):
            if row and row[1]:
                body.append(_pin(row[0], row[1], -hw - 3.81, topL - i * 2.54, 0,
                                 kind=row[2] if len(row) > 2 else "passive"))
        for i, row in enumerate(R):
            if row and row[1]:
                body.append(_pin(row[0], row[1], hw + 3.81, topR - i * 2.54, 180,
                                 kind=row[2] if len(row) > 2 else "passive"))
        for i, row in enumerate(T):
            x = -(len(T) - 1) * 2.54 / 2.0 + i * 2.54
            if row and row[1]:
                body.append(_pin(row[0], row[1], x, hh + 3.81, 270,
                                 kind=row[2] if len(row) > 2 else "power_in"))
        for i, row in enumerate(B):
            x = -(len(B) - 1) * 2.54 / 2.0 + i * 2.54
            if row and row[1]:
                body.append(_pin(row[0], row[1], x, -hh - 3.81, 90,
                                 kind=row[2] if len(row) > 2 else "power_in"))
        body.append(')')
    out = _hdr(name, ref, value or name, maxtop, keywords=keywords) + body + ['(embedded_fonts no)', ')']
    return SYMS.define(lib_id, "\n".join(out))


POWER_LIB = "GPiBridge"
HIDDEN_RAIL_NAMES = {"GND"}       # a ground glyph needs no caption


def power_lib_id(net):
    return "%s:PWR_%s" % (POWER_LIB, re.sub(r"[^A-Za-z0-9_+-]", "_", net))


def make_power(lib_id, net, down=False):
    """A power symbol whose pin NAME is the net name (that is how KiCad names
    the net).  `down` draws the ground style bar below the node."""
    name = lib_id.split(":", 1)[1]
    if down:
        gfx = [_poly([(0, 0), (0, -1.27)]), _poly([(-1.27, -1.27), (1.27, -1.27)]),
               _poly([(-0.762, -1.905), (0.762, -1.905)]), _poly([(-0.254, -2.54), (0.254, -2.54)])]
        vy, pa = -3.81, 90
    else:
        gfx = [_poly([(-0.762, 1.27), (0.0, 2.54)]), _poly([(0.0, 0.0), (0.0, 2.54)]),
               _poly([(0.0, 2.54), (0.762, 1.27)])]
        vy, pa = 3.556, 90
    out = ['(symbol "%s"' % name, '(power)', '(pin_numbers (hide yes))',
           '(pin_names (offset 0) (hide yes))', '(exclude_from_sim no) (in_bom yes) (on_board yes)',
           '(property "Reference" "#PWR" (at 0 -3.81 0) %s)' % _eff(hide=True),
           '(property "Value" "%s" (at 0 %.3f 0) %s)' % (net, vy, _eff()),
           '(property "Footprint" "" (at 0 0 0) %s)' % _eff(hide=True),
           '(property "Datasheet" "" (at 0 0 0) %s)' % _eff(hide=True),
           '(symbol "%s_0_1"' % name] + gfx + [')',
           '(symbol "%s_1_1"' % name, _pin("1", net, 0.0, 0.0, pa, 0.0, "power_in"), ')',
           '(embedded_fonts no)', ')']
    return SYMS.define(lib_id, "\n".join(out))


# ---------------------------------------------------------------------------
# A sheet
# ---------------------------------------------------------------------------
class Sch:
    def __init__(self, project, filename, paper="A2", title="", rev="A",
                 company="", comments=(), root=None, sheet_box_uuid=None, date=""):
        self.project, self.filename, self.paper = project, filename, paper
        self.title, self.rev, self.company, self.date = title, rev, company, date
        self.comments = list(comments)
        self.uuid = uuid_for(project, filename)
        self.root = root or self.uuid
        self.inst_path = ("/" + self.root + ("/" + sheet_box_uuid if sheet_box_uuid else ""))
        self.body, self._segs, self._bsegs = [], [], []
        self.pre = []            # items KiCad keeps before lib_symbols (bus aliases)
        self._manual_j = set()
        self.libs = set()
        self._n = 0
        self.W, self.H = PAPER[paper]
        self.texts = []            # (x0, y0, x1, y1, what) for overlap checks
        self.pinpts = []
        self.lcsc = {}            # ref -> LCSC code, for the BOM           # (x, y, ref, pin, is_power) every placed pin, for the touch check
        self.labelpts = []         # (x, y, name, kind) every label anchor, for the net check
        self.items = []            # (x0, y0, x1, y1, what) symbols bodies
        self.refs = {}             # ref -> (x, y)

    def _u(self, *k):
        self._n += 1
        return uuid_for(self.filename, self._n, *k)

    # -- wires, buses, junctions -------------------------------------------
    def wire(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = snap(x0), snap(y0), snap(x1), snap(y1)
        if (x0, y0) != (x1, y1):
            self._segs.append((x0, y0, x1, y1))
        return self

    def wires(self, *pts):
        for i in range(len(pts) - 1):
            self.wire(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        return self

    def bus(self, *pts):
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            self._bsegs.append((snap(a[0]), snap(a[1]), snap(b[0]), snap(b[1])))
        return self

    def bus_entry(self, x, y, dx=2.54, dy=2.54):
        """A bus entry whose wire end is at (x, y) and whose bus end is at
        (x + dx, y + dy)."""
        self.body.append('\t(bus_entry (at %s %s) (size %s %s) (stroke (width 0) (type default)) (uuid %s))'
                         % (g(x), g(y), g(dx), g(dy), q(self._u("be", x, y))))
        return self

    def junction(self, x, y):
        self._manual_j.add((snap(x), snap(y)))
        return self

    def nc(self, x, y):
        self.body.append('\t(no_connect (at %s %s) (uuid %s))' % (g(x), g(y), q(self._u("nc", x, y))))
        return self

    # -- labels ----------------------------------------------------------------
    def label(self, x, y, name, rot=0, justify="left bottom", size=1.27):
        self.labelpts.append((snap(x), snap(y), name, "label"))
        self.body.append('\t(label %s (at %s %s %d) %s (uuid %s))'
                         % (q(name), g(x), g(y), rot, _eff(size, justify=justify), q(self._u("l", name, x, y))))
        self._note_text(x, y, name, rot, justify, size)
        return self

    def glabel(self, x, y, name, shape="bidirectional", rot=0, size=1.27):
        """Global label.  rot 0 = flag to the right of the point, 180 = to the left."""
        justify = "left" if rot in (0, 90) else "right"
        self.body.append(
            '\t(global_label %s (shape %s) (at %s %s %d) (fields_autoplaced yes) %s (uuid %s)\n'
            '\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s %d) %s))'
            % (q(name), shape, g(x), g(y), rot, _eff(size, justify=justify), q(self._u("gl", name, x, y)),
               g(x), g(y), rot, _eff(1.27, hide=True)))
        self._note_text(x + (1.5 if rot == 0 else -1.5), y, name, rot, justify, size)
        return self

    def hlabel(self, x, y, name, shape="bidirectional", rot=0, size=1.27):
        """Hierarchical label: connects to the sheet pin of the same name in
        the parent.  rot 0: flag extends to the right; 180: to the left."""
        justify = "left" if rot in (0, 90) else "right"
        self.labelpts.append((snap(x), snap(y), name, "hlabel"))
        self.body.append('\t(hierarchical_label %s (shape %s) (at %s %s %d) %s (uuid %s))'
                         % (q(name), shape, g(x), g(y), rot, _eff(size, justify=justify),
                            q(self._u("hl", name, x, y))))
        self._note_text(x + (1.5 if rot == 0 else -1.5), y, name, rot, justify, size)
        return self

    def _note_text(self, x, y, s, rot, justify, size):
        w, h = text_w(s, size), text_h(s, size)
        if rot in (90, 270):
            w, h = h, w
        jx = "left" if "left" in justify else "right" if "right" in justify else "center"
        x0 = x if jx == "left" else x - w if jx == "right" else x - w / 2
        y0 = y - h if "bottom" in justify or justify in ("left", "right") else y if "top" in justify else y - h / 2
        self.texts.append((x0, y0, x0 + w, y0 + h, s))

    def text(self, x, y, s, size=1.27, bold=False, italic=False, justify="left bottom", rot=0):
        eff = "(effects (font (size %.2f %.2f)%s%s) (justify %s))" % (
            size, size, " (bold yes)" if bold else "", " (italic yes)" if italic else "", justify)
        self.body.append('\t(text %s (exclude_from_sim no) (at %s %s %d) %s (uuid %s))'
                         % (q(s), g(x), g(y), rot, eff, q(self._u("t", s[:24], x, y))))
        self._note_text(x, y, s, rot, justify, size)
        return self

    def note(self, x, y, s, size=1.27, cols=52, color=(255, 255, 194), w=None):
        """A filled comment box, wrapped to a readable column, placed by its
        top-left corner.  Returns its (w, h)."""
        s = wrap(s, cols)
        ww = w or (text_w(s, size) * 1.15 + 2.5)
        h = text_h(s, size) * 1.05 + 2.4
        ww, h = math.ceil(ww / GRID) * GRID, math.ceil(h / GRID) * GRID
        self.body.append(
            '\t(text_box %s (exclude_from_sim no) (at %s %s 0) (size %s %s)\n'
            '\t\t(margins 0.9525 0.9525 0.9525 0.9525) (stroke (width 0) (type default))\n'
            '\t\t(fill (type color) (color %d %d %d 1)) %s (uuid %s))'
            % (q(s), g(x), g(y), g(ww), g(h), color[0], color[1], color[2],
               _eff(size, justify="left top"), q(self._u("tb", s[:24], x, y))))
        self.texts.append((x, y, x + ww, y + h, "note:" + s[:20]))
        return ww, h

    def rect(self, x, y, w, h, style="dash", width=0.2):
        xy = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        pts = " ".join("(xy %s %s)" % (g(a), g(b)) for a, b in xy)
        self.body.append('\t(polyline (pts %s) (stroke (width %.3f) (type %s)) (uuid %s))'
                         % (pts, width, style, q(self._u("r", x, y))))
        return self

    def line(self, x0, y0, x1, y1, width=0.15, style="default"):
        self.body.append('\t(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width %.3f) (type %s)) (uuid %s))'
                         % (g(x0), g(y0), g(x1), g(y1), width, style, q(self._u("pl", x0, y0, x1, y1))))
        return self

    # -- symbols -----------------------------------------------------------
    def sym(self, lib_id, x, y, rot=0, ref=None, value="", footprint="", unit=1,
            mirror=None, dnp=False, in_bom=True, on_board=True, fields=None,
            ref_at=None, val_at=None, hide_value=False, hide_ref=False, lcsc=None,
            desc=None, fsize=1.27, justify="left"):
        """Place a symbol.  Field positions are ABSOLUTE sheet coordinates when
        given (ref_at/val_at), else to the upper left / lower left of the body.
        Returns a handle with .pin(n) -> (x, y)."""
        x, y = snap(x), snap(y)
        self.libs.add(lib_id)
        u = self._u("s", ref or lib_id, x, y, unit)
        node, pins = SYMS.get(lib_id)
        fang = (-rot) % 360
        if fang >= 180:
            fang -= 180
        bb = _body_bbox(node, unit, with_pins=False)
        # body bbox on the page
        corners = [_xform(px, py, rot, mirror) for px, py in [(bb[0], bb[1]), (bb[2], bb[3]), (bb[0], bb[3]), (bb[2], bb[1])]]
        xs = [x + c[0] for c in corners]; ys = [y + c[1] for c in corners]
        bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
        self.items.append((bx0, by0, bx1, by1, ref or lib_id))
        # KiCad draws a field with (symbol rotation + field angle) == 180 mirrored,
        # which swaps left and right justification; pre-swap so that "left" is left
        flip = ((rot % 360) + fang) % 360 == 180
        if mirror == "y":
            flip = not flip
        j_eff = {"left": "right", "right": "left"}.get(justify, justify) if flip else justify
        below, above = ("top", "bottom") if flip else ("bottom", "top")   # "bottom" = text sits above its anchor
        jh = "" if j_eff == "center" else j_eff + " "
        if ref_at is None:
            ref_at = (bx0, by0 - 0.6)
            rjust = ("right" if flip else "left") + " " + below
        else:
            rjust = jh + below
        if val_at is None:
            val_at = (bx0, by1 + 0.6)
            vjust = ("right" if flip else "left") + " " + above
        else:
            vjust = jh + above
        props = []

        def prop(name, v, at, just, hide=False, size=fsize):
            props.append('\t\t(property %s %s (at %s %s %d) %s)'
                         % (q(name), q(v), g(at[0]), g(at[1]), fang, _eff(size, hide=hide, justify=just)))
        prop("Reference", ref or "#U", ref_at, rjust, hide=hide_ref)
        prop("Value", value, val_at, vjust, hide=hide_value)
        prop("Footprint", footprint, (x, y), "left", hide=True)
        prop("Datasheet", "~", (x, y), "left", hide=True)
        prop("Description", desc or "", (x, y), "left", hide=True)
        if lcsc:
            prop("LCSC", lcsc, (x, y), "left", hide=True)
            self.lcsc[ref or lib_id] = lcsc
        for k, v in (fields or {}).items():
            prop(k, v, (x, y), "left", hide=True)
        # bounding boxes as RENDERED (the reference sits above its anchor, the
        # value below, both justified as asked), for the overlap check
        def _x0(x, w):
            return x if justify == "left" else x - w / 2 if justify == "center" else x - w
        if not hide_ref and ref:
            w = text_w(ref, fsize)
            rx = _x0(ref_at[0], w)
            self.texts.append((rx, ref_at[1] - fsize * 1.4, rx + w, ref_at[1], ref))
        if not hide_value and value:
            w = text_w(value, fsize)
            vx = _x0(val_at[0], w)
            self.texts.append((vx, val_at[1], vx + w, val_at[1] + fsize * 1.4, value))
        pintxt = "".join('\t\t(pin %s (uuid %s))\n' % (q(p["num"]), q(self._u("pin", ref, p["num"], p["unit"])))
                         for p in pins)
        mir = " (mirror %s)" % mirror if mirror else ""
        self.body.append(
            '\t(symbol (lib_id %s) (at %s %s %d)%s (unit %d) (exclude_from_sim no) (in_bom %s) (on_board %s) (dnp %s)\n'
            '\t\t(uuid %s)\n%s\n%s'
            '\t\t(instances (project %s (path %s (reference %s) (unit %d)))))'
            % (q(lib_id), g(x), g(y), rot, mir, unit, "yes" if in_bom else "no",
               "yes" if on_board else "no", "yes" if dnp else "no", q(u), "\n".join(props), pintxt,
               q(self.project), q(self.inst_path), q(ref or "#U"), unit))
        if ref:
            self.refs.setdefault(ref, (x, y))
        for p in pins:
            if p["unit"] in (0, unit):
                px, py = _xform(p["x"], p["y"], rot, mirror)
                self.pinpts.append((snap(x + px), snap(y + py), ref or lib_id, p["num"], False))
        return Placed(self, lib_id, (x, y, rot), mirror, ref, unit)

    def power(self, net, x, y, down=None, rot=0):
        """A power-symbol flag for `net` with its pin at (x, y).  `down` picks
        the ground-style glyph (bar below the node); rot=180 flips either glyph
        so a negative rail can hang from above or a ground can sit on top."""
        if down is None:
            down = net in ("GND", "AGND", "GNDA", "GND_CHASSIS") or net.startswith("GND") or net.startswith("-")
        return self._power_sym(power_lib_id(net), net, x, y, down, rot)

    def _power_sym(self, lib_id, net, x, y, down, rot=0):
        x, y = snap(x), snap(y)
        self.libs.add(lib_id)
        u = self._u("pw", net, x, y)
        vy = y + 4.2 if down else y - 3.9
        vx = x
        if rot == 180:
            vy = y - 4.2 if down else y + 3.9
        vjust = None
        if rot in (90, 270):
            # glyph to the right (90) or left (270) of the pin; the name starts just beyond
            # it, justified away from the pin.  KiCad mirrors the justification of a field
            # whose angle and the symbol's add to 180, so both cases write "right".
            vy = y
            vx = x + (1 if rot == 90 else -1) * (4.6 if down else 3.4)
            vjust = "right"
        # a field's angle is drawn relative to the symbol's: turn the name back to horizontal
        fang = (-rot) % 360
        if fang >= 180:
            fang -= 180
        self.body.append(
            '\t(symbol (lib_id %s) (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
            '\t\t(uuid %s)\n'
            '\t\t(property "Reference" "#PWR" (at %s %s 0) %s)\n'
            '\t\t(property "Value" %s (at %s %s %d) %s)\n'
            '\t\t(property "Footprint" "" (at %s %s 0) %s)\n'
            '\t\t(property "Datasheet" "" (at %s %s 0) %s)\n'
            '\t\t(property "Description" "" (at %s %s 0) %s)\n'
            '\t\t(pin "1" (uuid %s))\n'
            '\t\t(instances (project %s (path %s (reference "#PWR") (unit 1)))))'
            % (q(lib_id), g(x), g(y), rot, q(u), g(x), g(y), _eff(hide=True), q(net), g(vx), g(vy), fang,
               _eff(1.27, hide=net in HIDDEN_RAIL_NAMES, justify=vjust), g(x), g(y), _eff(hide=True), g(x), g(y), _eff(hide=True),
               g(x), g(y), _eff(hide=True), q(self._u("pwp", net, x, y)), q(self.project), q(self.inst_path)))
        w = text_w(net)
        if net not in HIDDEN_RAIL_NAMES:
            x0 = vx if rot == 90 else vx - w if rot == 270 else vx - w / 2
            self.texts.append((x0, vy - 0.9, x0 + w, vy + 0.9, net))
        elif rot in (90, 270):
            self.items.append((min(x, x + (2.6 if rot == 90 else -2.6)), y - 1.27,
                               max(x, x + (2.6 if rot == 90 else -2.6)), y + 1.27, "#gnd"))
        else:
            self.items.append((x - 1.27, y, x + 1.27, y + 2.6, "#gnd"))
        self.pinpts.append((x, y, "#PWR:" + net, "1", True))
        return (x, y)

    # -- child sheet box -------------------------------------------------------
    def sheet(self, x, y, w, h, name, filename, page, pins=()):
        """A sheet symbol.  pins = [(name, shape, side, offset)], side in l/r/t/b,
        offset along that side from the box's top-left corner."""
        u = uuid_for(self.project, "sheetbox", filename)
        x, y, w, h = snap(x), snap(y), snap(w), snap(h)
        ptxt = []
        pos = {}
        for pname, shape, side, off in pins:
            if side == "l":
                px, py, rot = x, y + off, 180
            elif side == "r":
                px, py, rot = x + w, y + off, 0
            elif side == "t":
                px, py, rot = x + off, y, 90
            else:
                px, py, rot = x + off, y + h, 270
            just = "right" if side == "l" else "left"
            ptxt.append('\t\t(pin %s %s (at %s %s %d) %s (uuid %s))'
                        % (q(pname), shape, g(px), g(py), rot, _eff(1.27, justify=just), q(self._u("sp", filename, pname))))
            pos[pname] = (snap(px), snap(py))
        self.body.append(
            '\t(sheet (at %s %s) (size %s %s) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
            '\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid %s)\n'
            '\t\t(property "Sheetname" %s (at %s %s 0) (effects (font (size 1.524 1.524)) (justify left bottom)))\n'
            '\t\t(property "Sheetfile" %s (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left top)))\n'
            '%s\n'
            '\t\t(instances (project %s (path %s (page %s)))))'
            % (g(x), g(y), g(w), g(h), q(u), q(name), g(x), g(y - 0.8), q(filename), g(x), g(y + h + 0.8),
               "\n".join(ptxt), q(self.project), q("/" + self.uuid), q(str(page))))
        self.items.append((x, y, x + w, y + h, "sheet:" + name))
        return u, pos

    # -- output ----------------------------------------------------------------
    def touches(self):
        """Pins that land in the INTERIOR of a wire, and pins that coincide
        with another pin: both make a connection nobody drew.  A power flag on
        a wire's interior is the classic way a rail gets shorted to a signal.
        Call before finalize()."""
        msgs = []
        segs = list(self._segs)

        def interior(seg, p):
            x0, y0, x1, y1 = seg
            px, py = p
            if abs(x0 - x1) < 1e-6 and abs(px - x0) < 1e-6:
                return min(y0, y1) + 1e-6 < py < max(y0, y1) - 1e-6
            if abs(y0 - y1) < 1e-6 and abs(py - y0) < 1e-6:
                return min(x0, x1) + 1e-6 < px < max(x0, x1) - 1e-6
            return False
        ends = set(self._manual_j)
        for (x, y, ref, num, pw) in self.pinpts:
            if (x, y) in ends:
                continue                      # a junction was asked for here: an intended T
            for sg in segs:
                if interior(sg, (x, y)):
                    msgs.append("%s pin %s at (%.2f, %.2f) lands inside a wire (%.1f,%.1f)-(%.1f,%.1f)"
                                % (ref, num, x, y, *sg))
                    break
        seen = {}
        for (x, y, ref, num, pw) in self.pinpts:
            k = (x, y)
            if k in seen and seen[k][0] != ref and not (pw or seen[k][2]):
                msgs.append("%s pin %s and %s pin %s share the point (%.2f, %.2f)" % (seen[k][0], seen[k][1], ref, num, x, y))
            seen.setdefault(k, (ref, num, pw))
        return msgs

    def nets(self):
        """Union-find over wires, pins, labels and power flags, the way KiCad
        connects them: wires meet at endpoints (and at junctions, where a wire
        ENDS on another wire), pins connect at their point, labels join by
        name, power flags are global by name.  Returns a list of problems:
        nets with two different rail names, or a rail together with a label."""
        from collections import Counter, defaultdict
        parent = {}

        def find(a):
            while parent.setdefault(a, a) != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        edges = defaultdict(list)

        def union(a, b):
            edges[a].append(b); edges[b].append(a)
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        segs = list(self._segs)
        pts = set(self._manual_j)
        ends = Counter()
        for x0, y0, x1, y1 in segs:
            ends[(x0, y0)] += 1; ends[(x1, y1)] += 1

        def interior(seg, p):
            x0, y0, x1, y1 = seg
            px, py = p
            if abs(x0 - x1) < 1e-6 and abs(px - x0) < 1e-6:
                return min(y0, y1) + 1e-6 < py < max(y0, y1) - 1e-6
            if abs(y0 - y1) < 1e-6 and abs(py - y0) < 1e-6:
                return min(x0, x1) + 1e-6 < px < max(x0, x1) - 1e-6
            return False
        auto = set()
        for p_ in list(ends):
            if any(interior(sg, p_) for sg in segs):
                pts.add(p_); auto.add(p_)
        # collinear overlapping segments are a connection KiCad makes and nobody drew
        overl = []
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if abs(a[1] - a[3]) < 1e-6 and abs(b[1] - b[3]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                    lo, hi = max(min(a[0], a[2]), min(b[0], b[2])), min(max(a[0], a[2]), max(b[0], b[2]))
                    if hi - lo > 1e-3:
                        overl.append((a, b))
                if abs(a[0] - a[2]) < 1e-6 and abs(b[0] - b[2]) < 1e-6 and abs(a[0] - b[0]) < 1e-6:
                    lo, hi = max(min(a[1], a[3]), min(b[1], b[3])), min(max(a[1], a[3]), max(b[1], b[3]))
                    if hi - lo > 1e-3:
                        overl.append((a, b))
        # split at junction points
        changed = True
        while changed:
            changed = False
            out = []
            for sg in segs:
                cut = next((q for q in pts if interior(sg, q)), None)
                if cut:
                    out.append((sg[0], sg[1], cut[0], cut[1])); out.append((cut[0], cut[1], sg[2], sg[3])); changed = True
                else:
                    out.append(sg)
            segs = out
        for x0, y0, x1, y1 in segs:
            union(("p", x0, y0), ("p", x1, y1))
        names = defaultdict(set)
        for (x, y, ref, num, pw) in self.pinpts:
            union(("p", x, y), ("pin", ref, num))
            if pw:
                union(("p", x, y), ("rail", ref[5:]))
        for (x, y, nm, kind) in self.labelpts:
            union(("p", x, y), (kind, nm))
        groups = defaultdict(list)
        for k in list(parent):
            groups[find(k)].append(k)
        msgs = []
        for a, b in overl:
            msgs.append("OVERLAP: wires (%.1f,%.1f)-(%.1f,%.1f) and (%.1f,%.1f)-(%.1f,%.1f) run on top of each other" % (a + b))
        for g in groups.values():
            rails = sorted({k[1] for k in g if k[0] == "rail"})
            labels = sorted({k[1] for k in g if k[0] in ("label", "hlabel")})
            pins = [k for k in g if k[0] == "pin" and not k[1].startswith("#")]
            if len(rails) > 1 or (rails and labels):
                js = sorted({(k[1], k[2]) for k in g if k[0] == "p" and (k[1], k[2]) in auto and (k[1], k[2]) not in self._manual_j})
                msgs.append("NET MERGE: rails %s with labels %s; pins %s; auto-junctions %s"
                            % (rails, labels, [(k[1], k[2]) for k in pins][:6], ["(%.1f,%.1f)" % j for j in js][:12]))
                # and the path between the two offending names, so the short can be found
                targets = [("rail", r) for r in rails] + [(kd, nm) for kd, nm in {(k[0], k[1]) for k in g if k[0] in ("label", "hlabel")}]
                src, dst = targets[0], targets[1]
                prev = {src: None}; queue = [src]
                while queue and dst not in prev:
                    cur = queue.pop(0)
                    for nb in edges[cur]:
                        if nb not in prev:
                            prev[nb] = cur; queue.append(nb)
                if dst in prev:
                    path = []; cur = dst
                    while cur is not None:
                        path.append(cur); cur = prev[cur]
                    msgs.append("      path: " + " - ".join("(%.1f,%.1f)" % (k[1], k[2]) if k[0] == "p" else ":".join(str(x) for x in k) for k in reversed(path)))
        return msgs

    def finalize(self):
        from collections import Counter

        def interior(seg, p):
            x0, y0, x1, y1 = seg
            px, py = p
            if x0 == x1 == px:
                return min(y0, y1) < py < max(y0, y1)
            if y0 == y1 == py:
                return min(x0, x1) < px < max(x0, x1)
            return False

        pts = set(self._manual_j)
        ends = Counter()
        for x0, y0, x1, y1 in self._segs:
            ends[(x0, y0)] += 1; ends[(x1, y1)] += 1
        for p, c in ends.items():
            if c >= 3:
                pts.add(p)
        for p in list(ends):
            if any(interior(sg, p) for sg in self._segs):
                pts.add(p)
        segs = list(self._segs)
        changed = True
        while changed:
            changed = False
            out = []
            for sg in segs:
                cut = next((p for p in pts if interior(sg, p)), None)
                if cut:
                    out.append((sg[0], sg[1], cut[0], cut[1])); out.append((cut[0], cut[1], sg[2], sg[3]))
                    changed = True
                else:
                    out.append(sg)
            segs = out
        for x0, y0, x1, y1 in segs:
            self.body.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))'
                             % (g(x0), g(y0), g(x1), g(y1), q(self._u("w", x0, y0, x1, y1))))
        for x0, y0, x1, y1 in self._bsegs:
            self.body.append('\t(bus (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))'
                             % (g(x0), g(y0), g(x1), g(y1), q(self._u("b", x0, y0, x1, y1))))
        for (px, py) in sorted(pts):
            self.body.append('\t(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid %s))'
                             % (g(px), g(py), q(self._u("j", px, py))))
        self._segs, self._bsegs, self._manual_j = [], [], set()
        return len(pts)

    def render(self, is_root=True):
        self.finalize()
        libtxt = "\n".join(SYMS.emit(l) for l in sorted(self.libs))
        libtxt = "\n".join("\t\t" + ln if ln.strip() else ln for ln in libtxt.split("\n"))
        tb = ["\t\t(title %s)" % q(self.title)] + (["\t\t(date %s)" % q(self.date)] if self.date else []) + ["\t\t(rev %s)" % q(self.rev)]
        if self.company:
            tb.append("\t\t(company %s)" % q(self.company))
        for i, c in enumerate(self.comments[:9], start=1):
            tb.append("\t\t(comment %d %s)" % (i, q(c)))
        si = '\t(sheet_instances (path "/" (page "1")))\n' if is_root else ""
        return ("(kicad_sch (version %s) (generator \"eeschema\") (generator_version \"9.0\")\n"
                "\t(uuid %s)\n\t(paper %s)\n\t(title_block\n%s\n\t)\n%s"
                "\t(lib_symbols\n%s\n\t)\n%s\n%s\t(embedded_fonts no)\n)\n"
                % (SCH_VERSION, q(self.uuid), q(self.paper), "\n".join(tb), "".join(l + "\n" for l in self.pre), libtxt, "\n".join(self.body), si))

    def save(self, outdir, is_root=True):
        path = os.path.join(outdir, self.filename)
        open(path, "w", encoding="utf-8").write(self.render(is_root))
        return path

    # -- checks ----------------------------------------------------------------
    def overlaps(self):
        """Text that lands on other text or on a symbol body, and anything off
        the page.  Returns a list of messages."""
        msgs = []
        W, H = self.W, self.H
        for (x0, y0, x1, y1, s) in self.texts + self.items:
            if x0 < 8 or y0 < 8 or x1 > W - 8 or y1 > H - 25:
                msgs.append("off page: %r at (%.0f,%.0f)-(%.0f,%.0f)" % (s[:24], x0, y0, x1, y1))
        T = self.texts
        for i in range(len(T)):
            a = T[i]
            for j in range(i + 1, len(T)):
                b = T[j]
                if a[0] < b[2] - 0.2 and b[0] < a[2] - 0.2 and a[1] < b[3] - 0.2 and b[1] < a[3] - 0.2:
                    msgs.append("text overlap: %r / %r at (%.0f,%.0f)" % (a[4][:20], b[4][:20], a[0], a[1]))
            for b in self.items:
                if b[4].startswith("sheet:"):
                    continue
                if a[0] < b[2] - 0.3 and b[0] < a[2] - 0.3 and a[1] < b[3] - 0.3 and b[1] < a[3] - 0.3:
                    msgs.append("text on symbol: %r on %s at (%.0f,%.0f)" % (a[4][:20], b[4], a[0], a[1]))
        # a wire through a note: it strikes through the text, or the box hides it
        for (x0, y0, x1, y1, s) in T:
            if not s.startswith("note:"):
                continue
            for (a, b, c, d) in self._segs:
                if (min(a, c) < x1 - 0.1 and x0 + 0.1 < max(a, c)
                        and min(b, d) < y1 - 0.1 and y0 + 0.1 < max(b, d)) or \
                        (a == c and x0 < a < x1 and min(b, d) < y1 and y0 < max(b, d)) or \
                        (b == d and y0 < b < y1 and min(a, c) < x1 and x0 < max(a, c)):
                    msgs.append("wire through note: %r, wire (%.1f,%.1f)-(%.1f,%.1f)" % (s[5:25], a, b, c, d))
        # the title block's lines, measured: KiCad's block holds about 98 mm of
        # text_w() at 1.5 mm (calibrated on GPiBridge's A3 sheet: a 93.6 mm line
        # fitted, a 107.0 mm one ran through the frame)
        for i, c in enumerate(self.comments[:9], start=1):
            if text_w(c, 1.5) > 98:
                msgs.append("title block: comment %d is too long (%.0f of 98 mm): %r" % (i, text_w(c, 1.5), c[:30]))
        if text_w(self.company, 1.5) > 98:
            msgs.append("title block: the company line is too long (%.0f of 98 mm)" % text_w(self.company, 1.5))
        return msgs


def _xform(px, py, rot, mirror):
    """A symbol point (y up) to its offset on the sheet (y down).  KiCad rotates first and
    mirrors after, on the sheet (checked against its ERC: a P-FET at 270 degrees, mirror
    y); the two orders differ only for 90 and 270 degrees."""
    a = math.radians(-rot)
    x, y = px * math.cos(a) + py * math.sin(a), px * math.sin(a) - py * math.cos(a)
    if mirror == "y":
        x = -x
    elif mirror == "x":
        y = -y
    return (x, y)


def _body_bbox(node, unit, with_pins=True):
    """Bounding box of a symbol unit's graphics (library coordinates, y up),
    with its pins' ends unless with_pins is False."""
    xs, ys = [], []
    for sub in kids(node, "symbol"):
        m = re.match(r".*_(\d+)_\d+$", val(sub))
        u = int(m.group(1)) if m else 0
        if u not in (0, unit):
            continue
        for c in sub:
            if not isinstance(c, list):
                continue
            h = head(c)
            if h == "rectangle":
                s, e = kid(c, "start"), kid(c, "end")
                xs += [num(s, 1), num(e, 1)]; ys += [num(s, 2), num(e, 2)]
            elif h in ("polyline",):
                for p in kids(kid(c, "pts"), "xy"):
                    xs.append(num(p, 1)); ys.append(num(p, 2))
            elif h == "circle":
                ce, r = kid(c, "center"), num(kid(c, "radius"), 1)
                xs += [num(ce, 1) - r, num(ce, 1) + r]; ys += [num(ce, 2) - r, num(ce, 2) + r]
            elif h == "arc":
                for k in ("start", "mid", "end"):
                    p = kid(c, k); xs.append(num(p, 1)); ys.append(num(p, 2))
            elif h == "pin" and with_pins:
                at = kid(c, "at"); xs.append(num(at, 1)); ys.append(num(at, 2))
    if not xs:
        return (-1.27, -1.27, 1.27, 1.27)
    return (min(xs), min(ys), max(xs), max(ys))


class Placed:
    def __init__(self, sch, lib_id, at, mirror, ref, unit):
        self.sch, self.lib_id, self.at, self.mirror, self.ref, self.unit = sch, lib_id, at, mirror, ref, unit

    def pin(self, n):
        return pin_xy(self.lib_id, self.at, n, self.mirror, self.unit)

    @property
    def x(self):
        return self.at[0]

    @property
    def y(self):
        return self.at[1]

    def __repr__(self):
        return "<%s %s at %s>" % (self.ref, self.lib_id, self.at)
