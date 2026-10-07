#!/usr/bin/env python3
"""Late pin assignment: which RP2354A GPIO, which LP5036 output and which 74HC4051 input
each line uses, chosen from the board so that the lines leave each chip in the order in
which they arrive at it, and need not cross.  River routing: a pin is bound only where
the river from the chip meets the river coming to it.

    python3 gen/assign.py        writes gen/assignment.json (pins.py and leds.py read it)

For each chip, a ring round it, just outside its own decoupling.  One multi-source
search outward from every cell of the ring, over the board with its big obstacles (the
coils, the antennas' keep-outs, through-hole pins, the board's edge), labels every cell
with the ring position at which its shortest path reaches the chip.  A line's
destination (the nearest of its other pads) then says where on the ring the line
arrives; a pin's own place on the ring is the point straight out from it.  Binding pins
to lines is a matching on the ring: least total squared distance along the ring, which
for a convex cost is a matching without crossings, within each pin's constraints:

  * LP5036 outputs are all alike: the firmware's bank split takes any mix of LEDs in a
    bank (firmware/src/led_engine.c), and led_map.h is generated from gen/leds.py;
  * 74HC4051 inputs are all alike: the firmware takes them from board_pins.h;
  * RP2354A GPIOs move within their function classes (gen/pins.py, FUNCTIONS): each coil
    bridge's two inputs on one PWM slice (A even, B odd, GPIO0-15), the audio on a free
    slice's A output, the three analogue lines on GPIO26-29, I2C0 and UART0 on pins
    their instances allow, the mux's three select lines on consecutive pins (one masked
    write), the rest anywhere.  A matching cannot hold all that, so a simulated
    annealing over valid assignments does, from the hand-written table.

The destinations come from the last netlist (hardware/checks/netlist.net).  Binding a pin
changes which chip pin a net reaches, never where the net goes, so running this again on
its own result changes nothing.
"""
import heapq, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from sexp import parse, kids, kid, val
import layout as L
import placement as PL
from parts import COILS

OUT = os.path.join(HERE, "assignment.json")
NETLIST = os.path.join(ROOT, "hardware", "checks", "netlist.net")
PRETTY = os.path.join(ROOT, "hardware", "lib", "OWL.pretty")
PITCH = 0.5                       # the search's grid, mm

# The chips whose pins are bound here: ref -> (board, the ring's margin outside the
# chip's pads, mm)
RING = {"U4": ("base", 2.6), "U3": ("base", 1.6), "U11": ("base", 1.4), "U101": ("tree", 1.6)}
LP5036_OUT = {ch: str(ch + 1) for ch in range(36)}                     # OUTn is pin n + 1
HC4051_IN = {0: "13", 1: "14", 2: "15", 3: "12", 4: "1", 5: "5", 6: "2", 7: "4"}


# ======================================================================================
# The board as the netlist and the placement give it
# ======================================================================================
def netlist():
    doc = parse(open(NETLIST, encoding="utf-8").read())[0]
    comps = {val(kid(c, "ref")): val(kid(c, "footprint")) for c in kids(kid(doc, "components"), "comp")}
    nets = {}
    for n in kids(kid(doc, "nets"), "net"):
        nets[val(kid(n, "name"))] = [(val(kid(x, "ref")), val(kid(x, "pin"))) for x in kids(n, "node")]
    return comps, nets


_FP = {}


def fp_pads(fpid):
    """{pad number: (x, y, half-size, plated through)} in the footprint's frame."""
    name = fpid.split(":", 1)[1]
    if name not in _FP:
        node = parse(open(os.path.join(PRETTY, name + ".kicad_mod"), encoding="utf-8").read())[0]
        pads = {}
        for p in kids(node, "pad"):
            num = val(p, 1)
            at, size = kid(p, "at"), kid(p, "size")
            x, y = float(val(at, 1)), float(val(at, 2))
            r = max(float(val(size, 1)), float(val(size, 2))) / 2
            pads.setdefault(num, (x, y, r, val(p, 2) == "thru_hole"))
        _FP[name] = pads
    return _FP[name]


