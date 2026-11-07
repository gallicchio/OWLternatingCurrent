"""ISENSE against duty at a fixed frequency: the 4.8 V power into the perch. Linear in
sin^2(pi d) while the token's LEDs are dark; the slope changes where they conduct."""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench
from owlboard import OwlBoard
cfg = bench.load_config(None)
runs = [(1, 142000, "owl at ft"), (1, 178000, "owl at the coupled peak"),
        (2, 303000, "cat at ft"), (2, 391000, "cat at the coupled peak"),
        (1, 303000, "owl perch at the cat's ft (cross-talk)"), (2, 142000, "cat perch at the owl's ft (cross-talk)")]
duties = [0.02, 0.03, 0.05, 0.07, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.4, 0.5]
out = {"step": "duty_scan", "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "runs": []}
with OwlBoard(port=cfg["board_port"]) as bd:
    for p, f, label in runs:
        pts = []
        for d in duties:
            r = bd.cmd(f"perch {p} {f} {d} 1500", timeout=6)
            pts.append({"duty": d, "isense_net_A": r["isense_net_A"], "isense_on_A": r["isense_on_A"],
                        "tripped": r["tripped"], "held_ms": r["held_ms"], "v5": r["v5"]})
            s2 = math.sin(math.pi * d) ** 2
            print(f"{label:42s} duty {d:.2f}: {r['isense_net_A']*1000:6.1f} mA  {r['isense_net_A']*4.8:.3f} W  "
                  f"P/sin^2 {r['isense_net_A']*4.8/s2:6.3f} W{'  TRIPPED' if r['tripped'] else ''}", flush=True)
            if r["tripped"]:
                break
            time.sleep(0.5)
        out["runs"].append({"perch": p, "freq_hz": f, "label": label, "points": pts})
name = time.strftime("bringup/results/%Y-%m-%d/%H%M%S") + "_duty_scan.json"
os.makedirs(os.path.dirname(name), exist_ok=True)
json.dump(out, open(name, "w"), indent=1)
print("record:", name)
