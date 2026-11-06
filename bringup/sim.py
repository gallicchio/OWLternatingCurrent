"""Simulated instruments and a simulated board, for debugging the bring-up steps without
hardware (`python3 run.py --sim ...`, and test_bringup.py).

The fakes imitate lab-instrument-control's drivers method by method (the parts bench.py's
adapters call), so the adapters themselves run in the simulation too. Behind them is
SimBoard: an electrical model of the base board's 12 V input and rails, from the same
numbers as expect.py, with faults that can be switched on:

    short12      a short on +12V after Q1 (D2 or C1 in backwards, a solder bridge): 0.5 ohm
    short5       a short on the 4.8 V rail: the buck starts into it
    ldo_short    a short on +3V3: the XC6206 current-limits at ~0.4 A
    fb_open      the buck's feedback divider open: "4.8 V" climbs toward 12 V
    no_xtal      the 12 MHz crystal dead: no USB (the RP2354A's ROM never enumerates)
    led_open:N   LED N (a led_map.h name) open: lighting it adds no current

The board's console is the bring-up image's own command code compiled for the PC
(firmware/test/bringup_sim, see owlboard.py); SimBoard only follows what it is asked
(LEDs lit) so the simulated supply's current responds.
"""

import json
import math
import random
from pathlib import Path

import numpy as np

import expect as E

RNG = random.Random(717)


class SimBoard:
    def __init__(self, faults=(), usb=False, token=None, seed=717, state_path=None):
        """state_path: a JSON file that keeps the simulated supply's settings from one
        run.py call to the next (as the real supply keeps them)."""
        self.state_path = Path(state_path) if state_path else None
        self.faults = set(faults)
        self.usb = usb                    # USB-C plugged into the PC
        self.token = token                # what lies on the pickup loop: 'owl', 'cat', 'bat', None
        self.rng = random.Random(seed)
        self.leds = {}                    # name -> duty (from the console commands)
        self.flashed = None               # None (blank), 'bringup', 'main'
        # the as-built tolerances of this simulated board
        self.v48 = 4.80 * (1 + self.rng.uniform(-0.01, 0.01))
        self.v33 = 3.30 * (1 + self.rng.uniform(-0.01, 0.01))
        self.f_token_err = {k: self.rng.uniform(-0.05, 0.05) for k in E.TOKEN_F}

    # -- the 12 V input ------------------------------------------------------------------
    def fault(self, name):
        return name in self.faults

    def buck_on(self, vin):
        return vin >= E.EN_ON_V

    def load_48_w(self, vin):
        """Power the 4.8 V rail delivers (W), or None for a short."""
        if not self.buck_on(vin):
            return 0.0
        if self.fault("short5"):
            return None
        p = 2 * 0.001 * 4.8                    # the UCC27524s' quiescent
        if not self.usb:                       # the logic runs from 4.8 V through D3
            i33 = 0.40 if self.fault("ldo_short") else 0.035
            p += i33 * 4.45
        for name, duty in self.leds.items():
            if f"led_open:{name.upper()}" in self.faults:
                continue
            p += 0.022 * duty * 4.8
        return p

    def input_current(self, vin):
        """Amps drawn at J1 at `vin` volts, steady state."""
        if vin <= 0:
            return 0.0
        if self.fault("short12"):
            return vin / 0.5
        i = max(vin - 0.6, 0.0) / 61e3          # the two 122 k dividers (Q1's diode, then Q1)
        p = self.load_48_w(vin)
        if p is None:
            return 5.0                          # the buck's current limit (3.5 A+) into a short
        if self.buck_on(vin):
            if self.fault("fb_open"):
                p += 0.05
            eff = 0.75 if p < 0.5 else 0.88
            i += p / eff / vin + 0.0005
        return i

    # -- the rails, at a steady input --------------------------------------------------
    def rails(self, vin):
        on = self.buck_on(vin)
        v48 = 0.0
        if on:
            v48 = min(vin * 0.96, 11.5) if self.fault("fb_open") else self.v48
            if self.fault("short5"):
                v48 = 0.05
        vbus = 5.0 if self.usb else 0.0
        vsys = max(v48 - 0.35, vbus - 0.30, 0.0)
        v33 = min(max(vsys - 0.25, 0.0), self.v33)
        if self.fault("ldo_short"):
            v33 = 0.02
        v11 = 1.10 if v33 > 2.9 else 0.0
        return {"+12V": max(vin - 0.01, 0.0), "+4.8V": v48, "VSYS": vsys, "+3V3": v33,
                "+1V1": v11, "VBUS": vbus}

    # -- the console's effects ---------------------------------------------------------
    def observe(self, line, reply):
        """Follow a console command (from owlboard.OwlBoard in sim mode)."""
        w = line.split()
        if not w or not isinstance(reply, dict) or not reply.get("ok"):
            return
        if w[0] == "led":
            if w[1:] == ["off"]:
                self.leds.clear()
            elif len(w) == 3:
                duty = float(w[2])
                key = w[1].upper()
                if duty <= 0:
                    self.leds.pop(key, None)
                else:
                    self.leds[key] = duty

    # -- the tanks, seen through a pickup loop -----------------------------------------
    def tank_response(self, f, vpp_drive):
        """Volts peak-to-peak across the token's tank when the generator drives the loop
        at f: a resonance of Q 25 at the token's (slightly off) frequency, clamped by its
        LEDs at ~3.6 Vpp."""
        if self.token is None:
            return 0.002 * vpp_drive
        f0 = E.TOKEN_F[self.token] * (1 + self.f_token_err[self.token])
        q = 25.0
        h = 0.08 * q / math.sqrt(1 + (q * (f / f0 - f0 / f)) ** 2)
        return min(h * vpp_drive, 3.6) * (1 + self.rng.gauss(0, 0.01))


