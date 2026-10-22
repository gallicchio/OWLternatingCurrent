#!/usr/bin/env python3
"""Recount the RP2354A ring crossings independently, and capture the ring data
(pin positions, line arrivals) for the relaxed-constraint search.

Runs the copy's gen/assign.py machinery (in review_KimiK3/project) with
assign.crossings and assign.bind_gpio wrapped to capture arguments.  The copy's
gen/assignment.json is rewritten by the run (allowed: it's the review copy).
Writes capture.json into this notes dir for relaxed_search.py.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "project")
sys.path.insert(0, os.path.join(PROJ, "gen"))
sys.path.insert(0, os.path.join(PROJ, "tools"))
import assign

captured = {}

orig_crossings = assign.crossings
def crossings_spy(ring, pairs):
    captured.setdefault("cross_calls", []).append({"P": ring.P, "pairs": [(p, a) for p, a in pairs]})
    return orig_crossings(ring, pairs)
assign.crossings = crossings_spy

orig_bind_gpio = assign.bind_gpio
def bind_gpio_spy(ring, arr, gpio_t, start):
    best, c = orig_bind_gpio(ring, arr, gpio_t, start)
    captured["P"] = ring.P
    captured["arr"] = arr
    captured["gpio_t"] = {str(g): t for g, t in gpio_t.items()}
    captured["best"] = best
    captured["dist"] = {n: ring.dist(arr[n], gpio_t[best[n]]) ** 2 for n in arr if n in best}
    return best, c
assign.bind_gpio = bind_gpio_spy

rc = assign.main()

# The last two crossings() calls are U4 before/after (report is called per chip,
# U4 last, two calls per report).
u4 = captured["cross_calls"][-2:]
assert u4[0]["P"] == captured["P"] and u4[1]["P"] == captured["P"]

def my_crossings(P, pairs, TIE=0.6):
    """Independent count: lines join pin positions to arrival positions round an
    annulus, each free to wind either way, so only the two cyclic orders matter.
    Try every cut of the pin circle and every cut of the arrival circle (a cut
    between adjacent points changes nothing, so cutting AT each distinct point,
    taking points in order just past the cut, covers every case).  Count pairs
    out of order with the same TIE rule.  n=30, so 30x30 cut pairs is trivial."""
    n = len(pairs)
    best = None
    for pc in sorted({p for p, _ in pairs}):
        order = sorted(pairs, key=lambda q: ((q[0] - pc) % P, q[1]))
        for ac in sorted({a for _, a in pairs}):
            ks = [(a - ac) % P for _, a in order]
            inv = sum(1 for i in range(n) for j in range(i + 1, n) if ks[i] > ks[j] + TIE)
            best = inv if best is None else min(best, inv)
    return best

for label, call in (("before", u4[0]), ("after", u4[1])):
    mine = my_crossings(call["P"], call["pairs"])
    print("U4 %s: assign.crossings says %s, my independent count says %d"
          % (label, "?", mine))

json.dump({"P": captured["P"], "arr": captured["arr"], "gpio_t": captured["gpio_t"],
           "best": captured["best"]},
          open(os.path.join(HERE, "capture.json"), "w"), indent=1)
print("captured ring data -> capture.json; assign rc=%d" % rc)
