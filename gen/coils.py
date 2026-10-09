#!/usr/bin/env python3
"""The PCB coils as footprints: one per coil type in gen/parts.py COILS.

    python3 gen/coils.py        check each coil's copper; print its turns, L and R
                                (gen/library.py writes the footprints: OWL:Coil_PEND, ...)

A coil is one footprint whose own copper is the spiral.  It is a KiCad net tie
(net_tie_pad_groups), so DRC accepts copper that joins pad 1 (one bridge output, e.g.
PEND1_A) to pad 2 (the other, PEND1_B); the board routes to both pads as to any part's.

Frame and conventions
---------------------
- The coil's centre is the footprint's origin; x right, y down (KiCad).  Angles run
  from +x toward +y, which is clockwise seen from the top.  The terminals (pads 1 and
  2) are at the +y side.  Place coils on the front, unflipped: a flip swaps F.Cu with
  B.Cu and In1.Cu with In2.Cu.
- r_out and r_in (COILS) are the copper's outer and inner edges: nothing of the spiral
  lies outside r_out or inside r_in.  Each layer's track centre runs from r_out - w/2 to
  r_in + w/2 as an Archimedean spiral, drawn as circular arcs of 30 degrees through
  three points of the spiral (each within 0.2 um of it; 1-degree line segments would
  be 18 000 lines, 3 MB, per coil).
- The layers are in series and all turn the same way, so their fields add:
      F.Cu outer -> inner, pad 3, In1.Cu inner -> outer, pad 4,
      In2.Cu outer -> inner, pad 5, B.Cu inner -> outer (COIL_LEV: a straight B.Cu track)
  Current into pad 1 circulates clockwise seen from the top, on every layer, so its
  field at the centre points down, from F.Cu toward B.Cu.
- Each layer makes COILS "turns" plus a fraction of a turn that brings the next
  layer change round to where it belongs (pads 1 and 2 side by side, the two inner
  layer changes on opposite sides of the hole): about one extra turn per coil in all,
  counted in L and R below.  The pitch is then (r_out - r_in - w) / turns-on-the-layer.
- Pads 1 and 2 (0.9 mm, 0.4 mm drill, plated, mask open) sit TERM_R outside r_out, at
  +y, TERM_PITCH apart.  Pad 4 (the outer layer change) sits beside pad 1; pads 3 and 5
  (inner) sit in the hole.  Pads 3-5 are 1.1 mm, 0.3 mm drill, tented, and have no net
  (the symbol has two pins): the spiral lands on their annulus, outside the hole's
  clearance, because DRC holds copper of no net to the board's hole clearance.  A board
  track reaching pad 1 or 2 radially, from outside, may be at most 2 * (TERM_R -
  KEEPOUT) - 0.1 = 0.8 mm wide over its last millimetre: wider, it would enter the
  keep-out and come within clearance of the outer turn.

Keep-outs and courtyard (the board generator relies on these)
--------------------------------------------------------------
- A rule area on every copper layer the coil uses, out to r_out + KEEPOUT (gen/layout.py
  COIL_KEEPOUT), centre hole included: no tracks, no vias, no zone fill.
- A second rule area, no zone fill only, over the same disc plus the terminals (pads
  1, 2 and 4), so that no pour squeezes between them as slivers.
- Courtyard on F.CrtYd and B.CrtYd: a circle r_out + COURTYARD, with a bump round the
  terminals.  It is the only check that keeps two coils' copper apart: DRC compares
  no copper of no net with other copper of no net, so two spirals may overlap without a
  clearance error, but never without a courtyard error.
- COIL_LEV (three layers, F.Cu, In1.Cu, In2.Cu): a DRV5055 sits in its hole on the
  bottom.  B.Cu carries no spiral; the coil's inner end comes down at pad 5 and leaves
  along a straight B.Cu track to pad 2, parallel to the +y axis.  On B.Cu the track and
  via keep-out is open over the sensor's hole (r < r_in - SENSOR_HOLE) and a corridor
  CORRIDOR_W wide centred on the +y axis, from the hole out past the keep-out, for the
  sensor's three lines; zone fill stays out of all of it.  B.CrtYd has a hole of the
  same radius, so the sensor's courtyard fits.  The +y axis points at the perch's
  socket (gen/mech.py), so the coil's two pads and the sensor's lines all head there.

Physics: L and R are computed with sim/physics/magnetics.py for the copper drawn here:
Mohan's current-sheet inductance for each layer (its d_out and d_in are the copper's
edges), plus the exact mutual inductance between the layers' turns, taken as coaxial
circles at their centre radii; R in squares of 1 oz copper at 20 C, leads and
via barrels included.
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from parts import COILS, PARTS
import layout
import project

TAU = 2 * math.pi
LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
# copper centres below the top copper's, in metres: JLC041611-7628 with 35 um copper on
# every layer, 0.2104 mm prepreg and a 1.065 mm core (gen/board.py's stack-up)
Z = {"F.Cu": 0.0, "In1.Cu": -0.2454e-3, "In2.Cu": -1.3454e-3, "B.Cu": -1.5908e-3}
PLATING = 20e-6                   # via barrel copper, m (JLCPCB: 18 um minimum)

PAD_D, PAD_DRILL = 0.9, 0.4       # pads 1 and 2: plated, so the board reaches them on any layer
VIA_D, VIA_DRILL = 1.1, 0.3       # pads 3-5, the layer changes
GAP = 0.2                         # the coil's own copper to its own pads: never closer
TERM_R = 0.75                     # the terminals' centres sit this far outside r_out
TERM_PITCH = 1.6                  # terminal centre to centre (a 0.7 mm gap between pads 1 and 2)
COURTYARD = 0.25                  # beyond r_out (the TMAG5273 between the pendulum coils)
KEEPOUT = layout.COIL_KEEPOUT     # beyond r_out: 0.3
POUR_MARGIN = 0.3                 # the no-fill area's margin round the terminals
ARC_DEG = 30.0                    # each arc of the spiral spans at most this
# a line landing on a pad of no net stays this far from its hole (KiCad's default hole
# clearance, above the project's 0.2 mm, plus 10 um)
HOLE_GAP = max(0.25, project.LIMITS["min_hole_clearance"]) + 0.01
MIN_TURN_GAP = 0.15               # the closest any two turns may come
SAMPLE_TOL = 0.005                # check() follows each arc by 0.25 mm chords, which sit up to
                                  # 3 um inside it: gaps are judged to within this
# COIL_LEV: the Hall sensor's hole and the corridor its lines leave by, on B.Cu
SENSOR_HOLE = 0.5                 # the hole is r < r_in - 0.5
CORRIDOR_W = 3.0
CORRIDOR_GAP = 0.25               # the coil's copper keeps this far from the corridor
EXIT_W = 0.8                      # the B.Cu track from pad 5 out to pad 2


def polar(r, th):
    return (r * math.cos(th), r * math.sin(th))


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Coil:
    """The copper, pads and outlines of one coil type, in millimetres and radians."""

    def __init__(self, key):
        c = COILS[key]
        self.key = key
        self.name = "Coil_" + key.split("_", 1)[1]
        self.r_out, self.r_in = c["r_out"], c["r_in"]
        self.n, self.w, self.nl = c["turns"], c["width"], c["layers"]
        self.R1 = self.r_out - self.w / 2            # outermost track centre
        self.R2 = self.r_in + self.w / 2             # innermost
        self.r_t = self.r_out + TERM_R               # pads 1, 2 and the outer layer change
        self.r_h = self.r_in - GAP - VIA_D / 2       # the inner layer changes
        self.dterm = 2 * math.asin(TERM_PITCH / 2 / self.r_t)
        self.spirals = []        # dict(layer, th0, th1, r0, r1): the centre line
        self.leads = []          # dict(layer, a, b, w): straight tracks
        self.pads = {}           # number -> dict(x, y, d, drill)
        self.links = []          # which items are meant to touch: (item, item)
        self.lev = key == "COIL_LEV"
        assert self.r_h - VIA_D / 2 > 0.5, key
        if self.nl == 4 and not self.lev:
            self._four()
        elif self.nl == 3 and self.lev:
            self._lev()
        else:
            raise SystemExit("gen/coils.py draws 4-layer coils and the 3-layer COIL_LEV, not %s" % key)

    # --- construction -------------------------------------------------------------------
    def _spiral(self, layer, th0, turns, inward):
        r0, r1 = (self.R1, self.R2) if inward else (self.R2, self.R1)
        s = dict(layer=layer, th0=th0, th1=th0 + TAU * turns, r0=r0, r1=r1, turns=turns,
                 id="spiral %s" % layer)
        self.spirals.append(s)
        return s

    def _pad(self, num, xy, via):
        self.pads[num] = dict(x=xy[0], y=xy[1], d=VIA_D if via else PAD_D,
                              drill=VIA_DRILL if via else PAD_DRILL, via=via, id="pad %s" % num)

    def _land(self, num, toward, w):
        """Where a line of width w coming from `toward` ends on pad `num` of no net: its
        copper stops HOLE_GAP from the hole and overlaps the annulus."""
        p = self.pads[num]
        c = (p["x"], p["y"])
        d = dist(c, toward)
        k = (p["drill"] / 2 + HOLE_GAP + w / 2) / d
        return (c[0] + (toward[0] - c[0]) * k, c[1] + (toward[1] - c[1]) * k)

    def _lead(self, layer, a, b, w=None, links=()):
        ld = dict(layer=layer, a=a, b=b, w=self.w if w is None else w,
                  id="lead %s %d" % (layer, len(self.leads)))
        self.leads.append(ld)
        for other in links:
            self.links.append((ld["id"], other))
        return ld

    def _join_end(self, sp, end, num, w=None):
        """A radial lead from a spiral's end to pad `num`."""
        th = sp["th1"] if end else sp["th0"]
        r = sp["r1"] if end else sp["r0"]
        q = polar(r, th)
        p = self.pads[num]
        if p["via"]:
            far = self._land(num, q, self.w if w is None else w)
        else:
            far = (p["x"], p["y"])                    # pads with a net may take a line to the centre
        self._lead(sp["layer"], q, far, w, links=(sp["id"], p["id"]))

    def _four(self):
        """Four layers.  Terminals at +y: pad 2, pad 1, pad 4, clockwise (seen from the top).
        F.Cu and In1.Cu make N turns (In1.Cu a sliver more, to reach pad 4); In2.Cu and
        B.Cu make about N + 1/2, which puts pad 5 opposite pad 3 in the hole."""
        n, d = self.n, self.dterm
        a1, a2, a4 = math.pi / 2 + d / 2, math.pi / 2 - d / 2, math.pi / 2 + 1.5 * d
        self._pad("1", polar(self.r_t, a1), False)
        self._pad("2", polar(self.r_t, a2), False)
        self._pad("3", polar(self.r_h, a1), True)
        self._pad("4", polar(self.r_t, a4), True)
        a5 = a4 + math.pi
        self._pad("5", polar(self.r_h, a5), True)
        f = self._spiral("F.Cu", a1, n, inward=True)
        i1 = self._spiral("In1.Cu", a1, n + d / TAU, inward=False)
        i2 = self._spiral("In2.Cu", a4, n + 0.5, inward=True)
        fb = ((a2 - a5) / TAU) % 1.0
        b = self._spiral("B.Cu", a5, n + fb, inward=False)
        self._join_end(f, False, "1")
        self._join_end(f, True, "3")
        self._join_end(i1, False, "3")
        self._join_end(i1, True, "4")
        self._join_end(i2, False, "4")
        self._join_end(i2, True, "5")
        self._join_end(b, False, "5")
        self._join_end(b, True, "2")

    def _lev(self):
        """Three layers and a B.Cu exit.  Pad 5 sits in the hole just left of the corridor
        (seen from the top), and the exit runs straight along +y from it to pad 2; pad 1
        and pad 4 follow pad 2 clockwise.  F.Cu makes N + 1/2 turns, which puts pad 3 at
        the far (-y) side of the hole, away from the sensor's corridor."""
        n, d = self.n, self.dterm
        cw = CORRIDOR_W / 2
        x_e = -(cw + CORRIDOR_GAP + max(VIA_D, EXIT_W) / 2)
        p5 = (x_e, math.sqrt(self.r_h ** 2 - x_e ** 2))
        p2 = (x_e, math.sqrt(self.r_t ** 2 - x_e ** 2))
        a5, a2 = math.atan2(p5[1], p5[0]), math.atan2(p2[1], p2[0])
        a1 = a2 + d
        a4 = a1 + d
        a3 = a1 + math.pi
        self._pad("1", polar(self.r_t, a1), False)
        self._pad("2", p2, False)
        self._pad("3", polar(self.r_h, a3), True)
        self._pad("4", polar(self.r_t, a4), True)
        self._pad("5", p5, True)
        f = self._spiral("F.Cu", a1, n + 0.5, inward=True)
        i1 = self._spiral("In1.Cu", a3, n + ((a4 - a3) / TAU) % 1.0, inward=False)
        i2 = self._spiral("In2.Cu", a4, n + ((a5 - a4) / TAU) % 1.0, inward=True)
        self._join_end(f, False, "1")
        self._join_end(f, True, "3")
        self._join_end(i1, False, "3")
        self._join_end(i1, True, "4")
        self._join_end(i2, False, "4")
        self._join_end(i2, True, "5")
        start = self._land("5", p2, EXIT_W)
        self._lead("B.Cu", start, p2, EXIT_W, links=("pad 5", "pad 2"))
        self.exit_x = x_e

    # --- derived numbers ----------------------------------------------------------------
    def copper_layers(self):
        return LAYERS[:self.nl] if not self.lev else LAYERS[:3]

    def via_count(self):
        return sum(1 for p in self.pads.values() if p["via"])

    def turns(self):
        return [s["turns"] for s in self.spirals]

    def pitch(self, s):
        return (self.R1 - self.R2) / s["turns"]

    def point(self, s, th):
        r = s["r0"] + (s["r1"] - s["r0"]) * (th - s["th0"]) / (s["th1"] - s["th0"])
        return polar(r, th)

    def spiral_length(self, s, steps=20000):
        """Arc length of a spiral's centre line (Simpson's rule)."""
        k = (s["r1"] - s["r0"]) / (s["th1"] - s["th0"])
        f = lambda th: math.hypot(s["r0"] + k * (th - s["th0"]), k)
        h = (s["th1"] - s["th0"]) / steps
        tot = f(s["th0"]) + f(s["th1"])
        for i in range(1, steps):
            tot += (4 if i % 2 else 2) * f(s["th0"] + i * h)
        return tot * h / 3

    def terminals(self):
        """The pads round the edge (1, 2, 4): (angle, radius of the pad)."""
        return [(math.atan2(p["y"], p["x"]), p["d"] / 2) for k, p in self.pads.items() if k in ("1", "2", "4")]

    def bump(self, margin):
        """The angular range (th0, th1) and outer radius of the terminals plus a margin."""
        lo, hi = [], []
        for th, rad in self.terminals():
            a = math.asin((rad + margin) / self.r_t)
            lo.append(th - a)
            hi.append(th + a)
        return min(lo), max(hi), self.r_t + max(r for _, r in self.terminals()) + margin

    # --- outlines -----------------------------------------------------------------------
    def disc(self, r, step_deg=2.0):
        """A polygon containing the circle of radius r (its edges touch the circle)."""
        m = int(round(360 / step_deg))
        rr = r / math.cos(math.pi / m)
        return [polar(rr, TAU * i / m) for i in range(m)]

    def disc_and_bump(self, r, margin, step_deg=2.0):
        """The circle r, plus the terminals' bump (as a star-shaped polygon)."""
        t0, t1, rb = self.bump(margin)
        assert rb > r
        m = int(round(360 / step_deg))
        rr = r / math.cos(math.pi / m)
        pts = [polar(rb, t0)]
        k = int(math.ceil((t1 - t0) / math.radians(step_deg)))
        rbb = rb / math.cos((t1 - t0) / k / 2)
        pts += [polar(rbb, t0 + (t1 - t0) * (i + 0.5) / k) for i in range(k)]
        pts.append(polar(rb, t1))
        pts.append(polar(rr, t1))
        span = TAU - (t1 - t0)
        k = int(math.ceil(span / math.radians(step_deg)))
        pts += [polar(rr / math.cos(span / k / 2), t1 + span * (i + 0.5) / k) for i in range(k)]
        pts.append(polar(rr, t0))
        return pts

    def keyhole(self, r):
        """COIL_LEV's B.Cu track keep-out: the disc r without the sensor's hole and the
        corridor along +y."""
        cw = CORRIDOR_W / 2
        rh = self.r_in - SENSOR_HOLE
        ya = math.sqrt(r * r - cw * cw)
        yh = math.sqrt(rh * rh - cw * cw)
        pts = []
        t_a, t_b = math.atan2(ya, cw), math.atan2(ya, -cw) - TAU     # outer circle, the long way
        k = int(math.ceil((t_a - t_b) / math.radians(2.0)))
        rr = r / math.cos((t_a - t_b) / k / 2)
        pts.append((cw, ya))
        pts += [polar(rr, t_a - (t_a - t_b) * (i + 0.5) / k) for i in range(k)]
        pts.append((-cw, ya))
        pts.append((-cw, yh))
        t_c, t_d = math.atan2(yh, -cw), math.atan2(yh, cw) + TAU      # round the hole, the long way
        k = int(math.ceil((t_d - t_c) / math.radians(2.0)))
        rr = rh / math.cos((t_d - t_c) / k / 2)                       # chords outside r_h: all of the hole stays open
        pts += [polar(rr, t_c + (t_d - t_c) * (i + 0.5) / k) for i in range(k)]
        pts.append((cw, yh))
        return pts

    # --- checks -------------------------------------------------------------------------
    def check(self):
        """Look at the copper as the fab will make it: the items that touch must be exactly
        the series chain pad 1 - F.Cu - pad 3 - In1.Cu - pad 4 - In2.Cu - pad 5 - (B.Cu) -
        pad 2; everything else at least GAP apart (turns of one spiral MIN_TURN_GAP), and no
        line within HOLE_GAP of a hole of no net.  Returns (problems, min turn gap, min
        other gap)."""
        problems = []
        items = []           # (id, layer, kind, data, half-width)
        for s in self.spirals:
            pts = []
            th, th1 = s["th0"], s["th1"]
            while True:
                pts.append(self.point(s, th))
                if th >= th1:
                    break
                r = s["r0"] + (s["r1"] - s["r0"]) * (th - s["th0"]) / (th1 - s["th0"])
                th = min(th1, th + 0.25 / r)                      # 0.25 mm chords: 3 um from the arc at r 3 mm
            items.append((s["id"], s["layer"], "poly", pts, self.w / 2))
        for ld in self.leads:
            items.append((ld["id"], ld["layer"], "poly", [ld["a"], ld["b"]], ld["w"] / 2))
        for num, p in self.pads.items():
            for layer in LAYERS:                                  # plated: copper on every layer
                items.append((p["id"], layer, "pad", (p["x"], p["y"]), p["d"] / 2))
        links = set()
        for a, b in self.links:
            links.add((a, b))
            links.add((b, a))
        # every segment (a pad is a segment of no length), with its arc length along its item
        segs = []
        for idx, (iid, layer, kind, data, hw) in enumerate(items):
            if kind == "pad":
                segs.append((iid, layer, data, data, hw, idx, 0.0))
            else:
                acc = 0.0
                for j in range(len(data) - 1):
                    segs.append((iid, layer, data[j], data[j + 1], hw, idx, acc))
                    acc += dist(data[j], data[j + 1])
        # a grid of cells; each segment is entered in every cell its box, grown by half the
        # largest distance worth checking, touches: two segments that close share a cell
        cell = 1.5
        reach = (max(PAD_D, VIA_D, EXIT_W, self.w) + GAP) / 2 + 0.05
        grid = {}
        boxes = []
        for si, (iid, layer, a, b, hw, idx, acc) in enumerate(segs):
            gx0 = int(math.floor((min(a[0], b[0]) - reach) / cell))
            gx1 = int(math.floor((max(a[0], b[0]) + reach) / cell))
            gy0 = int(math.floor((min(a[1], b[1]) - reach) / cell))
            gy1 = int(math.floor((max(a[1], b[1]) + reach) / cell))
            cells = [(layer, gx, gy) for gx in range(gx0, gx1 + 1) for gy in range(gy0, gy1 + 1)]
            boxes.append(cells)
            for k in cells:
                grid.setdefault(k, []).append(si)
        touching = set()
        min_turn, min_other = 1e9, 1e9
        local = 4 * (self.w + 1.0)                                # same spiral, this close along it: neighbours
        for si, A in enumerate(segs):
            cand = set()
            for k in boxes[si]:
                cand.update(grid[k])
            for sj in cand:
                if sj <= si:
                    continue
                B = segs[sj]
                same = A[5] == B[5]
                if same and (items[A[5]][2] != "poly" or abs(A[6] - B[6]) < local):
                    continue
                if not same and (A[0], B[0]) in touching and (A[0], B[0]) in links:
                    continue
                d = seg_seg(A[2], A[3], B[2], B[3]) - A[4] - B[4]
                if same:                                          # one spiral against its next turn
                    min_turn = min(min_turn, d)
                    if d < MIN_TURN_GAP - SAMPLE_TOL:
                        problems.append("%s: turns %.3f mm apart near (%.2f, %.2f)" % (A[0], d, A[2][0], A[2][1]))
                    continue
                if A[0] == B[0]:                                  # a pad with itself on another layer
                    continue
                if d < 1e-9:
                    touching.add((A[0], B[0]))
                    touching.add((B[0], A[0]))
                elif (A[0], B[0]) not in links:
                    min_other = min(min_other, d)
                    if d < GAP - SAMPLE_TOL:
                        problems.append("%s and %s on %s only %.3f mm apart" % (A[0], B[0], A[1], d))
        for a, b in sorted(touching):
            if a < b and (a, b) not in links:
                problems.append("%s touches %s: a short" % (a, b))
        for a, b in self.links:
            if (a, b) not in touching:
                problems.append("%s does not reach %s" % (a, b))
        # holes of no net: no line within HOLE_GAP of the drill (DRC's hole clearance)
        for num, p in self.pads.items():
            if not p["via"]:
                continue
            c = (p["x"], p["y"])
            for iid, layer, kind, data, hw in items:
                if kind != "poly":
                    continue
                for j in range(len(data) - 1):
                    g = pt_seg(c, data[j], data[j + 1]) - hw - p["drill"] / 2
                    if g < HOLE_GAP - 0.01 - SAMPLE_TOL:
                        problems.append("%s comes %.3f mm from pad %s's hole" % (iid, g, num))
                        break
        # the copper that touches is one path, pad 1 to pad 2, through the spirals in layer
        # order and pads 3, 4, 5 between them: a series coil, nothing shorted, nothing open
        adj = {}
        for a, b in touching:
            adj.setdefault(a, set()).add(b)
        path, prev, cur = ["pad 1"], None, "pad 1"
        while cur != "pad 2":
            nxt = [x for x in adj.get(cur, ()) if x != prev]
            if len(nxt) != 1:
                problems.append("the coil branches or stops at %s (next: %s)" % (cur, sorted(nxt)))
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
            if len(path) > 4 * len(items):
                problems.append("the coil's copper loops")
                break
        names = [p for p in path if not p.startswith("lead")]
        want = (["pad 1"] + sum(([s["id"], "pad %d" % (3 + i)] for i, s in enumerate(self.spirals)), [])[:-1]
                + (["pad 5"] if self.lev else []) + ["pad 2"])
        if names != want:
            problems.append("the series chain is %s, not %s" % (" - ".join(names), " - ".join(want)))
        return problems, min_turn, min_other


