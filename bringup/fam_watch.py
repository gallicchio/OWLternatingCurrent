#!/usr/bin/env python3
"""Watch the perches: presence, the live probe and the familiar events, while someone
puts tokens on and takes them off.

    python3 bringup/fam_watch.py SECONDS "what this run is"

Polls `status` about 5 times a second; prints a line on every presence change and every
event.  Record: bringup/results/<date>/<time>_fam_watch.json.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 300
WHAT = sys.argv[2] if len(sys.argv) > 2 else ''
out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_fam_watch.json')
rec = {'what': WHAT, 'samples': [], 'events': []}
t0 = time.time()


def ev(e):
    rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
    print(f'{time.time() - t0:7.2f} EVENT', json.dumps(e), flush=True)


def main():
    with OwlBoard(timeout=8) as b:
        last = None
        end = time.time() + SECS
        while time.time() < end:
            s = b.cmd('status', on_event=ev)['status']
            fam = [{k: f.get(k) for k in ('present', 'who', 'probe_mA', 'probe_empty_mA', 'isense_A')}
                   for f in s['familiars']]
            rec['samples'].append(dict(t=round(time.time() - t0, 3), fam=fam, taps=s['imu']['taps']))
            pres = tuple(f['present'] for f in fam)
            if pres != last:
                print(f'{time.time() - t0:7.2f} PRESENT owl perch {pres[0]}, cat perch {pres[1]}; probe '
                      f'{fam[0]["probe_mA"]} / {fam[1]["probe_mA"]} mA (empty {fam[0]["probe_empty_mA"]} / '
                      f'{fam[1]["probe_empty_mA"]})', flush=True)
                last = pres
            time.sleep(0.15)


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    print('record', fn, flush=True)