# ---- the fakes ---------------------------------------------------------------------------
class FakeE3646A:
    """Imitates lab-instrument-control's AgilentE36xxA for an E3646A, driving SimBoard
    on `board_out`."""
    outputs = 2
    ranges = ("P8V", "P20V")
    has_ocp = False

    def __init__(self, board, board_out=2):
        self.board, self.board_out = board, board_out
        self.idn = "Agilent Technologies,E3646A,0,1.7-5.0-1.0 (simulated)"
        self.model = "E3646A"
        self.out_on = False
        self.s = {n: {"volts": 0.0, "amps": 0.02, "range": "P8V", "ovp": 22.0, "ovp_on": True,
                      "ovp_tripped": False} for n in (1, 2)}
        self.offset_a = 0.0063              # the readback's offset (output 2: up to 10 mA)
        self.history = []                   # (volts, limit, measured V, I, mode) of each measure
        p = board.state_path
        if p is not None and p.exists():
            st = json.loads(p.read_text())
            self.out_on = st["out_on"]
            self.s = {int(k): v for k, v in st["s"].items()}

    def _save(self):
        p = self.board.state_path
        if p is not None:
            p.write_text(json.dumps({"out_on": self.out_on, "s": self.s}))

    def _max(self, n):
        return 8.0 if self.s[n]["range"] == "P8V" else 20.0

    def output(self, on):
        self.out_on = bool(on)
        self._save()
        return self.out_on

    def set_range(self, rng, out=1):
        name = {"LOW": "P8V", "HIGH": "P20V"}.get(rng.upper(), rng.upper())
        self.s[out]["range"] = name
        self._save()
        return self.setting(out)

    def set(self, volts, amps, out=1):
        if volts > self._max(out) + 1e-9:
            raise ValueError(f"E3646A (sim): {volts} V is outside range {self.s[out]['range']}")
        self.s[out].update(volts=volts, amps=amps)
        self._save()
        return self.setting(out)

    def set_ovp(self, volts=None, on=True, out=1):
        if volts is not None:
            self.s[out]["ovp"] = volts
        self.s[out]["ovp_on"] = on
        self._save()
        return self.setting(out)

    def clear_trips(self, out=1):
        self.s[out]["ovp_tripped"] = False
        self._save()
        return self.setting(out)

    def off(self):
        self.out_on = False
        for n in (1, 2):
            self.s[n]["volts"] = 0.0
        self._save()

    def setting(self, out=1):
        return dict(self.s[out], output=self.out_on)

    def _operate(self, out):
        """(volts at the terminals, amps, mode) at steady state."""
        s = self.s[out]
        if not self.out_on:
            return 0.0, 0.0, "OFF"
        if s["ovp_tripped"]:
            return 0.0, 0.0, "CV"
        if out != self.board_out:
            return s["volts"], 0.0, "CV"
        v, lim = s["volts"], s["amps"]
        if s["ovp_on"] and v > s["ovp"]:
            s["ovp_tripped"] = True
            return 0.0, 0.0, "CV"
        i = self.board.input_current(v)
        if i <= lim:
            return v, i, "CV"
        lo, hi = 0.0, v                       # constant current: where the board draws lim
        for _ in range(40):
            mid = (lo + hi) / 2
            if self.board.input_current(mid) > lim:
                hi = mid
            else:
                lo = mid
        return lo, lim, "CC"

    def measure(self, out=1):
        v, i, mode = self._operate(out)
        noise = self.board.rng.gauss(0, 0.0004)
        res = (v + self.board.rng.gauss(0, 0.002), i + self.offset_a + noise)
        self.history.append((self.s[out]["volts"], self.s[out]["amps"], res[0], res[1], mode))
        return res

    def mode(self, out=1):
        return self._operate(out)[2]

    def close(self):
        pass


