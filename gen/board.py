#!/usr/bin/env python3
"""Make hardware/OWLternatingCurrent.kicad_pcb: the whole panel (the base, the tree, the
perch, the bat and the two tokens, with the frame that holds them) from the netlist, the
floor plan (gen/layout.py), the placement table (gen/placement.py), the art
(gen/art.py) and the planned copper and router (gen/routes.py, gen/routing.py).

    python3 gen/board.py              place, route, pour, art, panel, save
    python3 gen/board.py --place      placement, outlines, art and panel only (no copper)

Runs inside KiCad's own Python (it relaunches itself there through tools/kienv.py), so
pcbnew does every rotation, flip and pad transform.

Coordinates: each board's own frame (gen/layout.py: millimetres, x right, y down); the
board's PANEL_OFFSETS place it on the panel, and ORIGIN puts the panel's top-left corner
on KiCad's page.

The stack-up (JLC04161H-7628, 1.6 mm, 1 oz on every layer): F.Cu is the scene's side
(LEDs, antennas, the coils' top turns); In1.Cu carries the supplies as pours and some
signals; In2.Cu is ground, unbroken except under the coils and the antennas; B.Cu is the
electronics' side.
"""
import json, math, os, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

if "--inside" not in sys.argv:
    import subprocess, kienv
    p = subprocess.Popen(kienv.python() + ["-u", os.path.abspath(__file__), "--inside"] + sys.argv[1:],
                         cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(os.environ, PYTHONHASHSEED="0"))
    for line in p.stdout:                       # as it comes, so a long route shows its progress
        if "Font '" not in line:
            sys.stdout.write(line)
            sys.stdout.flush()
    sys.exit(p.wait())

import pcbnew
from sexp import parse, kids, kid, val
import board_info as BI
import layout as L
import placement as PL

HW = BI.HW
PCB = BI.PCB
LIBDIR = os.path.join(HW, "lib", "OWL.pretty")
ORIGIN = (50.0, 50.0)
PANEL_W, PANEL_H = L.PANEL_W, L.PANEL_H


def mm(v):
    return pcbnew.FromMM(float(v))


def PP(x, y):
    """Panel millimetres to KiCad's."""
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


class Frame:
    """One board's frame on the panel: P(x, y) for its own coordinates.  A board the panel
    turns (gen/layout.py PANEL_ROT: the tree) is built unturned with its origin at its
    PANEL_OFFSETS point, then turned about that point as a whole (turn()), so nothing
    that builds it needs to know."""

    def __init__(self, name):
        self.name = name
        self.ox, self.oy = L.PANEL_OFFSETS[name]
        self.rot = L.PANEL_ROT.get(name, 0.0)

    def P(self, x, y):
        return PP(self.ox + x, self.oy + y)

    def B(self, v):
        return (pcbnew.ToMM(v.x) - ORIGIN[0] - self.ox, pcbnew.ToMM(v.y) - ORIGIN[1] - self.oy)


FRAMES = {n: Frame(n) for n in PL.BOARDS}


# ---------------------------------------------------------------------------
def read_netlist(path):
    doc = parse(open(path, encoding="utf-8").read())[0]
    comps = {}
    for c in kids(kid(doc, "components"), "comp"):
        ref = val(kid(c, "ref"))
        fields = {}
        fl = kid(c, "fields")
        for f in kids(fl, "field") if fl else []:
            if len(f) > 2:
                fields[val(kid(f, "name"))] = val(f, 2)
        comps[ref] = dict(value=val(kid(c, "value")), footprint=val(kid(c, "footprint")), fields=fields)
    nets = {}
    for n in kids(kid(doc, "nets"), "net"):
        nets[val(kid(n, "name"))] = [(val(kid(x, "ref")), val(kid(x, "pin"))) for x in kids(n, "node")]
    return comps, nets


STACKUP = [("F.Cu", "copper", 0.035), ("dielectric 1", "prepreg", 0.2104),
           ("In1.Cu", "copper", 0.035), ("dielectric 2", "core", 1.065),
           ("In2.Cu", "copper", 0.035), ("dielectric 3", "prepreg", 0.2104),
           ("B.Cu", "copper", 0.035)]


