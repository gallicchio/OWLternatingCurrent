#!/usr/bin/env python3
"""Make everything, from the parts table to the JLCPCB upload, and stop at the first
gate that fails (CLAUDE_PCB.md section 10).

    python3 build.py                 every step, in order
    python3 build.py board           from one step on
    python3 build.py --only release  just that step
    python3 build.py --until erc     up to and including that step
    python3 build.py --clean         remove the build's scratch (build/OWLternatingCurrent, build/jlc_pngs)

The steps, each a script that exits non-zero when its gate fails:

    library    gen/library.py         hardware/lib: every symbol, footprint, 3D model
    project    gen/project.py         the KiCad project: design rules, net classes
    schematic  gen/schematic.py       every sheet: base, tree, perch, bat, two tokens
    erc        tools/sch_check.py     KiCad 10's format, ERC at every severity, the netlist
    netcheck   tools/net_check.py     the netlist against the pin, mux, connector and LED tables
    art        gen/art.py             hardware/art.json (outlines, silkscreen, gold) and docs/images/art_*.png
    board      gen/board.py           the panel: placement, copper, pours  (when it exists)
    drc        tools/pcb_check.py     DRC at every severity with schematic parity
    release    mfg/make_release.py    mfg/release/: gerbers, BOM, CPL, checks, cost, fabrication notes
    images     tools/render_3d.py     docs/images/3d_*.png: each board, the panel, the set assembled

Until gen/board.py exists, the board and DRC steps are skipped and the release makes
its board-free half (the BOM, its checks, the parts' cost); the build then ends with
status 3, "INCOMPLETE", because there is nothing to order yet.

Needs KiCad 10 (tools/kienv.py finds it) and network access to JLCPCB's parts API and
EasyEDA (answers are cached: tools/jlc_cache.json, mfg/jlc_footprint_cache.json); the
images step needs Blender 4.2 or later (tools/render_3d.py finds it).
Everything a reviewer or the fab needs (hardware/, mfg/release/) is committed, so
nothing has to be built to look at the design or to order it.
"""
import os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
INCOMPLETE = 3


class Failed(Exception):
    pass


def py(script, *args, ok=(0,)):
    """Run one step's script; its exit status is its gate."""
    cmd = [sys.executable, os.path.join(ROOT, script)] + list(args)
    print("  $ %s" % " ".join([os.path.basename(sys.executable), script] + list(args)), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode not in ok:
        raise Failed("%s exited %d" % (script, r.returncode))
    return r.returncode


def have_board_script():
    return os.path.exists(os.path.join(ROOT, "gen", "board.py"))


def board():
    if not have_board_script():
        print("  (no gen/board.py yet: no board to make)")
        return "skipped"
    py("gen/board.py")


def drc():
    if not have_board_script():
        print("  (no board yet: no DRC)")
        return "skipped"
    py("tools/pcb_check.py")


def release():
    status = py("mfg/make_release.py", ok=(0, INCOMPLETE))
    return "incomplete" if status == INCOMPLETE else None


# (name, what it does, the gates of CLAUDE_PCB.md section 10 it holds, how)
STEPS = [
    ("library", lambda: py("gen/library.py"), ""),
    ("project", lambda: py("gen/project.py"), ""),
    ("schematic", lambda: py("gen/schematic.py"), ""),
    ("erc", lambda: py("tools/sch_check.py"), "1"),
    ("netcheck", lambda: py("tools/net_check.py"), "3"),
    ("art", lambda: py("gen/art.py"), ""),
    ("board", board, ""),
    ("drc", drc, "5"),
    ("release", release, "8 9 12"),
    ("images", lambda: py("tools/render_3d.py"), ""),
]

# What each gate of CLAUDE_PCB.md section 10 is held by in this build, printed at the end
# so that an unchecked gate is a visible line, not a silence.
GATES = [
    (1, "ERC clean, netlist exported", "tools/sch_check.py"),
    (2, "symbol pins against the datasheets' figures", None),
    (3, "every signal, rail, clock and strap traced", "tools/net_check.py (pins, mux, connectors, LED drivers)"),
    (4, "no overlaps on the schematic sheets", None),
    (5, "DRC clean on the shipped file, zones filled", "tools/pcb_check.py; mfg/make_release.py refuses a stale DRC or an unfilled board"),
    (6, "pads where KiCad puts them; connectors out; 3D models", None),
    (7, "silkscreen: overlaps, boxes, sizes, labels", None),
    (8, "every part coded, codes matching their descriptions, land patterns fitting, stock",
     "mfg/make_release.py (parts.py match words, value, package, MPN, stock; FOOTPRINT_CHECK.txt)"),
    (9, "CPL native and JLC-corrected, PLACEMENT_CHECKS.txt",
     "mfg/make_release.py (both sides, simulated against JLCPCB's drawings)"),
    (10, "revision and date on the silkscreen; DRAFT until real", "mfg/make_release.py stamps DRAFT while gen/board_info.py FOR_NAME is undecided (None)"),
    (11, "every rail's width by net", None),
    (12, "hand_solder_bom.csv empty", "mfg/make_release.py"),
    (13, "netlist: one-pin nets, rail aliases, freewheel paths, fuses, polarity", None),
    (14, "design equations against the netlist's values", None),
    (15, "fiducials, layer markers, paste openings", "mfg/make_release.py lists the fiducials and tooling holes it finds"),
    (16, "copper balance and current capacity", None),
]

CLEAN = [os.path.join("build", "OWLternatingCurrent"), os.path.join("build", "jlc_pngs")]


def main(argv):
    if "--clean" in argv:
        for p in CLEAN:
            shutil.rmtree(os.path.join(ROOT, p), ignore_errors=True)
        print("removed " + ", ".join(CLEAN))
        return 0
    names = [n for n, _, _ in STEPS]
    args = [a for a in argv if not a.startswith("--")]
    for a in args:
        if a not in names:
            raise SystemExit("unknown step %r: the steps are %s" % (a, ", ".join(names)))
    start = names.index(args[0]) if args else 0
    if "--only" in argv:
        todo = STEPS[start:start + 1]
    elif "--until" in argv:
        stop = names.index(argv[argv.index("--until") + 1])
        todo = STEPS[start:stop + 1]
    else:
        todo = STEPS[start:]
    t0 = time.time()
    notes = {}
    for name, fn, gates in todo:
        print("== %s%s" % (name, "   (gate %s)" % gates if gates else ""), flush=True)
        t = time.time()
        try:
            notes[name] = fn()
        except Failed as e:
            print("\nBUILD FAILED at %s: %s (%.0f s)" % (name, e, time.time() - t0))
            print("Nothing after it ran; fix it and run `python3 build.py %s`." % name)
            return 1
        print("   %s: %.0f s" % (name, time.time() - t))
    print("\nbuilt in %.0f s: %s" % (time.time() - t0, ", ".join(n for n, _, _ in todo)))
    if len(todo) == len(STEPS):
        print("\nCLAUDE_PCB.md section 10, as this build holds it:")
        for n, what, how in GATES:
            print("  %2d %-4s %s%s" % (n, "ok" if how else "--", what, (": " + how) if how else ": NOT CHECKED BY THE BUILD"))
    skipped = [n for n, v in notes.items() if v == "skipped"]
    if notes.get("release") == "incomplete" or skipped:
        print("\nINCOMPLETE: %s; mfg/release/ holds the BOM, its checks and the parts' cost, nothing to order yet."
              % ("no board (%s skipped)" % ", ".join(skipped) if skipped else "no board file"))
        return INCOMPLETE
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
