#!/usr/bin/env python3
"""Render the schematic to PDF and PNG, to look at it as Jason will.

    python3 tools/render_sch.py [out_dir] [--width 4000]

kicad-cli writes the PDF and an SVG; Inkscape turns the SVG into a PNG (run
without a display or session bus: Inkscape 1.x can otherwise wait forever).
"""
import glob, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gen"))
import kienv
import board_info as BI


def render(out, width=4000):
    sch = BI.SCH
    os.makedirs(out, exist_ok=True)
    kienv.run_cli(["sch", "export", "pdf", "-o", os.path.join(out, BI.NAME + "_schematic.pdf"), sch])
    svgdir = os.path.join(BI.SCRATCH, "sch_svg")
    shutil.rmtree(svgdir, ignore_errors=True)
    kienv.run_cli(["sch", "export", "svg", "-o", svgdir, sch])
    svgs = sorted(glob.glob(os.path.join(svgdir, "*.svg")))
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
    pngs = []
    for svg in svgs:
        # one PNG per sheet: OWLternatingCurrent.svg is the root, the rest are named
        # after their sheets (OWLternatingCurrent-base.svg)
        stem = os.path.splitext(os.path.basename(svg))[0]
        suffix = stem[len(BI.NAME):].lstrip("-") or "root"
        png = os.path.join(out, BI.IMAGE_PREFIX + "schematic_%s.png" % suffix)
        subprocess.run(["inkscape", svg, "--export-type=png", "--export-width=%d" % width,
                        "--export-background=white", "--export-filename=" + png],
                       capture_output=True, env=env, timeout=600)
        pngs.append(png)
    return pngs


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    w = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 4000
    print(render(args[0] if args else os.path.join(ROOT, "build", "view"), w))
