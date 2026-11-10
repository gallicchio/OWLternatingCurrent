"""Turn the levitation loop on and record it: `lev status` at about 10 Hz, every event,
and once a second the board's 12 V, faults, coil temperature model and core 1's worst tick.
Leaves the loop on at the end; stops early and turns it off on a fault.

    python3 bringup/lev_watch.py SECONDS "what this run is (supply, settings, ...)" [OFF_AT_C]

OFF_AT_C: turn the loop off (the bat drops) once the coil's thermometer reads this, so
the perch can be caught hot with an IR camera.

Writes bringup/results/<date>/<time>_lev_try.json. Used for the first hovers on
2026-11-08 (bringup/REVB.md 1.11). Set the loop's tunables first (`run.py console lev tune
g0_mm 9.5`); they are not saved across a reboot.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import OwlBoard                                       # noqa: E402

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 240
WHAT = sys.argv[2] if len(sys.argv) > 2 else ''
OFF_AT_C = float(sys.argv[3]) if len(sys.argv) > 3 else None
out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime('%H%M%S_lev_try.json')
rec = {'what': WHAT, 'samples': [], 'events': []}


def ev(e):
    rec['events'].append(dict(e, t=time.time()))
    print('EVENT', json.dumps(e), flush=True)


try:
    with OwlBoard(timeout=8) as b:
        print('lev on ->', b.cmd('lev on', on_event=ev), flush=True)
        t0 = time.time()
        last = 0.0
        while time.time() - t0 < DURATION:
            lv = b.cmd('lev status', on_event=ev)['lev']
            row = {k: lv.get(k) for k in ('state', 'gap_mm', 'gref_mm', 'bbat_mT', 'i_cmd_A', 'i_est_A',
                                          'mean_I_mA', 'rms_I_mA', 'peak_I_A', 'catches', 'losses', 'trips',
                                          'reason')}
            row['t'] = round(time.time() - t0, 2)
            rec['samples'].append(row)
            if time.time() - last > 1.0:
                s = b.cmd('status', on_event=ev)['status']
                row.update(v12=s['rails']['v12'], faults=s['faults'], i_lev=s['coils']['i_meas_A'][3],
                           temp_lev=s['temps_C']['lev'], tick_us_max=s['rt']['tick_us_max'],
                           lev_thermo=s.get('lev_thermo'))
                print(json.dumps(row), flush=True)
                last = time.time()
                th = row.get('lev_thermo') or {}
                if OFF_AT_C is not None and th.get('calibrated') and th.get('t_meas_C', -273) >= OFF_AT_C:
                    print(f"OFF_AT: thermometer {th['t_meas_C']} C >= {OFF_AT_C}: lev off ->",
                          b.cmd('lev off', on_event=ev), flush=True)
                    ev({'event': 'off_at', 't_meas_C': th['t_meas_C']})
                    break
            if lv.get('state') == 'fault':
                print('FAULT: lev off', b.cmd('lev off', on_event=ev), flush=True)
                break
            time.sleep(0.08)
finally:
    fn.write_text(json.dumps(rec, indent=1))
    print('record', fn, flush=True)