def seg_seg(a, b, c, d):
    """Distance between segments ab and cd (points allowed)."""
    if a == b and c == d:
        return dist(a, c)
    if a == b:
        return pt_seg(a, c, d)
    if c == d:
        return pt_seg(c, a, b)
    if _cross(a, b, c, d):
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def pt_seg(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    if L2 == 0:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _cross(a, b, c, d):
    def o(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 0) - (v < 0)
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


# ------------------------------------------------------------------------------------------
# Physics (sim/physics/magnetics.py: numpy and scipy, imported only here)
# ------------------------------------------------------------------------------------------
_PHYS = {}


def physics(key):
    """L (H), R (ohm, DC, 20 C) and the pieces, for the copper drawn."""
    if key in _PHYS:
        return _PHYS[key]
    sim = os.path.join(ROOT, "sim", "physics")
    if sim not in sys.path:
        sys.path.insert(0, sim)
    import magnetics as mg
    c = Coil(key)
    mm = 1e-3
    t = mg.OZ                                      # 1 oz on every layer
    L_self = sum(mg.L_mohan(s["turns"], 2 * c.r_out * mm, 2 * c.r_in * mm) for s in c.spirals)
    M = 0.0
    for s1 in c.spirals:
        for s2 in c.spirals:
            if s1 is s2:
                continue
            d = abs(Z[s1["layer"]] - Z[s2["layer"]])
            n1, n2 = max(1, int(round(s1["turns"]))), max(1, int(round(s2["turns"])))
            ra = [(c.R1 - (c.R1 - c.R2) * i / (n1 - 1)) * mm for i in range(n1)]
            rb = [(c.R1 - (c.R1 - c.R2) * i / (n2 - 1)) * mm for i in range(n2)]
            m = sum(float(mg.mutual_coaxial_loops(x, y, d)) for x in ra for y in rb)
            M += m * (s1["turns"] / n1) * (s2["turns"] / n2)
    L = L_self + M
    R_spiral = sum(mg.R_trace(c.spiral_length(s) * mm, c.w * mm, t) for s in c.spirals)
    R_leads = sum(mg.R_trace(dist(ld["a"], ld["b"]) * mm, ld["w"] * mm, t) for ld in c.leads)
    via_r = mg.RHO_CU * 1.6e-3 / (math.pi * VIA_DRILL * mm * PLATING)
    R = R_spiral + R_leads + c.via_count() * via_r
    # the toolkit's own estimate for the same coil with N turns on every layer, as a check
    zl = [Z[l] for l in c.copper_layers()]
    L_toolkit = float(mg.L_multilayer(c.n, c.R1 * mm, c.R2 * mm, zl))
    out = dict(L=float(L), L_self=float(L_self), M=float(M), R=float(R), R_spiral=float(R_spiral),
               R_leads=float(R_leads), R_vias=c.via_count() * via_r, L_toolkit=L_toolkit,
               length=sum(c.spiral_length(s) for s in c.spirals))
    _PHYS[key] = out
    return out


def value(key):
    """The schematic value: the inductance in whole microhenries, or to 0.1 uH below 20 uH
    (the tokens' tank capacitors are chosen from it)."""
    L = physics(key)["L"] * 1e6
    return "%suH coil" % (("%.1f" % L) if L < 20 else "%.0f" % L)


# ------------------------------------------------------------------------------------------
# The footprint
# ------------------------------------------------------------------------------------------
def _f(v):
    s = "%.6f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _xy(p):
    return "%s %s" % (_f(p[0]), _f(p[1]))


def _arc(a, m, b, w, layer):
    return '\t(fp_arc (start %s) (mid %s) (end %s) (stroke (width %s) (type solid)) (layer "%s"))' % (
        _xy(a), _xy(m), _xy(b), _f(w), layer)


def _line(a, b, w, layer):
    return '\t(fp_line (start %s) (end %s) (stroke (width %s) (type solid)) (layer "%s"))' % (
        _xy(a), _xy(b), _f(w), layer)


def _circle(r, w, layer, c=(0.0, 0.0)):
    return '\t(fp_circle (center %s) (end %s) (stroke (width %s) (type solid)) (fill none) (layer "%s"))' % (
        _xy(c), _xy((c[0] + r, c[1])), _f(w), layer)


def _zone(name, layers, pts, tracks=True, pour=True):
    na = lambda b: "not_allowed" if b else "allowed"
    out = ['\t(zone', '\t\t(net 0)', '\t\t(net_name "")',
           '\t\t(layers %s)' % " ".join('"%s"' % l for l in layers),
           '\t\t(name "%s")' % name, '\t\t(hatch edge 0.5)', '\t\t(connect_pads (clearance 0))',
           '\t\t(min_thickness 0.25)', '\t\t(filled_areas_thickness no)',
           '\t\t(keepout (tracks %s) (vias %s) (pads allowed) (copperpour %s) (footprints allowed))'
           % (na(tracks), na(tracks), na(pour)),
           '\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))',
           '\t\t(polygon (pts']
    row = []
    for p in pts:
        row.append("(xy %s)" % _xy(p))
        if len(row) == 6:
            out.append("\t\t\t" + " ".join(row))
            row = []
    if row:
        out.append("\t\t\t" + " ".join(row))
    out += ['\t\t))', '\t)']
    return "\n".join(out)


def _courtyard(c, layer):
    """A circle r_out + COURTYARD with a bump round the terminals: two arcs and two lines."""
    t0, t1, rb = c.bump(COURTYARD)
    rc = c.r_out + COURTYARD
    out = [_arc(polar(rc, t1), polar(rc, (t0 + t1) / 2 + math.pi), polar(rc, t0), 0.05, layer),
           _line(polar(rc, t0), polar(rb, t0), 0.05, layer),
           _arc(polar(rb, t0), polar(rb, (t0 + t1) / 2), polar(rb, t1), 0.05, layer),
           _line(polar(rb, t1), polar(rc, t1), 0.05, layer)]
    return out


def description(key):
    c = Coil(key)
    ph = physics(key)
    turns = c.turns()
    layers = "/".join(s["layer"].replace(".Cu", "") for s in c.spirals)
    pitches = [c.pitch(s) for s in c.spirals]
    txt = ("PCB coil (%s), the footprint's own copper, a net tie between pads 1 and 2: %d layers in series "
           "(%s), %s turns (%.1f in all), r %.2f-%.2f mm (copper edges), %.2f mm track at %.3f-%.3f mm pitch; "
           "L %.1f uH, R %.2f ohm (DC, 1 oz, 20 C); %d layer changes (pads 3-5). "
           "Pads 1, 2 at +y, %.2f mm out; current into pad 1 turns clockwise seen from the top. "
           "Keep-out to r %.2f, courtyard r %.2f. "
           % (key, len(c.spirals), layers, " + ".join("%.3g" % t for t in turns), sum(turns),
              c.r_in, c.r_out, c.w, min(pitches), max(pitches), ph["L"] * 1e6, ph["R"], c.via_count(),
              c.r_t, c.r_out + KEEPOUT, c.r_out + COURTYARD))
    if c.lev:
        txt += ("B.Cu: no spiral; the inner end leaves along x = %.2f to pad 2; the sensor's hole "
                "(r < %.2f) and a %.1f mm corridor along +y stay open to tracks. " % (
                    c.exit_x, c.r_in - SENSOR_HOLE, CORRIDOR_W))
    return txt + "Generated by gen/coils.py"


def footprint(key):
    c = Coil(key)
    name = c.name
    out = ['(footprint "%s"' % name, '\t(version 20240108)', '\t(generator "owl_gen")', '\t(layer "F.Cu")',
           '\t(descr "%s")' % description(key).replace('"', "'"),
           '\t(tags "PCB coil spiral inductor net tie")',
           '\t(property "Reference" "REF**" (at 0 -1 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
           '\t(property "Value" "%s" (at 0 1 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))' % name,
           '\t(attr through_hole exclude_from_pos_files exclude_from_bom)',
           '\t(net_tie_pad_groups "%s")' % ", ".join(sorted(c.pads))]
    step = math.radians(ARC_DEG)
    for s in c.spirals:
        m = int(math.ceil((s["th1"] - s["th0"]) / step - 1e-9))
        for i in range(m):
            ta = s["th0"] + (s["th1"] - s["th0"]) * i / m
            tb = s["th0"] + (s["th1"] - s["th0"]) * (i + 1) / m
            out.append(_arc(c.point(s, ta), c.point(s, (ta + tb) / 2), c.point(s, tb), c.w, s["layer"]))
    for ld in c.leads:
        out.append(_line(ld["a"], ld["b"], ld["w"], ld["layer"]))
    for num in sorted(c.pads):
        p = c.pads[num]
        layers = '"*.Cu"' if p["via"] else '"*.Cu" "*.Mask"'
        out.append('\t(pad "%s" thru_hole circle (at %s) (size %s %s) (drill %s) (layers %s) (remove_unused_layers no))'
                   % (num, _xy((p["x"], p["y"])), _f(p["d"]), _f(p["d"]), _f(p["drill"]), layers))
    # keep-outs
    rk = c.r_out + KEEPOUT
    if c.lev:
        out.append(_zone("%s: no tracks, vias or fill" % name, LAYERS[:3], c.disc(rk)))
        out.append(_zone("%s: B.Cu, no tracks or vias but the sensor's" % name, ["B.Cu"], c.keyhole(rk), pour=False))
    else:
        out.append(_zone("%s: no tracks, vias or fill" % name, LAYERS, c.disc(rk)))
    out.append(_zone("%s: no fill" % name, LAYERS, c.disc_and_bump(rk, POUR_MARGIN), tracks=False))
    # courtyards, fab
    out += _courtyard(c, "F.CrtYd")
    out += _courtyard(c, "B.CrtYd")
    if c.lev:
        out.append(_circle(c.r_in - SENSOR_HOLE, 0.05, "B.CrtYd"))
    out.append(_circle(c.r_out, 0.1, "F.Fab"))
    out.append(_circle(c.r_in, 0.1, "F.Fab"))
    if c.lev:
        cw, rh = CORRIDOR_W / 2, c.r_in - SENSOR_HOLE
        out.append(_circle(rh, 0.1, "B.Fab"))
        for x in (-cw, cw):
            out.append(_line((x, math.sqrt(rh * rh - cw * cw)), (x, c.r_out + KEEPOUT), 0.1, "B.Fab"))
    out.append(')')
    return name, "\n".join(out) + "\n"


def generated():
    """{footprint name: text} for gen/library.py."""
    out = {}
    for key in COILS:
        c = Coil(key)
        problems, _, _ = c.check()
        if problems:
            raise SystemExit("gen/coils.py: %s's copper fails its checks:\n  " % key + "\n  ".join(problems[:20]))
        want = value(key)
        have = PARTS[key]["value"]
        if have != want:
            raise SystemExit("gen/parts.py: %s's value is %r but its copper makes %r (gen/coils.py)" % (key, have, want))
        if PARTS[key]["fp"].split(":", 1)[1] != c.name:
            raise SystemExit("gen/parts.py: %s's footprint should be OWL:%s" % (key, c.name))
        name, text = footprint(key)
        out[name] = text
    return out


def main():
    print("%-10s %-11s %-6s %-26s %6s %6s %5s %4s %7s %7s %8s  %s"
          % ("coil", "footprint", "layers", "turns per layer", "turns", "gap", "minG", "vias",
             "L uH", "R ohm", "L(N) uH", "checks"))
    bad = 0
    for key in COILS:
        c = Coil(key)
        problems, min_turn, min_other = c.check()
        ph = physics(key)
        turns = c.turns()
        gap = min(c.pitch(sp) for sp in c.spirals) - c.w
        print("%-10s %-11s %-6d %-26s %6.2f %6.3f %5.2f %4d %7.2f %7.2f %8.2f  %s"
              % (key, c.name, len(c.spirals), " ".join("%.3f" % t for t in turns), sum(turns),
                 gap, min_other, c.via_count(), ph["L"] * 1e6, ph["R"], ph["L_toolkit"] * 1e6,
                 "ok" if not problems else "%d PROBLEMS" % len(problems)))
        for p in problems[:10]:
            print("      " + p)
        bad += bool(problems)
        if PARTS[key]["value"] != value(key):
            print("      gen/parts.py says %r; the copper makes %r" % (PARTS[key]["value"], value(key)))
            bad += 1
    print("(gap: the closest turns, pitch - width (check() measured %s); minG: the closest other copper of "
          "the coil; L(N): magnetics.L_multilayer with exactly 'turns' on every layer, for comparison)"
          % "the same to within its 0.005 mm chords")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
