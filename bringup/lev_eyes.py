#!/usr/bin/env python3
"""Light the bat's eyes a little at a time, and measure what the 80 kHz carrier heats.

    python3 bringup/lev_eyes.py SETPOINT_MM "what this run is"

The bat must already be hovering.  The set-point is fixed at SETPOINT_MM (zp_range 0),
far enough from the natural float that the coil carries 0.3 A or more one way: only
then can the coil's resistance thermometer read (rt.c step 6b), and it reads only while
the carrier is off.  So the eyes go on in bursts:

  baseline: eyes off BASE_S, the thermometer reading all the time;
  for each strength in STRENGTHS: eyes on ON_S, then off OFF_S, the status polled fast
  for the first seconds after the carrier stops (the copper cools in a few seconds,
  so the first readings show what the burst did).

The extra heat of a strength is the copper's rise over the burst against the baseline's
drift.  The ladder stops going up when the thermometer passes STOP_C, or rises more than
STOP_RISE_K over the baseline, or the bat's gap wobbles past STOP_GAP_SD_MM, or the bat
is lost.  A burst during which the IMU counted a tap (a bump to the board) is marked
"bumped": its numbers are void.  At the end: eyes off, the loop's settings back as found.  Never `lev off`.
The firmware's thermal cutoff stays on.  Lines starting with STEP, BURST, STOP, LOST,
SUMMARY and DONE are for a monitor; the record is
bringup/results/<date>/<time>_lev_eyes.json.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

SETPOINT = float(sys.argv[1]) if len(sys.argv) > 1 else 8.5
WHAT = sys.argv[2] if len(sys.argv) > 2 else ''
STRENGTHS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
BASE_S = 60.0
ON_S = 30.0
OFF_S = 20.0
FAST_S = 4.0                # status polled as fast as it answers for this long after a burst
STOP_C = 42.0               # the thermometer (anchored to the IMU, ~5 K below the IR camera)
STOP_RISE_K = 8.0
STOP_GAP_SD_MM = 0.15

out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_lev_eyes.json')
rec = {'what': WHAT, 'setpoint_mm': SETPOINT, 'strengths': STRENGTHS, 'on_s': ON_S, 'off_s': OFF_S,
       'samples': [], 'bursts': [], 'events': []}
t0 = time.time()


def say(*a):
    print(*a, flush=True)


def ev(e):
    rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
    say('EVENT', json.dumps(e))


def main():
    with OwlBoard(timeout=8) as b:
        cmd = lambda line: b.cmd(line, on_event=ev)                          # noqa: E731
        p = cmd('lev status')['lev']['params']
        found = {k: p[k] for k in ('g0_mm', 'zp_range_mm')}
        rec['found'] = found

        def sample(phase, full):
            lv = cmd('lev status')['lev']
            row = dict(t=round(time.time() - t0, 3), phase=phase, state=lv['state'], gap_mm=lv['gap_mm'],
                       i_est_A=lv['i_est_A'], mean_I_mA=lv['mean_I_mA'], rms_I_mA=lv['rms_I_mA'],
                       eyes=lv.get('eyes'), carrier=lv.get('carrier'))
            if full:
                s = cmd('status')['status']
                th = s.get('lev_thermo') or {}
                row.update(imu_g=s['imu']['g'], taps=s['imu']['taps'], double_taps=s['imu']['double_taps'])
                row.update(v12=s['rails']['v12'], faults=s['faults'], t_meas_C=th.get('t_meas_C'),
                           readings=th.get('readings'), r_meas_ohm=th.get('r_meas_ohm'),
                           board_C=th.get('board_C'), copper_C=th.get('copper_C'))
            rec['samples'].append(row)
            return row

        def run(seconds, phase, fast_s=0.0):
            rows, t_end, t_fast, last_full = [], time.time() + seconds, time.time() + fast_s, 0.0
            off_hold = None
            while time.time() < t_end:
                full = time.time() < t_fast or time.time() - last_full > 1.0
                r = sample(phase, full)
                if full:
                    last_full = time.time()
                rows.append(r)
                if r['state'] != 'hold':
                    off_hold = off_hold or time.time()
                    if time.time() - off_hold > 1.0:
                        return rows, True
                else:
                    off_hold = None
                time.sleep(0.03)
            return rows, False

        def therm(rows):
            """(first, last) new thermometer readings in rows: a reading counts when the
            reading counter moved."""
            out_, prev = [], None
            for r in rows:
                n = r.get('readings')
                if n is None:
                    continue
                if prev is not None and n != prev:
                    out_.append((r['t'], r['t_meas_C']))
                prev = n
            return out_

        def bumped(rows):
            """True if the IMU counted a tap (0.19 g) during rows: someone bumped the board,
            and the rows' gap and heat are void (Jason, 2026-11-10)."""
            t = [(r['taps'], r['double_taps']) for r in rows if r.get('taps') is not None]
            return len(t) > 1 and t[0] != t[-1]

        def gap_sd(rows):
            g = [r['gap_mm'] for r in rows if r['state'] == 'hold']
            return st.pstdev(g) if len(g) > 3 else 0.0

        def walk_g0(target, step=0.1, dt=0.3):
            """Move the set-point in small steps: setting g0 jumps the zero-power
            set-point to it, and a jump of a millimetre or more loses the bat."""
            g = cmd('lev status')['lev']['params']['g0_mm']
            while abs(target - g) > 1e-6:
                g = g + max(-step, min(step, target - g))
                cmd(f'lev tune g0_mm {g:.3f}')
                time.sleep(dt)

        def pin_here():
            """Fix the set-point where the zero-power walk has it, without a jump: g0
            first (it also sets the walk's set-point), then zp_range 0.  The other order
            clamps the set-point to the old g0 at once (lost the bat, 2026-11-10 15:35)."""
            g = cmd('lev status')['lev']['gzp_mm']
            cmd(f'lev tune g0_mm {g:.3f}')
            cmd('lev tune zp_range_mm 0')

        def finish(msg, hovering=False):
            cmd('lev eyes 0')
            if hovering:          # back to the zero-power walk, by steps, without a jump
                cmd('lev tune zp_range_mm 1.0')
                walk_g0(8.0)
                say('(left on the zero-power walk with g0 8.0, zp_range 1.0; the walk finds the natural float)')
            else:                 # the bat is gone: the settings that catch
                for k in ('zp_range_mm', 'g0_mm'):
                    cmd(f'lev tune {k} {found[k]}')
            say(msg)

        if sample('start', True)['state'] != 'hold':
            say('LOST: the bat is not hovering; nothing done')
            return
        cmd('lev eyes 0')
        pin_here()
        walk_g0(SETPOINT)
        say(f'STEP baseline: set-point {SETPOINT} mm, eyes off, {BASE_S:.0f} s')
        rows, lost = run(BASE_S, 'baseline')
        if lost:
            finish('LOST during the baseline: eyes off, settings back as found')
            return
        tb = therm(rows)
        h = [r for r in rows if r['state'] == 'hold' and r['t'] > rows[0]['t'] + 5]
        base = dict(phase='baseline', bumped=bumped(rows), n_therm=len(tb), gap_sd=round(gap_sd(h), 3),
                    mean_I_mA=round(st.mean(r['mean_I_mA'] for r in h), 1) if h else None,
                    t_first=tb[0] if tb else None, t_last=tb[-1] if tb else None)
        rec['bursts'].append(base)
        say('SUMMARY', json.dumps(base))
        if not tb:
            finish('STOP: the thermometer did not read at this set-point (current too small or not one way); '
                   'eyes off', hovering=True)
            return
        t_base = tb[-1][1]
        drift = (tb[-1][1] - tb[0][1]) / max(1.0, tb[-1][0] - tb[0][0])     # K/s with the eyes off
        for s in STRENGTHS:
            say(f'BURST eyes {s} for {ON_S:.0f} s')
            cmd(f'lev eyes {s}')
            on_rows, lost = run(ON_S, f'eyes {s}')
            cmd('lev eyes 0')
            if lost:
                finish(f'LOST during eyes {s}: eyes off, settings back as found')
                return
            off_rows, lost = run(OFF_S, f'after {s}', fast_s=FAST_S)
            tr = therm(off_rows)
            hon = [r for r in on_rows if r['state'] == 'hold' and r['t'] > on_rows[0]['t'] + 3]
            res = dict(phase=f'eyes {s}', bumped=bumped(on_rows + off_rows), gap_sd_on=round(gap_sd(hon), 3),
                       mean_I_mA_on=round(st.mean(r['mean_I_mA'] for r in hon), 1) if hon else None,
                       rms_I_mA_on=round(st.mean(r['rms_I_mA'] for r in hon), 1) if hon else None,
                       before_C=t_base, after_first=tr[0] if tr else None, after_last=tr[-1] if tr else None,
                       baseline_drift_K_per_s=round(drift, 4))
            if tr:
                res['rise_K'] = round(tr[0][1] - t_base, 2)
                res['rise_beyond_drift_K'] = round(tr[0][1] - t_base - drift * (tr[0][0] - on_rows[0]['t']), 2)
                t_base = tr[-1][1]
            rec['bursts'].append(res)
            say('SUMMARY', json.dumps(res))
            if lost:
                finish(f'LOST after eyes {s}: settings back as found')
                return
            why = None
            if tr and max(t for _, t in tr) >= STOP_C:
                why = f'the thermometer read {max(t for _, t in tr):.1f} C >= {STOP_C}'
            elif tr and res['rise_K'] > STOP_RISE_K:
                why = f'eyes {s} heated the copper {res["rise_K"]} K'
            elif res['gap_sd_on'] > STOP_GAP_SD_MM and not res['bumped']:
                why = f'the gap wobbled {res["gap_sd_on"]} mm with eyes {s}'
            elif not tr:
                why = 'no thermometer reading after the burst'
            if why:
                finish(f'STOP: {why}; eyes off', hovering=True)
                return
        finish('DONE: every strength tried; eyes off', hovering=True)


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    say('record', fn)
