#!/usr/bin/env python3
"""Does a RESTRICTED-space binding (bridges/audio on GPIO0-15 only, as shipped)
exist whose TRUE crossing count (min over all cuts of both circles) is below 84?

The search metric in gen/assign.py is a fixed-cut inversion count, which for the
shipped binding reads 98 while the true count is 84.  So configs the search
scored > 98 might still have true counts < 84.  Enumerate the whole restricted
space (same monotone framework as bind_gpio), histogram the fixed-cut metric,
and compute the true count for every config whose fixed-cut metric is low
enough that it could plausibly beat 84.
"""
import json, os, sys
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, "capture.json")))
P = C["P"]
arr = C["arr"]
gpio_t = {int(g): t for g, t in C["gpio_t"].items()}

BRIDGES = [("PEND1_IN1", "PEND1_IN2"), ("PEND2_IN1", "PEND2_IN2"), ("PEND3_IN1", "PEND3_IN2"),
           ("LEV_IN1", "LEV_IN2"), ("FAM1_A", "FAM1_B"), ("FAM2_A", "FAM2_B")]
ADC_NETS = ("HALL", "LEV_IPROPI", "MUX_OUT")
SINGLES = ("IMU_INT", "THEREMIN_PITCH", "THEREMIN_VOL", "DRV_nSLEEP", "DRV_nFAULT", "FAM_EN", "BUTTON")
I2C0 = [(4 * k, 4 * k + 1) for k in range(8)]
UART0 = [(0, 1), (12, 13), (16, 17), (28, 29)]
TIE = 0.6

def _cut(ts):
    ts = sorted(t % P for t in ts)
    g, i = max(((ts[(k + 1) % len(ts)] - ts[k]) % P, k) for k in range(len(ts)))
    return (ts[i] + g / 2) % P

pc = _cut(gpio_t.values())
ac = _cut(arr.values())
plin = {g: (t - pc) % P for g, t in gpio_t.items()}
alin = {n: (t - ac) % P for n, t in arr.items()}

def inv_of(a, nets):
    seq = [alin[n] for n in sorted(nets, key=lambda n: plin[a[n]])]
    return sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j] + TIE)

PINCUTS = sorted(set(gpio_t.values()))
ARRCUTS = sorted(set(arr.values()))

def true_count(a):
    pairs = [(gpio_t[a[n]], arr[n]) for n in a]
    best = None
    for pcut in PINCUTS:
        order = sorted(pairs, key=lambda q: ((q[0] - pcut) % P, q[1]))
        for acut in ARRCUTS:
            ks = [(x - acut) % P for _, x in order]
            v = sum(1 for i in range(len(ks)) for j in range(i + 1, len(ks)) if ks[i] > ks[j] + TIE)
            if best is None or v < best:
                best = v
    return best

bridges = sorted(BRIDGES, key=lambda b: (alin[b[0]] + alin[b[1]]) / 2)
adc = sorted(ADC_NETS, key=lambda n: alin[n])
singles = sorted(SINGLES, key=lambda n: alin[n])
bnets = [n for b in bridges for n in b]
CORE = bnets + ["AUDIO"] + list(adc)
MID = CORE + ["SDA", "SCL", "UART_TX", "UART_RX"]

hist = {}
candidates = []          # (fixed_inv, assignment)
THRESH = 118             # fixed-cut scores up to this get a true-count evaluation
for chosen in combinations(range(8), 6):
    slots = sorted(chosen, key=lambda k: plin[2 * k])
    a = {}
    for (n1, n2), k in zip(bridges, slots):
        a[n1], a[n2] = 2 * k, 2 * k + 1
    if inv_of(a, bnets) > THRESH:
        continue
    for au in (k for k in range(8) if k not in chosen):
        a1 = dict(a); a1["AUDIO"] = 2 * au
        if inv_of(a1, bnets + ["AUDIO"]) > THRESH:
            continue
        for spare in range(26, 30):
            apins = sorted((g for g in range(26, 30) if g != spare), key=lambda g: plin[g])
            a2 = dict(a1)
            for n, g in zip(adc, apins):
                a2[n] = g
            if inv_of(a2, CORE) > THRESH:
                continue
            used2 = set(a2.values())
            for sda, scl in I2C0:
                if sda in used2 or scl in used2:
                    continue
                for tx, rx in UART0:
                    if {tx, rx} & (used2 | {sda, scl}):
                        continue
                    a3 = dict(a2)
                    a3.update(SDA=sda, SCL=scl, UART_TX=tx, UART_RX=rx)
                    if inv_of(a3, MID) > THRESH:
                        continue
                    used4 = used2 | {sda, scl, tx, rx}
                    for m in range(28):
                        if {m, m + 1, m + 2} & used4:
                            continue
                        a4 = dict(a3)
                        a4.update(MUX_S0=m, MUX_S1=m + 1, MUX_S2=m + 2)
                        free = sorted(set(range(30)) - set(a4.values()), key=lambda g: plin[g])
                        for n, g in zip(singles, free):
                            a4[n] = g
                        v = inv_of(a4, list(a4))
                        hist[v] = hist.get(v, 0) + 1
                        if v <= THRESH:
                            candidates.append((v, a4))

print("restricted-space histogram of the fixed-cut metric (inv: count), low end:")
for v in sorted(hist)[:12]:
    print("  %3d: %d" % (v, hist[v]))
print("configs evaluated for true count: %d" % len(candidates))

best = None
for v, a4 in candidates:
    t = true_count(a4)
    if best is None or t < best[0]:
        best = (t, v, a4)
print("minimum TRUE crossing count over those candidates: %d" % best[0])
json.dump(best[2], open(os.path.join(HERE, "restricted_best.json"), "w"), indent=1)
ba = best[2]
bslices = {(ba[x] >> 1) & 7 for x, _ in BRIDGES}
au = (ba["AUDIO"] >> 1) & 7
ok = (sorted(ba.values()) == list(range(30))
      and all(ba[x] % 2 == 0 and ba[y] == ba[x] + 1 for x, y in BRIDGES)
      and len(bslices) == 6 and au not in bslices and ba["AUDIO"] % 2 == 0
      and len(bslices | {au}) == 7                      # one slice left for the tick
      and all(26 <= ba[n] <= 29 for n in ADC_NETS)
      and (ba["SDA"], ba["SCL"]) in I2C0 and (ba["UART_TX"], ba["UART_RX"]) in UART0
      and ba["MUX_S1"] == ba["MUX_S0"] + 1 and ba["MUX_S2"] == ba["MUX_S0"] + 2)
print("constraint check of that binding: %s (tick slice would be %d)"
      % ("VALID" if ok else "INVALID", ({0, 1, 2, 3, 4, 5, 6, 7} - bslices - {au}).pop()))
if best[0] < 84:
    print("a restricted-space binding beats 84 (fixed-cut metric %d):" % best[1])
    for n in sorted(ba, key=lambda n: ba[n]):
        print("  %-15s GPIO%d" % (n, ba[n]))
else:
    print("no restricted-space candidate with fixed-cut <= %d beats 84 true crossings" % THRESH)
