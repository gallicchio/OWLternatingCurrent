"""The bring-up steps (BRINGUP.md), one function each. run.py is the command line.

Every step:
- opens what it needs (bench.open_bench), so a missing instrument stops it before it
  changes anything;
- prints what it does and what it reads, against expect.py;
- writes its record to results/<date>/<time>_<step>.json (and plots beside it);
- raises AbortStep on a reading that says stop; the supply's output then goes off.

The steps never ask for keyboard input: the person at the bench does the physical part
between steps (BRINGUP.md says what), so they can be run from a chat with Claude.
"""

import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import numpy as np

import expect as E
from bench import AbortStep, open_bench, usb_devices
from owlboard import OwlBoard

ROOT = Path(__file__).resolve().parent.parent
FW = ROOT / "firmware"


# ---- the record ----------------------------------------------------------------------------
class Ctx:
    def __init__(self, cfg, sim=None, quiet=False):
        self.cfg, self.sim, self.quiet = cfg, sim, quiet
        self.record = {}
        self.warnings = []

    def say(self, *a):
        if not self.quiet:
            print(*a, flush=True)

    def warn(self, msg):
        self.warnings.append(msg)
        self.say("  WARNING: " + msg)

    def out_dir(self):
        d = Path(self.cfg["results"]) / datetime.now().strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, step, data, failed=None):
        stamp = datetime.now().strftime("%H%M%S")
        tag = "_sim" if self.sim is not None else ""
        p = self.out_dir() / f"{stamp}_{step}{tag}.json"
        data = dict(data, step=step, time=datetime.now().isoformat(timespec="seconds"),
                    simulated=self.sim is not None, warnings=self.warnings)
        if failed:
            data["aborted"] = failed
        p.write_text(json.dumps(data, indent=1, default=_jsonable))
        self.say(f"  record: {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")
        return p

    def board(self, env=None):
        if self.sim is not None:
            return OwlBoard(sim=self.sim, env=env)
        return OwlBoard(port=self.cfg["board_port"])


def _jsonable(x):
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return str(x)


def _plot(path, title, series, xlabel, ylabel, logx=False, marks=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for label, x, y in series:
        ax.plot(x, y, label=label)
    for x, text in marks:
        ax.axvline(x, color="grey", lw=0.8, ls="--")
        ax.text(x, ax.get_ylim()[1], text, rotation=90, va="top", ha="right", fontsize=8)
    if logx:
        ax.set_xscale("log")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.3)
    if len(series) > 1:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _nice(x):
    """The scope's 1-2-5 step at or above x."""
    e = 10 ** np.floor(np.log10(x))
    for m in (1, 2, 5, 10):
        if m * e >= x - 1e-12:
            return float(m * e)
    return float(10 * e)


def _rail_scope_setup(scope):
    """Each channel on its rail (expect.SCOPE_RAILS), the screen from about 0 to 1.25 x the
    nominal: coarse, for watching and for the power-up capture."""
    for ch, rail in E.SCOPE_RAILS.items():
        nom = E.RAILS[rail][1]
        scale = _nice(nom * 1.25 / 8)
        scope.setup(ch, scale=scale, offset=-4 * scale)


def _scope_rails(scope):
    """{rail: mean volts} from one forced acquisition."""
    w = scope.capture(list(E.SCOPE_RAILS))
    return {E.SCOPE_RAILS[ch]: float(np.mean(v)) for ch, (t, v) in w.items()}


# ---- find, off, status -------------------------------------------------------------------
def step_find(ctx):
    """What instruments answer, and whether a board is on USB."""
    rec = {"instruments": {}, "usb": {}}
    for name in ("supply", "scope", "gen", "dmm"):
        try:
            with open_bench(ctx.cfg, need=(name,), want=(), sim=ctx.sim) as b:
                inst = getattr(b, name)
                rec["instruments"][name] = inst.idn if inst is not None else None
        except Exception as e:                               # noqa: BLE001
            rec["instruments"][name] = f"not found: {e}"
        ctx.say(f"  {name:6s} {rec['instruments'][name]}")
    usb = usb_devices() if ctx.sim is None else (
        {"2e8a:000f": "RP2350 Boot"} if ctx.sim.usb and not ctx.sim.flashed else
        {"1209:0001": "OWL bring-up"} if ctx.sim.usb else {})
    rec["usb"] = {k: v for k, v in usb.items() if k.startswith(("2e8a", "1209", "2e8a"))}
    ctx.say(f"  board on USB: {rec['usb'] or 'none'}")
    ctx.save("find", rec)
    return rec


def step_ohms(ctx, where, board="1"):
    """One resistance reading with the Fluke 45 (unpowered board: the leads on `where`, a
    test point, and on ground), recorded with the board's name for comparison."""
    with open_bench(ctx.cfg, need=("dmm",), want=(), sim=ctx.sim) as b:
        r = b.dmm.ohms()
    txt = "open (overload)" if r == float("inf") else f"{r:.1f} ohm"
    ctx.say(f"  board {board}, {where} to GND: {txt}")
    if r < 100:
        ctx.warn(f"{where} reads {txt} to ground: look for a short before powering")
    ctx.save(f"ohms_{where.strip('+')}_board{board}", {"where": where, "board": board, "ohms": r})
    return r


def step_limit(ctx, amps):
    """Change the current limit with the output on (the voltage stays)."""
    with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
        s = b.supply
        if not s.is_on():
            raise AbortStep("the supply is off: run 'ramp' first")
        i_max = getattr(s, "i_max", 1.5)
        if amps > i_max:
            raise AbortStep(f"this supply's range gives {i_max} A at most: use the E3632A "
                            "(--psu E3632A) or the brick")
        if getattr(s, "ocp", None) and getattr(s.ps, "has_ocp", False) and amps > s.ocp:
            raise AbortStep(f"{amps} A is above the OCP of {s.ocp} A")
        v = s.setting()["volts"]
        s.set(v, amps)
        s.keep_on()
        vm, im = s.measure()
        ctx.say(f"  {v:.2f} V, limit now {amps * 1000:.0f} mA; reads {vm:.3f} V {im * 1000:.1f} mA (zero not subtracted)")
    return {"volts": v, "limit": amps}


