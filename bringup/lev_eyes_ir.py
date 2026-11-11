#!/usr/bin/env python3
"""The bat's eyes at the natural float, step by step, for a person with an IR camera.

    python3 bringup/lev_eyes_ir.py "what this run is"

At the natural float the coil carries no steady current, so its resistance
thermometer cannot read (it needs 0.3 A one way, rt.c step 6b): the IR camera is the
measure.  The bat must be hovering on the zero-power walk.  STAGES are (eyes, seconds);
at the end of each the script prints "IR NOW" so that the reading can be taken and
written down.  It records the loop (gap, current), the thermal model, the supply and
the IMU (a tap, which is a bump to the board, marks the stage "bumped": void).  Stops
early, eyes off, if the model's board node passes BOARD_MAX_C or the bat is lost.
Never `lev off`.  Record: bringup/results/<date>/<time>_lev_eyes_ir.json; the IR
readings are added to it by hand afterwards ("ir_C" per stage).
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

WHAT = sys.argv[1] if len(sys.argv) > 1 else ''
STAGES = [(0.0, 120), (0.05, 180), (0.1, 180), (0.15, 180), (0.0, 120)]
BOARD_MAX_C = 40.0

out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_lev_eyes_ir.json')
rec = {'what': WHAT, 'stages': STAGES, 'samples': [], 'summary': [], 'events': []}
t0 = time.time()


def say(*a):
    print(*a, flush=True)


def ev(e):
    rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
    say('EVENT', json.dumps(e))


def main():
    with OwlBoard(timeout=8) as b:
        cmd = lambda line: b.cmd(line, on_event=ev)                          # noqa: E731
        if cmd('lev status')['lev']['state'] != 'hold':
            say('LOST: the bat is not hovering; nothing done')
            return
        for k, (eyes, secs) in enumerate(STAGES):
            cmd(f'lev eyes {eyes}')
            say(f'STAGE {k + 1}/{len(STAGES)}: eyes {eyes} for {secs} s')
            rows, last_full, off_hold = [], 0.0, None
            end = time.time() + secs
            while time.time() < end:
                lv = cmd('lev status')['lev']
                row = dict(t=round(time.time() - t0, 3), stage=k, eyes=eyes, state=lv['state'],
                           gap_mm=lv['gap_mm'], gzp_mm=lv.get('gzp_mm'), i_est_A=lv['i_est_A'],
                           mean_I_mA=lv['mean_I_mA'], rms_I_mA=lv['rms_I_mA'], carrier=lv.get('carrier'))
                if time.time() - last_full > 1.0:
                    s = cmd('status')['status']
                    th = s.get('lev_thermo') or {}
                    row.update(v12=s['rails']['v12'], faults=s['faults'], board_C=th.get('board_C'),
                               copper_C=th.get('copper_C'), imu_g=s['imu']['g'], taps=s['imu']['taps'],
                               double_taps=s['imu']['double_taps'], temps=s['temps_C'])
                    last_full = time.time()
                rec['samples'].append(row)
                rows.append(row)
                if row['state'] != 'hold':
                    off_hold = off_hold or time.time()
                    if time.time() - off_hold > 1.0:
                        cmd('lev eyes 0')
                        say(f'LOST in stage {k + 1} (eyes {eyes}): eyes off')
                        return
                else:
                    off_hold = None
                if (row.get('board_C') or 0) > BOARD_MAX_C:
                    cmd('lev eyes 0')
                    say(f'STOP: the model board node {row["board_C"]} C > {BOARD_MAX_C}: eyes off. IR NOW')
                    return
                time.sleep(0.1)
            h = [r for r in rows if r['state'] == 'hold' and r['t'] > rows[0]['t'] + 10]
            full = [r for r in rows if r.get('taps') is not None]
            summ = dict(stage=k + 1, eyes=eyes, seconds=secs,
                        bumped=len(full) > 1 and (full[0]['taps'], full[0]['double_taps'])
                        != (full[-1]['taps'], full[-1]['double_taps']),
                        gap_mean=round(st.mean(r['gap_mm'] for r in h), 3) if h else None,
                        gap_sd=round(st.pstdev([r['gap_mm'] for r in h]), 3) if len(h) > 2 else None,
                        mean_I_mA=round(st.mean(r['mean_I_mA'] for r in h), 1) if h else None,
                        rms_I_mA=round(st.mean(r['rms_I_mA'] for r in h), 1) if h else None,
                        board_C_end=full[-1].get('board_C') if full else None,
                        copper_C_end=full[-1].get('copper_C') if full else None, ir_C=None)
            rec['summary'].append(summ)
            say('SUMMARY', json.dumps(summ))
            say(f'IR NOW: end of stage {k + 1} (eyes {eyes})')
        cmd('lev eyes 0')
        say('DONE: eyes off; the bat is still hovering')


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    say('record', fn)
