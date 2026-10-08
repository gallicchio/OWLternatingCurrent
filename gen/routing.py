"""Copper on the board, inside KiCad's Python: fixed copper (zones, tracks
and vias given as coordinates), ground fan-out vias, and the grid router for
everything else.  Called by gen/board.py.

Every pad, track, via and zone is an *item*: its cells on the routing grid
and the obstacle it stamps for other nets.  A net is complete when its items
form one group, where items join if they share a cell on a common layer, and
every via or through-hole pad of a plane's net joins the others through that
plane (the ground plane In2, the supply pours on In1).  Routing a net joins its groups one at a time, the
smallest first, with A* from that group to all the others.

Board millimetres throughout (board.P / board.B convert).  The routing grid's
layers: 0 = F.Cu, 1 = In1.Cu, 2 = B.Cu; In2.Cu is the ground plane.  (GPiBridge's
routing.py, with one Router per board of the panel: its pads, its outline, its planes.)
"""
import math
from array import array
import pcbnew
import router as R

LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.B_Cu]
LIDX = {pcbnew.F_Cu: 0, pcbnew.In1_Cu: 1, pcbnew.B_Cu: 2}
VIA = (0.45, 0.25)                 # pad, drill: JLCPCB's standard 4-layer via
# Planes, per Router: {net: polygon or None}: a via or through-hole pad of the net,
# inside the polygon (board mm; None = everywhere), is joined through that plane.


class Item:
    """cells: {layer: grid cells its copper covers}, for joining items;
    inner: where a routed track may end on it (a pad's cells far enough
    inside that a track ending there crosses the pad's edge at full width;
    any cell of a track, via or zone); obj, seg: a track's pcbnew object and
    (layer, start, end, width), for widening it afterwards."""
    __slots__ = ("net", "cells", "stamp", "plane", "what", "inner", "obj", "seg", "routed")

    def __init__(self, net, cells, stamp, plane, what, inner=None):
        self.net, self.cells, self.stamp, self.plane, self.what = net, cells, stamp, plane, what
        self.inner = inner if inner is not None else cells
        self.obj = self.seg = None
        self.routed = False                       # laid by the router (rip-up may take it back)