def step_off(ctx):
    with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
        b.supply.off()
        ctx.say("  supply output off, both outputs at 0 V")
    return {"off": True}


def step_status(ctx):
    with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
        s = b.supply.setting()
        v, i = b.supply.ps.measure(out=b.supply.out)
        mode = b.supply.mode()
        if s["output"]:
            b.supply.keep_on()
        ctx.say(f"  output {'ON' if s['output'] else 'off'}: set {s['volts']:.3f} V, limit "
                f"{s['amps'] * 1000:.0f} mA; reads {v:.3f} V, {i * 1000:.1f} mA (no zero subtracted), {mode}")
    return {"setting": s, "volts": v, "amps": i, "mode": mode}


# ---- the first power: the slow ramp ----------------------------------------------------------
def _settle(ctx, s, v, lim, dwell=1.2, cc_grace=0.8):
    """Wait at a step; CC for longer than cc_grace (C1 charging) is a fault."""
    t0 = time.time()
    cc_since = None
    while time.time() - t0 < dwell:
        m = s.mode()
        if m == "CC":
            cc_since = cc_since or time.time()
            if time.time() - cc_since > cc_grace:
                vm, im = s.measure()
                raise AbortStep(f"at {v:.1f} V the supply sat at its {lim * 1000:.0f} mA limit "
                                f"(reads {vm:.2f} V, {im * 1000:.0f} mA): a short or a heavy load")
        else:
            cc_since = None
        if ctx.sim is not None:
            break
        time.sleep(0.1)


def step_ramp(ctx, to=12.0, final_limit=0.15, hold=None):
    """The first power-up: J1 from 0 to `to` volts in the steps of expect.RAMP, each with
    a tight current limit; abort (output off) on a current limit, an unexpected current,
    a sag, or (with the scope on the rails) a rail out of its window. At the end the
    output stays on at `to` with `final_limit`."""
    hold = E.HOLD_S if hold is None else hold
    rec = {"steps": [], "to": to}
    failed = None
    try:
        with open_bench(ctx.cfg, need=("supply",), want=("scope",), sim=ctx.sim) as b:
            s = b.supply
            if ctx.sim is None:
                usb = {k for k in usb_devices() if k.startswith(("2e8a:", "1209:"))
                       and k != "2e8a:000c"}    # not the Raspberry Pi Debug Probe
                if usb:
                    ctx.warn(f"a board is on USB ({', '.join(usb)}): VBUS will power the logic, so "
                             "the rails before 6.7 V won't read 0 and the currents will be low")
            elif ctx.sim.usb:
                ctx.warn("(sim) USB plugged in")
            s.prepare(ovp=E.OVP_V)
            z = s.take_zero()
            rec["i_zero_A"] = z
            ctx.say(f"  supply: {s.idn}; output {s.out}; OVP {E.OVP_V} V; zero {z * 1000:.1f} mA at 0 V")
            if b.scope is not None:
                _rail_scope_setup(b.scope)
                ctx.say("  scope on the rails: " + ", ".join(f"CH{c} {r}" for c, r in E.SCOPE_RAILS.items()))
            else:
                ctx.say("  (no scope: currents only)")
            ctx.say(f"  {'set V':>6} {'limit':>6} {'V':>7} {'mA':>7}  {'mode':4}  rails")
            for v, lim, i_max, what in E.RAMP:
                if v > to + 1e-9:
                    break
                s.set(v, lim)
                _settle(ctx, s, v, lim)
                vm, im = s.measure()
                mode = s.mode()
                row = {"set_V": v, "limit_A": lim, "V": vm, "A": im, "mode": mode, "note": what}
                if b.scope is not None:
                    row["rails"] = _scope_rails(b.scope)
                rec["steps"].append(row)
                rails_txt = "  ".join(f"{k} {x:.2f}" for k, x in row.get("rails", {}).items())
                ctx.say(f"  {v:6.1f} {lim * 1000:5.0f}m {vm:7.3f} {im * 1000:7.1f}  {mode:4}  {rails_txt}")
                if mode == "CC":
                    raise AbortStep(f"current limit at {v} V ({im * 1000:.0f} mA)")
                if im > i_max:
                    raise AbortStep(f"{im * 1000:.1f} mA at {v} V, more than the {i_max * 1000:.0f} mA "
                                    f"expected ({what})")
                if vm < v - 0.15:
                    raise AbortStep(f"the input sags: {vm:.2f} V at {v} V set")
                r = row.get("rails")
                if r is not None:
                    if v < E.EN_ON_V - 0.1 and r["+4.8V"] > 0.5:
                        raise AbortStep(f"+4.8V reads {r['+4.8V']:.2f} V before the buck should start: "
                                        "something feeds it (USB? a short from +12V?)")
                    for rail, top in E.RAMP_OVER.items():
                        if r[rail] > top:
                            raise AbortStep(f"{rail} reads {r[rail]:.2f} V at {v} V in (over {top} V): "
                                            "the buck's feedback? a regulator in backwards?")
                    if v >= E.EN_ON_V + 0.5:
                        for rail, bottom in E.RAMP_UNDER.items():
                            if r[rail] < bottom:
                                raise AbortStep(f"{rail} reads {r[rail]:.2f} V at {v} V in (under {bottom} V)")
                        if not 0.9 <= r["+1V1"] <= 1.3:
                            ctx.warn(f"+1V1 reads {r['+1V1']:.2f} V (0.9-1.3 expected)")
            # hold at the top, watching for drift (a part warming up and drawing more)
            if rec["steps"] and abs(rec["steps"][-1]["set_V"] - to) < 1e-6 and hold > 0:
                ctx.say(f"  holding {to} V for {hold} s: touch U1, L1, U2, Q1 and the RP2354A for heat")
                t0 = time.time()
                reads = []
                n = 0
                while time.time() - t0 < hold and (ctx.sim is None or n < 5):
                    vm, im = s.measure()
                    reads.append((time.time() - t0, vm, im, s.mode()))
                    if reads[-1][3] == "CC":
                        raise AbortStep(f"current limit during the hold ({im * 1000:.0f} mA)")
                    n += 1
                    if ctx.sim is None:
                        time.sleep(1.0)
                rec["hold"] = reads
                i0, i1 = reads[0][2], reads[-1][2]
                drift = (i1 - i0) / max(i0, 1e-3)
                ctx.say(f"  hold: {i0 * 1000:.1f} -> {i1 * 1000:.1f} mA ({drift * 100:+.0f} %)")
                if abs(drift) > E.HOLD_DRIFT:
                    ctx.warn(f"the current drifted {drift * 100:+.0f} % in {hold} s")
                lo, hi = E.IDLE_12V_A
                if not lo <= i1 <= hi:
                    ctx.warn(f"idle {i1 * 1000:.1f} mA at {to} V is outside the estimate "
                             f"{lo * 1000:.0f}-{hi * 1000:.0f} mA (expect.py; an estimate, not a limit)")
            s.set(to, final_limit)
            s.keep_on()
            ctx.say(f"  left ON: {to} V, limit {final_limit * 1000:.0f} mA ('run.py off' to stop)")
    except AbortStep as e:
        failed = str(e)
        ctx.say(f"  ABORTED, output off: {failed}")
        raise
    finally:
        ctx.save("ramp", rec, failed)
    return rec


