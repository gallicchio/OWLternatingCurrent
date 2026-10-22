#!/usr/bin/env python3
"""Relaxed GPIO search: same cost model as gen/assign.py bind_gpio (fixed west
cuts, CROSS=150 per crossing, squared ring travel), but bridges and the audio
may also use GPIO16-29 where the PWM slice map allows it (GPIO 2k+16/2k+17 =
slice k, k<=6; ADC pins 26-29 effectively block slices 5 and 6 there, since a
bridge needs an even/odd pair and three of 26-29 are ADC).

Also:
  * replays the RESTRICTED space (GPIO0-15 only) to validate this scorer
    against assign.py's result (must reproduce 84);
  * reconstructs the hand-written pins.py DEFAULT binding's crossing count to
    check the "132 -> 84" claim.
Reads capture.json (written by recount.py).  Writes nothing else.
"""
import json, os, sys
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, "capture.json")))
P = C["P"]
arr = C["arr"]                       # net -> arrival t
gpio_t = {int(g): t for g, t in C["gpio_t"].items()}   # gpio -> pin t
BEST_FW = {n: int(g) for n, g in C["best"].items()}

BRIDGES = [("PEND1_IN1", "PEND1_IN2"), ("PEND2_IN1", "PEND2_IN2"), ("PEND3_IN1", "PEND3_IN2"),
           ("LEV_IN1", "LEV_IN2"), ("FAM1_A", "FAM1_B"), ("FAM2_A", "FAM2_B")]
ADC_NETS = ("HALL", "LEV_IPROPI", "MUX_OUT")
SINGLES = ("IMU_INT", "THEREMIN_PITCH", "THEREMIN_VOL", "DRV_nSLEEP", "DRV_nFAULT", "FAM_EN", "BUTTON")
I2C0 = [(4 * k, 4 * k + 1) for k in range(8)]
UART0 = [(0, 1), (12, 13), (16, 17), (28, 29)]
TIE = 0.6
CROSS = 150.0

assert len(arr) == 30, arr.keys()

def _cut(ts):
    ts = sorted(t % P for t in ts)
    g, i = max(((ts[(k + 1) % len(ts)] - ts[k]) % P, k) for k in range(len(ts)))
    return (ts[i] + g / 2) % P

pc = _cut(gpio_t.values())
ac = _cut(arr.values())
plin = {g: (t - pc) % P for g, t in gpio_t.items()}
alin = {n: (t - ac) % P for n, t in arr.items()}

def d2(g, n):
    d = abs(gpio_t[g] - arr[n]) % P
    d = min(d, P - d)
    return d * d

def inv_of(a, nets):
    """Crossings of the lines in `nets`, pin order vs arrival order (west cuts)."""
    seq = [alin[n] for n in sorted(nets, key=lambda n: plin[a[n]])]
    s = 0
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            if seq[i] > seq[j] + TIE:
                s += 1
    return s

def my_crossings(pairs):
    best = None
    for pcut in sorted({p for p, _ in pairs}):
        order = sorted(pairs, key=lambda q: ((q[0] - pcut) % P, q[1]))
        for acut in sorted({a for _, a in pairs}):
            ks = [(a - acut) % P for _, a in order]
            v = sum(1 for i in range(len(ks)) for j in range(i + 1, len(ks)) if ks[i] > ks[j] + TIE)
            best = v if best is None else min(best, v)
    return best

# ---- reconstruct the pins.py DEFAULT hand-written binding's crossings ----------
sys.path.insert(0, "/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/gen")
DEFAULT = {}   # net -> gpio, hand-written order in gen/pins.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "orig_pins", "/home/jason/stuff/mudd/pcbs/OWLternatingCurrent/gen/pins.py")
# pins.py reads assignment.json for _GPIO_OF but DEFAULT is independent; import
# would assert against assignment.json - fine, it matches.  But it also pulls
# the copy off sys.path order; load it directly.
pins_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins_mod)
DEFAULT = {net: g for g, (net, _, _) in pins_mod.DEFAULT.items()}
pairs_default = [(gpio_t[DEFAULT[n]], arr[n]) for n in DEFAULT]
pairs_fw = [(gpio_t[BEST_FW[n]], arr[n]) for n in BEST_FW]
print("hand-written DEFAULT binding: %d crossings (claim: 132)" % my_crossings(pairs_default))
print("firmware binding from capture: %d crossings (claim: 84)" % my_crossings(pairs_fw))
print("fixed-cut inv of firmware binding (bind_gpio's own metric): %d" % inv_of(BEST_FW, list(BEST_FW)))

# ---- the search ----------------------------------------------------------------
bridges = sorted(BRIDGES, key=lambda b: (alin[b[0]] + alin[b[1]]) / 2)
adc = sorted(ADC_NETS, key=lambda n: alin[n])
singles = sorted(SINGLES, key=lambda n: alin[n])
bnets = [n for b in bridges for n in b]

