"""The real firmware's own view: status, then its familiar events for a while, then a
forced sweep of each perch (the curve, the baseline). Supply current alongside."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench
from bench import open_bench
from owlboard import OwlBoard
cfg = bench.load_config(None)
LISTEN_S = float(sys.argv[1]) if len(sys.argv) > 1 else 60
rec = {"step": "real_familiar", "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "events": [], "sweeps": {}, "supply": []}
with open_bench(cfg, need=("supply",), want=()) as b, OwlBoard(port=cfg["board_port"]) as bd:
    b.supply.keep_on()
    st = bd.cmd("status", timeout=5).get("status", {})      # the real firmware nests it
    rec["status"] = st
    keep = {k: st[k] for k in st if k in ("version", "uptime_ms", "rails", "faults", "familiars", "scene", "lev", "pend", "theremin", "i2c", "usb_only", "power")}
    print("status:", json.dumps(keep)[:1500], flush=True)
    print("early events:", [e for e in bd.events][:10], flush=True)
    rec["events"] += bd.events
    bd.events = []
    t0 = time.time(); last_i = t0
    while time.time() - t0 < LISTEN_S:
        m = bd.read_json(time.time() + 1.0)
        if m is not None:
            m["t"] = round(time.time() - t0, 2)
            if m.get("event") != "sweep":
                print(f"  {m['t']:6.1f}s", json.dumps(m)[:300], flush=True)
            else:
                print(f"  {m['t']:6.1f}s sweep event, {len(m.get('f', []))} points", flush=True)
            rec["events"].append(m)
        if time.time() - last_i > 5:
            v, i = b.supply.measure(); rec["supply"].append((round(time.time() - t0, 1), v, i)); last_i = time.time()
            print(f"  {time.time()-t0:6.1f}s supply {v:.3f} V {i*1000:.1f} mA", flush=True)
    for p in ("fam1", "fam2"):
        bd.events = []
        r = bd.cmd(f"sweep {p}", timeout=15)
        # in live mode (the default) a perch never sweeps, so no event comes: 3 s is enough to know
        ev = bd.wait_event("sweep", timeout=15 if any(x.get("state") == "sweep" or x.get("state") == "idle" for x in st.get("familiars", [])) else 3)
        rec["sweeps"][p] = {"reply": r, "event": ev}
        if ev:
            f = ev.get("f", []); y = ev.get("y", ev.get("g", [])); base = ev.get("base", [])
            print(f"{p}: reply {json.dumps(r)[:200]}; event keys {list(ev)}; {len(f)} points", flush=True)
            if f and y:
                import statistics
                ratio = [yy / bb if bb else 0 for yy, bb in zip(y, base)] if base else []
                top = sorted(range(len(y)), key=lambda i: -(ratio[i] if ratio else y[i]))[:5]
                print("   largest y/base at:", [(round(f[i] / 1e3), round(ratio[i], 2) if ratio else round(y[i], 6)) for i in sorted(top)], flush=True)
        else:
            print(f"{p}: reply {json.dumps(r)[:300]}; no sweep event", flush=True)
    st2 = bd.cmd("status", timeout=5).get("status", {})
    rec["status_after"] = st2
    print("familiars after:", json.dumps(st2.get("familiars"))[:600], flush=True)
name = time.strftime("bringup/results/%Y-%m-%d/%H%M%S") + "_real_familiar.json"
os.makedirs(os.path.dirname(name), exist_ok=True)
json.dump(rec, open(name, "w"), indent=1)
print("record:", name)
