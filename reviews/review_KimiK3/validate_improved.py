#!/usr/bin/env python3
"""Validate improved.json (relaxed-search result) against the hard datasheet
constraints, exactly as check_gpio.py does for the shipped binding."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = {n: int(g) for n, g in json.load(open(os.path.join(HERE, "improved.json"))).items()}
BRIDGES = [("PEND1_IN1", "PEND1_IN2"), ("PEND2_IN1", "PEND2_IN2"), ("PEND3_IN1", "PEND3_IN2"),
           ("LEV_IN1", "LEV_IN2"), ("FAM1_A", "FAM1_B"), ("FAM2_A", "FAM2_B")]
I2C0 = {(4 * k, 4 * k + 1) for k in range(8)}
UART0 = {(0, 1), (12, 13), (16, 17), (28, 29)}
ok = True
def check(c, m):
    global ok
    print(("PASS  " if c else "FAIL  ") + m)
    ok = ok and c

check(len(A) == 30 and sorted(A.values()) == list(range(30)), "30 nets, GPIO0-29 each once")
slices = set()
for x, y in BRIDGES:
    g = A[x]
    check(g % 2 == 0 and A[y] == g + 1, "%s pair (%d,%d)" % (x, g, A[y]))
    s = (g >> 1) & 7
    check(s not in slices, "%s slice %d unique" % (x, s))
    slices.add(s)
au = A["AUDIO"]
check(au % 2 == 0 and ((au >> 1) & 7) not in slices, "AUDIO GPIO%d ch A, slice %d free" % (au, (au >> 1) & 7))
check(0 not in slices and ((au >> 1) & 7) != 0, "slice 0 still free for the tick")
for n in ("HALL", "LEV_IPROPI", "MUX_OUT"):
    check(26 <= A[n] <= 29, "%s on GPIO%d" % (n, A[n]))
check((A["SDA"], A["SCL"]) in I2C0, "I2C0 on (%d,%d)" % (A["SDA"], A["SCL"]))
check((A["UART_TX"], A["UART_RX"]) in UART0, "UART0 on (%d,%d)" % (A["UART_TX"], A["UART_RX"]))
check(A["MUX_S1"] == A["MUX_S0"] + 1 and A["MUX_S2"] == A["MUX_S0"] + 2,
      "MUX selects %d,%d,%d" % (A["MUX_S0"], A["MUX_S1"], A["MUX_S2"]))
print("VALID" if ok else "INVALID")
sys.exit(0 if ok else 1)
