#!/usr/bin/env python3
"""Hold the hovering bat at a series of set-points and record what each one costs.

    python3 bringup/lev_setpoint.py "what this run is"

The bat must already be hovering (`lev on`, caught).  The script:
  1. lets the zero-power walk find the bat's natural float, with its floor at 7.0 mm
     (g0 8.0, zp_range 1.0), and records it;
  2. fixes the set-point (zp_range 0) and steps it through STEPS, DWELL_S at each,
     recording the gap, its spread (the bat's bobbing), the coil current (mean, rms,
     peak), the coil's temperatures (model, thermometer) and the supply;
  3. compares the loop's gains for mass_g 3.6 (the default that flew) and 4.7 (the bat
     as weighed, with its cap) at the natural float;
  4. puts back the loop's own settings (g0, zp_range, mass_g as found).

Guards: the firmware's thermal cutoff stays on.  If the model's board node passes
BOARD_MAX_C, the bat goes back to its natural float until the node cools to
BOARD_RESUME_C.  Going up stops once the mean current passes I_UP_MAX_A (sensed).
If the bat is lost, the loop's settings go back to as found, the script prints
"LOST" and waits up to WAIT_LIFT_S for someone to lift the bat again, then carries on
with the next step.  Never sends `lev off`.

Lines starting with STEP, LOST, WAITING, CAUGHT, COOL, SUMMARY and DONE are for a
monitor; everything is saved to bringup/results/<date>/<time>_lev_setpoint.json.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

WHAT = sys.argv[1] if len(sys.argv) > 1 else ''
STEPS = [7.5, 7.75, 8.0, 8.25, 8.5, 8.75, 9.0, 9.5, 7.5, 7.25, 7.0, 7.5]
DWELL_S = 25.0
SETTLE_S = 4.0                  # excluded from a step's statistics
NATURAL_S = 40.0
BOARD_MAX_C = 40.0
BOARD_RESUME_C = 33.0
I_UP_MAX_A = 0.7
WAIT_LIFT_S = 2400.0

out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_lev_setpoint.json')
rec = {'what': WHAT, 'steps': STEPS, 'dwell_s': DWELL_S, 'samples': [], 'phases': [], 'events': []}
t0 = time.time()
LEV_KEYS = ('state', 'gap_mm', 'gref_mm', 'gzp_mm', 'bbat_mT', 'i_cmd_A', 'i_est_A', 'mean_I_mA',
            'rms_I_mA', 'peak_I_A', 'catches', 'losses', 'trips', 'reason')


def say(*a):
    print(*a, flush=True)


def ev(e):
    rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
    say('EVENT', json.dumps(e))


class Run:
    def __init__(self, b):
        self.b = b
        self.last_status = 0.0
        self.status = {}

    def cmd(self, line):
        return self.b.cmd(line, on_event=ev)

    def tune(self, name, v):
        return self.cmd(f'lev tune {name} {v}')

    def sample(self, phase):
        lv = self.cmd('lev status')['lev']
        row = {k: lv.get(k) for k in LEV_KEYS}
        row.update(t=round(time.time() - t0, 3), phase=phase)
        if time.time() - self.last_status > 1.0:
            s = self.cmd('status')['status']
            th = s.get('lev_thermo') or {}
            self.status = dict(v12=s['rails']['v12'], faults=s['faults'], i_lev=s['coils']['i_meas_A'][3],
                               temp_lev=s['temps_C']['lev'], board_C=th.get('board_C'),
                               copper_C=th.get('copper_C'), t_meas_C=th.get('t_meas_C'),
                               thermo_cal=th.get('calibrated'), imu_g=s['imu']['g'],
                               taps=s['imu']['taps'], double_taps=s['imu']['double_taps'])
            row.update(self.status)
            self.last_status = time.time()
        rec['samples'].append(row)
        return row

    def run_for(self, seconds, phase):
        """Sample for `seconds`; returns (rows, lost)."""
        rows = []
        end = time.time() + seconds
        off_hold = None
        while time.time() < end:
            r = self.sample(phase)
            rows.append(r)
            if r['state'] != 'hold':
                off_hold = off_hold or time.time()
                if time.time() - off_hold > 1.0:
                    return rows, True
            else:
                off_hold = None
            time.sleep(0.03)
        return rows, False

    def board_C(self):
        return self.status.get('board_C') or 0.0


def stats(rows, phase, setpoint, settle=SETTLE_S):
    if not rows:
        return {}
    t_start = rows[0]['t'] + settle
    h = [r for r in rows if r['t'] >= t_start and r['state'] == 'hold']
    if len(h) < 5:
        return dict(phase=phase, setpoint=setpoint, n=len(h))
    g = [r['gap_mm'] for r in h]
    i = [r['i_est_A'] for r in h]
    temps = [r for r in h if r.get('board_C') is not None]
    dt = (h[-1]['t'] - h[0]['t']) / max(1, len(h) - 1)
    taps = [(r['taps'], r['double_taps']) for r in rows if r.get('taps') is not None]
    bumped = len(taps) > 1 and taps[0] != taps[-1]      # the IMU counted a tap: the step is void
    return dict(phase=phase, setpoint=setpoint, bumped=bumped, n=len(h), sample_dt_s=round(dt, 3),
                gap_mean=round(st.mean(g), 3), gap_sd=round(st.pstdev(g), 3),
                gap_p2p=round(max(g) - min(g), 3),
                i_est_mean_A=round(st.mean(i), 3), i_est_sd_A=round(st.pstdev(i), 3),
                mean_I_mA=round(st.mean(r['mean_I_mA'] for r in h), 1),
                rms_I_mA=round(st.mean(r['rms_I_mA'] for r in h), 1),
                peak_I_A=round(max(r['peak_I_A'] for r in h), 3),
                gzp_mm=round(h[-1]['gzp_mm'], 3) if h[-1].get('gzp_mm') is not None else None,
                board_C_end=temps[-1]['board_C'] if temps else None,
                copper_C_end=temps[-1]['copper_C'] if temps else None,
                t_meas_C_end=temps[-1]['t_meas_C'] if temps else None,
                v12=temps[-1]['v12'] if temps else None)


def main():
    with OwlBoard(timeout=8) as b:
        R = Run(b)
        p = R.cmd('lev status')['lev']['params']
        found = {k: p[k] for k in ('g0_mm', 'zp_range_mm', 'mass_g')}
        rec['found'] = found
        say('found', json.dumps(found))

        def restore():
            for k in ('zp_range_mm', 'g0_mm', 'mass_g'):
                R.tune(k, found[k])

        def walk_g0(target, step=0.1, dt=0.3):
            """Move g0 (and with it the set-point) in small steps: a jump of a
            millimetre or more loses the bat."""
            g = R.cmd('lev status')['lev']['params']['g0_mm']
            while abs(target - g) > 1e-6:
                g = g + max(-step, min(step, target - g))
                R.tune('g0_mm', round(g, 3))
                time.sleep(dt)

        def pin_here():
            """g0 to where the walk has the set-point (no jump), before any zp_range
            change: zp_range clamps the set-point round the current g0 at once."""
            R.tune('g0_mm', round(R.cmd('lev status')['lev']['gzp_mm'], 3))

        def wait_for_bat(why):
            restore()
            say(f'LOST ({why}): settings back to as found; WAITING for the bat to be lifted')
            end = time.time() + WAIT_LIFT_S
            while time.time() < end:
                r = R.sample('waiting')
                if r['state'] == 'hold':
                    say('CAUGHT: hovering again; 15 s on the zero-power walk before going on')
                    R.run_for(15, 'recatch')
                    return True
                time.sleep(0.2)
            say('DONE: nobody lifted the bat; stopping (loop left on, waiting)')
            return False

        def natural():
            pin_here()
            R.tune('zp_range_mm', 1.0)
            walk_g0(8.0)
            rows, lost = R.run_for(NATURAL_S, 'natural')
            s = stats(rows, 'natural', None, settle=15.0)
            s['gzp_mm'] = rows[-1].get('gzp_mm') if rows else None
            return s, lost

        def cool():
            say(f'COOL: board node {R.board_C():.1f} C > {BOARD_MAX_C}: back to the natural float')
            pin_here()
            R.tune('zp_range_mm', 1.0)
            walk_g0(8.0)
            while R.board_C() > BOARD_RESUME_C:
                rows, lost = R.run_for(5, 'cool')
                if lost:
                    return False
            return True

        # wait for a hover to start from
        r = R.sample('start')
        if r['state'] != 'hold' and not wait_for_bat('not hovering at the start'):
            return
        # 1. the natural float
        s, lost = natural()
        rec['phases'].append(s)
        say('SUMMARY', json.dumps(s))
        if lost and not wait_for_bat('during the natural float'):
            return
        # 2. fixed set-points
        pin_here()
        R.tune('zp_range_mm', 0.0)
        going_up_ok = True
        for k, sp in enumerate(STEPS):
            prev = STEPS[k - 1] if k else 7.5
            if sp > prev and sp > 7.5 and not going_up_ok:
                say(f'STEP {sp}: skipped (the current going up passed {I_UP_MAX_A} A)')
                continue
            if R.board_C() > BOARD_MAX_C:
                if not cool() and not wait_for_bat('while cooling'):
                    return
                pin_here()
                R.tune('zp_range_mm', 0.0)
            say(f'STEP {sp} mm')
            walk_g0(sp)
            rows, lost = R.run_for(DWELL_S, f'sp {sp}')
            s = stats(rows, f'sp {sp}', sp)
            rec['phases'].append(s)
            say('SUMMARY', json.dumps(s))
            if lost:
                if not wait_for_bat(f'at set-point {sp}'):
                    return
                pin_here()
                R.tune('zp_range_mm', 0.0)
                continue
            if sp > 7.5 and abs(s.get('mean_I_mA', 0)) > I_UP_MAX_A * 1000:
                going_up_ok = False
        # 3. the gains: mass_g as found, then 4.7 (the bat as weighed), at the natural float
        for m in (found['mass_g'], 4.7):
            R.tune('mass_g', m)
            s, lost = natural()
            s['phase'] = f'natural, mass_g {m}'
            rec['phases'].append(s)
            say('SUMMARY', json.dumps(s))
            if lost:
                if not wait_for_bat(f'natural float with mass_g {m}'):
                    return
        pin_here()
        R.tune('zp_range_mm', 1.0)
        walk_g0(8.0)
        R.tune('mass_g', found['mass_g'])
        say('DONE: left on the zero-power walk (g0 8.0, zp_range 1.0); the bat is still hovering')


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    say('record', fn)
