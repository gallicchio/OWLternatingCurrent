"""The silkscreen the parts bring, board by board.  Called by gen/board.py after the
copper and before a turned board is turned, so it works in each board's own frame.

The top of every board is the scene (gen/art.py draws it): no designators, no footprint
outlines, nothing the art did not draw.  Underneath, for whoever debugs it: each part's
own outline and pin-1 mark, widened to JLCPCB's 0.15 mm (the passives' two dashes
dropped: beside an 0402 they say nothing and crowd the labels), and its designator,
0.8 mm high, beside it where it is clear of exposed copper, vias, the board's edge, the
other labels and the spell book's art, and nearest its own part; a designator that does
not fit goes to the fab layer only, which the assembly drawing prints.

JLCPCB prints nothing finer than 0.15 mm lines and nothing legible under 0.8 mm text.
"""
import math
import pcbnew

STROKE = 0.15
TEXT_H = 0.8
REF_W = 0.7
EDGE = 0.5               # silkscreen to the board's edge (gen/art.py keeps the same)
PAD_GAP = 0.15           # silkscreen to exposed copper
GAP = 0.12               # between two silkscreen items
PASSIVES = ("R_0402", "C_0402", "R_0603", "C_0603", "R_0805", "C_0805", "R_1206", "C_1206")


def mm(v):
    return pcbnew.FromMM(float(v))


def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


class Grid:
    """Rectangles (x0, y0, x1, y1, what) binned in 5 mm cells, for quick overlap tests."""
    CELL = 5.0

    def __init__(self):
        self.cells = {}

    def _keys(self, r):
        c = self.CELL
        for i in range(int(math.floor(r[0] / c)), int(math.floor(r[2] / c)) + 1):
            for j in range(int(math.floor(r[1] / c)), int(math.floor(r[3] / c)) + 1):
                yield (i, j)

    def add(self, r):
        for k in self._keys(r):
            self.cells.setdefault(k, []).append(r)

    def hit(self, r):
        for k in self._keys(r):
            for b in self.cells.get(k, ()):
                if r[0] < b[2] and b[0] < r[2] and r[1] < b[3] and b[1] < r[3]:
                    return b[4]
        return None


