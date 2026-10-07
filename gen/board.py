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
    r = subprocess.run(kienv.python() + [os.path.abspath(__file__), "--inside"] + sys.argv[1:],
                       cwd=ROOT, text=True, capture_output=True, env=dict(os.environ, PYTHONHASHSEED="0"))
    sys.stdout.write("\n".join(l for l in r.stdout.splitlines() if "Font '" not in l) + ("\n" if r.stdout else ""))
    sys.stderr.write("\n".join(l for l in r.stderr.splitlines() if "Font '" not in l))
    sys.exit(r.returncode)

import pcbnew
from sexp import parse, kids, kid, val
import board_info as BI
import layout as L
import placement as PL

HW = BI.HW
PCB = BI.PCB
LIBDIR = os.path.join(HW, "lib", "OWL.pretty")
ORIGIN = (50.0, 50.0)
PANEL_W = max(L.PANEL_OFFSETS["base"][0] + L.BASE_W, L.PANEL_OFFSETS["tree"][0] + L.TREE_W,
              L.PANEL_OFFSETS["owl_token"][0] + L.TOKEN_R) + L.GAP + L.RAIL
PANEL_H = max(L.PANEL_OFFSETS["base"][1] + L.BASE_H, L.PANEL_OFFSETS["bat"][1] + L.BAT_TAIL_Y,
              L.PANEL_OFFSETS["cat_token"][1] + L.TOKEN_R) + L.GAP + L.RAIL


def mm(v):
    return pcbnew.FromMM(float(v))


def PP(x, y):
    """Panel millimetres to KiCad's."""
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


class Frame:
    """One board's frame on the panel: P(x, y) for its own coordinates."""

    def __init__(self, name):
        self.name = name
        self.ox, self.oy = L.PANEL_OFFSETS[name]

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
        fps[ref] = fp
    return fps, netinfo


# ---------------------------------------------------------------------------
# The panel: a frame round the boards, joined to them by mouse-bite tabs
# ---------------------------------------------------------------------------
def panel(board, outl):
    """The frame's outer edge and the boards' edges are Edge.Cuts; the frame's inner
    edge follows the boards at GAP, as a routed slot that the tabs bridge.  Simplest
    form that JLCPCB accepts: each board's own outline is cut, the frame is the panel's
    rectangle minus the region round the boards; tabs are short bridges with a row of
    0.5 mm holes (mouse bites) on each side."""
    poly_edge(board, rounded_rect(0, 0, PANEL_W, PANEL_H, 2.0))
    # the frame's inner edge: a rectangle round all the boards (the area between the
    # boards is milled out; tabs join each board to the frame or to its neighbour)
    poly_edge(board, rounded_rect(L.RAIL, L.RAIL, PANEL_W - L.RAIL, PANEL_H - L.RAIL, 1.0))
    # fiducials and tooling holes on the frame: three of each, as far apart as possible
    marks = [(L.RAIL / 2 + 3, L.RAIL / 2), (PANEL_W - L.RAIL / 2 - 3, L.RAIL / 2), (L.RAIL / 2 + 3, PANEL_H - L.RAIL / 2)]
    return marks


def draw_outlines(board, outl):
    for name, polys in outl.items():
        F = FRAMES[name]
        for pts in polys:
            poly_edge(board, [(F.ox + x, F.oy + y) for x, y in pts])


# ---------------------------------------------------------------------------
def main():
    args = [a for a in sys.argv[1:] if a != "--inside"]
    pcbnew.KIID.SeedGenerator(1031)
    comps, nets = read_netlist(BI.NETLIST)
    board = pcbnew.CreateEmptyBoard()
    setup(board)
    outl, art = outlines()
    seed("outlines")
    draw_outlines(board, outl)
    seed("panel")
    panel(board, outl)
    fps, netinfo = place_parts(board, comps, nets)
    board.Save(PCB)
    import project
    project.write(HW)
    print("board: %d footprints on %d boards, panel %.1f x %.1f mm%s -> %s"
          % (len(fps), len(PL.BOARDS), PANEL_W, PANEL_H, "" if art else " (placeholder outlines: no gen/art.py yet)",
             os.path.relpath(PCB, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
