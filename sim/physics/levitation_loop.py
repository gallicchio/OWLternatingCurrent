#!/usr/bin/env python3
"""Closed-loop simulation of the levitating bat (vertical axis).

Plant (from the field computations, not linearised):
  m z'' = F_bias(gap) + F_coil(gap) * I - m g - c z'     (z up; gap = perch - bat)
  L dI/dt = V - R I                                     (the bridge's mean voltage)
Sensor: a Hall sensor at the coil's centre reads B_bat(gap) + B_bias + 3.69 mT/A * I,
  sampled at f_s with 0.08 mT rms noise and 12-bit quantisation of a DRV5055A3-like
  output (25 mV/mT at 3.3 V); the firmware subtracts the coil's share using the
  measured current, and inverts B_bat(gap) through a calibration table.
Controller (runs at f_s): PID on gap, with the derivative low-passed, plus a slow
  "zero-power" loop that moves the gap set-point until the mean coil current is zero.
  V is limited to +/-12 V.

Case: the bat is let go 1 mm below its equilibrium (a hand placing it), then at
1.5 s gets a 5 mN, 20 ms tap.  Reports settling, peak and mean current, coil power.

Writes results/levitation_loop.json and results/levitation_loop.png.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import magnetics as mg
from levitation import bias_magnet, bat_magnet, force_between, COIL, ZB

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
G = 9.81
M_BAT = 2.7e-3
L_COIL, R_COIL = 31.5e-6, 3.35
VMAX = 12.0


def tables():
    """F_bias, F_coil per amp and the bat's field at the sensor, against gap."""
    bias = bias_magnet(4e-3, 1e-3, 3e-3)
    gaps = np.linspace(4e-3, 14e-3, 21)
    ps = np.array([[0, 0, ZB - 0.6e-3]])
    Fb, Fc, Bb = [], [], []
    for g in gaps:
        bm = bat_magnet(g)
        Fb.append(force_between(bias, bm)[2])
        Fc.append(mg.force_torque(bm, COIL, 1.0)[0][2])
        Bb.append(bm.field(ps)[0, 2])
    B_bias = bias.field(ps)[0, 2]
    return gaps, np.array(Fb), np.array(Fc), np.array(Bb), B_bias


