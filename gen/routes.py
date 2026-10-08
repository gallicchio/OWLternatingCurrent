"""The copper laid by plan, board by board, before the router: Raspberry Pi's regulator
and the supply rings under the RP2354A (GPiBridge's, turned with the chip), the
RP2354A's decoupling stubs, the coil bridges' wide lines to their coils and to 12 V,
via fan-outs for the planes, then the router for everything else.

Everything is computed from the pads' positions on the board, so it follows the
placement.  Router coordinates are each board's millimetres from the corner of its
outline's bounding box (gen/board.py makes the Router).

GPiBridge's routes are written in GPiBridge's board frame (their RP2354A at (15, 10),
turned 180 degrees) and Raspberry Pi's (their RP2354A at the origin): Proxy lays them
in ours (gen/placement.py turns the whole corner 90 degrees clockwise to face the USB-C
at the back edge).  Their In1 was ground and In2 signals; here In2 is ground and In1
the 4.8 V plane with a ground island under the RP2354A's corner, so their In2 lines go
on our In1, inside that island.
"""
import json, math, os
import pcbnew
import layout as L
import placement as PL
import routing as RT
import router as RR

HERE = os.path.dirname(os.path.abspath(__file__))
CH = 0.3                                     # chamfer at each corner
G_U1 = (15.0, 10.0)                          # GPiBridge's RP2354A


def role(r):
    return PL.ROLES.get(r, r)


class Pads:
    """(ref, pad number) -> (x, y, net) for one board's footprints, in router millimetres."""

    def __init__(self, board, B, refs):
        self.xy, self.net, self.of = {}, {}, {}
        for fp in board.GetFootprints():
            if fp.GetReference() not in refs:
                continue
            for p in fp.Pads():
                key = (fp.GetReference(), p.GetNumber())
                if key in self.xy:
                    continue
                self.xy[key] = B(p.GetPosition())
                self.net[key] = p.GetNetname()
                self.of.setdefault(p.GetNetname(), []).append(key)

    def p(self, who, num):
        return self.xy[(role(who), num)]

    def n(self, who, num):
        return self.net[(role(who), num)]


def chamfer(pts, c=CH):
    """Cut every right-angle corner of a polyline at 45 degrees."""
    out = [pts[0]]
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        ux, uy = b[0] - a[0], b[1] - a[1]
        vx, vy = d[0] - b[0], d[1] - b[1]
        la, lb = math.hypot(ux, uy), math.hypot(vx, vy)
        if la < 1e-9 or lb < 1e-9:
            continue
        cos = (ux * vx + uy * vy) / (la * lb)
        if abs(cos) < 1e-6 and min(la, lb) > 2 * c:
            out.append((b[0] - ux / la * c, b[1] - uy / la * c))
            out.append((b[0] + vx / lb * c, b[1] + vy / lb * c))
        else:
            out.append(b)
    out.append(pts[-1])
    return out


# ======================================================================================
# GPiBridge's frame
# ======================================================================================
class Frame:
    """GPiBridge's board millimetres <-> ours (router millimetres on the base, whose
    outline starts at 0, 0)."""

    def __init__(self):
        self.mx, self.my = L.MCU

    def T(self, p):
        x, y = p
        return (round(self.mx - (y - G_U1[1]), 4), round(self.my + (x - G_U1[0]), 4))

    def Tinv(self, p):
        x, y = p
        return (round(G_U1[0] + (y - self.my), 4), round(G_U1[1] - (x - self.mx), 4))

    def T_rpi(self, p):
        """Raspberry Pi's frame (their RP2354A at the origin, 0 degrees) to ours."""
        return self.T((G_U1[0] - p[0], G_U1[1] - p[1]))


class Proxy:
    """Lay copper given in GPiBridge's frame: their layers 0 (F.Cu), 1 (In2), 2 (B.Cu)
    onto ours F.Cu, In1 (inside the RP2354A's ground island), B.Cu."""
    LMAP = {0: 0, 1: 1, 2: 2}

    def __init__(self, R, fr):
        self.R, self.fr = R, fr

    def track(self, net, L_, a, b, width):
        return self.R.track(net, self.LMAP[L_], self.fr.T(a), self.fr.T(b), width)

    def polyline(self, net, L_, pts, width):
        return self.R.polyline(net, self.LMAP[L_], [self.fr.T(p) for p in pts], width)

    def via(self, net, x, y, size=RT.VIA):
        return self.R.via(net, *self.fr.T((x, y)), size=size)


