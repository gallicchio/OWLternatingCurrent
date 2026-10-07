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
    (x, y), (cx, cy) = u1("39"), p("C12", "1")
    xm = cx + 0.57
    line("C12", "1", [(x, y), (xm, y), (xm, cy - (xm - cx - 0.27)), (cx + 0.27, cy), (cx, cy)], 0.15)
    line("C21", "1", [p("C21", "1"), u1("44")])
    (x, y), (cx, cy) = u1("45"), p("C18", "1")
    line("C18", "1", [(x, y), (cx + (cy - y), y), (cx, cy)])
    (x, y), (cx, cy) = u1("30"), p("C16", "1")
    line("C16", "1", [(x, y), (x, cy + (x - cx)), (cx, cy)])
    (x, y) = u1("1")
    xe = p("C15", "1")[0]
    line("C13", "1", [(x, y), (xe, y)], 0.25)
    yg = p("C13", "2")[1]
    line("C13", "2", [(p("C13", "2")[0], yg), (p("C10", "2")[0], yg)], 0.25)
    for a, b in (("C13", "C14"), ("C14", "C15")):
        xv = (p(a, "1")[0] + p(b, "1")[0]) / 2
        X.via("+3V3", xv, y)
        X.via("GND", xv, yg)
    # DVDD pin 6's capacitor: from Raspberry Pi's via inside the ring, along their In2
    # (our In1, inside the ground island) to a via beside the +1V1 test point
    c10_via = (21.45, 10.8)
    vx, vy = G_U1[0] + 2.15, G_U1[1] + 0.8
    tx, ty = p("TP3", "1")
    X.polyline("+1V1", 1, [(vx, vy), (c10_via[0], vy)], 0.3)
    X.via("+1V1", *c10_via)
    X.track("+1V1", 0, c10_via, (tx, ty), 0.25)
    cx, cy = p("C10", "1")
    X.polyline("+1V1", 0, [c10_via, (cx, c10_via[1] + (cx - c10_via[0])), (cx, cy)], 0.25)
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
            hole = c["r_in"] - CO.SENSOR_HOLE
            for k in R.g._disc(cx, cy, r):
                x, y = R.g.pos(k)
                dx, dy = x - cx, y - cy
                # into the footprint's frame (the inverse of placement.rel for side F)
                lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
                if math.hypot(lx, ly) < hole or (abs(lx) <= CO.CORRIDOR_W / 2 and ly > 0):
                    continue
                R.g.keep[2][k] = 1
                R.g.novia[k] = 1
            R._novia(cx, cy, r + RT.VIA[0] / 2 + 0.05)
        out[ref] = (cx, cy, c["r_out"])
    return out


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
    for num, p in (("1", p1), ("2", p2)):
        sx, sy = p[0] - (p1[0] + p2[0]) / 2, p[1] - (p1[1] + p2[1]) / 2
        s = math.hypot(sx, sy)
        sx, sy = sx / s, sy / s                     # sideways, away from the other terminal
        a = (p[0] + ux * 1.0, p[1] + uy * 1.0)
        b = (a[0] + (ux + sx) * spread, a[1] + (uy + sy) * spread)
        R.polyline(pads.net[(ref, num)], layer, [p, a, b], width)


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


def autoroute(R, first=(), width=0.2, layer_cost=None, skip=()):
    """`first`: (net, widths, kwargs) routed in that order; then every other net with
    pieces left, shortest first, at `width`."""
    import time
    done = set()
    for net, widths, kw in first:
        if net not in R.by_net:
            continue
        t = time.time()
        k = dict(layer_cost=layer_cost)
        k.update(kw)
        route_power(R, net, widths, **k)
        done.add(net)
        if time.time() - t > 20:
            print("   %s %-22s %.1f s" % (R.name, net, time.time() - t))
    rest = [n for n in R.by_net if not n.startswith("<") and n not in done and n not in skip and R.unrouted(n)]
    rest.sort(key=lambda n: span(R, n))
    for net in rest:
        t = time.time()
        if not R.route_net(net, width, layer_cost=layer_cost, bbox_margin=12.0):
            R.failed = [f for f in R.failed if f[0] != net]
            route_power(R, net, (width, 0.15), layer_cost=layer_cost)
        if time.time() - t > 20:
            print("   %s %-22s %.1f s" % (R.name, net, time.time() - t))


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
    n = R.fanout("GND")
    n5 = R.fanout("+5V")
    print("   base: planned copper and fan-outs: %d tracks, %d vias (%d ground, %d 4.8 V)"
          % (R.n_tracks, R.n_vias, n, n5))


def base_route(R):
    n = lambda label: "/Base/" + label
    usb = dict(layers=(0,))
    first = [
        # the RP2354A's corner first, top layer: crystal, USB, QSPI select, debug
        (n("XIN"), (0.15,), usb), (n("XOUT"), (0.15,), usb), ("Net-(C27-Pad2)", (0.15,), usb),
        (n("USB_DM"), (0.2,), usb), (n("USB_DP"), (0.2,), usb),
        (n("USB_D+"), (0.2,), {}), (n("USB_D-"), (0.2,), {}),
        ("Net-(J2-CC1)", (0.15,), usb), ("Net-(J2-CC2)", (0.15,), usb),
        (n("QSPI_SS"), (0.15,), {}), ("Net-(R14-Pad1)", (0.15,), {}),
        ("Net-(J4-SWCLK)", (0.2,), {}), ("Net-(J4-SWDIO)", (0.2,), {}),
        ("Net-(J5-RX)", (0.2,), {}), ("Net-(J5-TX)", (0.2,), {}),
        ("+1V1", (0.25, 0.2), {}), ("VBUS", (0.5, 0.3), {}), ("VSYS", (0.5, 0.3), {}),
        # wide lines: 12 V, the coils and the perch's coil through the socket
        ("+12V", (1.0, 0.6, 0.3), {}),
        (n("LEV_A"), (1.5, 1.0), {}), (n("LEV_B"), (1.5, 1.0), {}),
    ]
    for k in (1, 2, 3):
        first += [(n("PEND%d_A" % k), (1.5, 1.0), {}), (n("PEND%d_B" % k), (1.5, 1.0), {})]
    for w in ("OWL", "CAT"):
        first += [(n("%s_%s" % (w, c)), (1.2, 0.8), {}) for c in "ABC"]
    first += [("Net-(U1-SW)", (1.0, 0.6), {}), ("+3V3", (0.3, 0.2), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)


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
    n = R.fanout("GND_T")
    n5 = R.fanout("+5V_T")
    print("   tree: fan-outs: %d ground, %d 4.8 V" % (n, n5))


def tree_route(R):
    first = [("/Tree/LEV_A", (1.5, 1.0), {}), ("/Tree/LEV_B", (1.5, 1.0), {}), ("+3V3_T", (0.3, 0.2), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)


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
    first = [("/Perch/LEV_A", (1.5, 1.0), {}), ("/Perch/LEV_B", (1.5, 1.0), {})]
    autoroute(R, first, width=0.2, layer_cost=BOTTOM)


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