# ---- the rails, precisely -------------------------------------------------------------------
def step_rails(ctx, dmm_rail=None):
    """The rails' DC levels (scope means, or the DMM on one rail) and the buck's ripple."""
    rec = {}
    with open_bench(ctx.cfg, need=("supply",), want=("scope", "dmm"), sim=ctx.sim) as b:
        b.supply.keep_on() if b.supply.is_on() else None
        if not b.supply.is_on():
            raise AbortStep("the supply is off: run 'ramp' first")
        if dmm_rail:
            if b.dmm is None:
                raise AbortStep("no DMM configured (dmm_serial in bench.json)")
            if ctx.sim is not None:
                b.dmm.m.probe_at = dmm_rail
            v = b.dmm.volts()
            tp, nom, lo, hi, why = E.RAILS[dmm_rail]
            ok = lo <= v <= hi
            ctx.say(f"  DMM on {tp} ({dmm_rail}): {v:.4f} V  [{lo}-{hi}] {'ok' if ok else 'OUT'}  ({why})")
            rec["dmm"] = {dmm_rail: v, "ok": ok}
            ctx.save("rails_dmm", rec)
            return rec
        if b.scope is None:
            raise AbortStep("no scope: give --dmm RAIL to read one rail with the DMM instead")
        sc = b.scope
        _rail_scope_setup(sc)
        sc.timebase(1e-3)
        coarse = _scope_rails(sc)
        rec["coarse"] = coarse
        fine = {}
        for ch, rail in E.SCOPE_RAILS.items():     # zoom in round each rail's level
            sc.setup(ch, scale=0.05, offset=-coarse[rail])
        w = sc.capture(list(E.SCOPE_RAILS))
        for ch, (t, v) in w.items():
            fine[E.SCOPE_RAILS[ch]] = float(np.mean(v))
        rec["fine"] = fine
        ctx.say(f"  {'rail':6} {'TP':4} {'scope V':>8}  window")
        for rail, v in fine.items():
            tp, nom, lo, hi, why = E.RAILS[rail]
            flag = "ok" if lo - 0.05 <= v <= hi + 0.05 else "CHECK WITH THE DMM"
            ctx.say(f"  {rail:6} {tp:4} {v:8.3f}  {lo}-{hi}  {flag}")
        # the 4.8 V ripple, AC coupled, 20 MHz
        ch48 = [c for c, r in E.SCOPE_RAILS.items() if r == "+4.8V"][0]
        sc.setup(ch48, scale=0.01, offset=0.0, coupling="AC", bwlimit="20M")
        sc.timebase(2e-6)
        t, v = sc.capture([ch48])[ch48]
        pp = float(v.max() - v.min())
        f = sc.freq(ch48)
        rec["ripple_4v8"] = {"pkpk_V": pp, "freq_Hz": f}
        ctx.say(f"  +4.8V ripple {pp * 1000:.1f} mVpp (limit {E.RIPPLE_4V8_MAX * 1000:.0f}), "
                f"{'%.0f kHz' % (f / 1e3) if f else 'no steady frequency (pulse skipping at light load is normal)'}")
        if pp > E.RIPPLE_4V8_MAX:
            ctx.warn(f"+4.8V ripple {pp * 1000:.0f} mVpp")
        _plot(ctx.out_dir() / f"{datetime.now():%H%M%S}_ripple_4v8{'_sim' if ctx.sim else ''}.png",
              "+4.8V ripple (AC, 20 MHz)", [("+4.8V", t * 1e6, v * 1000)], "us", "mV")
        sc.setup(ch48, scale=_nice(4.8 * 1.25 / 8), offset=-4 * _nice(4.8 * 1.25 / 8), coupling="DC")
        sc.timebase(1e-3)
        sc.run()
        ctx.save("rails", rec)
    return rec


