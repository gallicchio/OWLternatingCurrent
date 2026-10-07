"""A grid router with A* per connection, for a four-layer board whose In2 is
an unbroken ground plane: tracks go on F.Cu, In1.Cu and B.Cu.  (GPiBridge's router,
gen/router.py there; here a board's real outline is its edge, and the grid is built
with slices rather than a loop per cell, for boards a hundred times larger.)

Adapted from the ECP5-2ADC-2DAC project's pcb/router.py.  Obstacles live in
reference-counted cell grids, one per (layer, width class): an obstacle of
radius R blocks every cell closer than R + clearance + half the track width,
so a track of that class is legal wherever its cells are free.  A net's own
pads and tracks are lifted out of the grids while it is routed, which lets a
track start inside its pad and join its own net anywhere.  Vias are through
vias and need a free cell on every routing layer in the via's class.

Grid pitch 0.1 mm, so the RP2354A's 0.4 mm pins sit on it.
"""
import heapq, math
from array import array

PITCH = 0.1
LAYERS = ["F.Cu", "In1.Cu", "B.Cu"]          # In2.Cu is the ground plane
NL = len(LAYERS)
CLEAR = 0.16                                   # rules ask 0.15; the grid rounds
# half widths: fine 0.127 mm, thin 0.15, mid 0.2, wide 0.4, power 1.0, heavy 2.0, via 0.45 mm pad
CLASSES = {"fine": 0.0635, "thin": 0.075, "mid": 0.1, "wide": 0.2, "power": 0.5, "heavy": 1.0, "via": 0.225}
CLS = ["fine", "thin", "mid", "wide", "power", "heavy", "via"]
VIA_COST = 40.0                                # about 4 mm of track
TURN_COST = 2.0
# per layer, the cost multiplier of (horizontal, vertical) steps: F.Cu free,
# In1 and B.Cu nudged toward one direction each so they cross cleanly
DIR_PENALTY = {0: (1.0, 1.0), 1: (1.0, 1.3), 2: (1.3, 1.0)}


def width_class(w):
    hw = w / 2.0
    for c in ("fine", "thin", "mid", "wide", "power", "heavy"):
        if hw <= CLASSES[c] + 1e-6:
            return c
    return "heavy"