# ======================================================================================
# The base: the RP2354A's corner
# ======================================================================================
def rpi_core(R, pads):
    """GPiBridge's rpi_core: Raspberry Pi's regulator copper (gen/rpi_minimal/
    regulator.json), the 1.1 V and 3.3 V rings under the chip, their vias, and the
    stubs from the supply pins to the rings, turned with our U4."""
    fr = Frame()
    d = json.load(open(os.path.join(HERE, "rpi_minimal", "regulator.json")))
    names = {}
    for f in d["footprints"]:
        if f["ref"] == "U1":
            for num, theirs in f["pads"].items():
                ours = pads.net.get(("U4", num))
                if ours:
                    names[theirs] = ours
    for fp in R.board.GetFootprints():
        if fp.GetReference() in [role(r) for r in ("decap:49", "decap:50", "decap:46", "L2", "rp:r33")]:
            for pad in fp.Pads():
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    for z in d["zones"]:
        for lname in z["layers"]:
            R.zone(names[z["net"]], pcbnew.F_Cu if lname == "F.Cu" else pcbnew.B_Cu,
                   [fr.T_rpi(p) for p in z["outline"]], priority=z["priority"], clearance=z["clearance"],
                   min_width=z["min_width"], connect="solid" if z["pad_connection"] == 2 else "thermal")
    for t in d["tracks"]:
        R.track(names[t["net"]], 0 if t["layer"] == "F.Cu" else 2, fr.T_rpi(t["start"]), fr.T_rpi(t["end"]),
                t["width"])
    vias = [(names[v["net"]], fr.T_rpi(v["at"]), (v["diameter"], v["drill"])) for v in d["vias"]]
    for net, at, size in vias:
        R.via(net, *at, size=size)
    for i, (n1, a1, s1) in enumerate(vias):
        for n2, a2, s2 in vias[i + 1:]:
            if n1 == n2 and math.hypot(a1[0] - a2[0], a1[1] - a2[1]) <= (s1[0] + s2[0]) / 2 + 1e-6:
                R.track(n1, 2, a1, a2, min(s1[0], s2[0]))
    # their USB lines from pins 51 and 52 to the 27 R (from RP-010328-CA)
    for pin, pts in (("52", [(0.4, -3.438), (0.4, -4.0), (-1.1, -5.5), (-1.1, -6.92)]),
                     ("51", [(0.8, -3.438), (0.775, -3.463), (0.775, -4.101), (-0.1, -4.976), (-0.1, -6.92)])):
        R.polyline(pads.net[("U4", pin)], 0, [fr.T_rpi(p) for p in pts], 0.15)
    # the rings: 1.1 V inside, 3.3 V outside; squares, so the turn does not matter
    cx, cy = L.MCU

    def sq(r):
        return [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
    R.zone("+1V1", pcbnew.F_Cu, sq(2.2), priority=3, clearance=0.15, min_width=0.2, connect="solid", item=False)
    R.zone("+3V3", pcbnew.F_Cu, sq(2.8), priority=1, clearance=0.15, min_width=0.15, connect="solid", item=False)
    # the bars and arcs, in GPiBridge's frame (their chip at 180 degrees), turned to ours
    gx, gy = G_U1

    def rect(net, x0, y0, x1, y1):
        corners = [(gx + x0, gy + y0), (gx + x1, gy + y0), (gx + x1, gy + y1), (gx + x0, gy + y1)]
        R._poly_item(net, 0, [fr.T(p) for p in corners])
    a, b = 1.85, 2.2
    for x0, y0, x1, y1 in ((-b, -b, b, -a), (-b, a, b, b), (-b, -b, -a, b), (a, -b, b, b)):
        rect("+1V1", x0, y0, x1, y1)
    a, b, h = 2.35, 2.8, 0.25
    u1 = {num: fr.Tinv(xy) for (ref, num), xy in pads.xy.items() if ref == "U4"}
    c6 = u1["6"][1] - gy
    c23 = u1["23"][0] - gx
    c39 = u1["39"][1] - gy
    rect("+3V3", c23 + h, -b, b, -a); rect("+3V3", a, -b, b, c6 - h)
    rect("+3V3", a, c6 + h, b, b); rect("+3V3", -b, a, b, b); rect("+3V3", -b, c39 + h, -a, b)
    rect("+3V3", -b, -b, -a, c39 - h); rect("+3V3", -b, -b, c23 - h, -a)
    R.via("+3V3", *fr.T((gx + 2.5, gy - 2.5)))
    for p in ((0.488, -2.15), (-2.15, -0.8)):
        R.via("+1V1", *fr.T_rpi(p), size=(0.6, 0.25))
    mine = {num: xy for (ref, num), xy in pads.xy.items() if ref == "U4"}
    for num in ("1", "11", "20", "30", "38", "44", "45"):
        x, y = mine[num]
        R.track("+3V3", 0, (x, y), _toward(x, y, cx, cy, 2.575), 0.2)
    for num in ("6", "23", "39"):
        x, y = mine[num]
        R.track("+1V1", 0, (x, y), _toward(x, y, cx, cy, 2.025), 0.2)


def _toward(x, y, cx, cy, r):
    dx, dy = x - cx, y - cy
    if abs(dx) > abs(dy):
        return (cx + math.copysign(r, dx), y)
    return (x, cy + math.copysign(r, dy))


def rpi_local(R, pads):
    """GPiBridge's decoupling stubs, USB-C lines and the regulator's output, in their
    frame through the proxy (gen/placement.py put each part where GPiBridge did)."""
    fr = Frame()
    X = Proxy(R, fr)
    # their part names -> our roles
    their = {"U1": "U4", "C17": "decap:38", "C12": "decap:39", "C21": "decap:44", "C18": "decap:45",
             "C16": "decap:30", "C13": "decap:1", "C14": "decap:11", "C15": "decap:20", "C10": "decap:6",
             "C11": "decap:23", "C19": "decap:54", "C20": "decap:53", "TP3": "tp:1v1", "R1": "usb:r_dm",
             "R2": "usb:r_dp", "R4": "usb:r_cc1", "R5": "usb:r_cc2", "J1": "J2", "U4": "U2", "C3": "ldo:cout",
             "TP2": "tp:3v3"}

    def p(ref, num):
        return fr.Tinv(pads.p(their[ref], num))

    def N(ref, num):
        return pads.n(their[ref], num)

    def line(ref, num, pts, width=0.2, layer=0):
        X.polyline(N(ref, num), layer, pts, width)

    u1 = lambda num: p("U1", num)
    (x, y), (cx, cy) = u1("38"), p("C17", "1")
    line("C17", "1", [(x, y), (cx + (cy - y), y), (cx, cy)])
    # (GPiBridge ran pin 39's line to C12 across the front of pins 40-43, which it left
    # unused; here they are the ADC inputs, so the router joins C12 after they escape)
    line("C21", "1", [p("C21", "1"), u1("44")])
    (x, y), (cx, cy) = u1("45"), p("C18", "1")
    line("C18", "1", [(x, y), (cx + (cy - y), y), (cx, cy)])
    (x, y), (cx, cy) = u1("30"), p("C16", "1")
    # (GPiBridge's ran out level beside pin 29 first, which left GPIO's pin 29 no room
    # for its via: here a short stub, then up at 45 degrees to the capacitor, moved up)
    line("C16", "1", [(x, y), (x, y - 0.45), (cx, y - 0.45 - abs(x - cx)), (cx, cy)])
    (x, y) = u1("1")
    # pin 1's 3.3 V line: straight out of the pin, a step across to the capacitors' column
    # (0.35 mm further out than GPiBridge's, clear of GPIO0's way out), down it through
    # C13, C14 and C15 (in our frame: their T)
    mx, my = fr.T((x, y))
    out = 1.0 if fr.T(p("C13", "1"))[1] > my else -1.0
    colx = fr.T(p("C13", "1"))[0]
    yend = fr.T(p("C15", "1"))[1]
    y1 = my + out * 0.6
    R.polyline(N("C13", "1"), 0, [(mx, my), (mx, y1), (colx, y1 + out * abs(mx - colx)), (colx, yend)], 0.25)
    yg = p("C13", "2")[1]
    line("C13", "2", [(p("C13", "2")[0], yg), (p("C10", "2")[0], yg)], 0.25)
    for a, b in (("C13", "C14"), ("C14", "C15")):
        # (GPiBridge's 3.3 V vias here went to its bottom 3.3 V pour; this board routes
        # 3.3 V, and they would stand in GPIO0's way)
        xv = (p(a, "1")[0] + p(b, "1")[0]) / 2
        X.via("GND", xv, yg)
    # DVDD pin 6's capacitor: from Raspberry Pi's via inside the ring, along their In2
    # (our In1, inside the ground island) to a via beside the +1V1 test point
    # (theirs went to a via 2 mm past the pins, in this board's fan-out: here In1 runs on
    # past it and across to a via just beyond the capacitor's own pad, the test point
    # beyond that)
    cx, cy = p("C10", "1")
    c10_via = (cx + 0.85, cy)
    vx, vy = G_U1[0] + 2.15, G_U1[1] + 0.8
    tx, ty = p("TP3", "1")
    X.polyline("+1V1", 1, [(vx, vy), (c10_via[0], vy), c10_via], 0.3)
    X.via("+1V1", *c10_via)
    X.track("+1V1", 0, c10_via, (tx, ty), 0.25)
    X.track("+1V1", 0, c10_via, (cx, cy), 0.25)
    # DVDD pin 23's capacitor: by the bottom layer round arc A's via
    cx, cy = p("C11", "1")
    X.via("+1V1", 17.0, 8.0)
    X.polyline("+1V1", 2, [(17.0, 8.0), (17.0, 7.2), (cx, 7.2 - (cx - 17.0)), (cx, cy + 0.77)], 0.25)
    X.via("+1V1", cx, cy + 0.77)
    X.track("+1V1", 0, (cx, cy + 0.77), (cx, cy), 0.25)
    line("C20", "1", [p("C19", "1"), p("C20", "1")])
    line("C20", "2", [p("C19", "2"), p("C20", "2")])
    # USB-C: the two D- pads join behind the row, the two D+ pads in front; the pair
    # runs to the 27 R
    jx = p("J1", "A6")[0]
    behind, front = jx - 1.045, jx + 1.005
    dm1, dm2 = p("J1", "B7")[1], p("J1", "A7")[1]
    dp1, dp2 = p("J1", "A6")[1], p("J1", "B6")[1]
    X.polyline(N("J1", "B7"), 0, [(jx, dm1), (behind, dm1), (behind, dm2), (jx, dm2)], 0.15)
    X.polyline(N("J1", "A6"), 0, [(jx, dp2), (front, dp2), (front, dp1)], 0.15)
    rx, ry = p("R1", "1")
    X.polyline(N("J1", "B7"), 0, chamfer([(jx, dm1), (rx, dm1), (rx, ry)]), 0.2)
    rx, ry = p("R2", "1")
    X.polyline(N("J1", "A6"), 0, chamfer([(jx, dp1), (rx, dp1), (rx, ry)]), 0.2)
    for pad, res in (("A5", "R4"), ("B5", "R5")):
        (x, y), (rx, ry) = p("J1", pad), p(res, "1")
        d = abs(y - ry)
        X.polyline(N("J1", pad), 0, [(x, y), (rx - d, y), (rx, ry)], 0.15)
    # 3.3 V out: the regulator through C3 to TP2, a via down to the plane... here to the
    # +3V3 routing; ground: the regulator's pin and C3 on a short line
    u2 = p("U4", "2")
    tx, ty = p("TP2", "1")
    X.track("+3V3", 0, u2, (tx, u2[1]), 0.4)
    X.track("+3V3", 0, (p("C3", "1")[0], u2[1]), p("C3", "1"), 0.4)
    g = p("U4", "1")
    X.polyline("GND", 0, [g, (p("C3", "2")[0] - 0.47, g[1]), p("C3", "2")], 0.4)
    for fp in R.board.GetFootprints():
        if fp.GetReference() == "J2":
            for pad in fp.Pads():
                if pad.GetNumber() in ("A1", "A12", "B1", "B12"):
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


# ======================================================================================
# Helpers for every board
# ======================================================================================
def keep_disc(R, cx, cy, r, layers=(0, 1, 2), via=True):
    """No track centre of any net within r of (cx, cy) on `layers` (nor a via)."""
    for k in R.g._disc(cx, cy, r):
        for L_ in layers:
            R.g.keep[L_][k] = 1
        if via:
            R.g.novia[k] = 1


def rule_area(R, pts, layers, name, tracks=False, vias=False, fills=True):
    """A KiCad rule area: no zone fill (and, if asked, no tracks or vias) inside pts."""
    z = pcbnew.ZONE(R.board)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowZoneFills(fills)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(R.P(x, y))
    R.board.Add(z)
    return z


def circle(cx, cy, r, n=72):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def coils(R):
    """The coils (gen/coils.py footprints, OWL:Coil_*): their spirals are copper of no net
    under rule areas the footprint carries; for the router, a disc on every layer that
    no track or via enters.  Their terminals (pads 1 and 2, plated) sit just outside it.
    Returns {ref: (cx, cy, r_out)}."""
    from parts import COILS
    out = {}
    for fp in R.board.GetFootprints():
        ref = fp.GetReference()
        if ref not in R.refs:
            continue
        name = str(fp.GetFPID().GetLibItemName())
        if not name.startswith("Coil_"):
            continue
        key = "COIL_" + name[len("Coil_"):]
        c = COILS[key]
        cx, cy = R.B(fp.GetPosition())
        r = c["r_out"] + L.COIL_KEEPOUT
        if c["layers"] == 4:
            R._item("<coil:%s>" % ref, ("disc", cx, cy, r), [0, 1, 2], clear=0.02, what="coil " + ref)
            R._novia(cx, cy, r + RT.VIA[0] / 2 + 0.05)
        else:
            # three layers (COIL_LEV): F.Cu and In1 closed; on B.Cu only the coil's own exit
            # (a pad and a track, gen/coils.py), with the sensor's hole and its corridor
            # toward the footprint's +y open (|x| <= CORRIDOR_W / 2)
            import coils as CO
            R._item("<coil:%s>" % ref, ("disc", cx, cy, r), [0, 1], clear=0.02, what="coil " + ref)
            a = math.radians(fp.GetOrientationDegrees())
            # (the grid bars a track's centre: its copper reaches half a width further,
            # so the opening is taken in and the disc out by the widest line's half, and
            # a little)
            m = 0.25
            hole = c["r_in"] - CO.SENSOR_HOLE - m
            for k in R.g._disc(cx, cy, r + m):
                x, y = R.g.pos(k)
                dx, dy = x - cx, y - cy
                # into the footprint's frame (the inverse of placement.rel for side F)
                lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
                if math.hypot(lx, ly) < hole or (abs(lx) <= CO.CORRIDOR_W / 2 - m and ly > 0):
                    continue
                R.g.keep[2][k] = 1
                R.g.novia[k] = 1
            R._novia(cx, cy, r + RT.VIA[0] / 2 + 0.05)
        out[ref] = (cx, cy, c["r_out"])
    return out


def exposed_pad(R, ref):
    """A chip's exposed pad (its largest SMD pad) as (pad, net, x0, y0, x1, y1), router mm."""
    fp = next(f for f in R.board.GetFootprints() if f.GetReference() == ref)
    best = None
    for p in fp.Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        bb = p.GetBoundingBox()
        a = bb.GetWidth() * bb.GetHeight()
        if best is None or a > best[0]:
            best = (a, p)
    p = best[1]
    bb = p.GetBoundingBox()
    x0, y0 = R.B(pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
    x1, y1 = R.B(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
    return p, p.GetNetname(), min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def ep_vias(R, ref, nx=2, ny=3, inset=0.55):
    """Vias inside a QFN's exposed pad, to the ground plane (its footprint has none)."""
    p, net, x0, y0, x1, y1 = exposed_pad(R, ref)
    if (x1 - x0) < (y1 - y0):
        cols, rows = nx, ny
    else:
        cols, rows = ny, nx
    for i in range(cols):
        for j in range(rows):
            x = x0 + inset + (x1 - x0 - 2 * inset) * (i / (cols - 1) if cols > 1 else 0.5)
            y = y0 + inset + (y1 - y0 - 2 * inset) * (j / (rows - 1) if rows > 1 else 0.5)
            R.via(net, x, y)


def ep_ties(R, ref, width=0.2):
    """Each pin on the exposed pad's net straight into the pad: along the pin, past the
    row's inner end, then to the pad's centre, so the pin needs no via of its own in the
    ring where the other pins escape."""
    fp = next(f for f in R.board.GetFootprints() if f.GetReference() == ref)
    ep, net, x0, y0, x1, y1 = exposed_pad(R, ref)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for p in fp.Pads():
        if p is ep or p.GetNetname() != net or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        bb = p.GetBoundingBox()
        px0, py0 = R.B(pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
        px1, py1 = R.B(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        px0, px1, py0, py1 = min(px0, px1), max(px0, px1), min(py0, py1), max(py0, py1)
        x, y = (px0 + px1) / 2, (py0 + py1) / 2
        if px0 < cx < px1 and py0 < cy < py1:
            continue
        if (py1 - py0) > (px1 - px0):           # a vertical pin: in along y
            yi = (py1 + 0.35) if cy > y else (py0 - 0.35)
            pts = [(x, y), (x, yi), (cx, cy)]
        else:
            xi = (px1 + 0.35) if cx > x else (px0 - 0.35)
            pts = [(x, y), (xi, y), (cx, cy)]
        R.polyline(net, 2 if fp.GetLayer() == pcbnew.B_Cu else 0, pts, width)


SKIP_FAN = ("USB_D", "XIN", "XOUT", "QSPI", "VREG", "Net-(U4-", "Net-(C27")


def local_first(R, ref, reach=8.0):
    """A chip's short local nets (a current-setting resistor, a regulator's capacitor),
    routed before its fan-out: the fan's vias would otherwise wall them in, and they
    need no via.  Returns how many it joined."""
    n = 0
    nets = {R.pads.net[k] for k in R.pads.xy if k[0] == ref}
    for net in sorted((m for m in nets if m), key=lambda m: span(R, m)):        # the shortest first
        if net in POWER or net.startswith("unconnected") or not R.unrouted(net) or span(R, net) > reach:
            continue
        if route_power(R, net, (0.2, 0.15)):
            n += 1
        else:
            print("   %s: local net %s left in pieces before the fan-out" % (R.name, net))
    return n


_LID = {0: pcbnew.F_Cu, 1: pcbnew.In1_Cu, 2: pcbnew.B_Cu}


def local_copper(R, L_, box):
    """The copper on layer L_ (pads as their bounding boxes, tracks, vias, zones) inside
    `box` (router millimetres), for exact clearance checks of planned lines:
    [(net, kind, shape, bounding box)]."""
    lid = _LID[L_]
    bx0, by0, bx1, by1 = box
    out = []

    def bbox(x0, y0, x1, y1):
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def near(b):
        return b[0] <= bx1 and b[2] >= bx0 and b[1] <= by1 and b[3] >= by0

    for fp in R.board.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnLayer(lid):
                continue
            bb = p.GetBoundingBox()
            x0, y0 = R.B(pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
            x1, y1 = R.B(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            b = bbox(x0, y0, x1, y1)
            if near(b):
                out.append((p.GetNetname(), "rect", b, b, "%s.%s" % (fp.GetReference(), p.GetNumber())))
    for t in R.board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            x, y = R.B(t.GetPosition())
            r = pcbnew.ToMM(t.GetWidth(lid)) / 2
            b = (x - r, y - r, x + r, y + r)
            if near(b):
                out.append((t.GetNetname(), "disc", (x, y, r), b, "via"))
        elif t.GetLayer() == lid:
            a, c = R.B(t.GetStart()), R.B(t.GetEnd())
            hw = pcbnew.ToMM(t.GetWidth()) / 2
            b = (min(a[0], c[0]) - hw, min(a[1], c[1]) - hw, max(a[0], c[0]) + hw, max(a[1], c[1]) + hw)
            if near(b):
                out.append((t.GetNetname(), "seg", (a, c, hw), b, "track"))
    for z in R.board.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(lid):
            continue
        ol = z.Outline()                              # kept alive while its chains are read
        for i in range(ol.OutlineCount()):
            ch = ol.Outline(i)
            pts = [R.B(ch.CPoint(j)) for j in range(ch.PointCount())]
            if pts:
                b = (min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts))
                if near(b):
                    out.append((z.GetNetname(), "poly", pts, b, "zone"))
    return out


def _clear_of(copper, net, a, b, need, why=None):
    """Is the segment a-b (its centre line) at least `need` from every copper of another
    net in `copper` (local_copper())?  `why`: a list to collect what is in the way."""
    sx0, sy0 = min(a[0], b[0]) - need, min(a[1], b[1]) - need
    sx1, sy1 = max(a[0], b[0]) + need, max(a[1], b[1]) + need
    for n, kind, sh, bb, what in copper:
        if n == net or bb[0] > sx1 or bb[2] < sx0 or bb[1] > sy1 or bb[3] < sy0:
            continue
        if kind == "disc":
            d = _pt_seg((sh[0], sh[1]), a, b) - sh[2]
        elif kind == "seg":
            d = _seg_seg(a, b, sh[0], sh[1]) - sh[2]
        else:
            pts = [(sh[0], sh[1]), (sh[2], sh[1]), (sh[2], sh[3]), (sh[0], sh[3])] if kind == "rect" else sh
            if RT.point_in_poly(a[0], a[1], pts) or RT.point_in_poly(b[0], b[1], pts):
                d = 0.0
            else:
                d = min(_seg_seg(a, b, pts[i - 1], pts[i]) for i in range(len(pts)))
        if d < need:
            if why is None:
                return False
            why.append("%s %s" % (what, n.split("/")[-1]))
    return not why


def _keep_free(R, L, a, b):
    kl = R.g.keep[L]
    return not any(kl[k] or R.g.outside[k] for k in R.g.shape_cells(("seg", a[0], a[1], b[0], b[1], 0.0), 0.0))


def _via_free(R, copper, net, x, y):
    """A via of `net` at (x, y): clear of other nets' copper on every layer (exact), and
    where the grid allows a drill (not too near another) inside the board."""
    if not (0 <= x < R.g.w and 0 <= y < R.g.h):
        return False
    k = R.g.k(x, y)
    if R.g.novia[k] or R.g.outside[k]:
        return False
    need = RT.VIA[0] / 2 + RR.CLEAR
    return all(_clear_of(copper[L], net, (x, y), (x, y), need) for L in range(RR.NL))


def fan(R, ref, width=0.15, power=()):
    """A planned fan-out for a fine-pitch chip: each signal pin a short straight stub,
    then a straight line out to a via of its own, the vias of a side evenly spaced in one
    row or two staggered rows (_fan_pattern), so the lines spread like a fan and none
    crosses another.  The pattern's own clearances are exact; against everything else
    the copper already there decides (exact too: a planned line is at any angle, which a
    grid can only judge to within its pitch); the pattern that serves the most pins is
    drawn, then one for each run of pins it left out.  The router then
    starts each net from its via, with every layer to choose from.  (Left to the router,
    the first nets hugged the chip and walled the later pins in; and lines straight out
    at the pins' 0.4 mm pitch leave no room for a via between them.)  Returns how many
    pins it fanned out; route_unfanned() routes the rest first."""
    fp = next(f for f in R.board.GetFootprints() if f.GetReference() == ref)
    L_ = 2 if fp.GetLayer() == pcbnew.B_Cu else 0
    xs = [xy for (r, num), xy in R.pads.xy.items() if r == ref]
    cx, cy = sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)
    sides = {}
    for p in fp.Pads():
        net = p.GetNetname()
        if not net or (net in POWER and net not in power) or any(k in net for k in SKIP_FAN) \
                or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or net.startswith("unconnected"):
            continue
        if net not in power and not R.unrouted(net):
            continue                                  # a local net, joined already (local_first())
        if (ref, p.GetNumber()) in R.__dict__.get("prefanned", ()):
            continue                                  # its way out planned already (straight_via())
        bb = p.GetBoundingBox()
        x0, y0 = R.B(pcbnew.VECTOR2I(bb.GetX(), bb.GetY()))
        x1, y1 = R.B(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        if (x1 - x0) > 2.0 or (y1 - y0) > 2.0:
            continue                                  # the exposed pad
        px, py = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = px - cx, py - cy
        if abs(dx) > abs(dy):
            u, tip = ((1.0 if dx > 0 else -1.0), 0.0), (x1 - x0) / 2
        else:
            u, tip = (0.0, (1.0 if dy > 0 else -1.0)), (y1 - y0) / 2
        t = (-u[1], u[0])                             # along the side
        sides.setdefault(u, []).append(((px - cx) * t[0] + (py - cy) * t[1], (px, py), tip, net, p.GetNumber()))
    allpads = sorted(pcbnew.ToMM(p.GetPosition().x) for p in fp.Pads())
    pitch = min((b - a for a, b in zip(allpads, allpads[1:]) if b - a > 0.2), default=0.5)
    def legal(u, pin, spots):
        """Of `spots` (place along the side, depth, straight run), those where the pin's
        stub, line and via are clear of everything already on the board."""
        s0, (px, py), tip, net, num = pin
        t = (-u[1], u[0])
        at = lambda hh, s: (px + u[0] * hh + t[0] * (s - s0), py + u[1] * hh + t[1] * (s - s0))
        a = tip + 0.25
        need = width / 2 + RR.CLEAR
        if not _clear_of(copper[L_], net, at(tip, s0), at(a, s0), need):
            return set()
        straight = {}
        out = set()
        for v, h, st in spots:
            if st not in straight:
                straight[st] = _clear_of(copper[L_], net, at(a, s0), at(a + st, s0), need) \
                    and _keep_free(R, L_, at(a, s0), at(a + st, s0))
            if straight[st] and _via_free(R, copper, net, *at(h, v)) and _keep_free(R, L_, at(a + st, s0), at(h, v)) \
                    and _clear_of(copper[L_], net, at(a + st, s0), at(h, v), need):
                out.add((v, h, st))
        return out

    def choose(u, pins):
        """The cheapest pattern for these pins that the board allows for the most of
        them: (pins it cannot serve, pattern, which it serves), or None."""
        nonlocal copper
        copper = {L: local_copper(R, L, (cx - 12, cy - 12, cx + 12, cy + 12)) for L in range(RR.NL)}
        geos = [geo for geo in (_fan_pattern(pins, *pat[1:]) for pat in _fan_patterns(pins)) if geo is not None]
        good = [legal(u, pin, {geo[i] for geo in geos}) for i, pin in enumerate(pins)]
        best = None
        for geo in geos:                              # cheapest first
            ok = [vhs in good[i] for i, vhs in enumerate(geo)]
            if best is None or ok.count(False) < best[0]:
                best = (ok.count(False), geo, ok)
                if not best[0]:
                    break
        dbg = os.environ.get("FAN_DEBUG", "")
        names = ["%s.%s" % (ref, pin[4]) for pin in pins]
        if dbg in names and best and best[0]:
            k = names.index(dbg)
            shown = 0
            for geo in geos:
                if geo[k] not in good[k]:
                    continue
                bad = [names[i] for i, vhs in enumerate(geo) if vhs not in good[i]]
                print("   debug %s: pattern %s fails %s" % (dbg, [tuple(round(c, 2) for c in g) for g in geo], bad))
                for i, vhs in enumerate(geo):
                    if vhs in good[i]:
                        continue
                    s0, (px, py), tip, net, num = pins[i]
                    t = (-u[1], u[0])
                    at = lambda hh, ss: (px + u[0] * hh + t[0] * (ss - s0), py + u[1] * hh + t[1] * (ss - s0))
                    v, h, st = vhs
                    a = tip + 0.25
                    why = []
                    need = width / 2 + RR.CLEAR
                    for p_, q_ in ((at(tip, s0), at(a, s0)), (at(a, s0), at(a + st, s0)), (at(a + st, s0), at(h, v))):
                        _clear_of(copper[L_], net, p_, q_, need, why)
                    for L in range(RR.NL):
                        _clear_of(copper[L], net, at(h, v), at(h, v), RT.VIA[0] / 2 + RR.CLEAR, why)
                    k_ = R.g.k(*at(h, v))
                    if R.g.novia[k_]:
                        why.append("no drill here (novia)")
                    print("      %s: %s" % (names[i], ", ".join(sorted(set(why))) or "keep/edge"))
                shown += 1
                if shown >= 6:
                    break
        return best

    def group(u, pins):
        """The cheapest pattern for these pins that the board allows for the most of
        them, drawn; returns the pins it left out."""
        best = choose(u, pins)
        if best is None:
            return list(pins)
        _, geo, ok = best
        t = (-u[1], u[0])
        need = width / 2 + RR.CLEAR
        left = []
        for pin, (v, h, st), fine in zip(pins, geo, ok):
            s0, (px, py), tip, net, num = pin
            at = lambda hh, s: (px + u[0] * hh + t[0] * (s - s0), py + u[1] * hh + t[1] * (s - s0))
            a = tip + 0.25
            if fine:
                R.polyline(net, L_, [(px, py), at(a + st, s0), at(h, v)], width)
                R.via(net, *at(h, v))
                continue
            clear = lambda p, q: _clear_of(copper[L_], net, p, q, need) and _keep_free(R, L_, p, q)
            if not clear(at(tip, s0), at(a, s0)):
                left.append(pin)
                continue
            # no via where the pattern puts it: the empty slot between its neighbours'
            # vias is twice as wide as a via, room for the line to go on through it to
            # a via further out
            on = None
            if clear(at(a, s0), at(a + st, s0)) and clear(at(a + st, s0), at(h, v)):
                on = next(((d, dv) for d in (0.4, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 3.5, 4.0) for dv in (0.0, 0.2, -0.2, 0.4, -0.4)
                           if _via_free(R, copper, net, *at(h + d, v + dv)) and clear(at(h, v), at(h + d, v + dv))), None)
            if on:
                d, dv = on
                R.polyline(net, L_, [(px, py), at(a + st, s0), at(h, v), at(h + d, v + dv)], width)
                R.via(net, *at(h + d, v + dv))
                continue
            if os.environ.get("FAN_WHY"):
                why = []
                for p_, q_ in ((at(a, s0), at(a + st, s0)), (at(a + st, s0), at(h, v)), (at(h, v), at(h, v))):
                    _clear_of(copper[L_], net, p_, q_, need, why)
                for L in range(RR.NL):
                    _clear_of(copper[L], net, at(h, v), at(h, v), RT.VIA[0] / 2 + RR.CLEAR, why)
                print("   why %s.%s (%s): %s" % (ref, num, net.split("/")[-1], ", ".join(sorted(set(why))) or "the grid (keep, edge or drill)"))
            # else the line still holds the pin's place in the fan as far as it is clear
            # (its neighbours lean over a gap), and the router takes the net on from its end
            pts = [(px, py), at(a, s0)]
            f = next((f for f in (1.0, 0.75, 0.5, 0.25) if clear(at(a, s0), at(a + st * f, s0))), 0.0) if st else 0.0
            if f:
                pts.append(at(a + st * f, s0))
            if f == 1.0:
                g = next((g for g in (1.0, 0.8, 0.6, 0.4, 0.2)
                          if clear(at(a + st, s0), at(a + st + (h - a - st) * g, s0 + (v - s0) * g))), 0.0)
                if g:
                    pts.append(at(a + st + (h - a - st) * g, s0 + (v - s0) * g))
            R.polyline(net, L_, pts, width)
            R.__dict__.setdefault("partial", []).append("%s.%s" % (ref, num))
        return left

    def runs(pins, gap):
        """The pins in runs of neighbours (no gap wider than `gap` along the side)."""
        out = [[pins[0]]]
        for p0, p1 in zip(pins, pins[1:]):
            if p1[0] - p0[0] > gap:
                out.append([])
            out[-1].append(p1)
        return out

    def fan_part(u, pins):
        """A pattern for these pins; those it leaves out, a pattern for each run of them
        between the pins it served, until a run gets nothing."""
        left = group(u, pins)
        if not left or len(left) == len(pins):
            return left
        return [p for run in runs(left, 1.5 * pitch) for p in fan_part(u, run)]

    copper = {}
    done, missed = 0, []
    for u, pins in sorted(sides.items()):
        pins.sort()
        # a side's pins in groups wherever two or more pins between them take no part
        # (power, the crystal's): each group its own fan, the gap kept clear
        left = [p for run in runs(pins, 2.5 * pitch) for p in fan_part(u, run)]
        missed += left
        done += len(pins) - len(left)
    for s0, xy, tip, net, num in missed:
        R.__dict__.setdefault("unfanned", []).append(net)
    part = [w for w in R.__dict__.pop("partial", []) if w.startswith(ref + ".")]
    if part:
        print("   %s: fan-out lines without a via for %s" % (R.name, " ".join(part)))
    if missed:
        print("   %s: no fan-out for %s" % (R.name, " ".join("%s.%s" % (ref, p[4]) for p in missed)))
    return done - len(part)


def route_unfanned(R):
    """The few pins the fan-outs left out (a capacitor or the crystal's lines in front of
    them), routed whole at once while the board round them is still empty."""
    for net in R.__dict__.pop("unfanned", []):
        if R.unrouted(net) and not route_power(R, net, (0.15,)):
            print("   %s: %s left in pieces (its pin has no fan-out)" % (R.name, net))


# a fan's own clearances, exact: track to track, track to via, via to via (0.15 mm
# rule plus 0.02 mm), for a 0.15 mm track and a 0.45 mm via
FAN_TT, FAN_TV, FAN_VV = 0.32, 0.47, 0.62


def _pt_seg(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    n = ax * ax + ay * ay
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / n))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _seg_seg(p, q, a, b):
    def side(o, x, y):
        return (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0])
    if side(p, q, a) * side(p, q, b) < 0 and side(a, b, p) * side(a, b, q) < 0:
        return 0.0
    return min(_pt_seg(p, a, b), _pt_seg(q, a, b), _pt_seg(a, p, q), _pt_seg(b, p, q))


def _fan_patterns(pins):
    """The fan patterns to try for one side, cheapest (most compact) first: (cost, rows,
    via spacing along the side, depth of the first row past the pads, sideways shift,
    straight run out of the pins before the lines lean).  Besides the shifts round the
    middle, a row with its first or last via straight out of its pin (something beside
    that end of the side)."""
    out = []
    n = len(pins)
    for rows, Ps in ((2, (0.5, 0.55, 0.65)), (1, (0.65, 0.72, 0.8))):
        for P in Ps:
            half = (pins[0][0] + pins[-1][0]) / 2
            ends = tuple(round(e + d, 3) for e in (pins[0][0] - (half - (n - 1) / 2.0 * P), pins[-1][0] - (half + (n - 1) / 2.0 * P))
                         for d in (0.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.4, -0.4))
            for i in range(4, 20):
                h0 = i * 0.2
                for shift in (0.0, 0.4, -0.4, 0.8, -0.8) + ends:
                    for st in (0.0, 0.8, 1.6, 2.4):
                        if st + 0.6 > h0:
                            continue
                        out.append((h0 + (0.3 if rows == 2 else 0.0) + 0.4 * abs(shift) + (P - 0.5) + 0.1 * st,
                                    rows, P, h0, shift, st))
    out.sort()
    return out


def _fan_pattern(pins, rows, P, h0, shift, st, dh=0.55):
    """Each pin's via (place along the side, depth) and straight run for one pattern:
    vias evenly spaced `P` apart, centred on the pins (plus `shift`), in one row `h0`
    past the pads or two staggered rows (lines to the second pass between the first's
    vias); each line straight out of its pin for `st` (through a gap between capacitors
    at the pins' own pitch), then leaning to its via.  None if a line leans more than 35
    degrees or the pattern's own copper is too close anywhere."""
    n = len(pins)
    centre = (pins[0][0] + pins[-1][0]) / 2 + shift
    geo, parts = [], []
    for i, (s0, xy, tip, net, num) in enumerate(pins):
        a = tip + 0.25
        v = centre + (i - (n - 1) / 2.0) * P
        h = tip + h0 + (dh if rows == 2 and i % 2 else 0.0)
        if abs(v - s0) > 0.7 * (h - a - st) + 1e-9:
            return None
        v, h = round(v, 4), round(h, 4)
        geo.append((v, h, st))
        parts.append(([((s0, tip), (s0, a + st)), ((s0, a + st), (v, h))], (v, h)))
    for i in range(n):
        for j in range(i + 1, min(n, i + 3)):
            (si, vi), (sj, vj) = parts[i], parts[j]
            if math.hypot(vi[0] - vj[0], vi[1] - vj[1]) < FAN_VV:
                return None
            if any(_pt_seg(vi, *sg) < FAN_TV for sg in sj) or any(_pt_seg(vj, *sg) < FAN_TV for sg in si):
                return None
            if any(_seg_seg(a[0], a[1], b[0], b[1]) < FAN_TT for a in si for b in sj):
                return None
    return geo


def fanout_band(R, ref, band=1.2):
    """No new via within `band` of a fine-pitch chip's pins: escapes spread out on the
    chip's own layer first.  (Without it each line dived to the cheaper layer at its pin's
    tip, and 0.45 mm vias at a 0.4 mm pitch walled the pins beside it in.)"""
    xs = [xy for (r, num), xy in R.pads.xy.items() if r == ref]
    x0, x1 = min(p[0] for p in xs) - band, max(p[0] for p in xs) + band
    y0, y1 = min(p[1] for p in xs) - band, max(p[1] for p in xs) + band
    i0, j0 = R.g.cell(x0, y0)
    i1, j1 = R.g.cell(x1, y1)
    nx = R.g.nx
    for j in range(max(0, j0), min(R.g.ny - 1, j1) + 1):
        a, b = j * nx + max(0, i0), j * nx + min(nx - 1, i1) + 1
        R.g.novia[a:b] = b"\x01" * (b - a)


def coil_stubs(R, pads, ref, spread=1.3, width=0.8):
    """From each of a coil's two terminals, a short line out and apart (the last
    millimetre into a terminal may be 0.8 mm wide at most), ending where the bridge's
    wide line can land: underneath, but on top for the levitation coil, whose B.Cu
    corridor beside its terminals carries the sensor's lines."""
    fp = next(f for f in R.board.GetFootprints() if f.GetReference() == ref)
    layer = 0 if str(fp.GetFPID().GetLibItemName()) == "Coil_LEV" else 2
    cx, cy = R.B(fp.GetPosition())
    p1, p2 = pads.xy[(ref, "1")], pads.xy[(ref, "2")]
    mx, my = (p1[0] + p2[0]) / 2 - cx, (p1[1] + p2[1]) / 2 - cy
    d = math.hypot(mx, my)
    ux, uy = mx / d, my / d                         # outward
    copper = local_copper(R, layer, (cx - 30, cy - 30, cx + 30, cy + 30))
    for num, p in (("1", p1), ("2", p2)):
        net = pads.net[(ref, num)]
        sx, sy = p[0] - (p1[0] + p2[0]) / 2, p[1] - (p1[1] + p2[1]) / 2
        s = math.hypot(sx, sy)
        sx, sy = sx / s, sy / s                     # sideways, away from the other terminal
        a = (p[0] + ux * 1.0, p[1] + uy * 1.0)
        # (shorter where a part stands in the way: the router takes the line on)
        for sp in (spread, spread * 0.6, spread * 0.3, 0.0):
            b = (a[0] + (ux + sx) * sp, a[1] + (uy + sy) * sp)
            if _clear_of(copper, net, a, b, width / 2 + RR.CLEAR) and _clear_of(copper, net, p, a, width / 2 + RR.CLEAR):
                break
        R.polyline(net, layer, [p, a, b], width)


def route_power(R, net, widths, **kw):
    """Join a net's pieces at the first width that fits each, then narrower; the last
    try searches four times as far."""
    ok = False
    for k, w in enumerate(widths):
        if k == len(widths) - 1:
            kw = dict(kw, max_pop=6000000)
            kw.pop("bbox_margin", None)
        n0 = len(R.failed)
        ok = R.route_net(net, w, **kw)
        if ok:
            R.failed = [f for f in R.failed if f[0] != net]
            break
        if k < len(widths) - 1:
            R.failed = R.failed[:n0]
    return ok


def span(R, net):
    pts = [R.g.pos(next(iter(next(iter(R.items[i].cells.values()))))) for i in R.by_net.get(net, [])
           if R.items[i].what not in ("track", "via", "zone")]
    if len(pts) < 2:
        return 0.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def live_stamp(R, net, r=3.0, most=24):
    """The router's view round a net's smallest piece the moment the net fails (later
    nets cover over what walled it in): R.live, for gen/board.py --stamps."""
    import routing as RT
    live = R.__dict__.setdefault("live", [])
    if len(live) >= most:
        return
    g = min(R.groups(net), key=len)
    it = next((R.items[i] for i in g if any(R.items[i].cells.values())), None)
    if it is None:
        return
    x, y = R.g.pos(next(iter(next(c for c in it.cells.values() if c))))
    st = RT.stamp(R, net, 0.2, max(0, x - r), max(0, y - r), x + r, y + r)
    st.update(board=R.name, at=[x + R.x0, y + R.y0], what=["live"] + sorted(set(R.items[i].what for i in g))[:5])
    live.append(st)


def autoroute(R, first=(), width=0.2, layer_cost=None, skip=()):
    """`first`: (net, widths, kwargs) routed in that order; then every other net with
    pieces left, shortest first, at `width`; then rip-up and reroute (repair())."""
    import time
    R.freeze_vias()
    spec, order = {}, []
    for net, widths, kw in first:
        if net not in R.by_net or net in spec:
            continue
        t = time.time()
        k = dict(layer_cost=layer_cost)
        k.update(kw)
        spec[net] = (widths, k)
        order.append(net)
        if not route_power(R, net, widths, **k):
            live_stamp(R, net)
            if os.environ.get("ROUTE_WHY") and net in R.region:
                cls, region = R.region[net]
                print("   why %s: %s" % (net, " ".join(sorted(set(R.walls(net, cls, region, planned=True))))))
            if len(R.live) >= int(os.environ.get("ROUTE_STOP") or 10 ** 6):
                return                            # debugging: stop at the n-th failure
        if time.time() - t > 20:
            print("   %s %-22s %.1f s" % (R.name, net, time.time() - t))
    rest = [n for n in R.by_net if not n.startswith("<") and n not in spec and n not in skip and R.unrouted(n)]
    rest.sort(key=lambda n: span(R, n))
    for net in rest:
        t = time.time()
        spec[net] = ((width, 0.15), dict(layer_cost=layer_cost))
        order.append(net)
        if not R.route_net(net, width, layer_cost=layer_cost, bbox_margin=12.0):
            R.failed = [f for f in R.failed if f[0] != net]
            route_power(R, net, (width, 0.15), layer_cost=layer_cost)
        if time.time() - t > 20:
            print("   %s %-22s %.1f s" % (R.name, net, time.time() - t))
    repair(R, spec, order)
    R.failed = [f for f in R.failed if R.unrouted(f[0])]


def repair(R, spec, order, rounds=2, most=8, depth=1):
    """Rip-up and reroute.  For each net still in pieces: route it again to see the
    pocket its search was walled into, take out the router's copper of the nets (`most`
    at most) that bound the pocket, route the walled-in net first and then those, in
    their first order; a net that ends in pieces then gets the same, `depth` levels
    down.  Kept if fewer of the nets touched end in pieces than before; otherwise every
    one of them gets its old copper back, exactly."""
    import time
    rank = {n: i for i, n in enumerate(order)}
    tried = set()

    def attempt(net, depth, saved, was):
        widths, kw = spec[net]
        R.region.pop(net, None)
        if route_power(R, net, widths, **kw):
            return [net]
        cls, region = R.region.get(net, (None, None))
        walls = [n for n in R.walls(net, cls, region) if n in spec and n not in saved][:most] if region else []
        if not walls or (net, tuple(walls)) in tried:
            return [net]
        tried.add((net, tuple(walls)))
        for n in walls:
            saved[n] = R.routed_copper(n)
            was[n] = R.unrouted(n) > 0
            R.rip(n)
        group = [net] + sorted(walls, key=rank.get)
        for n in group:
            widths, kw = spec[n]
            route_power(R, n, widths, **kw)
        touched = list(group)
        if depth > 0:
            for n in group:
                if R.unrouted(n):
                    touched += attempt(n, depth - 1, saved, was)
        return touched

    for rnd in range(rounds):
        fixed = 0
        for net in [n for n in order if R.unrouted(n)]:
            if not R.unrouted(net):
                continue
            t = time.time()
            saved, was = {net: R.routed_copper(net)}, {net: True}
            nfail = len(R.failed)
            touched = set(attempt(net, depth, saved, was))
            before = sum(1 for n in saved if was[n])
            after = sum(1 for n in saved if R.unrouted(n))
            if after < before:
                fixed += before - after
                verdict = "kept"
            else:
                for n in saved:
                    R.rip(n)
                    R.restore(n, saved[n])
                R.failed = R.failed[:nfail]
                verdict = "undone"
            if len(saved) > 1:
                print("   %s repair %s: ripped %s; %d -> %d in pieces, %s (%.0f s)"
                      % (R.name, net, " ".join(n.split("/")[-1] for n in saved if n != net), before, after,
                         verdict, time.time() - t))
        if not fixed:
            break


def stitch(R, net, pitch=7.0, layers=(0, 2)):
    """Ground vias on a grid wherever one fits with room round it for the pours on
    `layers`: every island of pour the tracks cut off then holds a via to the plane, so
    the filler keeps it (copper on every layer, nothing floating).  Returns how many."""
    g = R.g
    heavy = [g.g[(L_, "heavy")] for L_ in layers]
    vg = [g.g[(L_, "via")] for L_ in range(RR.NL)]
    n = 0
    y = pitch / 2
    while y < g.h:
        x = pitch / 2
        while x < g.w:
            k = g.k(x, y)
            if not g.novia[k] and not g.outside[k] and all(not v[k] for v in vg) and all(not h[k] for h in heavy):
                R.via(net, x, y)
                n += 1
            x += pitch
        y += pitch
    return n


# ======================================================================================
# The base
# ======================================================================================
ISLAND = (86.6, 0.0, 121.0, 27.0)     # In1 is ground here, under the RP2354A's corner
BOTTOM = {0: 2.0, 1: 2.0, 2: 1.0}     # the top is the scene: wiring goes underneath when it can


def base_layers(R):
    """In1 is the 4.8 V plane, except under the RP2354A's corner, where it is ground and
    the router may use it; In2 is ground everywhere."""
    x0, y0, x1, y1 = ISLAND
    W, H = R.g.w, R.g.h
    m = 0.6
    R.planes = {"GND": None,
                "+5V": [(m, m), (x0 - m, m), (x0 - m, y1 + m), (x1 + m, y1 + m), (x1 + m, m),
                        (W - m, m), (W - m, H - m), (m, H - m)]}
    g = R.g
    keep, out, nx = g.keep[1], g.outside, g.nx
    keep[:] = b"\x01" * len(keep)
    i0, j0 = g.cell(x0 + m, y0)
    i1, j1 = g.cell(x1 - m, y1 - m)
    for j in range(j0, j1 + 1):
        a, b = j * nx + i0, j * nx + i1 + 1
        keep[a:b] = out[a:b]


def keep_poly(R, pts, layers=(0, 1, 2), via=True):
    """No track centre of any net inside the polygon on `layers` (nor a via)."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    i0, j0 = R.g.cell(min(xs), min(ys))
    i1, j1 = R.g.cell(max(xs), max(ys))
    for j in range(max(0, j0), min(R.g.ny - 1, j1) + 1):
        for i in range(max(0, i0), min(R.g.nx - 1, i1) + 1):
            if RT.point_in_poly(i * RR.PITCH, j * RR.PITCH, pts):
                k = j * R.g.nx + i
                for L_ in layers:
                    R.g.keep[L_][k] = 1
                if via:
                    R.g.novia[k] = 1


def base_keepouts(R, pads):
    """The theremin's antennas (gen/art.py draws their gold on top): round each, no pour
    on any layer and no other copper; a 0.4 mm line from each pad straight out past the
    keep-out toward its oscillator, where the router takes it on."""
    try:
        import art
        ants = art.antennas()
    except ImportError:
        ants = [dict(net=n, keepout=circle(cx, cy, r + L.ANTENNA_KEEPOUT), pad=None)
                for n, (cx, cy, r) in (("MOON", L.MOON), ("GHOST", L.GHOST))]
    for a in ants:
        pts = [(x - R.x0, y - R.y0) for x, y in a["keepout"]]
        rule_area(R, pts, [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu], "antenna keep-out " + a["net"])
        keep_poly(R, pts)
        ref = "AE1" if a["net"] == "MOON" else "AE2"
        osc = "U12" if a["net"] == "MOON" else "U13"
        px, py = pads.xy[(ref, "1")]
        ox, oy = [sum(v) / len(v) for v in zip(*[xy for (r, n), xy in pads.xy.items() if r == osc])]
        d = math.hypot(ox - px, oy - py)
        ux, uy = (ox - px) / d, (oy - py) / d
        # step out until clear of the keep-out by a millimetre
        t = 0.0
        while RT.point_in_poly(px + ux * t, py + uy * t, pts) and t < 30.0:
            t += 0.2
        R.track(pads.net[(ref, "1")], 0, (px, py), (px + ux * (t + 1.0), py + uy * (t + 1.0)), 0.4)


def power_entry(R, pads):
    """The jack's centre pin down through F1 and Q1 to the 12 V hub: wide pours on the
    bottom, and Q1's gate network inside the hub's bay."""
    p = lambda ref, num: pads.xy[(ref, num)]
    j, f1, f2 = p("J1", "1"), p("F1", "1"), p("F1", "2")
    R.track(pads.net[("J1", "1")], 2, j, f1, 2.5)
    drain = [p("Q1", n) for n in ("5", "6", "7", "8")]
    xs = [q[0] for q in drain]
    R.zone(pads.net[("F1", "2")], pcbnew.B_Cu,
           [(min(xs) - 0.5, f2[1] - 0.9), (max(xs) + 0.5, f2[1] - 0.9), (max(xs) + 0.5, drain[0][1] + 0.6),
            (min(xs) - 0.5, drain[0][1] + 0.6)], priority=2, clearance=0.25, min_width=0.25, connect="solid")
    src = [p("Q1", n) for n in ("1", "2", "3")]
    g = p("Q1", "4")
    d1a, d1k, r1g = p("D1", "2"), p("D1", "1"), p("R1", "1")
    R.polyline(pads.net[("Q1", "4")], 2, [r1g, d1a, g], 0.3)
    top = src[0][1] - 1.0
    hub = [(g[0] - 0.75, top), (src[0][0] + 0.5, top), (src[0][0] + 0.5, top + 1.6),
           (p("D2", "1")[0] + 1.0, top + 1.6), (p("D2", "1")[0] + 1.0, p("C2", "1")[1] + 0.6),
           (d1k[0] - 1.4, p("C2", "1")[1] + 0.6), (d1k[0] - 1.4, d1a[1] + 1.2), (g[0] - 0.75, d1a[1] + 1.2)]
    R.zone("+12V", pcbnew.B_Cu, hub, priority=2, clearance=0.25, min_width=0.25, connect="solid")
    # the clamp's ground: two vias beside its anode pad
    x, y = p("D2", "2")
    for dy in (-0.8, 0.8):
        R.via("GND", x + 1.9, y + dy)
        R.track("GND", 2, (x, y + dy), (x + 1.9, y + dy), 0.8)


def buck(R, pads):
    """The 4.8 V buck's power loop: VIN to the input capacitors, SW across to the
    inductor (and the boot capacitor), the output to the plane through a row of vias."""
    p = lambda ref, num: pads.xy[(ref, num)]
    u1 = {n: p("U1", n) for n in ("1", "2", "3", "4", "5", "6")}
    cin, chf = p(role("buck:cin"), "1"), p(role("buck:cin_hf"), "1")
    vin = u1["3"]
    R.polyline("+12V", 2, [vin, (vin[0], chf[1] - 0.5), chf, cin], 0.6)
    # SW: narrow between GND and VIN, then 1 mm across to the inductor
    sw = pads.net[("U1", "2")]
    l1 = p("L1", "1")
    x1 = u1["2"][0] + 1.25
    R.track(sw, 2, u1["2"], (x1, u1["2"][1]), 0.6)
    R.polyline(sw, 2, [(x1, u1["2"][1]), (l1[0] - 2.0, u1["2"][1]), (l1[0], l1[1])], 1.0)
    cb = p(role("buck:boot"), "2")
    R.track(sw, 2, cb, (cb[0], u1["2"][1]), 0.4)
    bt = p(role("buck:boot"), "1")
    R.polyline(pads.net[("U1", "6")], 2, [u1["6"], (u1["6"][0], bt[1]), bt], 0.3)
    # the output: a pour joining the inductor's pad and the two capacitors, three vias
    # from it into the plane
    l2 = p("L1", "2")
    c6, c7 = p(role("buck:cout1"), "1"), p(role("buck:cout2"), "1")
    x0, x1 = min(l2[0], c6[0]) - 2.2, max(l2[0], c7[0]) + 2.2
    R.zone("+5V", pcbnew.B_Cu, [(x0, l2[1] - 0.6), (x1, l2[1] - 0.6), (x1, c6[1] + 0.35), (x0, c6[1] + 0.35)],
           priority=2, clearance=0.25, min_width=0.25, connect="solid")
    yv = (l2[1] + c6[1]) / 2
    for x in (x0 + 0.6, l2[0], x1 - 0.6):
        R.via("+5V", x, yv)


def base_plan(R):
    pads = R.pads
    base_layers(R)
    base_keepouts(R, pads)
    rpi_core(R, pads)
    rpi_local(R, pads)
    power_entry(R, pads)
    buck(R, pads)
    ep_vias(R, "U3")
    for ref in ("U3", "U5", "U6", "U7", "U8"):
        ep_ties(R, ref)
    # the top round the RP2354A is behind the tree: as cheap as the bottom there, so its
    # lines spread out on top before they need a via
    i0, j0 = R.g.cell(84.0, 0.0)
    i1, j1 = R.g.cell(124.0, 30.0)
    R.g.cheap = (0, i0, j0, i1, j1, 1.0 / BOTTOM[0])
    for net, widths, kw in CORNER:
        if net in R.by_net and net not in CRYSTAL and not route_power(R, net, widths, layer_cost=BOTTOM, **kw):
            print("   base: %s left in pieces before the fan-out" % net)
    xout(R, pads)
    straight_via(R, "U4", "19", 2.2)            # beside XIN, at the end of its group
    local = sum(local_first(R, ref) for ref in ("U3", "U15"))
    print("   base: %d local nets; fan-out %d + %d + %d" % (
        local, fan(R, "U4"), fan(R, "U3", power=("+3V3",)), fan(R, "U15", power=("+3V3",))))
    for net, widths, kw in CORNER:
        if net in CRYSTAL and net in R.by_net and not route_power(R, net, widths, layer_cost=BOTTOM, **kw):
            print("   base: %s left in pieces after the fan-out" % net)
    route_unfanned(R)
    n = R.fanout("GND")
    n5 = R.fanout("+5V")
    # 3.3 V has no plane: a via beside each pad (the RP2354A's are planned) gives every
    # pin a way onto every layer before the long lines fill the board round it
    n3 = R.fanout("+3V3", skip=("U4.",))
    print("   base: %d vias beside 3.3 V pads" % n3)
    for ref in ("U4", "U3", "U15"):
        fanout_band(R, ref)
    print("   base: planned copper and fan-outs: %d tracks, %d vias (%d ground, %d 4.8 V)"
          % (R.n_tracks, R.n_vias, n, n5))


# the widths each power line is widened toward after routing, widest first
_COIL = (1.5, 1.0, 0.6)
BASE_WIDEN = {"+12V": (1.0, 0.6), "VBUS": (0.4,), "VSYS": (0.4,), "+3V3": (0.4, 0.3), "+1V1": (0.4, 0.3),
              "Net-(U1-SW)": (1.0, 0.6)}
for _k in ("LEV", "PEND1", "PEND2", "PEND3"):
    BASE_WIDEN["/Base/%s_A" % _k] = BASE_WIDEN["/Base/%s_B" % _k] = _COIL
for _w in ("OWL", "CAT"):
    for _c in "ABC":
        BASE_WIDEN["/Base/%s_%s" % (_w, _c)] = (1.2, 0.8, 0.6)


def widen(R, table):
    for net, widths in table.items():
        if net in R.by_net:
            d, t = R.fatten(net, widths)
            if t:
                print("   %s: %-18s %3d of %3d tracks widened" % (R.name, net, d, t))


def pair_order(R, a, b):
    """Two nets that each join a bridge pin to one of a coil's two terminals: the one
    whose pads lie farther apart first."""
    def reach(net):
        pts = [R.pads.xy[k] for k in R.pads.of.get(net, [])]
        return max((math.hypot(p[0] - q[0], p[1] - q[1]) for p in pts for q in pts), default=0.0)
    return sorted((a, b), key=reach, reverse=True)


POWER = {"GND", "+5V", "+3V3", "+1V1", "+12V", "VBUS", "VSYS", "GND_T", "+5V_T", "+3V3_T"}


def travel_order(R, ref, nets):
    """A chip's lines, those that head straight out first and those that must travel
    round the chip last (they go round the outside of the others instead of hugging the
    pin row and walling the rest in): by the angle between each pin's direction from the
    chip's centre and its nearest destination's."""
    xs = [xy for (r, num), xy in R.pads.xy.items() if r == ref]
    cx, cy = sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)
    turn = {}
    for net in nets:
        mine = [xy for (r, num), xy in R.pads.xy.items() if r == ref and R.pads.net[(r, num)] == net]
        others = [R.pads.xy[k] for k in R.pads.of.get(net, []) if k[0] != ref]
        if not mine or not others:
            continue
        px, py = mine[0]
        dx, dy = min(others, key=lambda q: math.hypot(q[0] - px, q[1] - py))
        a = math.atan2(py - cy, px - cx)
        b = math.atan2(dy - cy, dx - cx)
        turn[net] = abs((b - a + math.pi) % (2 * math.pi) - math.pi)
    return sorted(turn, key=turn.get)


# the RP2354A's corner, top layer: crystal, USB, QSPI select, debug.  Routed before the
# chip's fan-out, which would otherwise wall the crystal in.
_TOP = dict(layers=(0,))
CORNER = [
    ("/Base/XIN", (0.15,), _TOP), ("/Base/XOUT", (0.15,), _TOP), ("Net-(C27-Pad2)", (0.15,), _TOP),
    ("/Base/USB_DM", (0.2,), _TOP), ("/Base/USB_DP", (0.2,), _TOP),
    ("/Base/USB_D+", (0.2,), {}), ("/Base/USB_D-", (0.2,), {}),
    ("Net-(J2-CC1)", (0.15,), _TOP), ("Net-(J2-CC2)", (0.15,), _TOP),
    ("/Base/QSPI_SS", (0.15,), {}), ("Net-(R14-Pad1)", (0.15,), {}),
    ("Net-(J4-SWCLK)", (0.2,), {}), ("Net-(J4-SWDIO)", (0.2,), {}),
    ("Net-(J5-RX)", (0.2,), {}), ("Net-(J5-TX)", (0.2,), {}),
]
def straight_via(R, ref, num, depth, width=0.15):
    """A pin's own way out, planned before its chip's fan-out: straight out of the pin to
    a via `depth` from its centre (a pin at the end of a group, where the fan's pattern
    would lean it into the crystal's lines); fan() then leaves it out."""
    fp = next(f for f in R.board.GetFootprints() if f.GetReference() == ref)
    xs = [xy for (r, n), xy in R.pads.xy.items() if r == ref]
    cx, cy = sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)
    px, py = R.pads.xy[(ref, num)]
    dx, dy = px - cx, py - cy
    u = ((1.0 if dx > 0 else -1.0), 0.0) if abs(dx) > abs(dy) else (0.0, (1.0 if dy > 0 else -1.0))
    net = R.pads.net[(ref, num)]
    v = (px + u[0] * depth, py + u[1] * depth)
    R.track(net, 2 if fp.GetLayer() == pcbnew.B_Cu else 0, (px, py), v, width)
    R.via(net, *v)
    R.__dict__.setdefault("prefanned", set()).add((ref, num))


def xout(R, pads):
    """The crystal's two lines, planned: XOUT east from its pin to just short of the
    crystal, then north to its series resistor; XIN east beside it to the crystal's pad
    (its capacitor the router joins after the fan-out).  (Routed, they cut diagonally in
    front of the pins either side of them and closed them in; this way the fan-out's vias
    for those pins fit between them and the pins.)"""
    net = "/Base/XOUT"
    x0, y0 = pads.xy[("U4", "22")]
    r = next(k for k in pads.of[net] if k[0] != "U4")
    rx, ry = pads.xy[r]
    # the crystal stands between: up its near side, clear of its pads, to the resistor's row
    y1 = next(f for f in R.board.GetFootprints() if f.GetReference() == "Y1")
    xc = min(R.B(pcbnew.VECTOR2I(p.GetBoundingBox().GetX(), p.GetBoundingBox().GetY()))[0] for p in y1.Pads()) - 0.35
    R.polyline(net, 0, [(x0, y0), (xc, y0), (xc, ry + 0.4), (xc + 0.4, ry), (rx, ry)], 0.15)
    net = "/Base/XIN"
    x0, y0 = pads.xy[("U4", "21")]
    yx, yy = pads.xy[("Y1", "1")]
    R.polyline(net, 0, [(x0, y0), (yx - abs(yy - y0), y0), (yx, yy)], 0.15)


# the crystal's lines, after the chip's fan-out: they run east from the middle of a side
# (pins 21, 22) and would close in the pins on either side of them; the fan's two groups
# there leave them the corridor between
CRYSTAL = ("/Base/XIN", "/Base/XOUT", "Net-(C27-Pad2)")


def base_route(R):
    n = lambda label: "/Base/" + label
    taken = set()
    early = list(CORNER)                  # routed in the plan already, before the fan-out
    taken = {e[0] for e in early}
    # then every short local connection (a chip's own capacitors and resistors), before
    # anything long passes by; then the RP2354A's lines and the LED drivers' in the
    # order of their pins round each chip, rivers that need not cross
    local = [net for net in R.by_net if not net.startswith("<") and net not in POWER and net not in taken
             and net not in BASE_WIDEN and span(R, net) < 10.0]
    early += [(net, (0.2, 0.15), {}) for net in sorted(local, key=lambda m: span(R, m))]
    taken |= set(local)
    mcu = [m for m in R.by_net if any(r == "U4" for r, _ in R.pads.of.get(m, [])) and m not in POWER
           and m not in taken and m.startswith("/Base/")]
    early += [(net, (0.2, 0.15), {}) for net in travel_order(R, "U4", set(mcu))]
    taken |= set(mcu)
    for chip in ("U3",):
        chans = [m for m in R.by_net if any(r == chip for r, _ in R.pads.of.get(m, [])) and m not in POWER
                 and m not in taken]
        early += [(net, (0.2, 0.15), {}) for net in travel_order(R, chip, set(chans))]
        taken |= set(chans)
    first = early + [
        ("+1V1", (0.25, 0.2), {}), ("VBUS", (0.4, 0.25), {}), ("VSYS", (0.4, 0.25), {}),
        # the power lines at a width every pin they reach can take (a DRV8874's are 0.4 mm
        # at 0.65 mm pitch); widened afterwards wherever there is room (WIDEN)
        ("+12V", (0.4, 0.25), {}),
    ]
    # each bridge's two coil lines: the one whose coil terminal lies farther from the bridge
    # first, so it takes the outer way round and the nearer one still reaches its terminal
    for name in ["LEV"] + ["PEND%d" % k for k in (1, 2, 3)]:
        first += [(net, (0.4, 0.25), {}) for net in pair_order(R, n(name + "_A"), n(name + "_B"))]
    for w in ("OWL", "CAT"):
        first += [(n("%s_%s" % (w, c)), (0.4, 0.25), {}) for c in "ABC"]
    first += [("Net-(U1-SW)", (0.6, 0.4), {}), ("+3V3", (0.2, 0.15), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)
    widen(R, BASE_WIDEN)
    print("   base: %d stitching vias" % stitch(R, "GND"))


def base_pours(R):
    edge = whole(R)
    x0, y0, x1, y1 = ISLAND
    R.zone("GND", pcbnew.In2_Cu, edge, priority=0, clearance=0.2, min_width=0.25, item=False, name="GND plane")
    R.zone("+5V", pcbnew.In1_Cu, edge, priority=0, clearance=0.25, min_width=0.25, item=False, name="4.8 V plane")
    R.zone("GND", pcbnew.In1_Cu, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], priority=1, clearance=0.2,
           min_width=0.2, item=False, name="GND island")
    R.zone("GND", pcbnew.B_Cu, edge, priority=0, clearance=0.25, min_width=0.25, item=False, name="GND bottom")
    R.zone("GND", pcbnew.F_Cu, edge, priority=0, clearance=0.25, min_width=0.25, item=False, name="GND top")


# ======================================================================================
# The tree, the perch, the bat and the tokens
# ======================================================================================
def no_tracks(R, L_):
    """A plane's layer: no track of any net (vias still pass)."""
    R.g.keep[L_][:] = b"\x01" * len(R.g.keep[L_])


def whole(R):
    """A pour's outline: the board's own edge, 0.5 mm in (gen/board.py inset): on a panel a
    bounding box would reach the tabs, and the edge itself the tabs' breakaway lines."""
    return R.pour_edge


def tree_plan(R):
    """In1 the tree's 4.8 V plane, In2 its ground; the levitation coil's two lines run
    the height of the tree underneath, from the base's socket to the perch's."""
    R.planes = {"GND_T": None, "+5V_T": None}
    no_tracks(R, 1)
    ep_vias(R, "U101")
    ep_ties(R, "U101")
    print("   tree: %d local nets; fan-out %d" % (local_first(R, "U101"), fan(R, "U101", power=("+3V3_T",))))
    route_unfanned(R)
    n = R.fanout("GND_T")
    n5 = R.fanout("+5V_T")
    fanout_band(R, "U101")
    print("   tree: fan-outs: %d ground, %d 4.8 V" % (n, n5))


def tree_route(R):
    wide = {"/Tree/LEV_A", "/Tree/LEV_B", "+3V3_T", "+5V_T", "GND_T"}
    local = [m for m in R.by_net if not m.startswith("<") and m not in wide and span(R, m) < 10.0]
    early = [(m, (0.2, 0.15), {}) for m in sorted(local, key=lambda m: span(R, m))]
    chans = [m for m in R.by_net if any(r == "U101" for r, _ in R.pads.of.get(m, [])) and m not in wide
             and m not in local]
    early += [(m, (0.2, 0.15), {}) for m in travel_order(R, "U101", set(chans))]
    first = early + [("/Tree/LEV_A", (0.4, 0.25), {}), ("/Tree/LEV_B", (0.4, 0.25), {}),
                     ("+3V3_T", (0.2, 0.15), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)
    widen(R, {"/Tree/LEV_A": _COIL, "/Tree/LEV_B": _COIL, "+3V3_T": (0.4, 0.3)})
    print("   tree: %d stitching vias" % stitch(R, "GND_T"))


def tree_pours(R):
    R.zone("GND_T", pcbnew.In2_Cu, whole(R), priority=0, clearance=0.2, min_width=0.25, item=False, name="GND plane")
    R.zone("+5V_T", pcbnew.In1_Cu, whole(R), priority=0, clearance=0.25, min_width=0.25, item=False,
           name="4.8 V plane")
    R.zone("GND_T", pcbnew.B_Cu, whole(R), priority=0, clearance=0.25, min_width=0.25, item=False, name="GND bottom")


def perch_plan(R):
    """The levitation coil uses F.Cu, In1 and In2 inside its disc; outside it In2 is
    ground.  Everything else is underneath."""
    R.planes = {"GND_P": None}
    n = R.fanout("GND_P")
    print("   perch: fan-outs: %d ground" % n)


def perch_route(R):
    first = [("/Perch/LEV_A", (0.4, 0.25), {}), ("/Perch/LEV_B", (0.4, 0.25), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)
    widen(R, {"/Perch/LEV_A": _COIL, "/Perch/LEV_B": _COIL, "+3V3_P": (0.4, 0.3)})
    print("   perch: %d stitching vias" % stitch(R, "GND_P", layers=(2,)))


def perch_pours(R):
    R.zone("GND_P", pcbnew.In2_Cu, whole(R), priority=0, clearance=0.2, min_width=0.25, item=False, name="GND plane")
    R.zone("GND_P", pcbnew.B_Cu, whole(R), priority=0, clearance=0.25, min_width=0.25, item=False, name="GND bottom")


# ======================================================================================
# Dispatch
# ======================================================================================
def plan(name, R):
    R.pads = Pads(R.board, R.B, R.refs)
    R.coil = coils(R)
    for ref in R.coil:
        coil_stubs(R, R.pads, ref)
    if name == "base":
        base_plan(R)
    elif name == "tree":
        tree_plan(R)
    elif name == "perch":
        perch_plan(R)


def route(name, R):
    if name == "base":
        base_route(R)
    elif name == "tree":
        tree_route(R)
    elif name == "perch":
        perch_route(R)
    else:
        autoroute(R, width=0.25)


def pours(name, R):
    if name == "base":
        base_pours(R)
    elif name == "tree":
        tree_pours(R)
    elif name == "perch":
        perch_pours(R)