def step_capture(ctx, limit=0.15, to=12.0):
    """The power-up on the scope: the output off until +4.8V has decayed, then one jump to
    `to` volts, captured on all four rails (trigger: +4.8V rising through 2.4 V). Shows the
    order the rails come up in and any overshoot. Leaves the output on."""
    rec = {}
    with open_bench(ctx.cfg, need=("supply", "scope"), want=(), sim=ctx.sim) as b:
        s, sc = b.supply, b.scope
        _rail_scope_setup(sc)
        s.off()
        ctx.say("  output off; waiting for +4.8V to fall below 0.3 V")
        t0 = time.time()
        while True:
            r = _scope_rails(sc)
            if r["+4.8V"] < 0.3 or ctx.sim is not None:
                break
            if time.time() - t0 > 120:
                raise AbortStep(f"+4.8V still {r['+4.8V']:.2f} V after 2 min off: something feeds it")
            time.sleep(1.0)
        s.prepare(ovp=E.OVP_V)
        sc.timebase(20e-3, delay=3 * 20e-3)               # the trigger 2 divisions from the left
        ch48 = [c for c, r in E.SCOPE_RAILS.items() if r == "+4.8V"][0]
        sc.arm({"source": ch48, "level": 2.4, "slope": "rising"})
        s.set(to, limit)
        s.on()
        w = sc.wait(list(E.SCOPE_RAILS), timeout=10)
        series, peaks = [], {}
        for ch, (t, v) in w.items():
            rail = E.SCOPE_RAILS[ch]
            series.append((f"CH{ch} {rail}", t * 1e3, v))
            peaks[rail] = float(np.max(v))
            nom = E.RAILS[rail][1]
            if peaks[rail] > nom * 1.08:
                ctx.warn(f"{rail} overshoots to {peaks[rail]:.2f} V ({nom} nominal)")
        rec["peaks"] = peaks
        png = ctx.out_dir() / f"{datetime.now():%H%M%S}_powerup{'_sim' if ctx.sim else ''}.png"
        _plot(png, f"Power-up: J1 0 -> {to} V at {limit * 1000:.0f} mA limit", series, "ms", "V")
        ctx.say("  peaks: " + ", ".join(f"{k} {v:.2f} V" for k, v in peaks.items()))
        ctx.say(f"  plot: {png}")
        try:
            sc.screenshot(png.with_name(png.stem + "_screen.png"))
        except Exception as e:                            # noqa: BLE001
            ctx.warn(f"no screenshot: {e}")
        sc.timebase(1e-3, delay=0)
        sc.run()
        s.keep_on()
        ctx.save("capture", rec)
    return rec


# ---- USB, flashing -------------------------------------------------------------------------
def step_usb(ctx):
    """Is the RP2354A on USB (blank: 2e8a:000f, the ROM's "RP2350 Boot"; flashed: 1209:...),
    and how the 12 V current changes with USB in (the logic moves to VBUS)."""
    usb = usb_devices() if ctx.sim is None else (
        {"2e8a:000f": "RP2350 Boot"} if ctx.sim.usb and not ctx.sim.flashed else
        {"1209:0001": "OWL bring-up"} if ctx.sim.usb else {})
    ours = {k: v for k, v in usb.items() if k.startswith(("2e8a:", "1209:"))}
    rec = {"usb": ours}
    ctx.say(f"  on USB: {ours or 'nothing from the board'}")
    if not ours:
        ctx.warn("no RP2350 on USB: check the cable (data, not charge-only), J2's joints, the "
                 "12 MHz crystal (scope XOUT with a x10 probe), +1V1, and try BOOT held at plug-in")
    try:
        with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
            if b.supply.is_on():
                b.supply.keep_on()
                v, i = b.supply.measure()
                rec["supply"] = {"V": v, "A_uncorrected": i}
                ctx.say(f"  12 V input now {i * 1000:.1f} mA (zero not subtracted); with USB in, the "
                        f"logic runs from VBUS: expect {E.IDLE_12V_USB_A[1] * 1000:.0f} mA or less")
    except Exception as e:                                # noqa: BLE001
        ctx.say(f"  (supply not read: {e})")
    ctx.save("usb", rec)
    return rec


def build_dir():
    """This machine's firmware build: firmware/build-<hostname> (firmware/build/ may be
    configured on another machine, at another path)."""
    import socket
    return FW / f"build-{socket.gethostname()}"


def step_build(ctx):
    """Build both firmware images and the host tests. CXXFLAGS="-include cstdint" works
    round the Pico SDK 2.1.1's pioasm on GCC 15 (it only reaches the PC-side tools)."""
    import os
    env = dict(os.environ, CXXFLAGS="-include cstdint")
    d = build_dir()
    rec = {"dir": str(d)}
    for cmd in (["cmake", "-S", str(FW), "-B", str(d)], ["cmake", "--build", str(d), "-j8"],
                ["make", "-C", str(FW / "test")]):
        ctx.say("  $ " + " ".join(cmd))
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
        ctx.say("    " + "\n    ".join(tail))
        if r.returncode:
            raise AbortStep(f"{' '.join(cmd[:2])} failed")
    rec["images"] = {p.name: p.stat().st_size for p in d.glob("*.uf2")}
    ctx.say(f"  images: {rec['images']}")
    ctx.save("build", rec)
    return rec


def _uf2(which):
    """The UF2 to flash: `which` ('owl_bringup' or 'owlternating') from this machine's build."""
    p = build_dir() / f"{which}.uf2"
    if not p.exists():
        raise AbortStep(f"no {p}: run 'run.py build' first")
    return p


def step_flash(ctx, which="owl_bringup", uf2=None):
    """Copy a UF2 onto the RP2350 drive (the ROM bootloader's mass storage), or use
    picotool if it is installed with USB support. Then wait for the board's console."""
    path = Path(uf2) if uf2 else _uf2(which)
    rec = {"uf2": str(path), "size": path.stat().st_size}
    ctx.say(f"  image: {path} ({path.stat().st_size // 1024} kB)")
    if ctx.sim is not None:
        ctx.sim.flashed = "bringup" if "bringup" in path.name else "main"
        ctx.say("  (sim) flashed")
        ctx.save("flash", rec)
        return rec
    picotool = shutil.which("picotool")
    if picotool:
        r = subprocess.run([picotool, "load", "-x", str(path), "-f"], capture_output=True, text=True,
                           timeout=60)
        rec["picotool"] = r.stdout + r.stderr
        ctx.say("  " + (r.stdout + r.stderr).strip().replace("\n", "\n  "))
        if r.returncode == 0:
            ctx.save("flash", rec)
            return rec
        ctx.say("  picotool failed; trying the RP2350 drive")
    drives = [p for p in Path("/media").glob("*/RP2350*")] + [p for p in Path("/run/media").glob("*/RP2350*")]
    if not drives:
        raise AbortStep("no RP2350 drive mounted: hold BOOT while plugging USB in (or "
                        "'picotool reboot -u -f' / the console's 'bootsel'), then open the drive "
                        "in the file manager so it mounts")
    dest = drives[0] / path.name
    shutil.copyfile(path, dest)
    subprocess.run(["sync"])
    rec["drive"] = str(drives[0])
    ctx.say(f"  copied to {drives[0]}; the board reboots into it")
    time.sleep(3)
    ctx.save("flash", rec)
    return rec