class _Link:
    def __init__(self, idn):
        self.idn = idn


class FakeSDS2104X:
    """Imitates the SDS2104X driver: channel 1-4 probe the rails per expect.SCOPE_RAILS,
    except while a token sweep is on (then channel 1 is across the token's tank)."""

    def __init__(self, board, supply):
        self.board, self.supply = board, supply
        self.link = _Link("Siglent Technologies,SDS2104X Plus,SIM,5.0.1.3.9R12 (simulated)")
        self.ch = {n: {"scale": 1.0, "offset": 0.0, "coupling": "DC", "probe": 10, "bwlimit": "20M",
                       "on": True} for n in (1, 2, 3, 4)}
        self.tdiv = 1e-3
        self.gen = None                         # set by openers(): the token sweep reads it
        self.armed = None

    mdepth = "10M"

    def q(self, cmd):
        if cmd == ":ACQuire:MDEPth?":
            return self.mdepth
        raise IOError(f"(sim) no answer to {cmd!r}")

    def acquire(self, mdepth=None, **kw):
        if mdepth is not None:
            self.mdepth = mdepth
        return {"mdepth": self.mdepth}

    def channel(self, ch, on=None, scale=None, offset=None, coupling=None, impedance=None,
                probe=None, bwlimit=None):
        c = self.ch[ch]
        for k, v in (("on", on), ("scale", scale), ("offset", offset), ("coupling", coupling),
                     ("probe", probe), ("bwlimit", bwlimit)):
            if v is not None:
                c[k] = v
        return dict(c)

    def timebase(self, scale=None, delay=None):
        if scale is not None:
            self.tdiv = scale
        return self.tdiv, 0.0

    def acquire_now(self, timeout=10.0):
        self.armed = None

    def trigger(self, source=None, level=None, slope=None, mode=None, coupling=None):
        self.trig = dict(source=source, level=level, slope=slope)
        return {}

    def arm(self):
        self.armed = list(self.supply.history)

    def single(self, timeout=10.0):
        self.arm()
        return self.wait_stop(timeout)

    def wait_stop(self, timeout=10.0):
        return "Stop"

    def run(self):
        pass

    def _vin(self):
        v, i, mode = self.supply._operate(self.supply.board_out)
        return v

    def _dc(self, ch):
        if self.gen is not None and self.gen.on_ and ch == 1:
            return None
        rail = E.SCOPE_RAILS.get(ch)
        return self.board.rails(self._vin()).get(rail, 0.0) if rail else 0.0

    def waveform(self, ch, points=None, start=0, preamble=True):
        n = 2000
        t = np.linspace(-5 * self.tdiv, 5 * self.tdiv, n)
        c = self.ch[ch]
        if self.gen is not None and self.gen.on_ and ch == 1:
            amp = self.board.tank_response(self.gen.f, self.gen.vpp) / 2
            v = amp * np.sin(2 * np.pi * self.gen.f * t)
        elif self.armed is not None:
            v = self._powerup(ch, t)
        else:
            dc = self._dc(ch)
            v = np.full(n, dc) + np.random.default_rng(ch).normal(0, 0.002, n)
            if E.SCOPE_RAILS.get(ch) == "+4.8V" and dc > 1:
                v += 0.012 * ((t * 400e3) % 1.0 - 0.5)           # the buck's ripple
        if c["coupling"] == "AC":
            v = v - v.mean()
        lo = -4.2 * c["scale"] - c["offset"]                    # the screen clips
        hi = 4.2 * c["scale"] - c["offset"]
        return t, np.clip(v, lo, hi), {"scale": c["scale"]}

    def _powerup(self, ch, t):
        """The rails as the supply jumps from 0 to its set voltage (C1 charging at the
        current limit), trigger at t = 0 on +12V crossing its level."""
        s = self.supply.s[self.supply.board_out]
        vset, lim = s["volts"], s["amps"]
        slope = lim / 470e-6                                     # V/s into C1 at the limit
        vin = np.clip((t + 6.0 / slope) * slope, 0, vset)
        rail = E.SCOPE_RAILS.get(ch)
        out = np.zeros_like(t)
        for k, vi in enumerate(vin):
            out[k] = self.board.rails(vi)[rail]
        return out

    def pava(self, item, ch):
        t, v, _ = self.waveform(ch)
        if item == "PKPK":
            return float(v.max() - v.min())
        if item == "MEAN":
            return float(v.mean())
        if item == "FREQ":
            if self.gen is not None and self.gen.on_ and ch == 1:
                return self.gen.f
            return 400e3 if E.SCOPE_RAILS.get(ch) == "+4.8V" else None
        return None

    def screenshot(self, path):
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n(simulated screenshot)")

    def close(self):
        pass