def main(wc_hz=25.0, dfilt_hz=400.0, n_avg=1, quiet=False, plot=True, release_mm=1.0):
    gaps, Fb, Fc, Bb, B_bias = tables()
    interp = lambda tab, g: np.interp(g, gaps, tab)
    # equilibrium (no current)
    W = M_BAT * G
    g0 = np.interp(0.0, (Fb - W)[::-1], gaps[::-1])
    k_neg = -np.interp(g0, gaps, np.gradient(Fb, gaps))
    kc0 = interp(Fc, g0)
    print(f"equilibrium gap {g0*1e3:.2f} mm; negative stiffness {k_neg:.1f} N/m; coil {kc0*1e3:.1f} mN/A")
    print("B_bat at sensor vs gap (mT):", " ".join(f"{g*1e3:.0f}:{b*1e3:.1f}" for g, b in zip(gaps[::4], Bb[::4])))

    fs = 10e3
    dt_ctrl = 1 / fs
    dt = 2e-6                                  # plant integration step
    steps = int(round(dt_ctrl / dt))
    # PID gains placing the closed loop near 25 Hz with good damping
    wc = 2 * np.pi * wc_hz
    Kp = (M_BAT * wc ** 2 + k_neg) / abs(kc0)            # A per m
    Kd = 2 * 0.7 * M_BAT * wc / abs(kc0)                  # A per (m/s)
    Ki = Kp * wc / 8                                       # A per (m s)
    sgn = np.sign(kc0)                                     # current that pulls the bat up
    rng = np.random.default_rng(1)
    noise_mT, lsb_mT = 0.08, 3.3 / 4096 / 0.025

    T = 3.0
    n = int(T / dt_ctrl)
    z_gap = g0 + release_mm * 1e-3            # released this far low (+) or high (-)
    v = 0.0
    I = 0.0
    integ = 0.0
    dfilt = 0.0
    g_prev = None
    g_ref = g0                                # zero-power loop moves this
    log = {k: [] for k in ("t", "gap", "I", "V", "gref")}
    Vcmd = 0.0
    for k in range(n):
        t = k * dt_ctrl
        # --- sensor (sampled) ---
        B = interp(Bb, z_gap) + B_bias + 3.69e-3 * I
        Bm = B * 1e3 + rng.normal(0, noise_mT / np.sqrt(n_avg))
        Bm = np.round(Bm / lsb_mT) * lsb_mT
        B_bat_est = Bm * 1e-3 - B_bias - 3.69e-3 * I     # firmware knows I (current sense)
        order = np.argsort(Bb)
        g_meas = np.interp(B_bat_est, Bb[order], gaps[order])
        # --- controller ---
        err = g_meas - g_ref                   # gap too big -> pull up
        integ = np.clip(integ + err * dt_ctrl, -0.02, 0.02)
        dg = 0.0 if g_prev is None else (g_meas - g_prev) / dt_ctrl
        g_prev = g_meas
        dfilt += (dg - dfilt) * (2 * np.pi * dfilt_hz * dt_ctrl)
        I_cmd = sgn * (Kp * err + Ki * integ + Kd * dfilt)
        # zero-power: move the set-point toward where the mean current vanishes
        g_ref += -0.3 * (I_cmd * sgn) * dt_ctrl * 1e-3 * 5
        g_ref = np.clip(g_ref, g0 - 2e-3, g0 + 2e-3)
        Vcmd = np.clip(R_COIL * I_cmd + L_COIL * 0 + 0.0, -VMAX, VMAX)
        # --- plant ---
        for _ in range(steps):
            tap = 5e-3 if 1.5 <= t < 1.52 else 0.0
            F = interp(Fb, z_gap) + interp(Fc, z_gap) * I - W + tap - 2e-3 * v
            a = F / M_BAT                       # +F is upward: reduces the gap
            v += a * dt
            z_gap -= v * dt
            I += (Vcmd - R_COIL * I) / L_COIL * dt
            t += dt
        if z_gap < 1.0e-3 or z_gap > 20e-3:
            print(f"lost the bat at t = {k*dt_ctrl:.3f} s (gap {z_gap*1e3:.1f} mm)")
            break
        log["t"].append(k * dt_ctrl)
        log["gap"].append(z_gap * 1e3)
        log["I"].append(I)
        log["V"].append(Vcmd)
        log["gref"].append(g_ref * 1e3)
    t = np.array(log["t"])
    gap = np.array(log["gap"])
    I = np.array(log["I"])
    late = t > 2.5
    res = dict(g0_mm=g0 * 1e3, k_neg=k_neg, coil_mN_per_A=kc0 * 1e3, fs=fs,
               Kp_A_per_mm=Kp * 1e-3, Kd=Kd, Ki=Ki,
               held=bool(len(t) == n), peak_I_A=float(np.abs(I).max()),
               settled_gap_mm=float(gap[late].mean()) if late.any() else None,
               gap_jitter_um_rms=float(gap[late].std() * 1e3) if late.any() else None,
               mean_I_late_mA=float(I[late].mean() * 1e3) if late.any() else None,
               rms_I_late_mA=float(np.sqrt(np.mean(I[late] ** 2)) * 1e3) if late.any() else None,
               coil_power_late_mW=float(np.mean(I[late] ** 2) * R_COIL * 1e3) if late.any() else None)
    res.update(wc_hz=wc_hz, dfilt_hz=dfilt_hz, n_avg=n_avg, release_mm=release_mm)
    if not quiet:
        print(json.dumps(res, indent=1))
    if not plot:
        return res
    json.dump(res, open(os.path.join(OUT, "levitation_loop.json"), "w"), indent=1)
    fig, ax = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
    ax[0].plot(t, gap, label="gap")
    ax[0].plot(t, log["gref"], "--", label="set-point (zero-power loop)")
    ax[0].set(ylabel="gap under perch (mm)", title="Levitating bat: release 1 mm low, tap at 1.5 s")
    ax[0].legend()
    ax[1].plot(t, I * 1e3)
    ax[1].set(xlabel="time (s)", ylabel="coil current (mA)")
    for a in ax:
        a.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "levitation_loop.png"), dpi=120)
    return res


if __name__ == "__main__":
    import sys
    if "--catch" in sys.argv:
        for rel in (-3.0, -2.0, 2.0, 3.0, 4.0):
            r = main(10, 80, 8, quiet=True, plot=False, release_mm=rel)
            print(f"released {rel:+.0f} mm from equilibrium: held={r['held']}, peak {r['peak_I_A']:.2f} A")
    elif "--sweep" in sys.argv:
        for wc, df, na in ((25, 400, 1), (15, 150, 1), (12, 100, 4), (10, 80, 8), (8, 60, 8)):
            r = main(wc, df, na, quiet=True, plot=False)
            print(f"loop {wc:3.0f} Hz, D filter {df:3.0f} Hz, avg {na}: held={r['held']}, peak {r['peak_I_A']:.2f} A, "
                  f"jitter {r['gap_jitter_um_rms'] or float('nan'):.1f} um, mean {r['mean_I_late_mA'] or float('nan'):.1f} mA, "
                  f"rms {r['rms_I_late_mA'] or float('nan'):.0f} mA, coil {r['coil_power_late_mW'] or float('nan'):.0f} mW")
    else:
        main(*[float(a) for a in sys.argv[1:3]], *(int(a) for a in sys.argv[3:4]))