# ---- the logic, through the bring-up image ------------------------------------------------------
def step_logic(ctx, tree=False):
    """id, rails, I2C, sensors and inputs from the bring-up image, against expect.py."""
    rec = {}
    with ctx.board() as bd:
        rec["id"] = bd.cmd("id")
        ctx.say(f"  board: {rec['id']}")
        r = rec["rails"] = bd.cmd("rails")
        ctx.say(f"  rails (ADC): V12 {r['v12']:.2f}  V5 {r['v5']:.2f}  VBUS {r['vbus']:.2f}  "
                f"usb_only {r['usb_only']}")
        for key, rail in (("v12", "+12V"), ("v5", "+4.8V")):
            nom = E.RAILS[rail][1]
            if r[key] > 1 and abs(r[key] / nom - 1) > E.RAIL_READ_TOL:
                ctx.warn(f"the ADC reads {rail} as {r[key]:.2f} V ({nom} nominal +-{E.RAIL_READ_TOL * 100:.0f} %): "
                         "a divider, the mux, or the ADC reference")
        scan = rec["i2c"] = bd.cmd("i2c scan")
        found = {a.lower() for a in scan["found"]}
        want = dict(E.I2C_BASE, **(E.I2C_TREE if tree else {}))
        for addr, what in want.items():
            ok = addr.lower() in found
            ctx.say(f"  I2C {addr} {what}: {'found' if ok else 'MISSING'}")
            if not ok:
                ctx.warn(f"I2C {addr} ({what}) missing")
        extra = found - {a.lower() for a in want} - ({a.lower() for a in E.I2C_TREE} if not tree else set())
        if extra:
            ctx.warn(f"unexpected I2C addresses: {sorted(extra)}")
        sen = rec["sensors"] = bd.cmd("sensors")
        imu, als, tmag = sen["imu"], sen["als"], sen["tmag"]
        if imu.get("present"):
            g = np.linalg.norm(imu["accel_g"])
            ctx.say(f"  IMU: whoami {imu.get('whoami')}, |a| = {g:.3f} g {imu['accel_g']}, {imu.get('temp_C')} C")
            if abs(g - 1) > 0.1:
                ctx.warn(f"the IMU reads |a| = {g:.2f} g at rest")
        if als.get("present"):
            ctx.say(f"  light: {als.get('lux')} lux")
        if tmag.get("present"):
            ctx.say(f"  TMAG5273: {tmag.get('mT')} mT, {tmag.get('temp_C')} C")
        ctx.say(f"  levitation Hall (perch, if plugged in): {sen.get('hall_lev_mT')} mT")
        rec["gpio"] = bd.cmd("gpio")
        ctx.say(f"  inputs: {rec['gpio']}")
        if rec["gpio"].get("nfault"):
            ctx.warn("nFAULT is asserted with every bridge asleep")
        rec["events"] = bd.events
    ctx.save("logic", rec)
    return rec


def led_names(drivers=(0, 1)):
    """[(name, driver, out)] from led_map.h, in its order."""
    text = (FW / "src" / "led_map.h").read_text()
    rows = re.findall(r'\{LED_DRV_(BASE|TREE),\s*(\d+), "(\w+)"', text)
    out = []
    for drv, ch, name in rows:
        d = 0 if drv == "BASE" else 1
        if d in drivers:
            out.append((name, d, int(ch)))
    return out


def step_leds(ctx, tree=False, duty=0.5, only=None):
    """Each LED alone at `duty`: the 12 V supply's extra current says it lit (and is not
    shorted); the person at the bench watches it light in turn (BRINGUP.md)."""
    rec = {"leds": []}
    names = led_names((0, 1) if tree else (0,))
    if only:
        names = [n for n in names if n[0] in {o.upper() for o in only}]
    with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b, ctx.board() as bd:
        s = b.supply
        if not s.is_on():
            raise AbortStep("the supply is off: run 'ramp' first")
        s.keep_on()
        bd.cmd("led off")
        time.sleep(0.3 if ctx.sim is None else 0)
        base = np.mean([s.measure()[1] for _ in range(3)])
        ctx.say(f"  baseline {base * 1000:.1f} mA; each LED at duty {duty}:")
        for name, drv, ch in names:
            bd.cmd(f"led {name} {duty}")
            time.sleep(0.3 if ctx.sim is None else 0)
            i = np.mean([s.measure()[1] for _ in range(2)])
            bd.cmd(f"led {name} 0")
            d = i - base
            rec["leds"].append({"name": name, "driver": drv, "out": ch, "delta_A": d})
            ctx.say(f"  {name:12s} drv {drv} out {ch:2d}: +{d * 1000:5.1f} mA")
        bd.cmd("led off")
        deltas = np.array([x["delta_A"] for x in rec["leds"]])
        if len(deltas):
            med = float(np.median(deltas))
            rec["median_A"] = med
            ctx.say(f"  median +{med * 1000:.1f} mA (estimate {E.LED_DELTA_12V_A * duty / 0.5 * 1000:.1f})")
            for x in rec["leds"]:
                if x["delta_A"] < E.LED_DELTA_MIN_FRACTION * med:
                    ctx.warn(f"{x['name']} added only {x['delta_A'] * 1000:.1f} mA: open, reversed, or "
                             "not soldered (the pumpkins' 5050s draw more, as three dice)")
    ctx.save("leds", rec)
    return rec


def step_ledwalk(ctx, ms=600):
    """Each LED alone in led_map order, for the eye: names printed as they light."""
    with ctx.board() as bd:
        bd.cmd(f"ledwalk {ms}", timeout=49 * ms / 1000 + 10,
               on_event=lambda e: ctx.say(f"  {e.get('i'):2}: {e.get('name')}") if e.get("event") == "ledwalk" else None)
    return {}


