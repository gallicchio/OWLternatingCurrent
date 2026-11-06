"""The bench for bringing up OWLternating Current: the instruments, behind small adapters
that the steps (steps.py) use and that sim.py imitates.

    from bench import open_bench
    with open_bench(config) as b:          # or open_bench(config, sim=SimBoard())
        b.supply.set(12.0, 0.15); b.supply.on()
        print(b.supply.measure())          # (volts, amps)

The drivers are lab-instrument-control's (~/mudd/lab-instrument-control, or $OWL_LAB):
- the Agilent E3646A two-output supply on RS-232 (the board's 12 V on one output);
- the Siglent SDS2104X Plus scope on the LAN (or USB);
- a function generator: the Siglent SDG1032X (LAN), the Agilent 33220A (LAN) or an HP
  33120A (GPIB through the Prologix adapter, or RS-232);
- optionally the Fluke 45 on RS-232.

Safety, the one rule: **any exception, Ctrl-C or kill turns the supply's output off.**
A step that means to leave the board powered says so with `supply.keep_on()` before it
returns; the supply's own current limit is then the guard until the next step.

Things to know about the E3646A (lab-instrument-control/hp/hp.md):
- One OUTPut switch serves both outputs. The output not used here is set to 0 V and
  20 mA, so switching on can't put anything on whatever is wired to it.
- One of the bench's two E3646As has a faulty output 1, so the 12 V goes on output 2 by
  default (`supply_output` in bench.json).
- Its current readback is good to 0.15 % + 10 mA on output 2: an offset of several mA, so
  every current here is read against a zero taken at 0 V with the board connected (the
  board draws nothing at 0 V).
"""

import contextlib
import glob
import json
import os
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = Path(os.environ.get("OWL_LAB", "~/mudd/lab-instrument-control")).expanduser()

DEFAULTS = {
    # The supply: None finds the E3646A among the RS-232 adapters (scpi_link's identify,
    # which only asks *IDN?). Give the /dev/serial/by-id/... path to skip the search.
    "supply_serial": None,
    "supply_output": 2,
    # The scope: an IP address, or "usb" for USBTMC.
    "scope": "192.168.8.203",
    "scope_probe": 10,          # the attenuation of the probes on the rails (x10)
    # The generator: "sdg:<ip>", "33220a:<ip>", "33120a:gpib:<addr>", "33120a:serial:<port>", or None.
    "gen": "sdg:192.168.8.246",
    "gen_channel": 1,
    # The Fluke 45: a /dev/serial/by-id/... path, or None (not used).
    "dmm_serial": None,
    # The board's console: None finds the USB CDC port (VID 0x1209); or a port, e.g. the
    # Debug Probe's UART on J5.
    "board_port": None,
    "results": str(HERE / "results"),
}


def load_config(path=None, **overrides):
    """bench.json (next to this file) over the defaults, then keyword overrides (from the
    command line) over both. None-valued overrides are ignored."""
    cfg = dict(DEFAULTS)
    p = Path(path) if path else HERE / "bench.json"
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    return cfg


def _lab(folder):
    """Make one of lab-instrument-control's driver folders importable."""
    d = LAB / folder
    if not d.is_dir():
        raise IOError(f"lab-instrument-control not found at {LAB} (set $OWL_LAB)")
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    if str(LAB) not in sys.path:
        sys.path.insert(0, str(LAB))


class AbortStep(RuntimeError):
    """A step found something wrong and turned the power off."""


# ---- the supply ------------------------------------------------------------------------
class Supply:
    """The board's 12 V: one output of an E3646A (`ps`, lab-instrument-control's
    AgilentE36xxA), on its 20 V range (1.5 A at most)."""

    def __init__(self, ps, out=2):
        self.ps, self.out = ps, out
        self.other = 1 if out == 2 else 2
        self.idn = ps.idn
        self.i_zero = 0.0
        self._keep_on = False

    def prepare(self, ovp=None):
        """Output off; both outputs at 0 V; ours on the high range with OVP at `ovp`; the
        other at 0 V, 20 mA (one switch serves both)."""
        self.ps.output(False)
        if self.ps.outputs > 1:
            self.ps.set_range("LOW", out=self.other)
            self.ps.set(0.0, 0.02, out=self.other)
        self.ps.set_range("HIGH", out=self.out)
        self.ps.set(0.0, 0.02, out=self.out)
        if ovp is not None:
            self.ps.clear_trips(out=self.out)
            self.ps.set_ovp(ovp, True, out=self.out)

    def set(self, volts, amps):
        return self.ps.set(volts, amps, out=self.out)

    def on(self):
        self._keep_on = False
        return self.ps.output(True)

    def off(self):
        """Output off and 0 V (both outputs)."""
        self.ps.off()

    def is_on(self):
        return self.ps.setting(self.out)["output"]

    def measure(self):
        """(volts, amps) at our output; amps less the zero (see take_zero)."""
        v, i = self.ps.measure(out=self.out)
        return v, i - self.i_zero

    def mode(self):
        return self.ps.mode(out=self.out)

    def take_zero(self, n=3):
        """The current reading at 0 V with the output on (the board draws nothing): the
        readback's offset, which later readings subtract."""
        self.set(0.0, 0.02)
        self.on()
        time.sleep(0.3)
        self.i_zero = 0.0
        reads = [self.ps.measure(out=self.out)[1] for _ in range(n)]
        self.i_zero = sum(reads) / n
        return self.i_zero

    def setting(self):
        return self.ps.setting(self.out)

    def keep_on(self):
        """Leave the output on when this step ends normally."""
        self._keep_on = True

    def close(self, failed):
        try:
            if failed or not self._keep_on:
                self.off()
        finally:
            self.ps.close()