class Grid:
    def __init__(self, w, h, edge_clear=0.3, outline=None):
        """A w x h mm grid.  outline: the board's edge as polygons in grid millimetres
        (the first the outside, the others holes); copper keeps edge_clear from it."""
        self.w, self.h = w, h
        self.nx, self.ny = int(round(w / PITCH)) + 1, int(round(h / PITCH)) + 1
        self.n = self.nx * self.ny
        self.g = {(L, c): array("H", bytes(2 * self.n)) for L in range(NL) for c in CLS}
        self.keep = {L: bytearray(self.n) for L in range(NL)}    # 1 = no track of any net
        self.novia = bytearray(self.n)
        nx = self.nx
        if outline is None:
            outline = [[(0, 0), (w, 0), (w, h), (0, h)]]
        # outside the outline (or inside a hole): blocked for everything
        outside = bytearray(self.n)
        for j in range(self.ny):
            y = j * PITCH
            xs = []
            for poly in outline:
                n = len(poly)
                for a in range(n):
                    x0, y0 = poly[a]
                    x1, y1 = poly[(a + 1) % n]
                    if (y0 > y) != (y1 > y):
                        xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            row = bytearray(b"\x01") * nx
            for a in range(0, len(xs) - 1, 2):
                i0 = max(0, int(math.ceil(xs[a] / PITCH)))
                i1 = min(nx - 1, int(math.floor(xs[a + 1] / PITCH)))
                if i1 >= i0:
                    row[i0:i1 + 1] = bytes(i1 - i0 + 1)
            outside[j * nx:(j + 1) * nx] = row
        self.outside = outside
        self.keep = {L: bytearray(outside) for L in range(NL)}
        self.novia = bytearray(outside)
        # within edge_clear (plus the track's half width) of the edge: blocked too
        for c in CLS:
            r = edge_clear + CLASSES[c]
            cells = set()
            for poly in outline:
                n = len(poly)
                for a in range(n):
                    (x0, y0), (x1, y1) = poly[a], poly[(a + 1) % n]
                    cells.update(self.shape_cells(("seg", x0, y0, x1, y1, 0.0), r))
            for L in range(NL):
                arr = self.g[(L, c)]
                for kk in cells:
                    arr[kk] += 1
        vcells = set()
        for poly in outline:
            n = len(poly)
            for a in range(n):
                (x0, y0), (x1, y1) = poly[a], poly[(a + 1) % n]
                vcells.update(self.shape_cells(("seg", x0, y0, x1, y1, 0.0), edge_clear + CLASSES["via"]))
        for kk in vcells:
            self.novia[kk] = 1

    def cell(self, x, y):
        return (int(round(x / PITCH)), int(round(y / PITCH)))

    def k(self, x, y):
        i, j = self.cell(x, y)
        return j * self.nx + i

    def pos(self, k):
        return ((k % self.nx) * PITCH, (k // self.nx) * PITCH)

    # ---- obstacles --------------------------------------------------------
    def shape_cells(self, shape, r):
        """Cells within r of a shape: ("disc", x, y, rad) | ("rect", x, y, hw,
        hh, ang) | ("seg", x0, y0, x1, y1, hw)."""
        kind = shape[0]
        if kind == "disc":
            _, x, y, rad = shape
            return self._disc(x, y, rad + r)
        if kind == "seg":
            _, x0, y0, x1, y1, hw = shape
            L = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(L / (PITCH * 0.5)))
            out = set()
            for s in range(n + 1):
                t = s / float(n)
                out.update(self._disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, hw + r))
            return out
        _, x, y, hw, hh, ang = shape
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        rr = math.hypot(hw, hh) + r
        ci, cj = self.cell(x, y)
        n = int(math.ceil(rr / PITCH)) + 1
        out = []
        for di in range(-n, n + 1):
            i = ci + di
            if not (0 <= i < self.nx):
                continue
            for dj in range(-n, n + 1):
                j = cj + dj
                if not (0 <= j < self.ny):
                    continue
                dx, dy = i * PITCH - x, j * PITCH - y
                ux, uy = dx * ca + dy * sa, -dx * sa + dy * ca
                gx, gy = max(0.0, abs(ux) - hw), max(0.0, abs(uy) - hh)
                if gx * gx + gy * gy <= r * r + 1e-9:
                    out.append(j * self.nx + i)
        return out

    def _disc(self, x, y, r):
        ci, cj = self.cell(x, y)
        n = int(math.ceil(r / PITCH)) + 1
        out = []
        r2 = r * r + 1e-9
        for di in range(-n, n + 1):
            i = ci + di
            if not (0 <= i < self.nx):
                continue
            dx2 = (i * PITCH - x) ** 2
            for dj in range(-n, n + 1):
                j = cj + dj
                if 0 <= j < self.ny and dx2 + (j * PITCH - y) ** 2 <= r2:
                    out.append(j * self.nx + i)
        return out

    def obstacle(self, shape, layers, clear=CLEAR):
        """{(L, cls): cells} that `shape` on `layers` blocks for each class."""
        out = {}
        for c in CLS:
            cells = self.shape_cells(shape, clear + CLASSES[c])
            for L in layers:
                out[(L, c)] = cells
        return out

    def add(self, cells):
        for key, ks in cells.items():
            a = self.g[key]
            for k in ks:
                a[k] += 1

    def sub(self, cells):
        for key, ks in cells.items():
            a = self.g[key]
            for k in ks:
                if a[k] > 0:
                    a[k] -= 1

    def keepout(self, x0, y0, x1, y1, layers, via=True):
        i0, j0 = self.cell(min(x0, x1), min(y0, y1))
        i1, j1 = self.cell(max(x0, x1), max(y0, y1))
        for j in range(max(0, j0), min(self.ny - 1, j1) + 1):
            for i in range(max(0, i0), min(self.nx - 1, i1) + 1):
                k = j * self.nx + i
                for L in layers:
                    self.keep[L][k] = 1
                if via:
                    self.novia[k] = 1

    # ---- the search -------------------------------------------------------
    def route(self, starts, goals, cls, layers=None, allow_via=True, max_pop=600000, bbox=None,
              via_cost=VIA_COST, layer_cost=None):
        """starts, goals: sets of (L, k).  Returns [(L, k), ...] or None.
        layer_cost: {L: multiplier} on a layer's step costs (default 1)."""
        nx = self.nx
        if bbox is None:
            i0, j0, i1, j1 = 0, 0, nx - 1, self.ny - 1
        else:
            i0, j0, i1, j1 = bbox
        grid = [self.g[(L, cls)] for L in range(NL)]
        vg = [self.g[(L, "via")] for L in range(NL)]
        keep = self.keep
        use = list(layers) if layers is not None else list(range(NL))
        goal = set(goals)
        gpts = list({(k % nx, k // nx) for (_, k) in goal})
        if len(gpts) > 60:
            gpts = gpts[::max(1, len(gpts) // 60)]

        def h(i, j):
            return min(max(abs(gi - i), abs(gj - j)) + 0.414 * min(abs(gi - i), abs(gj - j)) for gi, gj in gpts) * 0.98

        pq, best, par = [], {}, {}
        for s in starts:
            if s in goal:
                return [s]
            if s[0] not in use:
                continue
            best[s] = 0.0
            heapq.heappush(pq, (h(s[1] % nx, s[1] // nx), 0.0, s[0], s[1], -1))
        NB = [(1, 0, 1.0, 0), (-1, 0, 1.0, 0), (0, 1, 1.0, 1), (0, -1, 1.0, 1),
              (1, 1, 1.414, 2), (1, -1, 1.414, 3), (-1, 1, 1.414, 3), (-1, -1, 1.414, 2)]
        pops, found = 0, None
        while pq:
            f, gc, L, k, d = heapq.heappop(pq)
            if best.get((L, k), 1e18) < gc - 1e-9:
                continue
            pops += 1
            if pops > max_pop:
                break
            if (L, k) in goal:
                found = (L, k)
                break
            i, j = k % nx, k // nx
            ph, pv = DIR_PENALTY[L]
            if layer_cost:
                lc = layer_cost.get(L, 1.0)
                ph, pv = ph * lc, pv * lc
            gl, kl = grid[L], keep[L]
            for di, dj, c, nd in NB:
                ii, jj = i + di, j + dj
                if ii < i0 or jj < j0 or ii > i1 or jj > j1:
                    continue
                kk = jj * nx + ii
                if (gl[kk] or kl[kk]) and (L, kk) not in goal:
                    continue
                if di and dj:
                    if gl[j * nx + ii] or gl[jj * nx + i]:
                        continue
                    cc = c * (ph + pv) / 2.0
                else:
                    cc = c * (ph if di else pv)
                if d >= 0 and d != nd:
                    cc += TURN_COST
                ng = gc + cc
                if ng < best.get((L, kk), 1e18):
                    best[(L, kk)] = ng
                    par[(L, kk)] = (L, k)
                    heapq.heappush(pq, (ng + h(ii, jj), ng, L, kk, nd))
            if allow_via and not self.novia[k] and all(not vg[LL][k] for LL in range(NL)):
                for LL in use:
                    if LL == L:
                        continue
                    ng = gc + via_cost
                    if ng < best.get((LL, k), 1e18):
                        best[(LL, k)] = ng
                        par[(LL, k)] = (L, k)
                        heapq.heappush(pq, (ng + h(i, j), ng, LL, k, -1))
        if found is None:
            return None
        path, cur = [], found
        while cur is not None:
            path.append(cur)
            cur = par.get(cur)
        path.reverse()
        return path


def simplify(path, nx):
    """Runs of one direction on one layer become segments; a change of layer
    is a via.  Returns (segments [(L, x0, y0, x1, y1)], vias [(x, y)])."""
    segs, vias = [], []
    if not path:
        return segs, vias
    pts = [(L, (k % nx) * PITCH, (k // nx) * PITCH) for L, k in path]
    i = 0
    while i < len(pts) - 1:
        L, x, y = pts[i]
        if pts[i + 1][0] != L:
            vias.append((x, y))
            i += 1
            continue
        dx, dy = round((pts[i + 1][1] - x) / PITCH), round((pts[i + 1][2] - y) / PITCH)
        j = i + 1
        while j + 1 < len(pts) and pts[j + 1][0] == L and \
                (round((pts[j + 1][1] - pts[j][1]) / PITCH), round((pts[j + 1][2] - pts[j][2]) / PITCH)) == (dx, dy):
            j += 1
        segs.append((L, x, y, pts[j][1], pts[j][2]))
        i = j
    return segs, vias