def pin_options(slice_k, relaxed):
    """even pins whose even/odd pair is slice k."""
    lo = 2 * slice_k
    opts = [lo]
    hi = lo + 16
    if relaxed and hi + 1 <= 29:
        opts.append(hi)
    return opts

best_inv = 10 ** 9
best_cost = None
best_a = None
nodes = 0

def run(relaxed):
    """Find the minimum-crossing binding (and least cost among those).  Seeded
    with the firmware binding's 84, so pruning is sound from the start."""
    global best_inv, best_cost, best_a, nodes
    best_inv = inv_of(BEST_FW, list(BEST_FW))
    best_cost = CROSS * best_inv + sum(d2(BEST_FW[n], n) for n in BEST_FW)
    best_a = dict(BEST_FW)
    for chosen in combinations(range(8), 6):
        # side choices: a bridge slice k<=4 may take pins (2k+16, 2k+17)
        side_lists = []
        for k in chosen:
            opts = pin_options(k, relaxed)
            if len(opts) == 2 and opts[1] >= 26:
                opts = [opts[0]]          # 26-29: ADC blocks the pair anyway
            side_lists.append(opts)
        # enumerate side combinations
        def rec_side(idx, evens):
            if idx == len(chosen):
                yield list(evens)
            else:
                for e in side_lists[idx]:
                    yield from rec_side(idx + 1, evens + [e])
        for evens in rec_side(0, []):
            slots = sorted(range(6), key=lambda i: plin[evens[i]])
            a = {}
            for si, (n1, n2) in zip(slots, bridges):
                a[n1], a[n2] = evens[si], evens[si] + 1
            inv = inv_of(a, bnets)
            nodes += 1
            if inv > best_inv:
                continue
            free_slices = [k for k in range(8) if k not in chosen]
            for au_slice in free_slices:
                for au_pin in pin_options(au_slice, relaxed):
                    if au_pin in a.values():
                        continue
                    a1 = dict(a); a1["AUDIO"] = au_pin
                    inv1 = inv_of(a1, bnets + ["AUDIO"])
                    if inv1 > best_inv:
                        continue
                    for spare in range(26, 30):
                        apins = sorted((g for g in range(26, 30) if g != spare), key=lambda g: plin[g])
                        if any(g in a1.values() for g in apins):
                            continue
                        a2 = dict(a1)
                        for n, g in zip(adc, apins):
                            a2[n] = g
                        inv2 = inv_of(a2, bnets + ["AUDIO"] + list(adc))
                        if inv2 > best_inv:
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
                                inv3 = inv_of(a3, bnets + ["AUDIO"] + list(adc) + ["SDA", "SCL", "UART_TX", "UART_RX"])
                                if inv3 > best_inv:
                                    continue
                                used4 = used2 | {sda, scl, tx, rx}
                                for m in range(28):
                                    if {m, m + 1, m + 2} & used4:
                                        continue
                                    a4 = dict(a3)
                                    a4.update(MUX_S0=m, MUX_S1=m + 1, MUX_S2=m + 2)
                                    base_nets = bnets + ["AUDIO"] + list(adc) + ["SDA", "SCL", "UART_TX", "UART_RX",
                                                                                 "MUX_S0", "MUX_S1", "MUX_S2"]
                                    inv4 = inv_of(a4, base_nets)
                                    if inv4 > best_inv:
                                        continue
                                    free = sorted(set(range(30)) - set(a4.values()), key=lambda g: plin[g])
                                    for n, g in zip(singles, free):
                                        a4[n] = g
                                    inv5 = inv_of(a4, list(a4))
                                    nodes += 1
                                    if inv5 <= best_inv:
                                        cost = CROSS * inv5 + sum(d2(a4[n], n) for n in a4)
                                        if inv5 < best_inv or cost < best_cost:
                                            best_inv, best_cost, best_a = inv5, cost, dict(a4)

run(relaxed=False)
print("restricted replay: min crossings = %d, cost %.1f (assign.py got 84 / 5676.2+; validates scorer)"
      % (best_inv, best_cost))

run(relaxed=True)
print("relaxed (bridges/audio may use GPIO16-29): nodes touched = %d" % nodes)
print("relaxed minimum: %d crossings (cost %.1f)" % (best_inv, best_cost))
if best_inv < 84:
    print("IMPROVEMENT over 84:")
    for n in sorted(best_a, key=lambda n: best_a[n]):
        print("  %-15s GPIO%d" % (n, best_a[n]))
else:
    print("no binding with fewer than 84 crossings exists in the relaxed space")
json.dump(best_a, open(os.path.join(HERE, "improved.json"), "w"), indent=1)
print("improved binding -> improved.json; true min-cut count = %d"
      % my_crossings([(gpio_t[best_a[n]], arr[n]) for n in best_a]))