class FakeSDG:
    def __init__(self):
        self.idn = "Siglent Technologies,SDG1032X,SIM,1.01.01.30R1B2 (simulated)"
        self.f, self.vpp, self.on_ = 1e3, 0.0, False

    def output(self, ch, on=None, load=None):
        if on is not None:
            self.on_ = on
        return {}

    def sine(self, ch, freq, vpp, offset=0.0, phase=0.0):
        self.f, self.vpp = freq, vpp

    def close(self):
        self.on_ = False


class FakeFluke:
    def __init__(self, board, supply):
        self.board, self.supply = board, supply
        self.fn = "VDC"
        self.probe_at = "+4.8V"                 # which rail the (simulated) leads touch

    def function(self, name, auto=True):
        self.fn = name

    def read(self, settle=0):
        if self.fn == "VDC":
            v = self.supply._operate(self.supply.board_out)[0]
            return self.board.rails(v)[self.probe_at]
        return 12.3e3

    def close(self):
        pass


def openers(board):
    """bench.open_bench's openers, simulated."""
    import bench as B
    made = {}

    def supply(cfg):
        made["ps"] = FakeE3646A(board, int(cfg["supply_output"]))
        return B.Supply(made["ps"], out=int(cfg["supply_output"]))

    def _ps():
        if "ps" not in made:
            made["ps"] = FakeE3646A(board, 2)
        return made["ps"]

    def scope(cfg):
        made["sds"] = FakeSDS2104X(board, _ps())
        if "sdg" in made:
            made["sds"].gen = made["sdg"]
        return B.Scope(made["sds"], probe=cfg["scope_probe"])

    def gen(cfg):
        made["sdg"] = FakeSDG()
        if "sds" in made:
            made["sds"].gen = made["sdg"]
        return B.Gen("sdg", made["sdg"], 1)

    def dmm(cfg):
        return B.DMM(FakeFluke(board, _ps()))

    return {"supply": supply, "scope": scope, "gen": gen, "dmm": dmm}