def find_e3646a():
    """The /dev/serial/by-id path of the first E3646A among the RS-232 adapters."""
    _lab(".")
    import scpi_link
    for r in scpi_link.identify_serial_ports(listen=0.5, sweep=False):
        if r.get("idn") and "E3646A" in r["idn"]:
            return r["port"]
    raise IOError("no E3646A answered on any RS-232 adapter (is it set to RS-232, 9600 8N? "
                  "lab-instrument-control/hp/hp.md)")


def open_supply(cfg):
    _lab("hp")
    from agilent_E36xxA import AgilentE36xxA
    port = cfg["supply_serial"] or find_e3646a()
    return Supply(AgilentE36xxA(serial=port), out=int(cfg["supply_output"]))


# ---- the scope -------------------------------------------------------------------------
class Scope:
    """The SDS2104X Plus: DC levels and ripple from captured waveforms (numpy), so the
    simulated scope feeds the same code."""

    MDEPTH = "10k"     # points per capture: waveform() fetches the whole record, and at
                       # 10M a capture would be megabytes; 10k covers every view here

    def __init__(self, sc, probe=10):
        self.sc, self.probe = sc, probe
        self.idn = sc.link.idn
        self._old_mdepth = None
        try:
            self._old_mdepth = sc.q(":ACQuire:MDEPth?")
            sc.acquire(mdepth=self.MDEPTH)
        except Exception as e:                      # noqa: BLE001 - slower, not wrong
            print(f"  (scope: memory depth left as it was: {e})")

    def setup(self, ch, scale, offset=0.0, coupling="DC", bwlimit="20M"):
        return self.sc.channel(ch, on=True, scale=scale, offset=offset, coupling=coupling,
                               impedance="1M", probe=self.probe, bwlimit=bwlimit)

    def timebase(self, scale, delay=0.0):
        return self.sc.timebase(scale=scale, delay=delay)

    def capture(self, chans, trigger=None, timeout=10.0):
        """One acquisition: forced (trigger None) or on a trigger dict(source, level, slope).
        Returns {ch: (t, v)}."""
        if trigger is None:
            self.sc.acquire_now(timeout)
        else:
            self.sc.trigger(source=trigger["source"], level=trigger["level"],
                            slope=trigger.get("slope", "rising"), mode="normal")
            self.sc.single(timeout)
        out = {}
        for ch in chans:
            t, v, _ = self.sc.waveform(ch)
            out[ch] = (t, v)
        return out

    def arm(self, trigger):
        self.sc.trigger(source=trigger["source"], level=trigger["level"],
                        slope=trigger.get("slope", "rising"), mode="normal")
        self.sc.arm()

    def wait(self, chans, timeout=10.0):
        self.sc.wait_stop(timeout)
        return {ch: self.sc.waveform(ch)[:2] for ch in chans}

    def freq(self, ch):
        return self.sc.pava("FREQ", ch)

    def pkpk(self, ch):
        return self.sc.pava("PKPK", ch)

    def screenshot(self, path):
        self.sc.screenshot(str(path))

    def run(self):
        self.sc.run()

    def close(self):
        try:
            if self._old_mdepth and self._old_mdepth != self.MDEPTH:
                self.sc.acquire(mdepth=self._old_mdepth)     # a shared scope: put it back
        finally:
            self.sc.close()


def open_scope(cfg):
    _lab("siglent")
    from siglent_SDS2104X import SDS2104X, USB_PRODUCT, USB_VENDOR
    if cfg["scope"] == "usb":
        from scpi_link import usbtmc_node
        sc = SDS2104X(usb=usbtmc_node(USB_VENDOR, USB_PRODUCT))
    else:
        sc = SDS2104X(cfg["scope"])
    return Scope(sc, probe=cfg["scope_probe"])


