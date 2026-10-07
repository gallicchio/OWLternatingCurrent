#!/usr/bin/env python3
"""What can a PCB coil do to a neodymium magnet?

One canonical coil: a 4-layer spiral, 15 mm outer radius, 3 mm inner, 12 turns
per layer (0.6 mm track, 1 mm pitch), on JLC04161H-7628.  Its resistance is
computed for 1 oz outer / 0.5 oz inner (JLCPCB's default) and 2 oz / 1 oz.

Questions:
 1. Levitation: how much current holds a magnet (plus a little 3D-printed bat)
    under the coil at a given gap, and how hot does that make the coil?
 2. Pendulum kicks: the work one current pulse does on a magnet swinging past
    at a given height, against the energy the swing loses to air each cycle.
 3. Sliding and rolling: lateral force on a disc magnet lying on a cover
    plate, against sliding friction; torque on a magnet ball, against rolling
    resistance.

Writes results/coil_forces.json and results/coil_forces.png.
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

Z = [0.0, -0.21e-3, -1.275e-3, -1.485e-3]           # L1..L4, top copper at z=0
COIL = mg.multilayer_coil(12, 15e-3, 3e-3, Z, per_turn=64)
TURN_LEN = sum(mg.polyline_length(p) for p in COIL) / 4


def coil_R(outer_oz, inner_oz):
    return (2 * mg.R_trace(TURN_LEN, 0.6e-3, outer_oz * mg.OZ)
            + 2 * mg.R_trace(TURN_LEN, 0.6e-3, inner_oz * mg.OZ))


def disc(z_bottom, x=0.0, axis=(0, 0, 1), d=10e-3, h=3e-3, Br=1.43):
    """10 x 3 mm N52 disc whose bottom face is z_bottom above the top copper."""
    return mg.cylinder_magnet(d / 2, h, Br, center=(x, 0, z_bottom + h / 2), axis=axis,
                              nz=8, nseg=48)


def main():
    R1 = coil_R(1, 0.5)
    R2 = coil_R(2, 1)
    L = mg.L_multilayer(12, 15e-3, 3e-3, Z)
    res = {"coil": "4-layer spiral, r 15/3 mm, 12 turns/layer, 0.6 mm track",
           "L_uH": L * 1e6, "R_1oz_0.5oz": R1, "R_2oz_1oz": R2}
    print(f"coil: L = {L*1e6:.1f} uH, R = {R1:.2f} ohm (1/0.5 oz), {R2:.2f} ohm (2/1 oz)")

    # 1. levitation of a magnet below the coil (axis vertical, N up toward coil)
    print("\n1. suspended under the coil (attractive levitation, coil only, no iron)")
    lev = []
    for gap in (2e-3, 5e-3, 8e-3, 12e-3):
        # magnet below the bottom copper (z = Z[-1]); its top face 'gap' below it
        m = mg.cylinder_magnet(5e-3, 3e-3, 1.43, center=(0, 0, Z[-1] - gap - 1.5e-3),
                               axis=(0, 0, 1), nz=8, nseg=48)
        F, _ = mg.force_torque(m, COIL, 1.0)
        mass = 1.77e-3 + 3e-3              # magnet + 3 g bat
        I_need = mass * G / abs(F[2])
        P1, P2 = I_need ** 2 * R1, I_need ** 2 * R2
        lev.append(dict(gap_mm=gap * 1e3, F_per_A_mN=F[2] * 1e3, I_hold_A=I_need,
                        P_1oz_W=P1, P_2oz_W=P2))
        print(f"  gap {gap*1e3:4.1f} mm: Fz = {F[2]*1e3:7.2f} mN/A -> hold {mass*1e3:.1f} g needs "
              f"{I_need:.2f} A = {P1:.1f} W (1 oz) / {P2:.1f} W (2 oz)")
    res["levitation"] = lev

    # 2. pendulum: bat bob with a 10x3 disc, N down, passing over the coil
    print("\n2. pendulum kicks (bob passes over the coil centre)")
    Lp, mbob, A = 0.15, 8e-3, 0.035          # 15 cm thread, 8 g bob, 35 mm amplitude
    w0 = np.sqrt(G / Lp)
    E = 0.5 * mbob * w0 ** 2 * A ** 2
    kick = []
    for h in (5e-3, 10e-3, 15e-3, 20e-3):
        xs = np.linspace(-30e-3, 30e-3, 61)
        Fx = np.array([mg.force_torque(disc(h, x, axis=(0, 0, -1)), COIL, 1.0)[0][0] for x in xs])
        # The coil repels a N-down magnet approaching when its current is one way;
        # firmware switches the current so the force always points along the motion:
        # repel behind the bob after it passes, attract it in before.  Work per pass
        # with the best sign chosen at each x:
        W = np.trapz(np.abs(Fx), xs)
        kick.append(dict(height_mm=h * 1e3, Fx_max_mN_per_A=float(np.abs(Fx).max() * 1e3),
                         work_per_pass_uJ_per_A=W * 1e6))
        print(f"  height {h*1e3:4.1f} mm: |Fx|max = {np.abs(Fx).max()*1e3:6.2f} mN/A, "
              f"best work per pass = {W*1e6:7.1f} uJ at 1 A")
    for Q in (10, 30, 100):
        dE = 2 * np.pi * E / Q
        print(f"  swing energy {E*1e6:.0f} uJ; loss per cycle at Q={Q:3d}: {dE*1e6:6.1f} uJ "
              f"(two passes per cycle)")
    res["pendulum"] = dict(L=Lp, m=mbob, A=A, period=2 * np.pi / w0, E_uJ=E * 1e6, kicks=kick,
                           loss_uJ={str(Q): 2 * np.pi * E / Q * 1e6 for Q in (10, 30, 100)})

    # 3a. sliding puck: 10x3 disc lying flat (axis vertical) on a 1 mm cover
    print("\n3a. sliding puck on a 1 mm cover (axis vertical)")
    xs = np.linspace(-25e-3, 25e-3, 51)
    Fx = np.array([mg.force_torque(disc(1e-3, x, axis=(0, 0, -1)), COIL, 1.0)[0][0] for x in xs])
    Tq = np.array([mg.force_torque(disc(1e-3, x, axis=(0, 0, -1)), COIL, 1.0)[1][1] for x in xs])
    m_puck = 4e-3
    print(f"  |Fx|max = {np.abs(Fx).max()*1e3:.1f} mN/A; friction (mu 0.25, {m_puck*1e3:.0f} g puck) "
          f"= {0.25*m_puck*G*1e3:.1f} mN; tipping torque max {np.abs(Tq).max()*1e3:.2f} mN m/A")
    res["puck"] = dict(Fx_max_mN_per_A=float(np.abs(Fx).max() * 1e3), friction_mN=0.25 * m_puck * G * 1e3,
                       torque_max_mNm_per_A=float(np.abs(Tq).max() * 1e3))

    # 3b. rolling ball: 10 mm N52 sphere inside a 3D-printed shell; centre h above copper
    print("\n3b. rolling ball (10 mm sphere magnet, axis horizontal)")
    roll = []
    for hc in (8e-3, 12e-3, 18e-3):
        T = [mg.force_torque(mg.sphere_magnet(5e-3, 1.43, center=(x, 0, hc), axis=(1, 0, 0),
                                              nth=16, nseg=48), COIL, 1.0)[1][1] for x in xs]
        roll.append(dict(centre_height_mm=hc * 1e3, torque_max_uNm_per_A=float(np.abs(T).max() * 1e6)))
        rr = 0.01 * (4.1e-3 + 6e-3) * G * hc    # rolling-resistance torque, Crr ~0.01
        print(f"  centre {hc*1e3:4.1f} mm: |torque|max = {np.abs(T).max()*1e6:7.1f} uN m/A vs "
              f"rolling resistance ~{rr*1e6:.2f} uN m")
    res["rolling"] = roll
    json.dump(res, open(os.path.join(OUT, "coil_forces.json"), "w"), indent=1)

    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(xs * 1e3, Fx * 1e3)
    ax[0].set(xlabel="puck centre x (mm)", ylabel="Fx (mN) at 1 A", title="Lateral force on a 10x3 mm disc, 1 mm above")
    ax[1].plot([r["gap_mm"] for r in lev], [r["I_hold_A"] for r in lev], "o-")
    ax[1].set(xlabel="gap below coil (mm)", ylabel="current to hold 4.8 g (A)",
              title="Coil-only levitation: current needed")
    for a in ax:
        a.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "coil_forces.png"), dpi=120)


if __name__ == "__main__":
    main()
