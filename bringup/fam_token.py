#!/usr/bin/env python3
"""Can the board see a token on its perch?  Live currents and sweeps, token off and on.

    python3 bringup/fam_token.py "what this run is" [sweep]

With "sweep" the perches run in sweep mode (`fam sweep`, the original design) for the
whole run, so that `sweep fam1|fam2` returns its curve, and the firmware's own
arrived / left events are recorded; `fam live` is put back at the end.

In live mode (`fam live`, the default) each perch is driven at its token's frequency
and the firmware calls a token present when the perch draws more than an empty one.
On 2026-11-09 the status's currents did not move when Jason lifted the tokens
(results/2026-11-09/125924_fam_presence.json), at the status's 1 mA resolution.  This
script looks harder: it averages the live currents over each phase (status polled
fast, so the 1 mA steps dither into a finer mean), and asks each perch for a sweep
(`sweep fam1|fam2`: the curve and the empty-perch baseline) in every phase.

PHASES are (name, seconds).  Each phase starts with a line "DO: ..." for the person at
the bench, waits PREP_S for the token to be placed, then records.  Record:
bringup/results/<date>/<time>_fam_token.json.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

WHAT = sys.argv[1] if len(sys.argv) > 1 else ''
MODE = sys.argv[2] if len(sys.argv) > 2 else 'live'
PHASES = [('no tokens', 'both tokens off'),
          ('owl on', 'put the OWL token on its target'),
          ('owl and cat on', 'put the CAT token on its target too'),
          ('cat only', 'take the OWL token off'),
          ('no tokens again', 'take the CAT token off')]
PREP_S = 12.0
REC_S = 20.0

out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_fam_token.json')
rec = {'what': WHAT, 'mode': MODE, 'phases': [], 'samples': [], 'sweeps': [], 'events': []}
t0 = time.time()


def say(*a):
    print(*a, flush=True)


def main():
    with OwlBoard(timeout=15) as b:
        def ev(e):
            rec['events'].append(dict(e, t=round(time.time() - t0, 2)))
            if e.get('event') == 'sweep':
                rec['sweeps'].append(dict(e, t=round(time.time() - t0, 2), phase=cur['name']))
                say('SWEEP', e.get('perch'), 'points', len(e.get('f_kHz', [])))
            else:
                say('EVENT', json.dumps(e))

        cmd = lambda line, **k: b.cmd(line, on_event=ev, **k)               # noqa: E731
        cur = {'name': 'start'}
        if MODE == 'sweep':
            cmd('fam sweep')
        try:
            run_phases(b, cmd, cur, ev)
        finally:
            if MODE == 'sweep':
                cmd('fam live')
                say('fam live again')


def run_phases(b, cmd, cur, ev):
    if True:
        for name, do in PHASES:
            cur['name'] = name
            say(f'DO: {do}  ({PREP_S:.0f} s, then {REC_S:.0f} s of recording)')
            time.sleep(PREP_S)
            say(f'RECORDING: {name}')
            rows = []
            end = time.time() + REC_S
            while time.time() < end:
                s = cmd('status')['status']
                f = s['familiars']
                row = dict(t=round(time.time() - t0, 3), phase=name,
                           fam=[{k: p.get(k) for k in ('state', 'who', 'present', 'f_hz', 'duty', 'isense_A', 'p_W')}
                                for p in f],
                           lux=s['light']['lux'], taps=s['imu']['taps'])
                rows.append(row)
                rec['samples'].append(row)
                time.sleep(0.05)
            summ = dict(phase=name, n=len(rows))
            for k in range(2):
                i = [r['fam'][k]['isense_A'] for r in rows]
                p = [r['fam'][k]['p_W'] for r in rows]
                summ[f'fam{k + 1}'] = dict(i_mA=round(1000 * st.mean(i), 3), i_sd_mA=round(1000 * st.pstdev(i), 3),
                                           p_mW=round(1000 * st.mean(p), 2),
                                           present=sorted({r['fam'][k]['present'] for r in rows}))
            for perch in ('fam1', 'fam2'):
                try:
                    b.events.clear()                       # each was already passed to ev()
                    n0 = len(rec['sweeps'])
                    cmd(f'sweep {perch}')
                    if len(rec['sweeps']) == n0:          # not already in with the reply
                        w = b.wait_event('sweep', timeout=15)
                        if w:
                            ev(w)
                        for e in b.events:                 # wait_event keeps the others here:
                            ev(e)                          # an arrived / left event (lost one, 16:15)
                        b.events.clear()
                except Exception as e:                                  # noqa: BLE001
                    say('sweep failed', perch, e)
            rec['phases'].append(summ)
            say('SUMMARY', json.dumps(summ))
        say('DONE')


try:
    main()
finally:
    fn.write_text(json.dumps(rec, indent=1))
    say('record', fn)