# ---- the generator ---------------------------------------------------------------------
class Gen:
    """A sine source into a high-impedance load (amplitudes are open-circuit volts)."""

    def __init__(self, kind, g, ch=1):
        self.kind, self.g, self.ch = kind, g, ch
        self.idn = getattr(g, "idn", kind)

    def sine(self, freq, vpp):
        if self.kind == "sdg":
            self.g.output(self.ch, load="HZ")
            self.g.sine(self.ch, freq, vpp)
        elif self.kind == "33220a":
            self.g.output(load="INF")
            self.g.sine(freq, vpp)
        else:                                      # 33120a: amplitudes for its load setting
            self.g.output(load="INF")
            self.g.sine(freq, vpp)

    def on(self):
        if self.kind == "sdg":
            self.g.output(self.ch, True)
        elif self.kind == "33220a":
            self.g.output(True)
        # the 33120A has no output switch: it is live while set

    def off(self):
        if self.kind == "sdg":
            self.g.output(self.ch, False)
        elif self.kind == "33220a":
            self.g.output(False)
        else:
            self.g.off()                           # 0 V DC

    def close(self):
        try:
            self.off()
        finally:
            self.g.close()


def open_gen(cfg):
    spec = cfg["gen"]
    if not spec:
        return None
    kind, _, addr = spec.partition(":")
    if kind == "sdg":
        _lab("siglent")
        from siglent_SDG1032X import SDG1032X
        return Gen("sdg", SDG1032X(addr, vlimit=5.0), int(cfg["gen_channel"]))
    _lab("hp")
    if kind == "33220a":
        from agilent_33220A import Agilent33220A
        return Gen("33220a", Agilent33220A(addr))
    if kind == "33120a":
        from hp_33120A import HP33120A
        how, _, where = addr.partition(":")
        g = HP33120A(int(where)) if how == "gpib" else HP33120A(serial=where)
        return Gen("33120a", g)
    raise ValueError(f"unknown generator {spec!r}")


# ---- the multimeter --------------------------------------------------------------------
class DMM:
    def __init__(self, m):
        self.m = m
        self.idn = "Fluke 45"

    def volts(self):
        self.m.function("VDC")
        return self.m.read(settle=1)

    def ohms(self):
        self.m.function("OHMS")
        return self.m.read(settle=2)

    def close(self):
        self.m.close()


def open_dmm(cfg):
    if not cfg["dmm_serial"]:
        return None
    _lab("fluke")
    from fluke_45 import Fluke45
    return DMM(Fluke45(cfg["dmm_serial"]))


# ---- the whole bench -------------------------------------------------------------------
class Bench:
    def __init__(self):
        self.supply = self.scope = self.gen = self.dmm = None
        self.sim = None
        self.failed = False

    def close(self):
        for name in ("gen", "scope", "dmm"):
            inst = getattr(self, name)
            if inst is not None:
                with contextlib.suppress(Exception):
                    inst.close()
        if self.supply is not None:
            self.supply.close(self.failed)


def _raise_on_term(signum, frame):
    raise KeyboardInterrupt(f"signal {signum}")


@contextlib.contextmanager
def open_bench(cfg, need=("supply",), want=("scope", "gen", "dmm"), sim=None):
    """The instruments a step needs (an error if one can't be opened) and the ones it
    would like (None if absent). With `sim` (a sim.SimBoard), simulated instruments.
    On any exception the supply's output goes off."""
    signal.signal(signal.SIGTERM, _raise_on_term)
    b = Bench()
    openers = {"supply": open_supply, "scope": open_scope, "gen": open_gen, "dmm": open_dmm}
    if sim is not None:
        import sim as simmod
        openers = simmod.openers(sim)
        b.sim = sim
    try:
        for name in need:
            setattr(b, name, openers[name](cfg))
        for name in want:
            if name in need:
                continue
            try:
                setattr(b, name, openers[name](cfg))
            except Exception as e:                  # noqa: BLE001 - optional instrument
                print(f"  ({name} not available: {e})")
        yield b
    except BaseException:
        b.failed = True
        raise
    finally:
        b.close()


def usb_devices():
    """{'vid:pid': description} of what is on USB now (from sysfs, no lsusb needed)."""
    out = {}
    for d in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        base = os.path.dirname(d)
        try:
            vid = open(d).read().strip()
            pid = open(os.path.join(base, "idProduct")).read().strip()
            prod = ""
            p = os.path.join(base, "product")
            if os.path.exists(p):
                prod = open(p).read().strip()
            out[f"{vid}:{pid}"] = prod
        except OSError:
            pass
    return out
