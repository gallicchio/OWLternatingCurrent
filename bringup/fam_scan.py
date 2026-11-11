#!/usr/bin/env python3
"""Where does a token show in the perch current, at the live drive's level?  Scans with
the tokens off and on, for the live mode's presence probe.

    python3 bringup/fam_scan.py PHASE "what this run is"

PHASE names what is on the targets now (e.g. "none", "owl", "owl+cat"): one run per
phase, started once the person at the bench says the tokens are placed.

Each perch is scanned with `fam scan famN FRAC` (firmware main.c: 48 frequencies, 100 to
440 kHz, each at FRAC and FRAC/3 of the live duty cap; the mean ISENSE at each), REPEATS
times at each FRAC.  Record: bringup/results/<date>/<time>_fam_scan_<PHASE>.json.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

PHASE = sys.argv[1]
WHAT = sys.argv[2] if len(sys.argv) > 2 else ''
FRACS = (1.0, 0.3)
REPEATS = 2

out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime(f'%H%M%S_fam_scan_{PHASE}.json')
rec = {'what': WHAT, 'phase': PHASE, 'fracs': FRACS, 'scans': [], 'events': []}
t0 = time.time()


def say(*a):
    print(*a, flush=True)


def main():
    with OwlBoard(timeout=10) as b:
        def ev(e):
            rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
        name = PHASE
        if True:
            for rep in range(REPEATS):
                for perch in ('fam1', 'fam2'):
                    for frac in FRACS:
                        b.events.clear()
                        b.cmd(f'fam scan {perch} {frac}', on_event=ev)
                        w = b.wait_event('scan', timeout=10)
                        for e in b.events:
                            ev(e)
                        b.events.clear()
                        if not w:
                            say('no scan from', perch)
                            continue
                        rec['scans'].append(dict(phase=name, rep=rep, perch=perch, frac=frac,
                                                 t=round(time.time() - t0, 2), rows=w['rows']))
        say('DONE', name)


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    say('record', fn)
