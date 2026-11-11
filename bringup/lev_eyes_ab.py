#!/usr/bin/env python3
"""Does the eyes' breathing move the bat?  The hovering bat, eyes off then on, by turns.

    python3 bringup/lev_eyes_ab.py "what this run is" [EYES] [SECONDS]

Alternates `lev eyes 0` and `lev eyes EYES` (default 0.1, the firmware's default, which
breathes), SECONDS each (default 40), three times each, `lev status` polled as fast as it
answers.  Each stretch's first 5 s are left out.  A stretch in which the IMU counted a
tap (a bump) is marked void.  Leaves the eyes at EYES.  Never `lev off`.  Record:
bringup/results/<date>/<time>_lev_eyes_ab.json.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

WHAT = sys.argv[1] if len(sys.argv) > 1 else ''
EYES = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
SECS = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_lev_eyes_ab.json')
rec = {'what': WHAT, 'eyes': EYES, 'secs': SECS, 'samples': [], 'summary': [], 'events': []}
t0 = time.time()


def ev(e):
    rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
    print('EVENT', json.dumps(e), flush=True)


def main():
    with OwlBoard(timeout=8) as b:
        cmd = lambda line: b.cmd(line, on_event=ev)                          # noqa: E731
        for k, eyes in enumerate([0.0, EYES] * 3):
            cmd(f'lev eyes {eyes}')
            s0 = cmd('status')['status']['imu']
            rows, end = [], time.time() + SECS
            while time.time() < end:
                lv = cmd('lev status')['lev']
                r = dict(t=round(time.time() - t0, 3), k=k, eyes=eyes, state=lv['state'], gap_mm=lv['gap_mm'],
                         gzp_mm=lv['gzp_mm'], i_est_A=lv['i_est_A'], mean_I_mA=lv['mean_I_mA'],
                         rms_I_mA=lv['rms_I_mA'], carrier=lv['carrier'])
                rows.append(r)
                rec['samples'].append(r)
                if r['state'] != 'hold':
                    print('LOST', flush=True)
                    return
            s1 = cmd('status')['status']['imu']
            h = [r for r in rows if r['t'] > rows[0]['t'] + 5]
            g = [r['gap_mm'] for r in h]
            summ = dict(k=k, eyes=eyes, n=len(h), bumped=(s0['taps'], s0['double_taps']) != (s1['taps'], s1['double_taps']),
                        gap_mean=round(st.mean(g), 3), gap_sd=round(st.pstdev(g), 3),
                        gap_p2p=round(max(g) - min(g), 3), gzp_end=h[-1]['gzp_mm'],
                        mean_I_mA=round(st.mean(r['mean_I_mA'] for r in h), 1),
                        rms_I_mA=round(st.mean(r['rms_I_mA'] for r in h), 1))
            rec['summary'].append(summ)
            print('SUMMARY', json.dumps(summ), flush=True)


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    print('record', fn, flush=True)