class Board:
    def __init__(self, name, comps):
        self.name = name
        self.place = PL.BOARDS[name].place
        self.comps = comps
        self.w, self.h = {"base": (L.BASE_W, L.BASE_H), "tree": (L.TREE_W, L.TREE_H)}[name]

    def pad(self, ref, num):
        x, y, rot, side = self.place[ref]
        px, py, r, th = fp_pads(self.comps[ref])[num]
        dx, dy = PL.rel(rot, side, px, py)
        return (x + dx, y + dy)

    def pads(self, ref):
        x, y, rot, side = self.place[ref]
        out = {}
        for num, (px, py, r, th) in fp_pads(self.comps[ref]).items():
            dx, dy = PL.rel(rot, side, px, py)
            out[num] = (x + dx, y + dy, r, th)
        return out


# ======================================================================================
# The search: every cell labelled with where its shortest path meets the chip's ring
# ======================================================================================
class Ring:
    """A circle round a chip, through the corners of its pads' box grown by `margin`,
    parametrised by t, the distance along it clockwise on the screen from +x.  (A circle,
    not a rectangle: every line arriving from a rectangle's corner wedge would arrive
    at the corner itself, and their order would be lost.)"""

    def __init__(self, bd, ref, margin):
        ps = [(x, y) for num, (x, y, r, th) in bd.pads(ref).items() if num.isdigit()]
        self.pin_box = (min(p[0] for p in ps), max(p[0] for p in ps), min(p[1] for p in ps), max(p[1] for p in ps))
        ax0, ax1, ay0, ay1 = self.pin_box
        self.cx, self.cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        self.R = math.hypot((ax1 - ax0) / 2 + margin, (ay1 - ay0) / 2 + margin)
        self.P = 2 * math.pi * self.R

    def t(self, x, y):
        a = math.atan2(y - self.cy, x - self.cx)
        return (a % (2 * math.pi)) * self.R

    def pin_t(self, x, y):
        """A pin's place on the ring: straight out from its side of the package."""
        ax0, ax1, ay0, ay1 = self.pin_box
        d = {"top": abs(y - ay0), "right": abs(x - ax1), "bottom": abs(y - ay1), "left": abs(x - ax0)}
        side = min(d, key=d.get)
        if side in ("top", "bottom"):
            dy = math.sqrt(max(self.R ** 2 - (x - self.cx) ** 2, 0.0))
            return self.t(x, self.cy + (dy if side == "bottom" else -dy))
        dx = math.sqrt(max(self.R ** 2 - (y - self.cy) ** 2, 0.0))
        return self.t(self.cx + (dx if side == "right" else -dx), y)

    def dist(self, a, b):
        d = abs(a - b) % self.P
        return min(d, self.P - d)

    def inside(self, x, y):
        return (x - self.cx) ** 2 + (y - self.cy) ** 2 < self.R ** 2


def obstacles(bd):
    """The cells no line crosses: off the board (and its last millimetre), the coils, the
    antennas' keep-outs, through-hole pins (a line may pass between them)."""
    nx, ny = int(bd.w / PITCH) + 1, int(bd.h / PITCH) + 1
    block = bytearray(nx * ny)

    def disc(cx, cy, r):
        i0, i1 = max(0, int((cx - r) / PITCH)), min(nx - 1, int((cx + r) / PITCH) + 1)
        j0, j1 = max(0, int((cy - r) / PITCH)), min(ny - 1, int((cy + r) / PITCH) + 1)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                if (i * PITCH - cx) ** 2 + (j * PITCH - cy) ** 2 <= r * r:
                    block[j * nx + i] = 1
    for j in range(ny):
        for i in range(nx):
            x, y = i * PITCH, j * PITCH
            if x < 1.0 or y < 1.0 or x > bd.w - 1.0 or y > bd.h - 1.0:
                block[j * nx + i] = 1
    for ref, (x, y, rot, side) in bd.place.items():
        name = bd.comps[ref].split(":", 1)[1]
        if name.startswith("Coil_"):
            disc(x, y, COILS["COIL_" + name[5:]]["r_out"] + L.COIL_KEEPOUT + 0.3)
            continue
        for num, (px, py, r, th) in bd.pads(ref).items():
            if th:
                disc(px, py, r + 0.25)
    if bd.name == "base":
        for (cx, cy, r) in (L.MOON, L.GHOST):
            disc(cx, cy, r + L.ANTENNA_KEEPOUT)
    return block, nx, ny