class Router:
    def __init__(self, board, P, B, w, h, refs=None, planes=None, outline=None, name=""):
        """P, B: this board's millimetres (0..w, 0..h) to KiCad's and back; refs: the
        footprints on it; planes: {net: polygon or None}; outline: its edge."""
        self.board, self.P, self.B, self.name = board, P, B, name
        self.refs = refs
        self.planes = planes if planes is not None else {"GND": None}
        self.g = R.Grid(w, h, outline=outline)
        self.items = []
        self.by_net = {}
        self.nets = {}
        for name, ni in board.GetNetsByName().items():
            if str(name):
                self.nets[str(name)] = ni
        self.failed = []
        self.region = {}                          # net -> (class, cells) of a walled-in search
        self.n_tracks = self.n_vias = 0

    # ---- items ----------------------------------------------------------------
    def _item(self, net, shape, layers, plane=False, clear=R.CLEAR, what="", inner=None):
        c0 = self.g.shape_cells(shape, 0.0)
        cells = {L: set(c0) for L in layers}
        stamp = self.g.obstacle(shape, layers, clear)
        self.g.add(stamp)
        it = Item(net, cells, stamp, plane, what, {L: set(inner) for L in layers} if inner is not None else None)
        self.items.append(it)
        self.by_net.setdefault(net, []).append(len(self.items) - 1)
        return it

    def lift(self, net):
        for i in self.by_net.get(net, []):
            self.g.sub(self.items[i].stamp)

    def drop(self, net):
        for i in self.by_net.get(net, []):
            self.g.add(self.items[i].stamp)

    @staticmethod
    def pad_shape(pad, B):
        """("disc", x, y, r), ("seg", x0, y0, x1, y1, r) for an oval (the
        segment between its end circles' centres), or ("rect", x, y, hw, hh,
        angle) for the rest (a rounded rectangle's corners count as square)."""
        x, y = B(pad.GetPosition())
        sz = pad.GetSize(pcbnew.F_Cu)
        w, h = pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)
        kind = pad.GetShape(pcbnew.F_Cu)
        ang = -pad.GetOrientationDegrees()
        if kind == pcbnew.PAD_SHAPE_CIRCLE or (kind == pcbnew.PAD_SHAPE_OVAL and abs(w - h) < 1e-6):
            return ("disc", x, y, w / 2)
        if kind == pcbnew.PAD_SHAPE_OVAL:
            # the long axis in the pad's frame, turned onto the board (the
            # inverse of the turn shape_cells applies to a rect)
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            if h > w:
                L = (h - w) / 2
                dx, dy = -L * sa, L * ca
            else:
                L = (w - h) / 2
                dx, dy = L * ca, L * sa
            return ("seg", x - dx, y - dy, x + dx, y + dy, min(w, h) / 2)
        return ("rect", x, y, w / 2, h / 2, ang)

    @staticmethod
    def pad_layers(pad):
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            return [0, 1, 2]
        return [LIDX[l] for l in LAYERS if pad.IsOnLayer(l)]

    def load_pads(self):
        """Every pad becomes an item; drills (plated or not) forbid vias nearby."""
        for fp in self.board.GetFootprints():
            if self.refs is not None and fp.GetReference() not in self.refs:
                continue
            for pad in fp.Pads():
                shape = self.pad_shape(pad, self.B)
                x, y = shape[1], shape[2]
                att = pad.GetAttribute()
                if att in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    d = pcbnew.ToMM(pad.GetDrillSize().x)
                    # no via drill within 0.25 mm of this drill (hole to hole), any net
                    self._novia(x, y, d / 2 + VIA[1] / 2 + 0.25)
                if att == pcbnew.PAD_ATTRIB_NPTH:
                    d = pcbnew.ToMM(pad.GetDrillSize().x)
                    self._item("<npth>", ("disc", x, y, d / 2), [0, 1, 2], clear=0.25, what="npth")
                    continue
                layers = self.pad_layers(pad)
                if not layers:
                    continue
                net = pad.GetNetname() or "<nc:%s.%s>" % (fp.GetReference(), pad.GetNumber())
                self._item(net, shape, layers, plane=(att == pcbnew.PAD_ATTRIB_PTH),
                           what="%s.%s" % (fp.GetReference(), pad.GetNumber()), inner=self._inner_cells(shape))
                # no vias inside any pad (SMD or through hole), nor touching it
                self._novia_shape(shape, VIA[0] / 2 + 0.05)

    def _inner_cells(self, shape, m=0.075):
        """A pad's cells at least m inside its edge (half a 0.15 mm track), so
        a track ending there never meets the pad at a corner only (KiCad's
        connection-width check); a pad too small for that offers its centre."""
        if shape[0] == "disc":
            _, x, y, rad = shape
            cells = self.g._disc(x, y, rad - m) if rad > m else []
            cx, cy = x, y
        elif shape[0] == "seg":
            _, x0, y0, x1, y1, hw = shape
            cells = self.g.shape_cells(("seg", x0, y0, x1, y1, max(hw - m, 0.0)), 1e-4)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        else:
            _, cx, cy, hw, hh, ang = shape
            cells = self.g.shape_cells(("rect", cx, cy, max(hw - m, 0.0), max(hh - m, 0.0), ang), 1e-4)
        return set(cells) or {self.g.k(cx, cy)}

    def _novia(self, x, y, r):
        for k in self.g._disc(x, y, r):
            self.g.novia[k] = 1

    def _novia_shape(self, shape, r):
        for k in self.g.shape_cells(shape, r):
            self.g.novia[k] = 1

    def keepout(self, x0, y0, x1, y1, layers, via=True):
        self.g.keepout(x0, y0, x1, y1, layers, via)

    # ---- adding copper ----------------------------------------------------------
    def track(self, net, L, a, b, width, stamp=True):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(self.P(*a)); t.SetEnd(self.P(*b))
        t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(LAYERS[L])
        t.SetNet(self.nets[net])
        self.board.Add(t)
        self.n_tracks += 1
        if stamp:
            it = self._item(net, ("seg", a[0], a[1], b[0], b[1], width / 2), [L], what="track")
            it.obj, it.seg = t, (L, a, b, width)
        return t

    # ---- widening, after routing ------------------------------------------------
    def fatten(self, net, widths, split=1.5):
        """Widen the net's tracks toward `widths` (the widest first) wherever the copper
        round them leaves room: the router laid them at a width every pin they reach can
        take, and a power line is wide only where it can be.  Long tracks are first cut
        `split` from each end, so the part beside a fine pin stays narrow and the rest
        widens.  Returns (tracks widened, tracks in all)."""
        ids = [i for i in self.by_net.get(net, []) if self.items[i].what == "track" and self.items[i].seg]
        for i in ids:
            L, a, b, w = self.items[i].seg
            routed = self.items[i].routed
            n = math.hypot(b[0] - a[0], b[1] - a[1])
            if n <= 2 * split + 0.5:
                continue
            ux, uy = (b[0] - a[0]) / n, (b[1] - a[1]) / n
            p1 = (a[0] + ux * split, a[1] + uy * split)
            p2 = (b[0] - ux * split, b[1] - uy * split)
            self._kill(i)
            for q0, q1 in ((a, p1), (p1, p2), (p2, b)):
                self.track(net, L, q0, q1, w)
                self.items[-1].routed = routed
        self.lift(net)
        done = total = 0
        try:
            for i in list(self.by_net.get(net, [])):
                it = self.items[i]
                if it.what != "track" or not it.seg:
                    continue
                total += 1
                L, a, b, w = it.seg
                for wn in widths:
                    if wn <= w + 1e-6:
                        break
                    cls = R.width_class(wn)
                    cells = self.g.shape_cells(("seg", a[0], a[1], b[0], b[1], 0.0), 0.0)
                    g, kl = self.g.g[(L, cls)], self.g.keep[L]
                    if any(g[k] or kl[k] for k in cells):
                        continue
                    it.obj.SetWidth(pcbnew.FromMM(wn))
                    it.seg = (L, a, b, wn)
                    it.stamp = self.g.obstacle(("seg", a[0], a[1], b[0], b[1], wn / 2), [L], R.CLEAR)
                    done += 1
                    break
        finally:
            self.drop(net)
        return done, total

    def _kill(self, i):
        """Take a track or via out of the board and of the router (its item stays, empty)."""
        it = self.items[i]
        self.g.sub(it.stamp)
        it.stamp = {}
        it.cells = {}
        it.inner = {}
        it.what = "dead"
        self.board.Remove(it.obj)
        it.seg = None

    def polyline(self, net, L, pts, width):
        for a, b in zip(pts, pts[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                self.track(net, L, a, b, width)

    def via(self, net, x, y, size=VIA):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(self.P(x, y))
        v.SetWidth(pcbnew.FromMM(size[0])); v.SetDrill(pcbnew.FromMM(size[1]))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        # no pad on an inner layer the via does not connect on: the ground plane
        # then comes 0.2 mm from the drill instead of from a pad, and two vias
        # that touch on a layer they do not use make no narrow copper there
        v.Padstack().SetUnconnectedLayerMode(pcbnew.UNCONNECTED_LAYER_MODE_REMOVE_EXCEPT_START_AND_END)
        v.SetNet(self.nets[net])
        self.board.Add(v)
        self.n_vias += 1
        it = self._item(net, ("disc", x, y, size[0] / 2), [0, 1, 2], plane=True, what="via")
        it.obj, it.seg = v, ("via", x, y, size[1])
        self._novia(x, y, size[1] / 2 + VIA[1] / 2 + 0.25)
        if getattr(self, "_vcount", None) is not None:
            for k in self.g._disc(x, y, size[1] / 2 + VIA[1] / 2 + 0.25):
                self._vcount[k] += 1
        return v

    def zone(self, net, layer, pts, priority=0, clearance=0.15, min_width=0.15, connect="thermal",
             name=None, item=True, spoke=0.25, gap=0.2):
        """A copper pour.  With item=True its outline's inside is also a
        routing item: other nets keep clear of it, its own net may join it."""
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        z.SetNet(self.nets[net])
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(pcbnew.FromMM(clearance))
        z.SetMinThickness(pcbnew.FromMM(min_width))
        z.SetPadConnection({"thermal": pcbnew.ZONE_CONNECTION_THERMAL,
                            "solid": pcbnew.ZONE_CONNECTION_FULL}[connect])
        z.SetThermalReliefGap(pcbnew.FromMM(gap))
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(spoke))
        if name:
            z.SetZoneName(name)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(self.P(x, y))
        self.board.Add(z)
        if item and layer in LIDX:
            self._poly_item(net, LIDX[layer], pts)
        return z

    def _poly_item(self, net, L, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        i0, j0 = self.g.cell(min(xs), min(ys))
        i1, j1 = self.g.cell(max(xs), max(ys))
        inside = []
        for j in range(max(0, j0), min(self.g.ny - 1, j1) + 1):
            for i in range(max(0, i0), min(self.g.nx - 1, i1) + 1):
                if point_in_poly(i * R.PITCH, j * R.PITCH, pts):
                    inside.append(j * self.g.nx + i)
        stamp = {}
        inset = set(inside)
        for c in R.CLS:
            r = R.CLEAR + R.CLASSES[c]
            n = int(math.ceil(r / R.PITCH))
            grown = set()
            # only the border cells need growing
            for k in inside:
                i, j = k % self.g.nx, k // self.g.nx
                if all(((j + dj) * self.g.nx + i + di) in inset for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    grown.add(k)
                    continue
                for di in range(-n, n + 1):
                    for dj in range(-n, n + 1):
                        if (di * di + dj * dj) * R.PITCH * R.PITCH <= r * r:
                            ii, jj = i + di, j + dj
                            if 0 <= ii < self.g.nx and 0 <= jj < self.g.ny:
                                grown.add(jj * self.g.nx + ii)
            stamp[(L, c)] = list(grown)
        self.g.add(stamp)
        it = Item(net, {L: inset}, stamp, False, "zone")
        self.items.append(it)
        self.by_net.setdefault(net, []).append(len(self.items) - 1)

    # ---- connectivity ---------------------------------------------------------
    def groups(self, net):
        ids = [i for i in self.by_net.get(net, []) if self.items[i].what != "dead"]
        parent = {i: i for i in ids}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        owner = {}
        first_plane = None
        poly = self.planes.get(net, False)
        for i in ids:
            it = self.items[i]
            if it.plane and poly is not False and (poly is None or self._inside(it, poly)):
                if first_plane is None:
                    first_plane = i
                else:
                    union(i, first_plane)
            for L, cells in it.cells.items():
                for k in cells:
                    o = owner.get((L, k))
                    if o is None:
                        owner[(L, k)] = i
                    else:
                        union(i, o)
        out = {}
        for i in ids:
            out.setdefault(find(i), []).append(i)
        return list(out.values())

    def _inside(self, it, poly):
        cells = next(iter(it.cells.values()))
        k = next(iter(cells))
        x, y = self.g.pos(k)
        return point_in_poly(x, y, poly)

    def cells_of(self, ids, layers=None, inner=False):
        s = set()
        for i in ids:
            for L, cells in (self.items[i].inner if inner else self.items[i].cells).items():
                if layers is None or L in layers:
                    for k in cells:
                        s.add((L, k))
        return s

    def unrouted(self, net):
        return len(self.groups(net)) - 1

    # ---- routing --------------------------------------------------------------
    def route_net(self, net, width, layers=(0, 1, 2), layer_cost=None, via_cost=R.VIA_COST,
                  max_pop=1500000, allow_via=True, bbox_margin=None):
        """Join the net's pieces, the smallest to the rest each time.  A piece that cannot
        be joined is set aside (the others may still reach it) and the rest go on: one
        blocked pad does not leave the whole net unrouted.  True if it ends in one piece."""
        cls = R.width_class(width)
        tries = 0
        stuck = set()                                 # items of pieces that failed as a start
        ok = True
        while True:
            groups = self.groups(net)
            if len(groups) < 2:
                return ok
            groups.sort(key=lambda g: len(self.cells_of(g)))
            free = [g for g in groups if not stuck.intersection(g)]
            if not free:
                return False
            src = free[0]
            others = [i for g in groups if g is not src for i in g]
            starts = self.cells_of(src, layers, inner=True)
            goals = self.cells_of(others, layers, inner=True)
            if not starts or not goals:
                self.failed.append((net, "no cells on the allowed layers"))
                return False
            bbox = None
            if bbox_margin is not None:
                pts = [self.g.pos(k) for _, k in list(starts) + list(goals)]
                m = bbox_margin
                bbox = (max(0, int((min(p[0] for p in pts) - m) / R.PITCH)),
                        max(0, int((min(p[1] for p in pts) - m) / R.PITCH)),
                        min(self.g.nx - 1, int((max(p[0] for p in pts) + m) / R.PITCH)),
                        min(self.g.ny - 1, int((max(p[1] for p in pts) + m) / R.PITCH)))
            self.lift(net)
            try:
                path = self.g.route(starts, goals, cls, layers=layers, allow_via=allow_via, max_pop=max_pop,
                                    bbox=bbox, via_cost=via_cost, layer_cost=layer_cost)
            finally:
                self.drop(net)
            if path is None:
                if self.g.last_region:
                    self.region[net] = (cls, self.g.last_region)
                what = ",".join(sorted(self.items[i].what for i in src if self.items[i].what not in ("track", "via")))
                self.failed.append((net, "from %s: %s" % (what or "a track", getattr(self.g, "last_why", "?"))))
                stuck.update(src)
                ok = False
                continue
            self.lay(net, path, width)
            tries += 1
            if tries > 200:
                self.failed.append((net, "too many pieces"))
                return False

    def lay(self, net, path, width):
        segs, vias = R.simplify(path, self.g.nx)
        n0 = len(self.items)
        for (L, x0, y0, x1, y1) in segs:
            self.track(net, L, (x0, y0), (x1, y1), width)
        for (x, y) in vias:
            self.via(net, x, y)
        for it in self.items[n0:]:
            it.routed = True

    # ---- rip-up -------------------------------------------------------------------
    def freeze_vias(self):
        """From here on a via the router lays can be taken back out: remember where vias
        may not go before it (the planned copper), and count the router's own."""
        self._nbase = bytes(self.g.novia)
        self._vcount = array("H", bytes(2 * len(self.g.novia)))

    def routed_copper(self, net):
        """The router's tracks and vias of `net`, to put back exactly (restore())."""
        return [it.seg for i in self.by_net.get(net, []) for it in [self.items[i]] if it.routed and it.seg]

    def rip(self, net):
        """Take every track and via the router laid for `net` back out."""
        for i in self.by_net.get(net, []):
            it = self.items[i]
            if not it.routed or it.what == "dead":
                continue
            if it.what == "via":
                _, x, y, d = it.seg
                for k in self.g._disc(x, y, d / 2 + VIA[1] / 2 + 0.25):
                    if self._vcount[k]:               # (a via from before freeze_vias() stays marked)
                        self._vcount[k] -= 1
                        if not self._vcount[k]:
                            self.g.novia[k] = self._nbase[k]
            self._kill(i)

    def restore(self, net, copper):
        for seg in copper:
            if seg[0] == "via":
                self.via(net, seg[1], seg[2])
            else:
                L, a, b, w = seg
                self.track(net, L, a, b, w)
            self.items[-1].routed = True

    def walls(self, net, cls, region, planned=False):
        """The nets whose router-laid copper bounds `region` (a walled-in search's cells,
        router.last_region): the ones to rip up so `net` can get out."""
        n = self.g.nx * self.g.ny
        nx = self.g.nx
        edge = {}
        for st in region:
            L, k = divmod(st, n)
            g, kl = self.g.g[(L, cls)], self.g.keep[L]
            for dk in (1, -1, nx, -nx, nx + 1, nx - 1, -nx + 1, -nx - 1):
                kk = k + dk
                if 0 <= kk < n and (g[kk] or kl[kk]):
                    edge.setdefault(L, set()).add(kk)
        out = []
        for other, ids in self.by_net.items():
            if other == net:
                continue
            for i in ids:
                it = self.items[i]
                if (it.routed or planned) and it.what != "dead" and any(
                        edge.get(L) and not edge[L].isdisjoint(ks)
                        for (L, c), ks in it.stamp.items() if c == cls):
                    out.append(other if not planned else "%s:%s%s" % (other, it.what, "" if it.routed else "(planned)"))
                    if not planned:
                        break
        if planned:
            kept = sum(1 for L, ks in edge.items() for k in ks if self.g.keep[L][k])
            out.append("keep:%d cells; layers %s" % (kept, sorted(edge)))
        return out

    def fanout(self, net, pad_items=None, reach=1.6, width=0.25, skip=()):
        """A via beside every SMD pad of `net` that does not already reach
        it through copper: a short track from the pad to the nearest spot where
        a via fits.  For a plane's net every via joins its plane."""
        made = 0
        for i in list(self.by_net.get(net, [])):
            it = self.items[i]
            if it.plane or it.what in ("track", "via", "zone") or not it.what:
                continue
            if pad_items is not None and it.what not in pad_items:
                continue
            if any(it.what.startswith(p) for p in skip):
                continue
            if self._reaches_plane(net, i):
                continue
            spot = self._via_spot(net, it, reach, width)
            if spot is None:
                continue                          # the router joins it to the net later
            path, (x, y) = spot
            if len(path) > 1:
                self.lay(net, path, width)
            self.via(net, x, y)
            made += 1
        return made

    def _reaches_plane(self, net, i):
        poly = self.planes.get(net, False)
        if poly is False:
            return False
        for g in self.groups(net):
            if i in g:
                return any(self.items[j].plane and (poly is None or self._inside(self.items[j], poly)) for j in g)
        return False

    def _via_spot(self, net, it, reach, width):
        """Breadth-first from the pad's cells on F.Cu to the nearest cell
        where a via of `net` fits; returns (path, (x, y))."""
        cls = R.width_class(width)
        L = min(it.cells)
        self.lift(net)
        try:
            gl = self.g.g[(L, cls)]
            vg = [self.g.g[(LL, "via")] for LL in range(R.NL)]
            start = list(it.cells[L])
            sx = sum(self.g.pos(k)[0] for k in start) / len(start)
            sy = sum(self.g.pos(k)[1] for k in start) / len(start)
            par = {k: None for k in start}
            frontier = list(start)
            nx = self.g.nx
            maxd = reach / R.PITCH
            while frontier:
                nxt = []
                # nearest-first inside a ring: sort by distance from the pad centre
                frontier.sort(key=lambda k: (self.g.pos(k)[0] - sx) ** 2 + (self.g.pos(k)[1] - sy) ** 2)
                poly = self.planes.get(net)
                for k in frontier:
                    # (a via needs no free track cell: keep only bars tracks, as on
                    # a plane's layer; novia holds the via keep-outs)
                    if k not in it.cells[L] and not self.g.novia[k] and all(not v[k] for v in vg) \
                            and (not poly or point_in_poly(*self.g.pos(k), poly)):
                        path = []
                        c = k
                        while c is not None:
                            path.append((L, c))
                            c = par[c]
                        path.reverse()
                        # start the track at the pad's centre cell
                        ck = self.g.k(sx, sy)
                        if ck in it.cells[L] and path[0][1] != ck:
                            path.insert(0, (L, ck))
                        return path, self.g.pos(k)
                for k in frontier:
                    i, j = k % nx, k // nx
                    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                        ii, jj = i + di, j + dj
                        if not (0 <= ii < nx and 0 <= jj < self.g.ny):
                            continue
                        kk = jj * nx + ii
                        if kk in par or gl[kk] or self.g.keep[L][kk]:
                            continue
                        if (ii - sx / R.PITCH) ** 2 + (jj - sy / R.PITCH) ** 2 > maxd * maxd:
                            continue
                        par[kk] = k
                        nxt.append(kk)
                frontier = nxt
        finally:
            self.drop(net)
        return None


def stamp(R, net, width, x0, y0, x1, y1):
    """The router's view of a window, for looking at why a net failed: per
    layer, 0 free, 1 blocked for this net's track width, 2 the net's own
    copper; and where a via would fit."""
    import router as RR
    cls = RR.width_class(width)
    i0, j0 = R.g.cell(x0, y0)
    i1, j1 = R.g.cell(x1, y1)
    own = R.cells_of(R.by_net.get(net, []))
    R.lift(net)
    try:
        layers = []
        for L in range(RR.NL):
            g = R.g.g[(L, cls)]
            rows = []
            for j in range(j0, j1 + 1):
                row = []
                for i in range(i0, i1 + 1):
                    k = j * R.g.nx + i
                    row.append(2 if (L, k) in own else (1 if (g[k] or R.g.keep[L][k]) else 0))
                rows.append(row)
            layers.append(rows)
        via = []
        vg = [R.g.g[(L, "via")] for L in range(RR.NL)]
        for j in range(j0, j1 + 1):
            via.append([0 if (not R.g.novia[j * R.g.nx + i] and all(not v[j * R.g.nx + i] for v in vg)) else 1
                        for i in range(i0, i1 + 1)])
    finally:
        R.drop(net)
    return dict(net=net, width=width, x0=i0 * RR.PITCH, y0=j0 * RR.PITCH, pitch=RR.PITCH, layers=layers, via=via)


def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xc:
                inside = not inside
    return inside