def step_coils(ctx, which=("pend1", "pend2", "pend3"), duty=None, ms=None):
    """Each coil: a short pulse; the mirror's current against V/R, nFAULT, the offset."""
    duty = E.COIL_TEST_DUTY if duty is None else duty
    ms = E.COIL_TEST_MS if ms is None else ms
    rec = {"coils": []}
    with ctx.board() as bd:
        for c in which:
            # ok:false still carries the measurements (a pulse stopped by nFAULT or the
            # mirror, or refused): report it, don't raise
            r = bd.cmd(f"coil {c} {duty} {ms}", timeout=ms / 1000 + 5, check=False)
            want = E.COIL_R[c]
            r_est = r.get("r_est_ohm")          # the loop less the DRV8874's 0.2 ohm (the image's)
            ok = (r.get("ok") and r_est is not None and abs(r_est / want - 1) <= E.COIL_R_TOL
                  and not r.get("nfault"))
            rec["coils"].append(dict(r, expected_ohm=want, ok=ok))
            if "i_mean_A" not in r:
                ctx.warn(f"{c}: refused: {r.get('error')}")
                continue
            ctx.say(f"  {c:6s} {duty:+.2f} x {r['v12']:.1f} V for {r.get('ran_ms', ms):.0f} ms: "
                    f"{r['i_mean_A']:.3f} A mean (expected {r.get('i_expected_A', 0):.3f}), "
                    f"{r['i_peak_A']:.3f} peak, coil {r_est if r_est is None else round(r_est, 2)} ohm "
                    f"(design {want:.2f}), mirror after {r['i_off_A'] * 1000:.1f} mA, nFAULT {r.get('nfault')}"
                    f"  {'ok' if ok else 'CHECK'}")
            if not ok:
                ctx.warn(f"{c}: {r.get('error') or ''} coil {r_est} ohm against {want:.2f}, nFAULT {r.get('nfault')}")
    ctx.save("coils", rec)
    return rec


def step_perch(ctx, which=(1, 2), token=None):
    """Sweep each familiar perch (bring-up image's `sweep`): the bridge's supply current
    against frequency. With a token on the perch its resonance shows as a bump."""
    rec = {"sweeps": {}}
    env = {"OWL_SIM_TOKEN": token} if (ctx.sim is not None and token) else None
    series = []
    with ctx.board(env=env) as bd:
        for p in which:
            pts = []
            r = bd.cmd(f"sweep {p}", timeout=20,
                       on_event=lambda e: pts.append((e["f"], e["i_A"])) if e.get("event") == "sweep_pt" else None)
            bd.events = [e for e in bd.events if e.get("event") != "sweep_pt"]   # kept in pts
            pts.sort()
            rec["sweeps"][p] = pts
            if pts:
                f, i = np.array(pts).T
                k = int(np.argmax(i - np.median(i)))
                ctx.say(f"  perch {p}: {len(pts)} points, {i.min() * 1000:.0f}-{i.max() * 1000:.0f} mA, "
                        f"largest bump at {f[k] / 1e3:.0f} kHz")
                series.append((f"perch {p}", f / 1e3, i * 1000))
    if series:
        png = ctx.out_dir() / f"{datetime.now():%H%M%S}_perch{'_' + token if token else ''}{'_sim' if ctx.sim else ''}.png"
        marks = [(E.TOKEN_F[t] / 1e3, t) for t in ("owl", "cat")]
        _plot(png, f"Perch sweeps{' with the ' + token + ' token' if token else ''}", series, "kHz", "mA", marks=marks)
        ctx.say(f"  plot: {png}")
    ctx.save("perch", rec)
    return rec


def step_tank(ctx, token, vpp=1.0, points=61):
    """A token's (or the bat's) resonance, unpowered: the generator drives a few turns of
    wire under it through 100 ohm; scope CH1 (x10 probe) across its tank capacitor. A log
    sweep round the expected frequency; the peak and its Q."""
    f0 = E.TOKEN_F[token]
    fs = np.geomspace(f0 * 0.6, f0 * 1.6, points)
    rec = {"token": token, "expected_Hz": f0, "points": []}
    with open_bench(ctx.cfg, need=("gen", "scope"), want=(), sim=ctx.sim) as b:
        if ctx.sim is not None:
            ctx.sim.token = token
        g, sc = b.gen, b.scope
        sc.setup(1, scale=0.2, offset=0.0, coupling="AC", bwlimit="20M")
        g.sine(fs[0], vpp)
        g.on()

        def point(f):
            g.sine(f, vpp)
            sc.timebase(_nice(2.0 / f / 10))
            t, v = sc.capture([1])[1]
            rec["points"].append((float(f), float(v.max() - v.min())))

        try:
            for f in fs:                          # coarse, +-60 % round the design
                point(f)
            fpk = max(rec["points"], key=lambda p: p[1])[0]
            for f in np.geomspace(fpk * 0.9, fpk * 1.1, 41):     # fine, round the peak
                point(f)
        finally:
            g.off()
    rec["points"].sort()
    f, a = np.array(rec["points"]).T
    k = int(np.argmax(a))
    half = a[k] / np.sqrt(2)
    above = np.where(a >= half)[0]
    bw = f[above[-1]] - f[above[0]] if len(above) > 1 else float("nan")
    rec.update(peak_Hz=float(f[k]), peak_Vpp=float(a[k]), q=float(f[k] / bw) if bw else None)
    err = f[k] / f0 - 1
    ok = abs(err) <= E.TOKEN_F_TOL
    ctx.say(f"  {token}: peak {f[k] / 1e3:.1f} kHz ({err * 100:+.1f} % from {f0 / 1e3:.0f}), "
            f"{a[k]:.2f} Vpp, Q ~{rec['q']:.0f}  {'ok' if ok else 'OFF TUNE'}")
    if a[k] > 3.0:
        ctx.warn("the tank reached its LEDs' clamp: lower vpp for a true Q")
    if not ok:
        ctx.warn(f"{token} tuned {err * 100:+.0f} % off")
    png = ctx.out_dir() / f"{datetime.now():%H%M%S}_tank_{token}{'_sim' if ctx.sim else ''}.png"
    _plot(png, f"The {token}'s tank through a pickup loop", [(token, f / 1e3, a)], "kHz", "Vpp",
          logx=True, marks=[(f0 / 1e3, "designed")])
    ctx.say(f"  plot: {png}")
    ctx.save(f"tank_{token}", rec)
    return rec


