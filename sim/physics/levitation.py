#!/usr/bin/env python3
"""Can a PCB coil (no iron) levitate a small PCB bat?  Zero-power suspension.

A bias magnet above the 'perch' PCB carries the bat's weight by attraction; the
4-layer PCB coil only stabilises it (attraction grows as the gap shrinks, so
the vertical direction is unstable: Earnshaw).  A Hall sensor at the coil's
centre, on the perch's underside, measures the gap.  With an integrator on the
coil current the loop settles where the bias alone holds the bat, so the mean
coil current is near zero ("zero-power" maglev).

The bat: a 0.8 mm PCB (~1.5 g with LEDs, its own receive coil for wireless
power) carrying a magnet on top.  Bias and bat magnets point the same way along
the axis, so they attract.

Computes: equilibrium gap, the negative stiffness there, the coil's force per
amp, the lateral stiffness (must be positive), the Hall sensor's field and its
sensitivity to the gap, and the coil current for a PD loop with a 15 Hz
bandwidth and a 0.5 mm disturbance.

Writes results/levitation.json and results/levitation.png.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import magnetics as mg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
G = 9.81
Z = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]
COIL = mg.multilayer_coil(12, 15e-3, 3e-3, Z, per_turn=64)
ZB = Z[-1]                       # perch underside (bottom copper)
DOWN = (0, 0, -1)


def bias_magnet(d, h, lift):
    """Bias magnet above the perch: bottom face `lift` above top copper."""
    return mg.cylinder_magnet(d / 2, h, 1.43, center=(0, 0, lift + h / 2), axis=DOWN,
                              nz=10, nseg=64)


def bat_magnet(gap, d=10e-3, h=2e-3, x=0.0):
    """Bat's magnet: top face `gap` below the perch's bottom copper."""
    return mg.cylinder_magnet(d / 2, h, 1.43, center=(x, 0, ZB - gap - h / 2), axis=DOWN,
                              nz=8, nseg=48)


def force_between(m_src, m_tgt):
    """Force on m_tgt from m_src's equivalent currents (all loops equal current)."""
    I = m_src.currents[0]
    return mg.force_torque(m_tgt, m_src.loops, I)[0]


def main():
    res = {"cases": []}
    m_bat = 1.5e-3 + 1.2e-3           # PCB bat + 10x2 mm N52 disc (1.18 g)
    for bias_d, bias_h, lift in [(2e-3, 1e-3, 1.0e-3), (3e-3, 1e-3, 1.0e-3), (3e-3, 1e-3, 3.0e-3), (4e-3, 1e-3, 3.0e-3), (5e-3, 1e-3, 4.0e-3)]:
        bias = bias_magnet(bias_d, bias_h, lift)
        gaps = np.linspace(3e-3, 30e-3, 55)
        Fz = np.array([force_between(bias, bat_magnet(g))[2] for g in gaps])
        W = m_bat * G
        # attraction is upward (+z) on the bat; equilibrium where Fz = W
        i = np.where(np.diff(np.sign(Fz - W)))[0]
        if len(i) == 0:
            print(f"bias {bias_d*1e3:.0f}x{bias_h*1e3:.0f} lift {lift*1e3:.0f}: no equilibrium "
                  f"(Fz {Fz.min()*1e3:.1f}..{Fz.max()*1e3:.1f} mN vs W {W*1e3:.1f} mN)")
            continue
        j = i[0]
        geq = gaps[j] + (W - Fz[j]) * (gaps[j + 1] - gaps[j]) / (Fz[j + 1] - Fz[j])
        kneg = -(Fz[j + 1] - Fz[j]) / (gaps[j + 1] - gaps[j])    # dF/d(gap) < 0 -> unstable
        # coil gain at equilibrium
        Fc = mg.force_torque(bat_magnet(geq), COIL, 1.0)[0][2]
        # lateral stiffness from the bias (restoring?) at 0.5 mm offset
        Fx = force_between(bias, bat_magnet(geq, x=0.5e-3))[0]
        klat = -Fx / 0.5e-3
        # Hall sensor 0.6 mm below bottom copper, on axis
        ps = np.array([[0, 0, ZB - 0.6e-3]])
        B_bias = bias.field(ps)[0, 2]
        B_bat = bat_magnet(geq).field(ps)[0, 2]
        dB = (bat_magnet(geq + 0.1e-3).field(ps)[0, 2] - bat_magnet(geq - 0.1e-3).field(ps)[0, 2]) / 0.2e-3
        CA, CB = mg.segments(COIL)
        B_coil = mg.bfield(CA, CB, 1.0, ps)[0, 2]
        # PD loop: closed-loop natural frequency fc
        fc = 15.0
        Kp = (m_bat * (2 * np.pi * fc) ** 2 + kneg) / abs(Fc)       # A per metre
        I_dist = Kp * 0.5e-3
        case = dict(bias=f"{bias_d*1e3:.0f}x{bias_h*1e3:.0f} mm, {lift*1e3:.0f} mm above perch",
                    bat_mass_g=m_bat * 1e3, gap_eq_mm=geq * 1e3, k_neg_N_per_m=kneg,
                    coil_mN_per_A=Fc * 1e3, k_lat_N_per_m=klat,
                    hall_B_bias_mT=B_bias * 1e3, hall_B_bat_mT=B_bat * 1e3,
                    hall_dB_mT_per_mm=dB, hall_B_coil_mT_per_A=B_coil * 1e3,
                    Kp_A_per_mm=Kp * 1e-3, I_for_0p5mm_A=I_dist)
        res["cases"].append(case)
        print(f"bias {case['bias']}: bat {m_bat*1e3:.1f} g hangs at {geq*1e3:.1f} mm; "
              f"k_neg {kneg:.1f} N/m; coil {Fc*1e3:+.1f} mN/A; lateral k {klat:+.1f} N/m")
        print(f"   Hall: bias {B_bias*1e3:+.1f} mT, bat {B_bat*1e3:+.1f} mT, "
              f"{dB:+.1f} mT/mm of gap, coil {B_coil*1e3:+.2f} mT/A; "
              f"PD at {fc:.0f} Hz: Kp {Kp*1e-3:.2f} A/mm -> {I_dist:.2f} A for 0.5 mm")
        res.setdefault("curves", []).append(dict(gaps_mm=(gaps * 1e3).tolist(), Fz_mN=(Fz * 1e3).tolist(),
                                                 label=case["bias"]))
    json.dump(res, open(os.path.join(OUT, "levitation.json"), "w"), indent=1)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for c in res.get("curves", []):
        ax.plot(c["gaps_mm"], c["Fz_mN"], label="bias " + c["label"])
    ax.axhline(m_bat * G * 1e3, color="k", ls="--", label=f"bat weight ({m_bat*1e3:.1f} g)")
    ax.set(xlabel="gap: perch underside to bat magnet (mm)", ylabel="attraction (mN)",
           title="Zero-power suspension: bias attraction vs gap")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "levitation.png"), dpi=120)


if __name__ == "__main__":
    main()
