import numpy as np
# Coil driven by a 40 kHz phase-correct PWM on a DRV8874 (PWM mode, IMODE=GND fixed
# off-time 25 us slow-decay chopping at ITRIP=3.3 A). Coil 30.1 uH, R 2.76 ohm, V=12.
L, R, V, T, ITRIP, TOFF = 30.1e-6, 2.76, 12.0, 25e-6, 3.3, 25e-6
dt = 10e-9
def run(imean_target):
    D = imean_target * R / V          # duty the firmware asks for (u = I R / V12)
    n = int(40 * T / dt)
    I = np.zeros(n)
    t = np.arange(n) * dt
    ph = (t % T) / T
    on = (ph > 0.5 - D/2) & (ph < 0.5 + D/2)   # centre-aligned pulse
    off_reg = 0.0
    for k in range(1, n):
        if off_reg > 0:                     # fixed off-time chopping: brake
            v = 0.0; off_reg -= dt
        elif on[k]:
            v = V
        else:
            v = 0.0                         # brake (slow decay): V_L = -I R
        I[k] = I[k-1] + (v - R * I[k-1]) / L * dt
        if I[k] >= ITRIP:
            off_reg = TOFF
    tail = slice(int(30*T/dt), None)
    return I[tail].mean(), I[tail].max(), I[tail].min()
print(f"{'cmd mean A':>10} {'actual mean':>11} {'peak':>6} {'valley':>7} {'ripple pp':>9}")
for im in (0.1, 0.3, 0.6, 1.0, 1.5, 2.0, 2.4, 2.87, 3.0):
    m, pk, vl = run(im)
    print(f"{im:10.2f} {m:11.2f} {pk:6.2f} {vl:7.2f} {pk-vl:9.2f}{'  <-- ITRIP chopping' if pk >= 3.29 else ''}")
