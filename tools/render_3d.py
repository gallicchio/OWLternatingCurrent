#!/usr/bin/env python3
"""3D pictures for the README: each board from above, from below and in perspective
(KiCad's raytracer), the panel as it comes from JLCPCB, and the whole set assembled on a
table (Blender, from each board's glTF and the printed parts' meshes).

    python3 tools/render_3d.py                 everything
    python3 tools/render_3d.py --only boards   KiCad's renders only
    python3 tools/render_3d.py --only set      the assembled set only
    python3 tools/render_3d.py --draft         small and quick, to check the framing

Writes docs/images/3d_<board>_top.png, _bottom.png, _persp.png, 3d_panel_top.png,
3d_panel_bottom.png and 3d_set.png, 3d_set_side.png.  Works in build/render3d/: each
board cut out of the panel into a .kicad_pcb of its own (its outline, its parts, its
copper; the tree turned back upright), and each one's .glb.
"""
import json, math, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kienv

WORK = os.path.join(ROOT, "build", "render3d")
IMAGES = os.path.join(ROOT, "docs", "images")
BOARDS = ["base", "tree", "perch", "bat", "owl_token", "cat_token"]


# ---------------------------------------------------------------------------------------
# 1. Each board cut out of the panel (runs in KiCad's Python)
# ---------------------------------------------------------------------------------------
def split():
    """build/render3d/<board>.kicad_pcb for every board, and frames.json: where each
    board's own origin is in its file (KiCad millimetres)."""
    sys.argv.append("--inside")                  # (gen/board.py runs itself in KiCad's Python otherwise)
    import pcbnew
    import board as BD
    import placement as PL
    import panel as PN
    import routing as RT
    outl, _ = BD.outlines()
    frames = {}
    for name in BOARDS:
        b = pcbnew.LoadBoard(BD.PCB)
        F = BD.FRAMES[name]
        outer = [PN.to_panel(name, x, y) for x, y in outl[name][0]]
        mm = lambda v: (pcbnew.ToMM(v.x) - BD.ORIGIN[0], pcbnew.ToMM(v.y) - BD.ORIGIN[1])

        def inside(v):
            return RT.point_in_poly(*mm(v), outer)
        refs = set(PL.BOARDS[name].place)
        for fp in list(b.GetFootprints()):
            if fp.GetReference() not in refs:
                b.Delete(fp)
        for t in list(b.GetTracks()):
            if not inside(t.GetBoundingBox().Centre()):
                b.Delete(t)
        for z in list(b.Zones()):
            if not inside(z.GetBoundingBox().Centre()):
                b.Delete(z)
        for d in list(b.GetDrawings()):
            if d.GetLayer() == pcbnew.Edge_Cuts or not inside(d.GetBoundingBox().Centre()):
                b.Delete(d)
        # turned back upright (gen/board.py turn(), undone)
        if F.rot:
            pivot = BD.PP(F.ox, F.oy)
            ang = pcbnew.EDA_ANGLE(-F.rot, pcbnew.DEGREES_T)
            for it in list(b.GetFootprints()) + list(b.GetTracks()) + list(b.Zones()) + list(b.GetDrawings()):
                it.Rotate(pivot, ang)
        # its own edge, and its own holes
        for poly in outl[name]:
            pts = [BD.PP(F.ox + x, F.oy + y) for x, y in poly]
            for a, c in zip(pts, pts[1:] + pts[:1]):
                s = pcbnew.PCB_SHAPE(b)
                s.SetShape(pcbnew.SHAPE_T_SEGMENT)
                s.SetStart(a)
                s.SetEnd(c)
                s.SetLayer(pcbnew.Edge_Cuts)
                s.SetWidth(pcbnew.FromMM(0.05))
                b.Add(s)
        path = os.path.join(WORK, name + ".kicad_pcb")
        b.Save(path)
        BD.write_stackup(path)
        o = BD.PP(F.ox, F.oy)
        frames[name] = [pcbnew.ToMM(o.x), pcbnew.ToMM(o.y)]
        print("split: %s" % name)
    json.dump(frames, open(os.path.join(WORK, "frames.json"), "w"), indent=1)


# ---------------------------------------------------------------------------------------
# 2. KiCad's renders
# ---------------------------------------------------------------------------------------
# per board: (rotation for the view from above, camera zoom)
VIEW = {"base": (0, 0.92), "tree": (0, 0.9), "perch": (0, 0.9), "bat": (0, 0.9),
        "owl_token": (0, 0.9), "cat_token": (0, 0.9)}


