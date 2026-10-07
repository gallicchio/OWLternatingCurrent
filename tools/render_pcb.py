#!/usr/bin/env python3
"""Render the board's layers as KiCad draws them, to look at the copper.

    python3 tools/render_pcb.py [name=layers ...] [--crop x0,y0,x1,y1] [--width 3000]

Each name=layers pair writes build/view/pcb_<name>.png from KiCad's SVG export
of those layers (comma separated); without pairs it writes the usual set: top
copper, In2, bottom copper (mirrored), and the top silkscreen.  --crop takes
board millimetres from the top-left corner.
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kienv
import board_info as BI

PCB = BI.PCB
OUT = os.path.join(ROOT, "build", "view")
SETS = {
    "top": "F.Cu,F.Mask,F.SilkS,Edge.Cuts",
    "in1": "In1.Cu,Edge.Cuts",
    "in2": "In2.Cu,Edge.Cuts",
    "bottom": "B.Cu,B.SilkS,Edge.Cuts",
    "silk": "F.SilkS,F.Fab,Edge.Cuts",
}


def render(name, layers, crop=None, width=3000, mirror=False):
    svg = os.path.join(ROOT, "build", "pcb_%s.svg" % name)
    args = ["pcb", "export", "svg", "--mode-single", "--layers", layers, "--page-size-mode", "2",
            "--exclude-drawing-sheet", "--drill-shape-opt", "2", "-o", svg, PCB]
    if mirror:
        args.insert(3, "--mirror")
    kienv.run_cli(args)
    png = os.path.join(OUT, "pcb_%s.png" % name)
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
    cmd = ["inkscape", svg, "--export-type=png", "--export-width=%d" % width, "--export-background=#101418",
           "--export-filename=" + png]
    if crop:
        # the SVG (page-size-mode 2) spans the board's outline in millimetres; Inkscape's
        # export area is in px at 96 per inch
        k = 96 / 25.4
        x0, y0, x1, y1 = crop
        cmd.insert(2, "--export-area=%g:%g:%g:%g" % (x0 * k, y0 * k, x1 * k, y1 * k))
    subprocess.run(cmd, capture_output=True, env=env, timeout=600)
    return png


def main():
    args = sys.argv[1:]
    crop = None
    width = 3000
    if "--crop" in args:
        i = args.index("--crop")
        crop = [float(v) for v in args[i + 1].split(",")]
        del args[i:i + 2]
    if "--width" in args:
        i = args.index("--width")
        width = int(args[i + 1])
        del args[i:i + 2]
    pairs = [a.split("=", 1) for a in args if "=" in a] or [(k, v) for k, v in SETS.items() if k != "in1"]
    for name, layers in pairs:
        print(render(name, layers, crop, width, mirror=(name == "bottom")))


if __name__ == "__main__":
    main()