def search(bd, ring, block, nx, ny):
    """Multi-source Dijkstra outward from the ring: (distance, ring position) per cell."""
    INF = float("inf")
    dist = [INF] * (nx * ny)
    lab = [None] * (nx * ny)
    par = [-1] * (nx * ny)
    pq = []
    for j in range(ny):
        for i in range(nx):
            x, y = i * PITCH, j * PITCH
            on = (not ring.inside(x, y) and (x - ring.cx) ** 2 + (y - ring.cy) ** 2 <= (ring.R + PITCH) ** 2
                  and not block[j * nx + i])
            if on:
                k = j * nx + i
                dist[k] = 0.0
                lab[k] = ring.t(x, y)
                pq.append((0.0, k))
    heapq.heapify(pq)
    NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    while pq:
        d, k = heapq.heappop(pq)
        if d > dist[k]:
            continue
        i, j = k % nx, k // nx
        for di, dj, c in NB:
            ii, jj = i + di, j + dj
            if not (0 <= ii < nx and 0 <= jj < ny):
                continue
            kk = jj * nx + ii
            if block[kk] or ring.inside(ii * PITCH, jj * PITCH):
                continue
            nd = d + c * PITCH
            if nd < dist[kk]:
                dist[kk] = nd
                lab[kk] = lab[k]
                par[kk] = k
                heapq.heappush(pq, (nd, kk))
    return dist, lab, par


def sees(ring, block, nx, x, y):
    """Whether the straight line from (x, y) in to the ring, toward its centre, is free."""
    dx, dy = ring.cx - x, ring.cy - y
    L = math.hypot(dx, dy) - ring.R
    if L <= 0:
        return True
    n = int(L / (PITCH / 2)) + 1
    for k in range(n + 1):
        f = (L * k / n) / (L + ring.R)
        i, j = int(round((x + dx * f) / PITCH)), int(round((y + dy * f) / PITCH))
        if block[j * nx + i]:
            return False
    return True