def step_osc(ctx):
    with ctx.board() as bd:
        r = bd.cmd("osc 200")
    lo, hi = E.THEREMIN_HZ
    for k in ("pitch_hz", "volume_hz"):
        ok = lo <= r[k] <= hi
        ctx.say(f"  {k}: {r[k] / 1e3:.1f} kHz {'ok' if ok else 'OUT OF RANGE'}")
        if not ok:
            ctx.warn(f"theremin {k} {r[k]} Hz")
    ctx.save("osc", r)
    return r


def step_tone(ctx, hz=440, ms=1000, amp=0.1):
    with ctx.board() as bd:
        r = bd.cmd(f"tone {hz} {ms} {amp}", timeout=ms / 1000 + 5)
    ctx.say(f"  played: {r} (the SOUND switch must be on to hear it)")
    ctx.save("tone", r)
    return r


def _reply(bd, deadline):
    """The command's reply (a JSON object with "ok"), events before it kept in bd.events."""
    while True:
        m = bd.read_json(deadline)
        if m is None or ("ok" in m and "event" not in m):
            return m
        bd.events.append(m)


def _tone_cost_12v_A(amp):
    """The 12 V current a tone should add: full scale 3.3 Vpp x 1.1 into 8 ohm, the NS4150B
    at 90 %, the buck at 85 %."""
    vpk = amp * 1.65 * 1.09
    return (vpk * vpk / 2.0 / 8.0) / 0.9 / 0.85 / 12.0


def step_audio(ctx, hz=440, ms=6000, amps=(0.25, 1.0)):
    """Is the amplifier driving the speaker? Each tone's extra 12 V current (the supply's
    readback) against what it should cost (amp 0.25: ~1.3 mA; 1.0: ~20 mA at 12 V), with
    the amplifier's own 1.8 mA (SOUND on) read first. With the scope, the +4.8V channel
    AC-coupled during the loudest tone: the amplifier's ~400 kHz switching when awake, a
    440 Hz envelope when it drives the speaker."""
    rec = {"hz": hz, "ms": ms, "tones": []}
    with open_bench(ctx.cfg, need=("supply",), want=("scope",), sim=ctx.sim) as b:
        if not b.supply.is_on():
            raise AbortStep("the supply is off: run 'ramp' first")
        b.supply.keep_on()

        def current(n=8, dt=0.15):
            xs = []
            for _ in range(n):
                xs.append(b.supply.measure()[1])
                time.sleep(dt)
            return float(np.mean(xs)), float(np.std(xs))

        i0, s0 = current(12)
        rec["idle_A"] = i0
        amp_on = i0 > E.AUDIO_AMP_IDLE_12V_A * 0.6
        ctx.say(f"  12 V idle {i0 * 1000:.2f} mA (+-{s0 * 1000:.2f}): the amplifier looks "
                f"{'AWAKE (SOUND on)' if amp_on else 'asleep (SOUND off, or no 4.8 V)'} "
                f"against its ~{E.AUDIO_AMP_IDLE_12V_A * 1000:.1f} mA")
        rec["amp_awake_guess"] = amp_on
        sc = b.scope
        ch48 = [c for c, r in E.SCOPE_RAILS.items() if r == "+4.8V"][0] if sc else None
        if sc:
            sc.setup(ch48, scale=0.01, offset=0.0, coupling="AC", bwlimit="20M")
            sc.timebase(1e-3)
            t, v = sc.capture([ch48])[ch48]
            rec["scope_quiet"] = {"pkpk_V": float(v.max() - v.min())}
            quiet = (t, v)
        with ctx.board() as bd:
            for amp in amps:
                bd._send(f"tone {hz} {ms} {amp}")
                time.sleep(0.4)                       # the 100 ms ramp up, the readback's lag
                during = []
                cap = None
                t0 = time.time()
                while time.time() - t0 < ms / 1000 - 0.6:
                    during.append(b.supply.measure()[1])
                    if sc and amp == max(amps) and cap is None and time.time() - t0 > 0.8:
                        tt, vv = sc.capture([ch48])[ch48]
                        cap = (tt, vv)
                    time.sleep(0.1)
                r = _reply(bd, time.time() + ms / 1000 + 5)
                time.sleep(0.5)
                i_after, _ = current(6)
                i_on = float(np.mean(during))
                want = _tone_cost_12v_A(amp)
                d = i_on - (i0 + i_after) / 2
                verdict = ("DRIVING the speaker" if d > 0.5 * want else
                           "no load drawn: no signal reaches the speaker" if d < 0.15 * want else "partial")
                ctx.say(f"  tone {hz} Hz amp {amp}: 12 V {i_on * 1000:.2f} mA during, {i_after * 1000:.2f} after: "
                        f"+{d * 1000:.2f} mA against ~{want * 1000:.1f} expected: {verdict}")
                tone = dict(amp=amp, i_during_A=i_on, i_after_A=i_after, delta_A=d, expected_A=want,
                            verdict=verdict, reply=r, n=len(during))
                if cap is not None:
                    tt, vv = cap
                    pp = float(vv.max() - vv.min())
                    tone["scope_pkpk_V"] = pp
                    ctx.say(f"  +4.8V during the tone: {pp * 1000:.1f} mVpp (quiet: "
                            f"{rec['scope_quiet']['pkpk_V'] * 1000:.1f})")
                    png = ctx.out_dir() / f"{datetime.now():%H%M%S}_audio_4v8{'_sim' if ctx.sim else ''}.png"
                    _plot(png, f"+4.8V (AC) quiet and during a {hz} Hz tone at {amp}",
                          [("quiet", quiet[0] * 1e3, quiet[1] * 1e3), ("tone", tt * 1e3, vv * 1e3)], "ms", "mV")
                    ctx.say(f"  plot: {png}")
                rec["tones"].append(tone)
        if sc:
            sc.setup(ch48, scale=_nice(4.8 * 1.25 / 8), offset=-4 * _nice(4.8 * 1.25 / 8), coupling="DC")
            sc.timebase(1e-3)
            sc.run()
    if not amp_on:
        ctx.warn("the amplifier looked asleep: flip SOUND and run again")
    ctx.save("audio", rec)
    return rec


