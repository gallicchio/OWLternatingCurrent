#!/usr/bin/env python3
"""Bring-up steps for OWLternating Current, one per command (BRINGUP.md has the order and
what to do by hand between them).

    python3 bringup/run.py find                 # which instruments answer
    python3 bringup/run.py ramp                 # first power: 0 -> 12 V, tight current limits
    python3 bringup/run.py rails                # the rails on the scope, the 4.8 V ripple
    python3 bringup/run.py off                  # supply off (also: any error, Ctrl-C)
    python3 bringup/run.py --sim ramp           # the same against a simulated board
    python3 bringup/run.py --sim --fault short5 ramp   # ... with a fault, to see it abort

Instruments come from bringup/bench.json (see bench.DEFAULTS), and the options below.
Exit status: 0 done, 2 aborted (the reason is printed; the supply is off), 1 other error.
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench                                         # noqa: E402
import steps                                         # noqa: E402
from bench import AbortStep                          # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=sorted(steps.STEPS))
    ap.add_argument("args", nargs="*", help="console: the command line; tank: owl|cat|bat; "
                    "coils: coil names; leds: LED names; rails: a rail for the DMM (e.g. +3V3); "
                    "audio: tone amplitudes; sweep: perch f0 f1 points")
    ap.add_argument("--config", help="bench.json to use")
    ap.add_argument("--supply", dest="supply_serial", help="the E3646A's serial port")
    ap.add_argument("--output", dest="supply_output", type=int, help="the E3646A output with the board (default 2)")
    ap.add_argument("--scope", help="scope IP, or 'usb'")
    ap.add_argument("--gen", help="sdg:IP | 33220a:IP | 33120a:gpib:N | 33120a:serial:PORT | none")
    ap.add_argument("--dmm", dest="dmm_serial", help="the Fluke 45's serial port")
    ap.add_argument("--port", dest="board_port", help="the board's console port (default: find it on USB)")
    ap.add_argument("--to", type=float, default=12.0, help="ramp/capture: the top voltage")
    ap.add_argument("--limit", type=float, default=0.15, help="ramp/capture: the current limit left set (A)")
    ap.add_argument("--hold", type=float, help="ramp: seconds to hold at the top")
    ap.add_argument("--tree", action="store_true", help="logic/leds: the tree is plugged in")
    ap.add_argument("--duty", type=float, help="coils/leds/sweep: the duty")
    ap.add_argument("--hz", type=float, default=440.0, help="audio: the tone")
    ap.add_argument("--ms", type=int, help="coils: pulse length; audio: each tone's length")
    ap.add_argument("--vpp", type=float, default=1.0, help="tank: the generator's amplitude")
    ap.add_argument("--image", default="owl_bringup", help="flash: owl_bringup or owlternating")
    ap.add_argument("--uf2", help="flash: a .uf2 file to flash instead")
    ap.add_argument("--token", help="perch (sim): the token on the perch")
    ap.add_argument("--sim", action="store_true", help="simulated instruments and board")
    ap.add_argument("--fault", action="append", default=[], help="sim: a fault (sim.py's list)")
    ap.add_argument("--sim-usb", action="store_true", help="sim: USB plugged in")
    a = ap.parse_args(argv)

    gen = None if a.gen is None else (None if a.gen.lower() == "none" else a.gen)
    cfg = bench.load_config(a.config, supply_serial=a.supply_serial, supply_output=a.supply_output,
                            scope=a.scope, dmm_serial=a.dmm_serial, board_port=a.board_port)
    if a.gen is not None:
        cfg["gen"] = gen
    simboard = None
    if a.sim:
        import sim
        simboard = sim.SimBoard(faults=a.fault, usb=a.sim_usb, token=a.token,
                                state_path=Path(cfg["results"]) / "sim_state.json")
        simboard.flashed = "bringup"
        cfg["dmm_serial"] = cfg["dmm_serial"] or "sim"
    ctx = steps.Ctx(cfg, sim=simboard)
    print(f"== {a.step}{' (simulated)' if a.sim else ''}")
    kw = {}
    s = a.step
    if s in ("ramp", "capture"):
        kw = {"to": a.to}
        kw["final_limit" if s == "ramp" else "limit"] = a.limit
        if s == "ramp" and a.hold is not None:
            kw["hold"] = a.hold
    elif s == "rails" and a.args:
        kw = {"dmm_rail": a.args[0]}
    elif s == "flash":
        kw = {"which": a.args[0] if a.args else a.image, "uf2": a.uf2}   # `flash owlternating` or --image
    elif s == "logic":
        kw = {"tree": a.tree}
    elif s == "leds":
        kw = {"tree": a.tree, "only": a.args or None}
        if a.duty is not None:
            kw["duty"] = a.duty
    elif s == "coils":
        kw = {"which": a.args or ("pend1", "pend2", "pend3"), "duty": a.duty, "ms": a.ms}
    elif s == "perch":
        kw = {"which": [int(x) for x in a.args] or (1, 2), "token": a.token}
    elif s == "audio":
        kw = {"hz": a.hz, "amps": tuple(float(x) for x in a.args) or (0.25, 1.0)}
        if a.ms is not None:
            kw["ms"] = a.ms
    elif s == "speaker" and a.args:
        kw = {"amp": float(a.args[0])}
    elif s == "sweep":
        # sweep [perch [f0 f1 [points]]] --duty D
        if a.args:
            kw["perch"] = int(a.args[0])
        if len(a.args) >= 3:
            kw["f0"], kw["f1"] = float(a.args[1]), float(a.args[2])
        if len(a.args) >= 4:
            kw["points"] = int(a.args[3])
        if a.duty is not None:
            kw["duty"] = a.duty
    elif s == "tank":
        if not a.args:
            ap.error("tank needs owl, cat or bat")
        kw = {"token": a.args[0], "vpp": a.vpp}
    elif s == "ohms":
        if not a.args:
            ap.error("ohms needs a test point name, e.g. TP1 or +12V (and optionally the board: 1 or 2)")
        kw = {"where": a.args[0], "board": a.args[1] if len(a.args) > 1 else "1"}
    elif s == "limit":
        if not a.args:
            ap.error("limit needs amps, e.g. 0.8")
        kw = {"amps": float(a.args[0])}
    elif s == "console":
        if not a.args:
            ap.error("console needs a command")
        kw = {"line": " ".join(a.args)}
    try:
        steps.STEPS[s](ctx, **kw)
    except AbortStep as e:
        print(f"ABORTED: {e}")
        return 2
    except KeyboardInterrupt:
        print("interrupted: supply off")
        return 2
    except Exception:                                # noqa: BLE001
        traceback.print_exc()
        print("ERROR (the supply was turned off if this step had it open)")
        return 1
    if ctx.warnings:
        print(f"done, {len(ctx.warnings)} warning(s):")
        for w in ctx.warnings:
            print("  - " + w)
    else:
        print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