def arrival(bd, ring, field, nx, ny, pads, block):
    """Where on the ring a line from these pads arrives, as (path length, t): along the
    nearest pad's shortest path, back to the first point that sees the chip, and that
    point's angle round the ring's centre.  (The grid's own labels would do, but an
    8-neighbour search measures distance as an octagon does, so every far line would
    arrive at one of eight points.)  A pad inside an obstacle, a through-hole pin in its
    own disc, starts from the nearest free cell."""
    dist, lab, par = field
    best = None
    for (x, y) in pads:
        if ring.inside(x, y):
            # a destination inside the ring itself (a part beside the chip): its own angle
            if best is None or best[0] > 0.0:
                best = (0.0, ring.t(x, y))
            continue
        ci, cj = int(round(x / PITCH)), int(round(y / PITCH))
        for rr in range(0, 9):
            cands = []
            for dj in range(-rr, rr + 1):
                for di in range(-rr, rr + 1):
                    if max(abs(di), abs(dj)) != rr:
                        continue
                    ii, jj = ci + di, cj + dj
                    if 0 <= ii < nx and 0 <= jj < ny and lab[jj * nx + ii] is not None:
                        cands.append((dist[jj * nx + ii], jj * nx + ii))
            if cands:
                d, k = min(cands)
                if best is None or d < best[0]:
                    while par[k] >= 0 and not sees(ring, block, nx, (k % nx) * PITCH, (k // nx) * PITCH):
                        k = par[k]
                    best = (d, ring.t((k % nx) * PITCH, (k // nx) * PITCH))
                break
    return best


# ======================================================================================
# Matching
# ======================================================================================
def hungarian(cost):
    """Minimum-cost assignment of n rows to m >= n columns: returns col[row]."""
    n, m = len(cost), len(cost[0])
    INF = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    col = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            col[p[j] - 1] = j - 1
    return col


def crossings(ring, pairs):
    """How many pairs of lines must cross between the chip and the ring: (pin t, arrival
    t) pairs, the lines leaving through the annulus round the chip, free to wind either
    way, so only the two cyclic orders matter: the fewest pairs out of order between
    them, over every way of cutting each circle open."""
    n = len(pairs)
    if n < 2:
        return 0
    best = None
    for pc in sorted({p for p, a in pairs}):
        order = sorted(pairs, key=lambda q: ((q[0] - pc) % ring.P, q[1]))
        for ac in sorted({a for p, a in pairs}):
            ks = [(a - ac) % ring.P for p, a in order]
            inv = sum(1 for i in range(n) for j in range(i + 1, n) if ks[i] > ks[j] + TIE)
            if best is None or inv < best:
                best = inv
    return best


def bind_free(ring, lines, pins):
    """lines: {net: arrival t}; pins: {key: pin t}.  Returns {net: key}."""
    names, keys = sorted(lines), sorted(pins, key=lambda k: pins[k])
    cost = [[ring.dist(lines[n], pins[k]) ** 2 for k in keys] for n in names]
    col = hungarian(cost)
    return {n: keys[c] for n, c in zip(names, col)}


# ---- the RP2354A ------------------------------------------------------------------------
BRIDGES = [("PEND1_IN1", "PEND1_IN2"), ("PEND2_IN1", "PEND2_IN2"), ("PEND3_IN1", "PEND3_IN2"),
           ("LEV_IN1", "LEV_IN2"), ("FAM1_A", "FAM1_B"), ("FAM2_A", "FAM2_B")]
ADC_NETS = ("HALL", "LEV_IPROPI", "MUX_OUT")
I2C0 = [(4 * k, 4 * k + 1) for k in range(8)]             # (SDA, SCL)
UART0 = [(0, 1), (12, 13), (16, 17), (28, 29)]             # (TX, RX)
UNITS = [list(b) for b in BRIDGES] + [["SDA", "SCL"], ["UART_TX", "UART_RX"], ["MUX_S0", "MUX_S1", "MUX_S2"]]


def violations(a):
    """How many of the RP2354A's function constraints the assignment breaks (0: valid)."""
    v = 0
    if len(set(a.values())) != len(a):
        v += 100
    slices = set()
    for x, y in BRIDGES:
        g = a[x]
        v += (g % 2 != 0) + (a[y] != g + 1) + (g >= 16)
        slices.add(g // 2)
    au = a["AUDIO"]
    v += (au % 2 != 0) + (au >= 16) + (au // 2 in slices)
    v += sum(1 for n in ADC_NETS if not 26 <= a[n] <= 29)
    v += ((a["SDA"], a["SCL"]) not in I2C0) + ((a["UART_TX"], a["UART_RX"]) not in UART0)
    v += (a["MUX_S1"] != a["MUX_S0"] + 1) + (a["MUX_S2"] != a["MUX_S0"] + 2)
    return v


def gpio_valid(a):
    return violations(a) == 0


TIE = 0.6        # lines arriving this close together (mm along the ring) run side by side and
                 # can change places farther out: their order is no crossing


def _cut(ts, P):
    """Where to open a circle of points: the middle of their widest gap."""
    ts = sorted(t % P for t in ts)
    gaps = [((ts[(i + 1) % len(ts)] - ts[i]) % P, i) for i in range(len(ts))]
    g, i = max(gaps)
    return (ts[i] + g / 2) % P


def cyclic_crossings(P, seq):
    """seq: the lines' arrival positions in the order of their pins round the chip.  The
    fewest pairs out of order over every rotation of the arrivals (lines within TIE of
    each other never count): one count, then each rotation's change in one pass."""
    n = len(seq)
    order = sorted(range(n), key=lambda i: seq[i])
    vals = list(seq)
    inv = sum(1 for i in range(n) for j in range(i + 1, n) if vals[i] > vals[j] + TIE)
    best = inv
    for k in order[:-1]:
        # the smallest arrival becomes the largest: it was out of order with the larger
        # ones before it, and is now out of order with the smaller ones after it
        x = vals[k]
        before = sum(1 for i in range(k) if vals[i] > x + TIE)
        x2 = x + P
        after = sum(1 for j in range(k + 1, n) if x2 > vals[j] + TIE)
        before2 = sum(1 for i in range(k) if vals[i] > x2 + TIE)
        after1 = sum(1 for j in range(k + 1, n) if x > vals[j] + TIE)
        inv += (after + before2) - (before + after1)
        vals[k] = x2
        best = min(best, inv)
    return best


CROSS = 150.0    # one crossing costs as much as this much squared sideways travel, mm^2
SINGLES = ("IMU_INT", "THEREMIN_PITCH", "THEREMIN_VOL", "DRV_nSLEEP", "DRV_nFAULT", "FAM_EN", "BUTTON")


def bind_gpio(ring, arr, gpio_t, start):
    """An exhaustive search.  Both circles are opened at the chip's west side, where it
    has no GPIO and where its USB, QSPI and regulator lie (the pins' widest gap, and the
    arrivals': nothing on the board lies north-west of the chip), so a line may wrap
    round the east side but not the west; a crossing is then a pair of lines out of
    order, and the cost is CROSS a crossing plus the squared sideways travel round the
    ring.  The groups go in arrival order within their kind (the six bridges onto the
    slices chosen for them, the three analogue lines onto GPIO26-29), and the free lines
    fill the pins left in arrival order: what is searched is which slices the bridges
    and the audio take, which analogue pin is spare, and where I2C, UART and the mux's
    selects sit."""
    from itertools import combinations
    have = set(arr)
    pc = _cut(gpio_t.values(), ring.P)
    ac = _cut([arr[n] for n in have], ring.P)
    plin = {g: (t - pc) % ring.P for g, t in gpio_t.items()}
    alin = {n: (arr[n] - ac) % ring.P for n in have}
    A = lambda n: alin.get(n, 0.0)

    def score(a):
        seq = [alin[n] for n in sorted(have, key=lambda n: plin[a[n]])]
        inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j] + TIE)
        return CROSS * inv + sum(ring.dist(arr[n], gpio_t[a[n]]) ** 2 for n in have), inv
    bridges = sorted(BRIDGES, key=lambda b: (A(b[0]) + A(b[1])) / 2)
    adc = sorted(ADC_NETS, key=A)
    singles = sorted(SINGLES, key=A)
    best, c_best = None, None
    for chosen in combinations(range(8), 6):
        slots = sorted(chosen, key=lambda k: plin[2 * k])
        base = {}
        for (n1, n2), k in zip(bridges, slots):
            base[n1], base[n2] = 2 * k, 2 * k + 1
        for au in [k for k in range(8) if k not in chosen]:
            a1 = dict(base)
            a1["AUDIO"] = 2 * au
            for spare in range(26, 30):
                pins = sorted([g for g in range(26, 30) if g != spare], key=lambda g: plin[g])
                a2 = dict(a1)
                for n, g in zip(adc, pins):
                    a2[n] = g
                used2 = set(a2.values())
                for sda, scl in I2C0:
                    if sda in used2 or scl in used2:
                        continue
                    for tx, rx in UART0:
                        if {tx, rx} & (used2 | {sda, scl}):
                            continue
                        used4 = used2 | {sda, scl, tx, rx}
                        for m in range(28):
                            if {m, m + 1, m + 2} & used4:
                                continue
                            a = dict(a2)
                            a.update(SDA=sda, SCL=scl, UART_TX=tx, UART_RX=rx, MUX_S0=m, MUX_S1=m + 1, MUX_S2=m + 2)
                            free = sorted(set(range(30)) - set(a.values()), key=lambda g: plin[g])
                            for n, g in zip(singles, free):
                                a[n] = g
                            if not gpio_valid(a):
                                continue
                            c, inv = score(a)
                            if c_best is None or c < c_best:
                                best, c_best = a, c
    assert best is not None, "no valid GPIO assignment found"
    return best, c_best


# ======================================================================================
def main():
    import pins as PINS
    comps, nets = netlist()
    boards = {n: Board(n, comps) for n in ("base", "tree")}
    out = {"gpio": {}, "led": {"BASE": {}, "TREE": {}}, "mux": {}, "report": {}}
    rings, fields = {}, {}
    grids = {n: obstacles(b) for n, b in boards.items()}
    for ref, (bname, margin) in RING.items():
        bd = boards[bname]
        ring = Ring(bd, ref, margin)
        block, nx, ny = grids[bname]
        rings[ref] = ring
        fields[ref] = (search(bd, ring, block, nx, ny), nx, ny)

    def arrival_of(ref, pin):
        """Where the line on `ref`'s pin arrives on its ring (None: no line there)."""
        bd = boards[RING[ref][0]]
        ring = rings[ref]
        field, nx, ny = fields[ref]
        for net, nodes in nets.items():
            if (ref, pin) in nodes:
                others = [bd.pad(r, p) for r, p in nodes if r != ref]
                a = arrival(bd, ring, field, nx, ny, others, grids[RING[ref][0]][0]) if others else None
                return a[1] if a else None
        return None

    def report(ref, before, after, pin_t, arr):
        ring = rings[ref]
        pb = [(pin_t[before[n]], arr[n]) for n in arr]
        pa = [(pin_t[after[n]], arr[n]) for n in arr]
        cb = sum(ring.dist(p, a) ** 2 for p, a in pb)
        ca = sum(ring.dist(p, a) ** 2 for p, a in pa)
        r = dict(lines=len(pa), crossings_before=crossings(ring, pb), crossings_after=crossings(ring, pa),
                 cost_before=round(cb, 1), cost_after=round(ca, 1))
        out["report"][ref] = r
        print("assign %-5s %2d lines: crossings %3d -> %3d, sum of squared ring distances %8.0f -> %8.0f mm^2"
              % (ref, r["lines"], r["crossings_before"], r["crossings_after"], cb, ca))

    def net_on(ref, pin):
        for net, nodes in nets.items():
            if (ref, pin) in nodes:
                return net, nodes
        return None, []

    # ---- the LP5036s: every LED by name (its role), on the output the netlist has now ---
    import leds as LEDS
    role_of = {r: k for k, r in PL.ROLES.items()}
    for ref, drv in (("U3", "BASE"), ("U101", "TREE")):
        bd = boards[RING[ref][0]]
        ring = rings[ref]
        pin_t = {ch: ring.pin_t(*bd.pad(ref, num)) for ch, num in LP5036_OUT.items()}
        now = {}
        for ch, num in LP5036_OUT.items():
            net, nodes = net_on(ref, num)
            leds_ = [role_of.get(r, "") for r, p in nodes if role_of.get(r, "").startswith("led:")]
            if leds_:
                now[leds_[0][4:]] = ch
            elif net:
                # an LED on another board, reached through a connector: by its net's name
                names = {nm for (d, c), (nm, col, w) in LEDS.DEFAULT.items() if d == drv}
                short = net.split("/")[-1]
                for nm in (short, "PERCH_" + short):
                    if nm in names:
                        now[nm] = ch
        arr = {name: arrival_of(ref, LP5036_OUT[ch]) for name, ch in now.items()}
        missing = [n for n, t in arr.items() if t is None]
        assert not missing, "%s: no line found for %s" % (ref, missing)
        bound = bind_free(ring, arr, pin_t)
        report(ref, now, bound, pin_t, arr)
        out["led"][drv] = {n: bound[n] for n in sorted(bound)}

    # ---- the 74HC4051 ---------------------------------------------------------------------
    bd = boards["base"]
    ring = rings["U11"]
    pin_t = {ch: ring.pin_t(*bd.pad("U11", num)) for ch, num in HC4051_IN.items()}
    now = {net_on("U11", num)[0].split("/")[-1]: ch for ch, num in HC4051_IN.items()}
    arr = {net: arrival_of("U11", HC4051_IN[ch]) for net, ch in now.items()}
    bound = bind_free(ring, arr, pin_t)
    report("U11", now, bound, pin_t, arr)
    out["mux"] = {n: bound[n] for n in sorted(bound)}

    # ---- the RP2354A ----------------------------------------------------------------------
    import symbols as SYM
    ring = rings["U4"]
    gpio_t = {g: ring.pin_t(*bd.pad("U4", str(pin))) for g, pin in SYM.GPIO_PIN.items()}
    now = {net_on("U4", str(pin))[0].split("/")[-1]: g for g, pin in SYM.GPIO_PIN.items()}
    assert sorted(now) == sorted(PINS.DEFAULT_DIR), "the netlist's GPIO nets are not pins.py's"
    arr = {net: arrival_of("U4", str(SYM.GPIO_PIN[g])) for net, g in now.items()}
    arr = {n: t for n, t in arr.items() if t is not None}
    best, c = bind_gpio(ring, arr, gpio_t, now)
    report("U4", now, best, gpio_t, arr)
    out["gpio"] = {n: best[n] for n in sorted(best)}

    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    print("assign: -> %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