def setup(board):
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.m_MinClearance = mm(0.15)
    ds.m_HoleClearance = mm(0.2)
    ds.m_HoleToHoleMin = mm(0.25)
    ds.m_CopperEdgeClearance = mm(0.3)
    ds.m_TrackMinWidth = mm(0.127)
    ds.m_ViasMinSize = mm(0.45)
    ds.m_MinThroughDrill = mm(0.25)
    for name in ("In1.Cu", "In2.Cu"):
        board.SetLayerType(board.GetLayerID(name), pcbnew.LT_SIGNAL)
    # the drill/place origin at the panel's bottom-left corner: Gerbers, drill and the
    # placement file all measure from it, x right and y up
    ds.SetAuxOrigin(PP(0, PANEL_H))
    ds.SetGridOrigin(PP(0, PANEL_H))


def poly_edge(board, pts, layer=None, width=0.1):
    layer = pcbnew.Edge_Cuts if layer is None else layer
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(PP(*a)); s.SetEnd(PP(*b))
        s.SetLayer(layer); s.SetWidth(mm(width))
        board.Add(s)


def rounded_rect(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def placeholder_outline(name):
    """Until gen/art.py draws the boards: plain shapes of the right size."""
    if name == "base":
        return [rounded_rect(0, 0, L.BASE_W, L.BASE_H, L.BASE_R)]
    if name == "tree":
        return [rounded_rect(0, 0, L.TREE_W, L.TREE_H, 4.0)]
    if name == "perch":
        return [rounded_rect(-L.PERCH_W / 2, L.PERCH_FRONT, L.PERCH_W / 2, L.PERCH_BACK, 2.0)]
    if name == "bat":
        return [rounded_rect(-L.BAT_SPAN / 2, L.BAT_HEAD_Y, L.BAT_SPAN / 2, L.BAT_TAIL_Y, 3.0)]
    return [[(L.TOKEN_R * math.cos(2 * math.pi * k / 64), L.TOKEN_R * math.sin(2 * math.pi * k / 64))
             for k in range(64)]]


def outlines():
    try:
        import art
        return {n: art.outline(n) for n in PL.BOARDS}, art
    except ImportError:
        return {n: placeholder_outline(n) for n in PL.BOARDS}, None


# ---------------------------------------------------------------------------
SEEDS = set()


def seed(what):
    """Restart KiCad's UUID generator from a seed named for what comes next, so each
    part's UUIDs depend on that part alone (a rebuild changes only what changed)."""
    n = zlib.crc32(("owl:" + what).encode()) or 1
    assert n not in SEEDS, "two seeds collide: %s" % what
    SEEDS.add(n)
    pcbnew.KIID.SeedGenerator(n)


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    fp = pcbnew.FootprintLoad(LIBDIR, name)
    if fp is None:
        raise SystemExit("footprint %s not found in %s" % (fpid, LIBDIR))
    return fp


def place_parts(board, comps, nets):
    netinfo = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pin_net = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[(ref, pin)] = name
    fps = {}
    for ref, c in sorted(comps.items()):
        if not c["footprint"] or c["footprint"].endswith(":"):
            continue                         # PWR_FLAGs
        bname = PL.board_of(ref)
        x, y, rot, side = PL.BOARDS[bname].place[ref]
        F = FRAMES[bname]
        seed(ref)
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        for k, v in c["fields"].items():
            if k in ("LCSC", "MPN"):
                fp.SetField(k, v)
                f = fp.GetField(k) if hasattr(fp, "GetField") else fp.GetFieldByName(k)
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        board.Add(fp)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(F.P(x, y))
        for pad in fp.Pads():
            n = pin_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netinfo[n])
                # an exposed pad joins its ground pour solid: its heat goes into the
                # plane, and spokes round its thermal vias would be starved
                sz = pad.GetSize(pcbnew.F_Cu) if hasattr(pad, "GetSize") else pad.GetSize()
                if n.startswith("GND") and pcbnew.ToMM(sz.x) * pcbnew.ToMM(sz.y) > 2.0:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        fps[ref] = fp
    return fps, netinfo


