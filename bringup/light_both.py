"""Alternate the two perches, each at its coupled peak, so both tokens show lit (each
about 45 % of the time) while someone looks. Stops after MINUTES or when STOP exists."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import bench
from owlboard import OwlBoard
STOP = os.path.join(os.path.dirname(__file__), "light_both.stop")
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 15
cfg = bench.load_config(None)
t_end = time.time() + 60 * MINUTES
n = 0
with OwlBoard(port=cfg["board_port"]) as bd:
    while time.time() < t_end and not os.path.exists(STOP):
        for cmdline in ("perch 1 178000 0.2 450", "perch 2 391000 0.2 450"):
            r = bd.cmd(cmdline, timeout=5)
            if not r.get("ok") or r.get("tripped"):
                print("stopping:", r, flush=True)
                sys.exit(2)
            if n % 40 == 0:
                print(time.strftime("%H:%M:%S"), cmdline, f"isense {r.get('isense_on_A')} A v5 {r.get('v5')}", flush=True)
            n += 1
print("done", n, "pulses", flush=True)
