"""The levitation coil's resistance thermometer against its thermal model, on the bench,
with no bat and the loop off: the console drives the coil steadily (no catch, no motion,
so V/I is the resistance plus the bridge's and the mirror's errors).

    python3 bringup/coil_thermo.py sweep         # cold: short pulses at 0.3-0.9 A, both ways
    python3 bringup/coil_thermo.py heat 600 0.6  # 600 s at 0.6 A, then a cool-down probed
                                                 # every 10 s by 0.65 A for 0.4 s
    python3 bringup/coil_thermo.py cool          # the cool-down alone

Records status (lev_thermo, temps, coil current and u) at about 5 Hz to
bringup/results/<date>/<time>_coil_thermo_<mode>.json. The thermal cutoff stays on.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owlboard import BoardError, OwlBoard                           # noqa: E402

RDSON = 0.3                    # rough; the firmware converts amps to duty with its own R
mode = sys.argv[1] if len(sys.argv) > 1 else 'sweep'
out = Path(__file__).resolve().parent / 'results' / time.strftime('%Y-%m-%d')
out.mkdir(parents=True, exist_ok=True)
fn = out / time.strftime(f'%H%M%S_coil_thermo_{mode}.json')
rec = {'mode': mode, 'argv': sys.argv[1:], 'samples': [], 'events': []}
t0 = time.time()


def sample(b, tag):
    s = b.cmd('status', on_event=lambda e: rec['events'].append(dict(e, t=time.time() - t0)))['status']
    row = dict(t=round(time.time() - t0, 2), tag=tag, v12=s['rails']['v12'], faults=s['faults'],
               temps=s['temps_C'], i=s['coils']['i_meas_A'][3], u=s['coils']['u'][3],
               r_model=s['coils']['r_ohm'][3], **s.get('lev_thermo', {}))
    rec['samples'].append(row)
    return row


def drive(b, amps, seconds, tag, every=0.2):
    """Hold `amps` on the levitation coil for `seconds` (2 s console requests, renewed)."""
    end = time.time() + seconds
    last_req = 0.0
    row = None
    while time.time() < end:
        if time.time() - last_req > 1.0:
            r = sample(b, tag) if row is None else row
            duty = amps * (r['r_model'] + RDSON) / r['v12']
            ms = int(min(2000, max(1, (end - time.time()) * 1000 + 50)))
            try:
                b.cmd(f'coil lev {duty:.4f} {ms}')
            except BoardError as e:             # the firmware refused (too warm, ...)
                print('refused:', e, flush=True)
                rec['events'].append(dict(refused=str(e), t=time.time() - t0))
                return False
            last_req = time.time()
        row = sample(b, tag)
        time.sleep(every)
    return True


def quiet(b, seconds, tag, every=1.0):
    end = time.time() + seconds
    while time.time() < end:
        sample(b, tag)
        time.sleep(every)


try:
    with OwlBoard(timeout=8) as b:
        print('lev off ->', b.cmd('lev off'), flush=True)
        quiet(b, 3, 'start')
        if mode == 'sweep':
            for amps in (0.3, 0.4, 0.5, 0.6, 0.8, 0.9, -0.3, -0.5, -0.8, -0.9, 0.3):   # the console allows 1.0 A
                drive(b, amps, 1.5, f'{amps:+.1f}A')
                r = rec['samples'][-1]
                print(f"{amps:+.1f} A: i {r['i']:.3f} u {r['u']:+.3f} R {r['r_meas_ohm']:.3f} "
                      f"n {r['readings']} cal {r['calibrated']} t_meas {r['t_meas_C']} model {r['temps']['lev']}",
                      flush=True)
                quiet(b, 15, 'rest')
        elif mode == 'heat':
            secs = float(sys.argv[2]) if len(sys.argv) > 2 else 600
            amps = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
            t1 = time.time()
            ok = True
            while ok and time.time() - t1 < secs:
                ok = drive(b, amps, 30, 'heat')
                r = rec['samples'][-1]
                print(f"t {r['t']:.0f}: i {r['i']:.3f} R {r['r_meas_ohm']:.3f} t_meas {r['t_meas_C']} "
                      f"model cu {r.get('copper_C')} board {r['board_C']} cal {r['calibrated']} "
                      f"tmag {r['temps']['tmag']} faults {r['faults']}", flush=True)
        if mode in ('heat', 'cool'):
            for k in range(60):                     # 10 min of cooling, probed every 10 s
                drive(b, 0.65, 0.4, 'probe', every=0.05)   # the sense reads ~0.63 of it
                r = rec['samples'][-1]
                if k % 6 == 0:
                    print(f"cool {r['t']:.0f}: R {r['r_meas_ohm']:.3f} t_meas {r['t_meas_C']} "
                          f"model cu {r.get('copper_C')} board {r['board_C']}", flush=True)
                quiet(b, 9.7, 'cool')
        if mode not in ('sweep', 'heat', 'cool'):
            sys.exit(__doc__)
finally:
    fn.write_text(json.dumps(rec, indent=1))
    print('record', fn, flush=True)