class Silk:
    def __init__(self, board, name, refs, B, edge):
        """refs: this board's footprints; B: KiCad -> board millimetres; edge: the board's
        outline, inset by EDGE (board millimetres)."""
        self.board, self.name, self.B, self.edge = board, name, B, edge
        self.fps = [f for f in board.GetFootprints() if f.GetReference() in refs]
        self.grid = {pcbnew.F_SilkS: Grid(), pcbnew.B_SilkS: Grid()}
        self.placed = 0
        self.to_fab = 0
        self.why = {}

    def box(self, bb, grow=0.0):
        x0, y0 = self.B(pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
        x1, y1 = self.B(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        return (x0 - grow, y0 - grow, x1 + grow, y1 + grow)

    def inside(self, r):
        return all(point_in_poly(x, y, self.edge) for x, y in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])))

    # ---- what the labels must keep clear of ---------------------------------------------
    def obstacles(self, art_items):
        top, bot = pcbnew.F_SilkS, pcbnew.B_SilkS
        for fp in self.fps:
            back = fp.GetLayer() == pcbnew.B_Cu
            for pad in fp.Pads():
                r = self.box(pad.GetBoundingBox(), PAD_GAP) + ("%s pad %s" % (fp.GetReference(), pad.GetNumber()),)
                th = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                if th or not back:
                    self.grid[top].add(r)
                if th or back:
                    self.grid[bot].add(r)
            fab = [it for it in fp.GraphicalItems() if it.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab)
                   and it.GetClass() == "PCB_SHAPE"]
            if fab and not str(fp.GetFPID().GetLibItemName()).startswith("Coil_"):
                bb = fab[0].GetBoundingBox()
                for it in fab[1:]:
                    bb.Merge(it.GetBoundingBox())
                self.grid[bot if back else top].add(self.box(bb) + ("%s body" % fp.GetReference(),))
        for t in self.board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                r = self.box(t.GetBoundingBox(), 0.05) + ("via",)
                self.grid[top].add(r)
                self.grid[bot].add(r)
        for layer, r in art_items:
            self.grid[layer].add(r + ("art",))

    # ---- the parts' own silkscreen -------------------------------------------------------
    def footprint_graphics(self):
        for fp in self.fps:
            name = str(fp.GetFPID().GetLibItemName())
            back = fp.GetLayer() == pcbnew.B_Cu
            for it in list(fp.GraphicalItems()):
                if it.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                    continue
                if it.GetLayer() == pcbnew.F_SilkS or name.startswith(PASSIVES):
                    fp.Remove(it)                    # the scene's side, or a passive's dashes
                    continue
                if it.GetClass() == "PCB_TEXT":
                    it.SetTextThickness(mm(STROKE))
                elif not it.IsSolidFill() and pcbnew.ToMM(it.GetWidth()) < STROKE:
                    it.SetWidth(mm(STROKE))
                r = self.box(it.GetBoundingBox())
                if not self.inside(r) or self._on_pad(it, fp):
                    fp.Remove(it)                    # past the board's edge (a header's body), or on a pad
                    continue
                self.grid[it.GetLayer()].add(self.box(it.GetBoundingBox(), GAP) + ("%s outline" % fp.GetReference(),))
            if not back:
                for f in (fp.Reference(), fp.Value()):
                    if f.GetLayer() == pcbnew.F_SilkS:
                        f.SetLayer(pcbnew.F_Fab)

    def _on_pad(self, it, fp, gap=0.05):
        """Whether a silkscreen line of the part runs over one of its pads (the solder
        mask's opening would clip it)."""
        if it.GetClass() != "PCB_SHAPE" or it.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            return False
        a, b = self.B(it.GetStart()), self.B(it.GetEnd())
        hw = pcbnew.ToMM(it.GetWidth()) / 2 + gap
        for pad in fp.Pads():
            x0, y0, x1, y1 = self.box(pad.GetBoundingBox())
            # sample the line: any point within hw of the pad's box
            n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
            for i in range(n + 1):
                x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
                if x0 - hw <= x <= x1 + hw and y0 - hw <= y <= y1 + hw:
                    return True
        return False

    # ---- designators ---------------------------------------------------------------------
    def references(self):
        bodies = {}
        for fp in self.fps:
            # only the parts underneath, where the labels go (not the coils: a label inside
            # a coil's circle is not "nearer" to the coil)
            if fp.GetLayer() != pcbnew.B_Cu or str(fp.GetFPID().GetLibItemName()).startswith("Coil_"):
                continue
            bb = None
            for pad in fp.Pads():
                # (Merge in place: its return value is a view of a temporary)
                if bb is None:
                    bb = pad.GetBoundingBox()
                else:
                    bb.Merge(pad.GetBoundingBox())
            for it in fp.GraphicalItems():
                if it.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab) and it.GetClass() == "PCB_SHAPE" and bb is not None:
                    bb.Merge(it.GetBoundingBox())
            bodies[fp.GetReference()] = self.box(bb) if bb is not None else None
        for fp in sorted(self.fps, key=lambda f: _refkey(f.GetReference())):
            ref = fp.GetReference()
            t = fp.Reference()
            back = fp.GetLayer() == pcbnew.B_Cu
            if not back or bodies.get(ref) is None or str(fp.GetFPID().GetLibItemName()).startswith("Coil_"):
                self._to_fab(fp)
                continue
            layer = pcbnew.B_SilkS
            t.SetLayer(layer)
            t.SetVisible(True)
            t.SetTextSize(pcbnew.VECTOR2I(mm(REF_W), mm(TEXT_H)))
            t.SetTextThickness(mm(STROKE))
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            t.SetMirrored(True)
            x0, y0, x1, y1 = bodies[ref]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            done = False
            for gap in (0.2, 0.5, 0.9):
                for side in "UDLR":
                    for angle in ((0,) if side in "UD" else (0, 90)):
                        t.SetTextAngleDegrees(angle)
                        t.SetPosition(self._P(cx, cy, fp))
                        ex = self.box(t.GetEffectiveTextShape().BBox())
                        hw, hh = (ex[2] - ex[0]) / 2, (ex[3] - ex[1]) / 2
                        x, y = {"U": (cx, y0 - gap - hh), "D": (cx, y1 + gap + hh),
                                "L": (x0 - gap - hw, cy), "R": (x1 + gap + hw, cy)}[side]
                        t.SetPosition(self._P(x, y, fp))
                        r = self.box(t.GetEffectiveTextShape().BBox())
                        if not self.inside(r):
                            self.why["outside the board"] = self.why.get("outside the board", 0) + 1
                            continue
                        h = self.grid[layer].hit(r)
                        if h:
                            key = h.split(" ")[-1] if " " in h else h
                            self.why[key] = self.why.get(key, 0) + 1
                            continue
                        if not _nearest_is(ref, r, bodies):
                            self.why["nearer another part"] = self.why.get("nearer another part", 0) + 1
                            continue
                        self.grid[layer].add((r[0] - GAP, r[1] - GAP, r[2] + GAP, r[3] + GAP, "%s ref" % ref))
                        done = True
                        break
                    if done:
                        break
                if done:
                    break
            if done:
                self.placed += 1
            else:
                self._to_fab(fp)

    def _P(self, x, y, fp):
        # board millimetres back to KiCad's, through a footprint's own frame-free position
        # (B is a translation here: the board is not turned yet)
        bx, by = self.B(fp.GetPosition())
        p = fp.GetPosition()
        return pcbnew.VECTOR2I(p.x + mm(x - bx), p.y + mm(y - by))

    def _to_fab(self, fp):
        """The designator on the fab layer only (the assembly drawing): the footprint's own
        ${REFERENCE} text sized to the part, the field itself hidden."""
        t = fp.Reference()
        back = fp.GetLayer() == pcbnew.B_Cu
        t.SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
        t.SetVisible(False)
        self.to_fab += 1
        for it in fp.GraphicalItems():
            if it.GetClass() == "PCB_TEXT" and "${REFERENCE}" in it.GetText() and it.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
                bb = fp.GetBoundingBox(False)
                side = min(pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight()))
                h = max(0.25, min(1.0, 0.4 * side))
                it.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
                it.SetTextThickness(mm(max(0.04, 0.15 * h)))
                it.SetPosition(fp.GetPosition())
                it.SetKeepUpright(True)