def panel_edges(outl):
    """Each board's outer edge and its own holes, in panel millimetres, where they end up
    (a turned board turned)."""
    import panel as PN
    edges = {n: [PN.to_panel(n, x, y) for x, y in polys[0]] for n, polys in outl.items()}
    holes = [[PN.to_panel(n, x, y) for x, y in pts] for n, polys in outl.items() for pts in polys[1:]]
    return edges, holes


def inset(pts, d):
    """A polygon (board millimetres) shrunk by d: where a pour may reach, d inside the
    board's edge everywhere, the tabs' breakaway lines included."""
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        ps.Append(mm(x), mm(y))
    ps.Inflate(-mm(d), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    c = ps.Outline(0)
    return [(pcbnew.ToMM(c.CPoint(i).x), pcbnew.ToMM(c.CPoint(i).y)) for i in range(c.PointCount())]


# (KiCad 10's GetLayerID knows only the long names, F.Silkscreen: the short ones give an
# undefined layer, which kicad-cli then refuses to load)
ART_LAYERS = {"F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS, "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask,
              "F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab}
JUSTIFY = {"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "center": pcbnew.GR_TEXT_H_ALIGN_CENTER,
           "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}


def shape(board, layer, kind, width=0.0, filled=False, net=None):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(kind)
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    if filled:
        s.SetFilled(True)
    if net is not None:
        s.SetNet(net)
    return s


def polygon(board, layer, F, pts, net=None):
    s = shape(board, layer, pcbnew.SHAPE_T_POLY, filled=True, net=net)
    s.SetPolyPoints([F.P(x, y) for x, y in pts])
    board.Add(s)


def draw_art(board, art, netinfo):
    """gen/art.py's drawing (hardware/art.json): silkscreen, mask openings and copper on
    each board, and the theremin's two antennas: their gold (copper on the antenna's net,
    solid, with the mask open over it) and, round each, no pour on any layer."""
    n = 0
    for name in PL.BOARDS:
        F = FRAMES[name]
        for lname, items in art.art(name).items():
            layer = ART_LAYERS[lname]
            back = lname.startswith("B.")
            for it in items:
                kind = it[0]
                if kind == "poly":
                    polygon(board, layer, F, it[1])
                elif kind == "polyline":
                    for a, b in zip(it[1], it[1][1:]):
                        sg = shape(board, layer, pcbnew.SHAPE_T_SEGMENT, it[2])
                        sg.SetStart(F.P(*a)); sg.SetEnd(F.P(*b))
                        board.Add(sg)
                elif kind == "circle":
                    _, cx, cy, r, w = it
                    c = shape(board, layer, pcbnew.SHAPE_T_CIRCLE, w)
                    c.SetCenter(F.P(cx, cy)); c.SetEnd(F.P(cx + r, cy))
                    board.Add(c)
                elif kind == "arc":
                    _, cx, cy, r, a0, a1, w = it
                    pt = lambda a: F.P(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
                    c = shape(board, layer, pcbnew.SHAPE_T_ARC, w)
                    c.SetArcGeometry(pt(a0), pt((a0 + a1) / 2), pt(a1))
                    board.Add(c)
                elif kind == "text":
                    _, txt, x, y, h, ang, just = it
                    t = pcbnew.PCB_TEXT(board)
                    t.SetText(txt)
                    t.SetLayer(layer)
                    t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
                    t.SetTextThickness(mm(art.text_thickness(h)))
                    t.SetHorizJustify(JUSTIFY[just])
                    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
                    t.SetMirrored(back)
                    t.SetTextAngleDegrees(ang)
                    t.SetPosition(F.P(x, y))
                    board.Add(t)
                n += 1
    F = FRAMES["base"]
    for a in art.antennas():
        net = netinfo["/Base/" + a["net"]]
        for pts in a["copper"]:
            polygon(board, pcbnew.F_Cu, F, pts, net=net)
        for pts in a["mask_open"]:
            polygon(board, pcbnew.F_Mask, F, pts)
        n += len(a["copper"]) + len(a["mask_open"])
    return n


def turn(board, name):
    """Turn everything of a turned board (built unturned at its origin: gen/layout.py)
    about that origin: footprints, copper, zones, drawings, text."""
    F = FRAMES[name]
    if not F.rot:
        return 0
    pivot = PP(F.ox, F.oy)
    ang = pcbnew.EDA_ANGLE(F.rot, pcbnew.DEGREES_T)
    w, h = {"tree": (L.TREE_W, L.TREE_H)}[name]
    lo, hi = PP(F.ox - 1.0, F.oy - 1.0), PP(F.ox + w + 1.0, F.oy + h + 1.0)

    def mine(item):
        c = item.GetBoundingBox().Centre()
        return lo.x <= c.x <= hi.x and lo.y <= c.y <= hi.y
    items = [f for f in board.GetFootprints() if PL.board_of(f.GetReference()) == name]
    items += [t for t in board.GetTracks() if mine(t)]
    items += [z for z in board.Zones() if mine(z)]
    items += [d for d in board.GetDrawings() if mine(d)]
    for it in items:
        it.Rotate(pivot, ang)
    return len(items)


# ---------------------------------------------------------------------------
# Copper: a router per board (gen/routing.py), the planned copper and the rest
# (gen/routes.py), then the pours
# ---------------------------------------------------------------------------
def router(board, name, polys):
    """The router for one board, in its own millimetres shifted so that the outline's
    bounding box starts at 0, 0 (the base's does already)."""
    import routing as RT
    F = FRAMES[name]
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    x0, y0 = math.floor(min(xs)), math.floor(min(ys))
    w, h = math.ceil(max(xs)) - x0, math.ceil(max(ys)) - y0

    def P(x, y):
        return F.P(x + x0, y + y0)

    def B(v):
        x, y = F.B(v)
        return (x - x0, y - y0)
    R = RT.Router(board, P, B, w, h, refs=set(PL.BOARDS[name].place), planes={},
                  outline=[[(x - x0, y - y0) for x, y in p] for p in polys], name=name)
    R.x0, R.y0 = x0, y0
    R.outline = [[(x - x0, y - y0) for x, y in p] for p in polys]
    R.pour_edge = [(x - x0, y - y0) for x, y in inset(polys[0], 0.5)]
    return R


def copper(board, outl, args):
    import time
    import routes as RS
    out = {}
    only = args[args.index("--only") + 1].split(",") if "--only" in args else list(PL.BOARDS)
    for name in PL.BOARDS:
        if name not in only:
            continue
        t = time.time()
        seed("copper:" + name)
        R = router(board, name, outl[name])
        R.load_pads()
        RS.plan(name, R)
        if "--planned" not in args:
            RS.route(name, R)
        left = {n: R.unrouted(n) for n in R.by_net if not n.startswith("<") and R.unrouted(n)}
        print("copper %-9s %5d tracks %4d vias, %.0f s; %d nets with unjoined pieces%s"
              % (name, R.n_tracks, R.n_vias, time.time() - t, len(left),
                 (": " + ", ".join("%s(%d)" % kv for kv in sorted(left.items())))[:400] if left else ""))
        for net, why in R.failed[:30]:
            print("   UNROUTED %s: %s" % (net, why))
        if "--stamps" in args:
            stamps(R, name)
        out[name] = R
    return out


def stamps(R, name, r=4.0, most=16):
    """The router's view round each net left in pieces (gen/routing.py stamp()), for
    tools/stamps.py to draw: build/stamps_<board>.json."""
    import routing as RT
    out = list(getattr(R, "live", []))
    for net in sorted(n for n in R.by_net if not n.startswith("<") and R.unrouted(n))[:most]:
        for g in sorted(R.groups(net), key=len)[:2]:
            it = next((R.items[i] for i in g if any(R.items[i].cells.values())), None)
            if it is None:
                continue
            k = next(iter(next(c for c in it.cells.values() if c)))
            x, y = R.g.pos(k)
            st = RT.stamp(R, net, 0.2, max(0, x - r), max(0, y - r), x + r, y + r)
            st.update(board=name, at=[x + R.x0, y + R.y0], what=sorted(set(R.items[i].what for i in g))[:6])
            out.append(st)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "build", "stamps_%s.json" % name), "w"))


def pours_only(board, routers):
    import routes as RS
    for name, R in routers.items():
        seed("pours:" + name)
        RS.pours(name, R)


def fill(board):
    # the filler drops islands it judges unconnected from the board's connectivity,
    # which a board built in memory has not computed yet
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    zs = [z for z in board.Zones() if not z.GetIsRuleArea()]
    n = sum(1 for z in zs if z.HasFilledPolysForLayer(z.GetFirstLayer())
            and z.GetFilledPolysList(z.GetFirstLayer()).OutlineCount())
    print("pours: %d zones, %d filled" % (len(zs), n))


# The physical stack-up, written into the board file (KiCad's Python cannot set it): JLCPCB's
# JLC04161H-7628 with 1 oz copper inside and out, and the colours that are ordered, so
# KiCad's 3D view and renders show the board as it will come (purple, white, ENIG).
STACKUP = [("F.SilkS", "Top Silk Screen", [("color", '"White"')]),
           ("F.Paste", "Top Solder Paste", []),
           ("F.Mask", "Top Solder Mask", [("color", '"Purple"'), ("thickness", "0.01")]),
           ("F.Cu", "copper", [("thickness", "0.035")]),
           ("dielectric 1", "prepreg", [("thickness", "0.2104"), ("material", '"FR4"'), ("epsilon_r", "4.4"),
                                        ("loss_tangent", "0.02")]),
           ("In1.Cu", "copper", [("thickness", "0.035")]),
           ("dielectric 2", "core", [("thickness", "1.065"), ("material", '"FR4"'), ("epsilon_r", "4.6"),
                                     ("loss_tangent", "0.02")]),
           ("In2.Cu", "copper", [("thickness", "0.035")]),
           ("dielectric 3", "prepreg", [("thickness", "0.2104"), ("material", '"FR4"'), ("epsilon_r", "4.4"),
                                        ("loss_tangent", "0.02")]),
           ("B.Cu", "copper", [("thickness", "0.035")]),
           ("B.Mask", "Bottom Solder Mask", [("color", '"Purple"'), ("thickness", "0.01")]),
           ("B.Paste", "Bottom Solder Paste", []),
           ("B.SilkS", "Bottom Silk Screen", [("color", '"White"')])]


def write_stackup(path):
    """Put STACKUP into the saved board file's setup, in place of any there."""
    text = open(path, encoding="utf-8").read()
    if "(stackup" in text:
        return
    lines = ["\t\t(stackup"]
    for name, kind, props in STACKUP:
        lines.append('\t\t\t(layer "%s"' % name)
        lines.append('\t\t\t\t(type "%s")' % kind)
        lines += ["\t\t\t\t(%s %s)" % kv for kv in props]
        lines.append("\t\t\t)")
    lines += ['\t\t\t(copper_finish "ENIG")', "\t\t\t(dielectric_constraints no)", "\t\t)"]
    i = text.index("\t(setup\n") + len("\t(setup\n")
    open(path, "w", encoding="utf-8").write(text[:i] + "\n".join(lines) + "\n" + text[i:])


def prune(board):
    """Vias the routing did not need, taken out (KiCad's DRC: via_dangling): a via that
    joins copper on fewer than two layers, most of them planned beside a pad that the
    router then reached another way.  Tracks meeting at such a via on its one layer get
    a short joint to its centre (the router may end a track anywhere on a via's pad);
    a lone track to it is a stub, taken out back to the first pad, zone, via or fork.
    Run on filled zones; refill after.  Returns how many items went."""
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    pads, zones, by_net = {}, {}, {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetname(), []).append(p)
    for z in board.Zones():
        if not z.GetIsRuleArea():
            zones.setdefault(z.GetNetname(), []).append(z)
    shapes = {}                                   # copper drawn as shapes: antennas, coil turns
    for d in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()]:
        if d.GetClass() in ("PCB_SHAPE", "PCB_FP_SHAPE") and d.GetLayer() in CU and d.GetNetname():
            shapes.setdefault(d.GetNetname(), []).append(d)
    # (board.GetTracks() is not called again once something is deleted: SWIG loses
    # track of its types then; the lists here are kept up to date instead)
    for t in board.GetTracks():
        by_net.setdefault(t.GetNetname(), []).append(t)
    is_via = lambda t: t.GetClass() == "PCB_VIA"

    def touching(net, pos, me, layer=None, reach=0):
        """(layers, tracks, anything but tracks) of `net` within `reach` (nm) of pos, `me`
        left out; a via is through every layer."""
        layers, tracks, other = set(), [], False
        for t in by_net.get(net, []):
            if t is me or not t.HitTest(pos, reach):
                continue
            if is_via(t):
                layers |= set(CU)
                other = True
            elif layer is None or t.GetLayer() == layer:
                layers.add(t.GetLayer())
                tracks.append(t)
        for p in pads.get(net, []):
            on = {L for L in CU if (layer is None or L == layer) and p.IsOnLayer(L) and p.HitTest(pos, reach, L)}
            layers |= on
            other = other or bool(on)
        for z in zones.get(net, []):
            on = {L for L in CU if (layer is None or L == layer) and z.IsOnLayer(L) and z.HitTestFilledArea(L, pos, reach)}
            layers |= on
            other = other or bool(on)
        for d in shapes.get(net, []):
            if (layer is None or d.GetLayer() == layer) and d.HitTest(pos, reach):
                layers.add(d.GetLayer())
                other = True
        return layers, tracks, other

    def drop(t):
        lst = by_net[t.GetNetname()]
        lst[:] = [x for x in lst if x is not t]
        board.Delete(t)                       # (Remove() hands it to Python, and SWIG then loses its types)

    def stub(net, here, t):
        """Take out the stub that starts at `here` with track t, back along it while
        nothing else meets it; returns how many tracks went."""
        n = 0
        while t is not None:
            far = t.GetEnd() if (t.GetStart() - here).EuclideanNorm() <= (t.GetEnd() - here).EuclideanNorm() else t.GetStart()
            L, w = t.GetLayer(), t.GetWidth()
            # something else ending on its body (the router may join a line anywhere
            # along a stub): it is cut back to there, not taken out
            join = None
            for o in by_net.get(net, []):
                if o is t:
                    continue
                for q in ((o.GetPosition(),) if is_via(o) else (o.GetStart(), o.GetEnd())):
                    if (q - far).EuclideanNorm() <= max(w, 1) // 2 or not t.HitTest(q, 0):
                        continue
                    d = (q - here).EuclideanNorm()
                    if join is None or d < join[0]:
                        join = (d, q)
            if join is not None:
                ax, ay = far.x, far.y
                fx, fy = here.x - ax, here.y - ay
                L2 = fx * fx + fy * fy
                k = max(0.0, min(1.0, ((join[1].x - ax) * fx + (join[1].y - ay) * fy) / L2)) if L2 else 0.0
                cut = pcbnew.VECTOR2I(int(ax + fx * k), int(ay + fy * k))
                if t.GetStart() == far:
                    t.SetEnd(cut)
                else:
                    t.SetStart(cut)
                return n + 1
            drop(t)
            n += 1
            _, nxt, other = touching(net, far, None, L, reach=w // 2)
            if other or len(nxt) != 1:
                break
            o = nxt[0]
            if min((o.GetStart() - far).EuclideanNorm(), (o.GetEnd() - far).EuclideanNorm()) > max(w, o.GetWidth()) // 2:
                break                             # it meets the middle of a track: that goes on both ways
            here, t = far, o
        return n

    gone = 0
    for net in list(by_net):
        if not net:
            continue
        for v in [t for t in by_net[net] if is_via(t)]:
            pos = v.GetPosition()
            # (anything on the via's pad joins it: the router may start a track anywhere on it)
            layers, tracks, other = touching(net, pos, v, reach=v.GetWidth(pcbnew.F_Cu) // 2)
            if len(layers) >= 2:
                continue
            drop(v)
            gone += 1
            if len(tracks) >= 2 or other:
                for o in tracks:
                    end = min((o.GetStart(), o.GetEnd()), key=lambda e: (e - pos).EuclideanNorm())
                    if (end - pos).EuclideanNorm() > 0:
                        j = pcbnew.PCB_TRACK(board)
                        j.SetStart(end); j.SetEnd(pos); j.SetWidth(o.GetWidth())
                        j.SetLayer(o.GetLayer()); j.SetNet(o.GetNet())
                        board.Add(j)
                        by_net[net].append(j)
                continue
            gone += stub(net, pos, tracks[0] if tracks else None)
    # then tracks with an end touching nothing (a planned stub the router did not use)
    for net in list(by_net):
        for t in [t for t in by_net.get(net, []) if not is_via(t)]:
            if not any(x is t for x in by_net[net]):
                continue                          # (gone with an earlier stub)
            for e in (t.GetStart(), t.GetEnd()):
                _, near, other = touching(net, e, t, t.GetLayer(), reach=t.GetWidth() // 2)
                if not near and not other:
                    gone += stub(net, e, t)
                    break
    return gone


def led_positions():
    """Every LED's place on its own board (the placement: KiCad coordinates, millimetres),
    for the firmware's light show (gen/firmware_leds.py reads it into led_map.h)."""
    out = {}
    for role, ref in PL.ROLES.items():
        if role.startswith("led:"):
            name = PL.board_of(ref)
            x, y, rot, side = PL.BOARDS[name].place[ref]
            out[role[4:]] = {"x_mm": x, "y_mm": y, "board": name}
    path = os.path.join(HW, "checks", "led_positions.json")
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    return len(out)


# ---------------------------------------------------------------------------
def main():
    args = [a for a in sys.argv[1:] if a != "--inside"]
    pcbnew.KIID.SeedGenerator(1031)
    comps, nets = read_netlist(BI.NETLIST)
    board = pcbnew.CreateEmptyBoard()
    setup(board)
    outl, art = outlines()
    fps, netinfo = place_parts(board, comps, nets)
    led_positions()
    if art:
        seed("art")
        n_art = draw_art(board, art, netinfo)
        print("art: %d items" % n_art)
    routers = None
    if "--place" not in args:
        routers = copper(board, outl, args)
        if "--nopour" not in args:
            pours_only(board, routers)
    import silk as SK
    seed("silk")
    n_ref = n_fab = 0
    for name in PL.BOARDS:
        F = FRAMES[name]
        S = SK.apply(board, name, set(PL.BOARDS[name].place), F.B, inset(outl[name][0], SK.EDGE), art, F)
        n_ref += S.placed
        n_fab += S.to_fab
        if S.why:
            print("   silk %s: labels refused for %s" % (name, ", ".join("%s %d" % kv for kv in sorted(S.why.items(), key=lambda kv: -kv[1])[:6])))
    print("silk: %d designators printed underneath, %d on the fab layer only" % (n_ref, n_fab))
    for name in PL.BOARDS:
        n = turn(board, name)
        if n:
            print("panel: %s turned %g degrees (%d items)" % (name, FRAMES[name].rot, n))
    import panel as PN
    edges, holes = panel_edges(outl)
    tabs, n_bites, per = PN.build(board, PP, mm, edges, holes, load_fp, seed)
    print("panel: %.1f x %.1f mm, %d tabs (%s), %d mouse-bite holes, 3 fiducials, 4 tooling holes"
          % (PANEL_W, PANEL_H, len(tabs), ", ".join("%s %d" % kv for kv in sorted(per.items())), n_bites))
    for n in PL.BOARDS:
        if per.get(n, 0) < 2:
            print("   PANEL: %s has %d tab(s)" % (n, per.get(n, 0)))
    if routers and "--nopour" not in args:
        fill(board)
        n = prune(board) if not os.environ.get("NOPRUNE") else 0
        if n:
            print("prune: %d vias and track ends the routing did not need" % n)
            fill(board)
    board.Save(PCB)
    write_stackup(PCB)
    import project
    project.write(HW)
    print("board: %d footprints on %d boards%s -> %s"
          % (len(fps), len(PL.BOARDS), "" if art else " (placeholder outlines: no gen/art.py yet)",
             os.path.relpath(PCB, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