def out_dir(draft):
    """docs/images/ for the pictures the README shows; a draft's go to build/ instead."""
    d = os.path.join(WORK, "draft") if draft else IMAGES
    os.makedirs(d, exist_ok=True)
    return d


def cli(args):
    kienv.run_cli(args)


def render(pcb, out, side, w, h, quality, rotate=None, zoom=1.0, persp=False, floor=False):
    args = ["pcb", "render", "--output", out, "--side", side, "--width", str(w), "--height", str(h),
            "--quality", quality, "--use-board-stackup-colors", "--background", "transparent",
            "--zoom", "%.3f" % zoom]
    if rotate:
        args += ["--rotate", rotate]
    if persp:
        args.append("--perspective")
    if floor:
        args.append("--floor")
    cli(args + [pcb])


def boards(draft):
    q = "basic" if draft else "high"
    w, h = (800, 600) if draft else (1600, 1200)
    IMG = out_dir(draft)
    for name in BOARDS:
        pcb = os.path.join(WORK, name + ".kicad_pcb")
        rot, zoom = VIEW[name]
        render(pcb, os.path.join(IMG, "3d_%s_top.png" % name), "top", w, h, q, "0,0,%d" % rot, zoom)
        # from below the board turns over left to right, as you would turn it in your hand
        render(pcb, os.path.join(IMG, "3d_%s_bottom.png" % name), "bottom", w, h, q, "0,0,%d" % -rot, zoom)
        render(pcb, os.path.join(IMG, "3d_%s_persp.png" % name), "top", w, h, q,
               "-48,0,%d" % (rot + 32), zoom * 0.95, persp=True, floor=not draft)
        print("rendered: %s" % name)
    render(os.path.join(ROOT, "hardware", "OWLternatingCurrent.kicad_pcb"), os.path.join(IMG, "3d_panel_top.png"),
           "top", w, int(w * 223.2 / 245.2), q, None, 0.95)
    render(os.path.join(ROOT, "hardware", "OWLternatingCurrent.kicad_pcb"), os.path.join(IMG, "3d_panel_bottom.png"),
           "bottom", w, int(w * 223.2 / 245.2), q, None, 0.95)
    print("rendered: the panel")


# ---------------------------------------------------------------------------------------
# 3. The set, assembled, on a table (Blender: tools/render_set_blender.py)
# ---------------------------------------------------------------------------------------
SOCKET = 8.5            # J3 and J201, PM254-2-08-Z-8.5: a board's edge stands this far up
HEADER_ROW = 2.54       # a right-angle 2x8 header on a board's back: its pins' middle, from that face
BAT_GAP = 11.0          # the bat's top surface below the perch's underside, floating


def blender():
    """A Blender whose Cycles works: $BLENDER, else the newest under ~/.local/blender (an
    official release: Ubuntu 22.04's packaged 3.0.1 renders every Cycles frame black),
    else the system's."""
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    import glob
    found = sorted(glob.glob(os.path.expanduser("~/.local/blender/blender-*/blender")))
    return found[-1] if found else "blender"