SPEAKER_SCAN_HZ = (200, 300, 400, 500, 700, 900, 1100, 1300, 1500, 1600, 1700, 1800, 1900, 2000, 2200,
                   2500, 3000, 3500, 4000)


def step_speaker(ctx, amp=1.0, hz=SPEAKER_SCAN_HZ):
    """The speaker's impedance against frequency, from the 12 V current a full-scale tone
    adds (6 s tones, the readback taken 1.2-4.5 s in). A moving cone shows its mechanical
    resonance as a dip in current (an impedance peak: 1.8 kHz on board 1, 2026-11-06),
    and the voice coil's inductance as the slow fall above it. A flat, resistive curve
    means the coil is not moving."""
    rec = {"amp": amp, "scan": []}
    with open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
        if not b.supply.is_on():
            raise AbortStep("the supply is off: run 'ramp' first")
        b.supply.keep_on()
        idle = float(np.mean([b.supply.measure()[1] for _ in range(6)]))
        rec["idle_A"] = idle
        with ctx.board() as bd:
            for f in hz:
                bd._send(f"tone {f} 6000 {amp}")
                time.sleep(1.2)
                xs = [b.supply.measure()[1] for _ in range(6)]     # ~3.3 s, inside the tone
                r = _reply(bd, time.time() + 8)
                if not (r and r.get("ok")):
                    raise AbortStep(f"tone {f}: {r}")
                d = float(np.mean(xs)) - idle
                vpk = amp * 1.65 * 1.09
                z = (vpk * vpk / 2.0) / (d * 12.0 * 0.9 * 0.85) if d > 0 else float("inf")
                rec["scan"].append((f, d, z))
                ctx.say(f"  {f:5d} Hz  +{d * 1000:6.2f} mA  ({z:5.1f} ohm equivalent)")
                time.sleep(0.3)
    if rec["scan"]:
        f, d, z = np.array(rec["scan"]).T
        k = int(np.argmin(d))
        ctx.say(f"  least current (highest impedance) at {f[k]:.0f} Hz: a moving cone's resonance if it is a "
                f"dip, not the top of a slope")
        png = ctx.out_dir() / f"{datetime.now():%H%M%S}_speaker{'_sim' if ctx.sim else ''}.png"
        _plot(png, f"12 V current added by a tone at {amp} of full scale", [("tone", f, d * 1000)], "Hz", "mA",
              logx=True)
        ctx.say(f"  plot: {png}")
    ctx.save("speaker", rec)
    return rec


def step_sweep(ctx, perch=1, f0=90e3, f1=500e3, points=200, duty=0.03):
    """One perch's bridge-current sweep over any range (the image's `sweep` with its
    arguments): finer, wider or harder than `perch`. The peaks are listed."""
    pts = []
    with ctx.board() as bd:
        r = bd.cmd(f"sweep {perch} {f0:.0f} {f1:.0f} {points} {duty}", timeout=points * 0.05 + 20,
                   on_event=lambda e: pts.append((e["f"], e["i_A"])) if e.get("event") == "sweep_pt" else None)
        bd.events = [e for e in bd.events if e.get("event") != "sweep_pt"]
    pts.sort()
    rec = {"perch": perch, "duty": duty, "reply": r, "sweep": pts}
    if pts:
        f, i = np.array(pts).T
        med = float(np.median(i))
        peaks = [k for k in range(1, len(i) - 1) if i[k] >= i[k - 1] and i[k] > i[k + 1] and i[k] > med * 1.5]
        rec["peaks"] = [(float(f[k]), float(i[k])) for k in peaks]
        ctx.say(f"  perch {perch}: {len(pts)} points {f[0] / 1e3:.0f}-{f[-1] / 1e3:.0f} kHz at duty {duty}: "
                f"{i.min() * 1e3:.2f}-{i.max() * 1e3:.2f} mA, median {med * 1e3:.2f}; peaks over 1.5 x median: "
                + (", ".join(f"{f[k] / 1e3:.0f} kHz ({i[k] * 1e3:.2f} mA)" for k in peaks) or "none"))
        png = ctx.out_dir() / f"{datetime.now():%H%M%S}_sweep{perch}{'_sim' if ctx.sim else ''}.png"
        _plot(png, f"Perch {perch} sweep, duty {duty}", [(f"perch {perch}", f / 1e3, i * 1e3)], "kHz", "mA",
              marks=[(E.TOKEN_F[t] / 1e3, t) for t in ("owl", "cat")])
        ctx.say(f"  plot: {png}")
    ctx.save("sweep", rec)
    return rec


def step_console(ctx, line, timeout=10):
    """Any one console command, its reply and events printed. A reboot gets no reply (the
    bring-up image answers first, the real firmware just goes), so none is waited for."""
    with ctx.board() as bd:
        if line.split()[:1] in (["reboot"], ["bootsel"]):
            bd._send(line)
            time.sleep(0.5)
            r = {"ok": True, "cmd": line.split()[0], "note": "sent; the board reboots without replying"}
            ctx.say(f"  {json.dumps(r)}")
            return r
        r = bd.cmd(line, timeout=timeout, check=False)
        for e in bd.events:
            ctx.say(f"  event: {json.dumps(e)}")
        ctx.say(f"  {json.dumps(r)}")
    return r


STEPS = {
    "build": step_build, "find": step_find, "off": step_off, "ohms": step_ohms, "limit": step_limit, "status": step_status, "ramp": step_ramp,
    "rails": step_rails, "capture": step_capture, "usb": step_usb, "flash": step_flash,
    "logic": step_logic, "leds": step_leds, "ledwalk": step_ledwalk, "coils": step_coils,
    "perch": step_perch, "tank": step_tank, "osc": step_osc, "tone": step_tone,
    "audio": step_audio, "speaker": step_speaker, "sweep": step_sweep, "console": step_console,
}
