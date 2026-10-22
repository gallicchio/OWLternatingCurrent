#!/usr/bin/env python3
"""Numbers behind Grok's design review. Reads nothing from the repo; prints only."""
import math

print("=== flux index, 10 x 2 mm N52 ===")
Br_T = 1.43
Br_kG = Br_T * 10.0
R, L = 5.0, 2.0  # mm
# on-axis field at the pole face of a uniformly magnetised cylinder
B_T = (Br_T / 2.0) * (L / math.sqrt(R * R + L * L))
B_kG = B_T * 10.0
area = math.pi * R * R
flux_index = B_kG ** 2 * area
print(f"B_face = {B_T:.3f} T = {B_kG:.2f} kG")
print(f"area = {area:.1f} mm^2")
print(f"flux index = {flux_index:.0f} kG^2 mm^2  (limit 50)")

print("\n=== small-parts cylinder (16 CFR 1501.4) ===")
# diameter 31.75 mm; depth 25.4 mm at the wall, 57.15 mm on axis, linear slant
dia, depth_wall, depth_axis = 31.75, 25.4, 57.15
radius = dia / 2.0
slope = (depth_axis - depth_wall) / radius

def depth_at(r):
    return depth_axis - slope * r

print(f"depth at r=0: {depth_at(0):.1f} mm; at r=6.6 (cap half-width): {depth_at(6.6):.1f} mm")
print(f"depth at r=12.5 (bat half-width): {depth_at(12.5):.1f} mm")
print("cap ~13 mm wide x ~25 mm long x ~6 mm tall: 25 < 44 mm available depth, fits")
print("bare bat 47.8 x 25: along the axis, depth at r=12.5 is only ~32 mm, so 47.8 does not lie flat in")

print("\n=== 12 V copper, IPC-2221 external 1 oz, 10 C ===")
def i_10c(width_mm):
    # I = 0.048 * dT^0.44 * A^0.725, A in mil^2, 1 oz = 1.37 mil
    w_mil = width_mm / 0.0254
    A = w_mil * 1.37
    return 0.048 * (10 ** 0.44) * (A ** 0.725)

for w in (0.4, 0.6, 1.0, 1.5):
    print(f"  {w:.1f} mm: {i_10c(w):.2f} A continuous for 10 C")

print("\n=== levitation electrical ===")
L, R, V = 30.1e-6, 2.56, 12.0
print(f"L/R = {L/R*1e6:.1f} us")
print(f"di/dt at 12 V = {V/L/1e6:.2f} A/us")
print(f"time 0 to 3.3 A = {3.3/(V/L)*1e6:.1f} us")
print(f"PWM period at 40 kHz = 25 us; DRV8874 tOFF = 25 us")
for i_avg in (0.5, 1.0, 2.0, 2.4):
    duty = i_avg * R / V
    ton = duty * 25e-6
    print(f"  Iavg {i_avg:.1f} A: duty {duty:.2f}, ton {ton*1e6:.1f} us, "
          f"ramp from 0 hits 3.3 A? {ton > 3.3/(V/L)}")

print("\n=== familiar empty-perch current at 4.8 V square wave ===")
for f, Lu, Ru in ((142e3, 30.3e-6, 2.13), (303e3, 30.3e-6, 2.13)):
    X = 2 * math.pi * f * Lu
    Z = math.hypot(Ru, X)
    V1 = 4 / math.pi * 4.8
    print(f"  {f/1e3:.0f} kHz: X={X:.1f} ohm, Z={Z:.1f} ohm, I1={V1/Z:.3f} A")

print("\n=== buck ===")
vref, rt, rb = 0.596, 36.0, 5.1
vout = vref * (1 + rt / rb)
print(f"nominal {vout:.3f} V")
# 1% resistors, Vref +2% corner
ratio_hi = (rt * 1.01) / (rb * 0.99)
vout_hi = vref * 1.02 * (1 + ratio_hi)
print(f"high corner (Vref+2%, R 1%): {vout_hi:.3f} V; 108% OVP trip {1.08*vout_hi:.3f} V")
print(f"EN at 12 V: {12*22/122:.2f} V; start if EN=1.21 V: {1.21*122/22:.2f} V")