def assembled(draft):
    import layout as L
    import mech as M
    frames = json.load(open(os.path.join(WORK, "frames.json")))
    glb = {}
    for name in BOARDS:
        ox, oy = frames[name]
        glb[name] = os.path.join(WORK, name + ".glb")
        cli(["pcb", "export", "glb", "--force", "--subst-models", "--include-tracks", "--include-pads",
             "--include-zones", "--include-silkscreen", "--include-soldermask",
             "--user-origin", "%.4fx%.4fmm" % (ox, oy), "-o", glb[name], os.path.join(WORK, name + ".kicad_pcb")])
        print("glTF: %s" % name)
    T = M.PCB_T
    sx, sy = L.TREE_SOCKET
    tree_top = SOCKET + L.TREE_H                 # the tree's top edge above the base
    perch_z = tree_top + SOCKET                  # the perch's underside
    coil_y = sy + L.PERCH_SOCKET_Y               # the levitation coil, in front of the tree
    bat_top = perch_z - BAT_GAP
    table = -T - M.FOOT_HEIGHT
    printed = os.path.join(ROOT, "print", "out")
    parts = [
        # (a board's glTF: its x and -y in the plane, its bottom face at z = 0)
        dict(file=glb["base"], rot=[0, 0, 0], at=[0, 0, -T]),
        # the tree stands in J3, its front toward you, its back's header in the socket
        dict(file=glb["tree"], rot=[90, 0, 0], at=[sx - L.TREE_W / 2, -(sy + HEADER_ROW), tree_top]),
        # the perch and the bat face you: their frames' -y is their front, so turned round
        dict(file=glb["perch"], rot=[0, 0, 180], at=[sx, -coil_y, perch_z]),
        dict(file=glb["bat"], rot=[0, 0, 180], at=[sx, -coil_y, bat_top - T]),
        dict(file=glb["owl_token"], rot=[0, 0, 0], at=[L.OWL_PERCH[0], -L.OWL_PERCH[1], 0.05]),
        dict(file=glb["cat_token"], rot=[0, 0, 0], at=[L.CAT_PERCH[0], -L.CAT_PERCH[1], 0.05]),
        # the prints, in their boards' frames (print/design.py): the owl on the perch's top,
        # the cap on the bat's
        dict(file=os.path.join(printed, "assembled", "owl_in_perch_frame.stl"), material="pla",
             rot=[0, 0, 0], at=[sx, -coil_y, perch_z + T]),
        dict(file=os.path.join(printed, "assembled", "bat_cap_in_bat_frame.stl"), material="pla",
             rot=[0, 0, 0], at=[sx, -coil_y, bat_top]),
    ] + [dict(file=os.path.join(printed, "foot.stl"), material="pla", rot=[0, 0, 0], at=[x, -y, table])
         for x, y in L.FEET]
    look = [sx - 5.0, -(sy + 20.0), 62.0]
    views = [dict(out=os.path.join(IMAGES, "3d_set.png"), at=[400.0, -470.0, 300.0], target=look, lens=50.0,
                  size=[1920, 1280], fstop=11.0),
             dict(out=os.path.join(IMAGES, "3d_set_side.png"), at=[-150.0, -300.0, 120.0],
                  target=[sx, -(sy + 25.0), 85.0], lens=60.0, size=[1280, 1280], fstop=8.0)]
    if draft:
        for v in views:
            v["size"] = [v["size"][0] // 3, v["size"][1] // 3]
            v["out"] = os.path.join(out_dir(True), os.path.basename(v["out"]))
    spec = dict(
        parts=parts, views=views, samples=16 if draft else 160,
        materials={"pla": dict(rgb=[0.012, 0.011, 0.014], rough=0.75),
                   "table": dict(rgb=[0.055, 0.036, 0.026], rough=0.6)},
        table=dict(size=2000.0, at=[sx, -sy, 0.0], z=table),
        world=dict(rgb=[0.012, 0.01, 0.022], strength=1.0),
        softbox=dict(at=[sx, -(sy + 30.0), 650.0], size=900.0, strength=2.5),
        lights=[dict(name="key", at=[-250.0, -320.0, 420.0], target=look, size=420.0, power=30.0),
                dict(name="fill", at=[480.0, -220.0, 220.0], target=look, size=320.0, power=10.0),
                dict(name="rim", at=[120.0, 320.0, 380.0], target=look, size=320.0, power=22.0,
                     rgb=[0.85, 0.75, 1.0])])
    path = os.path.join(WORK, "scene.json")
    json.dump(spec, open(path, "w"), indent=1)
    subprocess.run([blender(), "-b", "--python-exit-code", "1", "-P", os.path.join(HERE, "render_set_blender.py"),
                    "--", path], check=True, stdout=subprocess.DEVNULL if not os.environ.get("VERBOSE") else None)
    print("rendered: the set")


def main():
    args = sys.argv[1:]
    if "--split" in args:
        return split()
    only = args[args.index("--only") + 1] if "--only" in args else None
    draft = "--draft" in args
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(IMAGES, exist_ok=True)
    lib = os.path.join(WORK, "lib")
    if not os.path.exists(lib):                    # (a link left broken by a moved repository goes)
        if os.path.lexists(lib):
            os.remove(lib)
        os.symlink(os.path.relpath(os.path.join(ROOT, "hardware", "lib"), WORK), lib)     # ${KIPRJMOD}/lib
    subprocess.run(kienv.python() + [os.path.abspath(__file__), "--split"], check=True)
    if only in (None, "boards"):
        boards(draft)
    if only in (None, "set"):
        assembled(draft)


if __name__ == "__main__":
    sys.exit(main())
