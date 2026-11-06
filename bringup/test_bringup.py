"""The bring-up steps against the simulated bench (sim.py): `pytest bringup/`.

What they show: a good board passes every step; each simulated fault stops the ramp where
it should, with the supply's output off afterwards; the console steps work against the
bring-up image's own command code (firmware/test/bringup_sim; skipped if not built).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench                                    # noqa: E402
import expect as E                              # noqa: E402
import owlboard                                 # noqa: E402
import sim                                      # noqa: E402
import steps                                    # noqa: E402
from bench import AbortStep                     # noqa: E402

HAVE_SIM_BIN = owlboard.SIM_BIN.exists()
needs_sim_bin = pytest.mark.skipif(not HAVE_SIM_BIN, reason="make -C firmware/test bringup_sim")


def make_ctx(tmp_path, **board):
    cfg = bench.load_config(None)
    cfg["results"] = str(tmp_path)
    cfg["dmm_serial"] = "sim"
    sb = sim.SimBoard(state_path=tmp_path / "state.json", **board)
    sb.flashed = "bringup"
    return steps.Ctx(cfg, sim=sb, quiet=True)


def supply_on(tmp_path):
    return json.loads((tmp_path / "state.json").read_text())["out_on"]


def test_ramp_good_board(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_ramp(ctx, hold=1)
    assert [r["set_V"] for r in rec["steps"]] == [v for v, *_ in E.RAMP]
    assert all(r["mode"] == "CV" for r in rec["steps"])
    top = rec["steps"][-1]
    assert E.IDLE_12V_A[0] <= top["A"] <= E.IDLE_12V_A[1]
    assert abs(top["rails"]["+4.8V"] - 4.8) < 0.1
    assert supply_on(tmp_path)                  # left on for the next step
    assert not ctx.warnings


@pytest.mark.parametrize("fault, where, words", [
    ("short12", 1.0, "current limit"),
    ("short5", 7.0, "current limit"),
    ("ldo_short", 7.0, "current limit"),
    ("fb_open", 7.0, "+4.8V reads"),
])
def test_ramp_faults_stop_it(tmp_path, fault, where, words):
    ctx = make_ctx(tmp_path, faults=[fault])
    with pytest.raises(AbortStep) as e:
        steps.step_ramp(ctx, hold=0)
    assert words in str(e.value)
    assert not supply_on(tmp_path)
    rec = json.loads(sorted(tmp_path.glob("*/*_ramp_sim.json"))[-1].read_text())
    assert rec["aborted"] and rec["steps"][-1]["set_V"] == where


def test_ramp_stops_short_of_the_top(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_ramp(ctx, to=6.0, hold=0)
    assert rec["steps"][-1]["set_V"] == 6.0
    assert rec["steps"][-1]["rails"]["+4.8V"] < 0.5


def test_ramp_with_usb_warns_and_reads_low(tmp_path):
    ctx = make_ctx(tmp_path, usb=True)
    rec = steps.step_ramp(ctx, hold=0)
    assert any("USB" in w for w in ctx.warnings)
    assert rec["steps"][-1]["A"] < E.IDLE_12V_USB_A[1]


def test_rails_and_dmm(tmp_path):
    ctx = make_ctx(tmp_path)
    steps.step_ramp(ctx, hold=0)
    r = steps.step_rails(ctx)
    for rail, v in r["fine"].items():
        tp, nom, lo, hi, _ = E.RAILS[rail]
        assert lo <= v <= hi, rail
    assert r["ripple_4v8"]["pkpk_V"] < E.RIPPLE_4V8_MAX
    d = steps.step_rails(ctx, dmm_rail="+3V3")
    assert d["dmm"]["ok"]


def test_rails_refuses_when_off(tmp_path):
    ctx = make_ctx(tmp_path)
    with pytest.raises(AbortStep):
        steps.step_rails(ctx)


def test_capture(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_capture(ctx)
    assert rec["peaks"]["+4.8V"] < 5.0
    assert list(tmp_path.glob("*/*_powerup_sim.png"))
    assert supply_on(tmp_path)


@pytest.mark.parametrize("token", ["owl", "cat", "bat"])
def test_tank_finds_the_resonance(tmp_path, token):
    ctx = make_ctx(tmp_path)
    rec = steps.step_tank(ctx, token)
    f_true = E.TOKEN_F[token] * (1 + ctx.sim.f_token_err[token])
    assert abs(rec["peak_Hz"] / f_true - 1) < 0.025
    assert 10 < rec["q"] < 40


def test_a_crash_turns_the_supply_off(tmp_path):
    ctx = make_ctx(tmp_path)
    steps.step_ramp(ctx, hold=0)
    assert supply_on(tmp_path)
    with pytest.raises(ZeroDivisionError):
        with bench.open_bench(ctx.cfg, need=("supply",), want=(), sim=ctx.sim) as b:
            b.supply.keep_on()
            1 / 0
    assert not supply_on(tmp_path)


def test_led_names_match_the_map():
    names = steps.led_names()
    assert len(names) == 49
    assert len(steps.led_names((0,))) == 31
    assert ("STAR3", 0, 6) in names


# ---- the console steps, against the bring-up image's code built for the PC --------------
@needs_sim_bin
def test_logic(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_logic(ctx, tree=True)
    assert rec["id"]["image"] == "bringup"
    assert not ctx.warnings, ctx.warnings


@needs_sim_bin
def test_logic_missing_tree_driver(tmp_path, monkeypatch):
    monkeypatch.setenv("OWL_SIM_MISSING", "0x32")
    ctx = make_ctx(tmp_path)
    steps.step_logic(ctx, tree=True)
    assert any("0x32" in w for w in ctx.warnings)


@needs_sim_bin
def test_leds_find_an_open_led(tmp_path):
    ctx = make_ctx(tmp_path, faults=["led_open:STAR3"])
    steps.step_ramp(ctx, hold=0)
    rec = steps.step_leds(ctx)
    assert len(rec["leds"]) == 31
    flagged = [w for w in ctx.warnings if "added only" in w]
    assert len(flagged) == 1 and "STAR3" in flagged[0]


@needs_sim_bin
def test_coils(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_coils(ctx, which=("pend1", "pend2", "pend3", "lev"))
    assert all(c["ok"] for c in rec["coils"]), rec


@needs_sim_bin
def test_perch_sweep_sees_the_owl(tmp_path):
    ctx = make_ctx(tmp_path)
    rec = steps.step_perch(ctx, which=(1,), token="owl")
    pts = rec["sweeps"][1]
    assert len(pts) == 48                       # the image's default sweep
    f = max(pts, key=lambda p: p[1])[0]
    lo, hi = E.PERCH_SWEEP_PEAK["owl"]
    assert lo * 0.9 <= f <= hi * 1.15


@needs_sim_bin
def test_osc_and_tone(tmp_path):
    ctx = make_ctx(tmp_path)
    steps.step_osc(ctx)
    assert not ctx.warnings
    r = steps.step_tone(ctx)
    assert r["ok"]