def _nearest_is(ref, r, bodies):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2

    def dist(b):
        return math.hypot(max(b[0] - cx, 0, cx - b[2]), max(b[1] - cy, 0, cy - b[3]))
    mine = dist(bodies[ref])
    return all(dist(b) > mine + 0.05 for k, b in bodies.items() if k != ref and b is not None)


def _refkey(ref):
    order = {"U": 0, "Q": 1, "Y": 2, "L": 3, "J": 4, "F": 5, "D": 6, "SW": 7, "TP": 8, "R": 9, "C": 10}
    letters = "".join(c for c in ref if c.isalpha())
    num = int("".join(c for c in ref if c.isdigit()) or 0)
    return (order.get(letters, 11), letters, num)


def art_boxes(art, name, F):
    """The art's silkscreen on one board as rectangles to keep clear of (each stroke's
    segments one by one, so a big circle does not shadow its inside)."""
    out = []
    layers = {"F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS, "F.Mask": pcbnew.F_SilkS}
    for lname, items in art.art(name).items():
        if lname not in layers:
            continue
        layer = layers[lname]
        for it in items:
            k = it[0]
            if k == "polyline":
                w = it[2] / 2 + GAP
                for (ax, ay), (bx, by) in zip(it[1], it[1][1:]):
                    out.append((layer, (min(ax, bx) - w, min(ay, by) - w, max(ax, bx) + w, max(ay, by) + w)))
            elif k == "poly":
                xs, ys = [p[0] for p in it[1]], [p[1] for p in it[1]]
                out.append((layer, (min(xs) - GAP, min(ys) - GAP, max(xs) + GAP, max(ys) + GAP)))
            elif k in ("circle", "arc"):
                _, cx, cy, r = it[:4]
                w = it[-1] / 2 + GAP
                n = max(8, int(2 * math.pi * r / 1.5))
                a0, a1 = (0.0, 360.0) if k == "circle" else (it[4], it[5])
                pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                        cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    out.append((layer, (min(ax, bx) - w, min(ay, by) - w, max(ax, bx) + w, max(ay, by) + w)))
            elif k == "text":
                _, s, x, y, h, ang, just = it
                wdt = art.text_width(s, h) + h
                hw, hh = (wdt / 2, h) if abs(ang) % 180 < 45 else (h, wdt / 2)
                dx = {"left": hw, "right": -hw, "center": 0.0}[just] if abs(ang) % 180 < 45 else 0.0
                if lname.startswith("B.") and abs(ang) % 180 < 45:
                    dx = -dx
                out.append((layer, (x + dx - hw, y - hh, x + dx + hw, y + hh)))
    return out


def apply(board, name, refs, B, edge, art=None, F=None):
    S = Silk(board, name, refs, B, edge)
    S.obstacles(art_boxes(art, name, F) if art else [])
    S.footprint_graphics()
    S.references()
    return S
