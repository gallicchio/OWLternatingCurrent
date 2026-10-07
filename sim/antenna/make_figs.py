#!/usr/bin/env python3
"""
make_figs.py -- every figure in README.md, from the cached results (no solving here).

    em-env python make_figs.py [validation geometry candidates winner sensitivity current]

Reads results/<case>.json (+ out/<case>/result.npz), so it only works after the
run_*.py scripts have been run on this machine; the PNGs are committed.
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import antsim  # noqa: E402
import matching  # noqa: E402
import plotstyle as ps  # noqa: E402
import shapes  # noqa: E402

plt = ps.plt
FIGS = os.path.join(HERE, "figs")


def find(name):
    """Newest result of the current MODEL_REV for a case name."""
    best = None
    for fn in glob.glob(os.path.join(antsim.RESULTS, f"{name}_*.json")):
        with open(fn) as fh:
            s = json.load(fh)
        if s.get("name") != name or s.get("rev") != antsim.MODEL_REV:
            continue
        if not os.path.exists(os.path.join(antsim.OUT, s["tag"], "result.npz")):
            continue
        if best is None or os.path.getmtime(fn) > best[0]:
            best = (os.path.getmtime(fn), s)
    if best is None:
        raise KeyError(name)
    s = best[1]
    a = dict(np.load(os.path.join(antsim.OUT, s["tag"], "result.npz")))
    return s, a


def s11db(a):
    return 20 * np.log10(np.abs(a["s11"]))


def save(fig, name):
    os.makedirs(FIGS, exist_ok=True)
    fn = os.path.join(FIGS, name)
    fig.savefig(fn, dpi=150)
    plt.close(fig)
    print("wrote", fn)


# ----------------------------------------------------------------------------- validation
def fig_validation():
    import mom_dipole
    ps.setup()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.9))
    # (a) dipole: R and X against MoM
    s, a = find("dipole_fs_r0.125")
    f = a["f"] / 1e9
    z = a["zin"]
    fm = np.linspace(2.0e9, 3.0e9, 41)
    zm = mom_dipole.sweep(58e-3, 0.25e-3, fm, 121)
    ax1.plot(f, z.real, color=ps.SERIES[0], label="openEMS R (0.125 mm mesh)")
    ax1.plot(f, z.imag, color=ps.SERIES[1], label="openEMS X")
    ax1.plot(fm / 1e9, zm.real, ls="none", marker="o", ms=4, mfc=ps.SURFACE, mec=ps.SERIES[0],
             mew=1.2, label="MoM R (thin wire, a = w/4)")
    ax1.plot(fm / 1e9, zm.imag, ls="none", marker="o", ms=4, mfc=ps.SURFACE, mec=ps.SERIES[1],
             mew=1.2, label="MoM X")
    ax1.axhline(0, color=ps.MUTED, lw=0.8)
    fr, rr = mom_dipole.resonance(fm, zm)
    ax1.set_xlim(2.0, 3.0)
    ax1.set_ylim(-150, 250)
    ax1.set_xlabel("frequency (GHz)")
    ax1.set_ylabel("input impedance (Ω)")
    ax1.set_title("(a) 58 × 1 mm strip dipole in vacuum")
    ax1.legend(loc="upper left")
    ax1.text(0.98, 0.04,
             f"X = 0 at {s['f_res']/1e9:.3f} GHz (FDTD) vs {fr/1e9:.3f} GHz (MoM)\n"
             f"R there {s['r_res']:.1f} Ω vs {rr:.1f} Ω;  η_rad = {100*s['eta_rad'][1]:.1f} %"
             f" (PEC: must be 100)", transform=ax1.transAxes, ha="right", va="bottom",
             fontsize=7.5, color=ps.INK2)
    # (b) DN007 vs TI's measurement
    ps.band(ax2)
    meas = np.loadtxt(os.path.join(antsim.RESULTS, "dn007_measured_s11_digitized.csv"),
                      delimiter=",")
    ax2.plot(meas[:, 0], meas[:, 1], color=ps.INK, lw=1.6, ls=(0, (4, 2)),
             label="TI measured (SWRU120, CC2430DB)")
    cases = [("dn007_h1.0_g29x60", "1.0 mm FR4, 29 × 60 mm ground", ps.SERIES[0]),
             ("dn007_h1.0_g50x80", "1.0 mm FR4, 50 × 80 mm ground", ps.SERIES[1]),
             ("dn007_h1.6_g29x60", "1.6 mm FR4, 29 × 60 mm ground", ps.SERIES[2])]
    for name, lab, col in cases:
        try:
            s, a = find(name)
        except KeyError:
            continue
        ax2.plot(a["f"] / 1e9, s11db(a), color=col, label=f"openEMS, {lab}")
    ax2.axhline(-10, color=ps.MUTED, lw=0.8)
    ax2.set_xlim(2.0, 3.0)
    ax2.set_ylim(-35, 0)
    ax2.set_xlabel("frequency (GHz)")
    ax2.set_ylabel("|S11| (dB, 50 Ω)")
    ax2.set_title("(b) TI DN007 inverted-F replica vs measurement")
    ax2.legend(loc="lower right")
    fig.tight_layout()
    save(fig, "fig_validation.png")



# ----------------------------------------------------------------------------- helpers
def gain_cut(a, k, plane):
    """Gain (dBi) along a full 360-degree cut: plane in {'xy', 'xz', 'yz'}."""
    th, ph = a["theta"], a["phi"]
    E = a["E_norm"][k].astype(float)
    g = a["Dmax"][k] * a["eta"][k] * (E / E.max()) ** 2
    gdb = 10 * np.log10(np.maximum(g, 1e-6))
    if plane == "xy":                          # theta = 90, phi 0..360
        it = int(np.argmin(abs(th - 90)))
        ang = np.deg2rad(np.r_[ph, 360.0])
        return ang, np.r_[gdb[it, :], gdb[it, 0]]
    p0 = 0.0 if plane == "xz" else 90.0
    i0 = int(np.argmin(abs(ph - p0)))
    i1 = int(np.argmin(abs(ph - (p0 + 180.0))))
    # angle measured from +z, going through phi=p0 side then back over phi=p0+180
    ang = np.r_[np.deg2rad(th), np.deg2rad(360.0 - th[::-1])]
    return ang, np.r_[gdb[:, i0], gdb[::-1, i1]]


def draw_design(ax, d, ann=True, ground_depth=10.0):
    import view_geom
    view_geom.draw(ax, d, ground_depth=ground_depth, ann=ann)
    allp = np.vstack([np.asarray(P, float) for P in d["polys"]])
    ax.set_xlim(allp[:, 0].min() - 5, allp[:, 0].max() + 5)
    ax.set_ylim(-ground_depth + 2, allp[:, 1].max() + 4)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")


def smith_ax(ax):
    from skrf.plotting import smith
    smith(ax=ax, chart_type="z", draw_labels=False)
    for ln in ax.lines:
        ln.set_color(ps.GRID)
        ln.set_linewidth(0.6)
    for p in ax.patches:
        p.set_edgecolor(ps.GRID)
        p.set_linewidth(0.6)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.axis("off")
    th = np.linspace(0, 2 * np.pi, 361)
    ax.plot(np.cos(th), np.sin(th), color=ps.MUTED, lw=0.8)
    gam = 1 / 3                                     # |S11| = -10 dB circle
    ax.plot(gam * np.cos(th), gam * np.sin(th), color=ps.MUTED, lw=0.8, ls=(0, (3, 2)))
    ax.text(0.0, -gam - 0.06, "−10 dB", ha="center", va="top", fontsize=7, color=ps.INK2)


def smith_trace(ax, a, color, label, fmin=1.8e9, fmax=3.2e9):
    f = a["f"]
    m = (f >= fmin) & (f <= fmax)
    g = a["s11"][m]
    ax.plot(g.real, g.imag, color=color, label=label)
    mb = (f >= 2.400e9) & (f <= 2.4835e9)
    gb = a["s11"][mb]
    ax.plot(gb.real, gb.imag, color=color, lw=4.5, solid_capstyle="round", alpha=0.9)
    for fq, mk in ((2.0e9, "s"), (3.0e9, "^")):
        i = int(np.argmin(abs(f - fq)))
        ax.plot(a["s11"][i].real, a["s11"][i].imag, marker=mk, ms=5, color=color,
                mec=ps.SURFACE, mew=1.0)



# ----------------------------------------------------------------------------- final set
def designs():
    from run_candidates import BAT_PM, BAT_T, bat_design, ghost_design
    return dict(ghost=ghost_design(), bat_pm=bat_design(BAT_PM), bat_t=bat_design(BAT_T),
                bat_dipole=shapes.bat("dipole", span=46.0, yb=16.0))


CANDS = [  # case, label, colour slot, design key, show matched curve, show bare curve
    ("C_ghost", "ghost, tail-fed planar monopole", 1, "ghost", False, True),
    ("C_bat_pm", "bat, tail-fed planar monopole", 0, "bat_pm", True, True),
    ("A_batifa_span44", "bat, feet = feed + short (0.5 mm mesh)", 2, "bat_t", True, False),
    ("A_batdip_span46", "bat dipole, ideal balun (0.5 mm mesh)", 6, "bat_dipole", False, True),
]


def fig_candidates():
    ps.setup()
    D = designs()
    fig = plt.figure(figsize=(11.5, 7.4))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.0, 1.35])
    ax = fig.add_subplot(gs[1, :])
    ps.band(ax)
    for i, (case, lab, slot, key, show_m, show_b) in enumerate(CANDS):
        axg = fig.add_subplot(gs[0, i])
        draw_design(axg, D[key], ann=False, ground_depth=5.0)
        axg.set_title(lab.replace(" (0.5 mm mesh)", ""), fontsize=8.0)
        axg.set_xlabel("")
        axg.set_ylabel("")
        axg.tick_params(labelsize=7)
        try:
            _, a = find(case)
        except KeyError:
            continue
        col = ps.SERIES[slot]
        if show_b:
            ax.plot(a["f"] / 1e9, s11db(a), color=col, lw=2.0 if not show_m else 1.1,
                    ls="-" if not show_m else (0, (3, 2)), label=lab + (", bare" if show_m else ""))
        if show_m:
            net, msdb = matching.best_match(a["f"], a["zin"])
            ax.plot(a["f"] / 1e9, msdb, color=col, label=f"{lab} + pi: {matching.describe(net)}")
    ax.axhline(-10, color=ps.MUTED, lw=0.8)
    ax.set_xlim(1.8, 3.2)
    ax.set_ylim(-40, 0)
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("|S11| (dB, 50 Ω)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=7.5)
    ax.set_title("Return loss on the 100 × 80 mm board (0.25 mm mesh unless noted)")
    fig.tight_layout()
    save(fig, "fig_candidates.png")


def _annotate_ghost(ax, d):
    p = d["params"]
    R, yc = p["R"], p["yc"]
    allp = np.vstack([np.asarray(P, float) for P in d["polys"]])
    x0, x1, y1 = allp[:, 0].min(), allp[:, 0].max(), allp[:, 1].max()
    kw = dict(arrowstyle="<->", color=ps.INK2, lw=0.8, shrinkA=0, shrinkB=0)
    ax.annotate("", (x0, y1 + 1.2), (x1, y1 + 1.2), arrowprops=kw)
    ax.text(0.5 * (x0 + x1), y1 + 1.5, f"{x1 - x0:.1f} mm", ha="center", va="bottom", fontsize=7.5,
            color=ps.INK2)
    ax.annotate("", (x1 + 1.5, 0), (x1 + 1.5, y1), arrowprops=kw)
    ax.text(x1 + 2.0, 0.5 * y1, f"{y1:.1f} mm", ha="left", va="center", fontsize=7.5,
            color=ps.INK2, rotation=90)
    tw, th = p["tab_w"], p["tab_h"]
    ax.plot([-tw / 2, -tw / 2, tw / 2, tw / 2], [0, th, th, 0], color=ps.INK2, lw=0.8,
            ls=(0, (3, 2)))
    ax.text(-tw / 2, th + 0.6, f"keep-out = FR4 tab {tw:.0f} × {th:.0f} mm (no copper on any layer)",
            fontsize=7, va="bottom", color=ps.INK2)


def fig_winner(case="C_ghost", key="ghost", label="ghost", slot=1, match=False):
    ps.setup()
    d = designs()[key]
    sm, a = find(case)
    f = a["f"] / 1e9
    col = ps.SERIES[slot]
    fig = plt.figure(figsize=(11.5, 7.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 1.0])
    axg = fig.add_subplot(gs[0, 0])
    draw_design(axg, d, ground_depth=7.0)
    if key == "ghost":
        _annotate_ghost(axg, d)
        axg.set_xlim(-d["params"]["tab_w"] / 2 - 2, d["params"]["tab_w"] / 2 + 6)
        axg.set_ylim(-6, d["params"]["tab_h"] + 3.5)
    axg.set_title(f"{label}: top copper on 1.6 mm FR4, at the edge of the 100 × 80 mm ground")
    ax = fig.add_subplot(gs[1, 0])
    ps.band(ax)
    ax.plot(f, s11db(a), color=col, label="bare antenna, 0.25 mm mesh")
    net = None
    if match:
        net, msdb = matching.best_match(a["f"], a["zin"])
        ax.plot(f, msdb, color=ps.INK, lw=1.4, ls=(0, (4, 2)),
                label=f"with pi network: {matching.describe(net)}")
    mesh_extra = ("S_ghost_mesh0.18", "0.18 mm mesh") if key == "ghost" else \
        ("S_batpm_mesh0.35", "0.35 mm mesh")
    for extra, lab2, c2 in ((mesh_extra[0], mesh_extra[1], ps.MUTED),):
        try:
            _, am = find(extra)
            ax.plot(am["f"] / 1e9, s11db(am), color=c2, lw=1.2, label=f"bare, {lab2}")
        except KeyError:
            pass
    ax.axhline(-10, color=ps.MUTED, lw=0.8)
    ax.set_xlim(1.8, 3.2)
    ax.set_ylim(-40, 0)
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("|S11| (dB, 50 Ω)")
    ax.legend(loc="lower left" if match else "lower right", fontsize=7.5)
    ax.set_title("Return loss at the feed")
    axs = fig.add_subplot(gs[0, 1])
    smith_ax(axs)
    smith_trace(axs, a, col, label)
    if match:
        am = dict(a)
        zm = matching.apply(a["zin"], a["f"], net)
        am["s11"] = matching.s11(zm)
        smith_trace(axs, am, ps.INK, "matched")
    axs.set_title("S11 1.8 → 3.2 GHz (■ 2.0, ▲ 3.0 GHz); thick: 2.400–2.484", fontsize=8.5)
    axz = fig.add_subplot(gs[1, 1])
    ps.band(axz, label=False)
    axz.plot(f, a["zin"].real, color=ps.SERIES[0], label="R")
    axz.plot(f, a["zin"].imag, color=ps.SERIES[1], label="X")
    axz.axhline(50, color=ps.MUTED, lw=0.8, ls=(0, (3, 2)))
    axz.axhline(0, color=ps.MUTED, lw=0.8)
    axz.set_xlim(1.8, 3.2)
    axz.set_ylim(-80, 160)
    axz.set_xlabel("frequency (GHz)")
    axz.set_ylabel("Zin (Ω)")
    axz.legend(loc="upper left")
    axz.set_title("Input impedance at the port (bare)")
    fig.tight_layout()
    save(fig, f"fig_{key}.png")


def fig_bat():
    fig_winner("C_bat_pm", "bat_pm", "bat (tail-fed)", 0, match=True)


def fig_patterns():
    ps.setup()
    rows = [("C_ghost", "ghost", 1), ("C_bat_pm", "bat (tail-fed)", 0)]
    fig, axs = plt.subplots(len(rows), 3, figsize=(11, 7.6), subplot_kw=dict(projection="polar"))
    cuts = [("xz", "horizontal plane if the board stands\nupright, antenna on top (xz)"),
            ("yz", "vertical plane through the\nantenna and board (yz)"),
            ("xy", "the board's own plane (xy)")]
    for r, (case, lab, slot) in enumerate(rows):
        try:
            _, a = find(case)
        except KeyError:
            continue
        k = int(np.argmin(abs(a["f_nf"] - 2.44e9)))
        gmax = 10 * np.log10(a["Dmax"][k] * a["eta"][k])
        for c, (pl, ttl) in enumerate(cuts):
            ax = axs[r, c]
            ang, g = gain_cut(a, k, pl)
            ax.plot(ang, np.maximum(g, -25), color=ps.SERIES[slot])
            ax.set_rlim(-25, 6)
            ax.set_rticks([-20, -10, 0])
            ax.set_yticklabels(["−20", "−10", "0 dBi"], fontsize=6.5, color=ps.INK2)
            if pl == "xy":
                ax.set_theta_zero_location("E")
                ax.set_theta_direction(1)
            else:
                ax.set_theta_zero_location("N")
                ax.set_theta_direction(-1)
            ax.grid(color=ps.GRID, lw=0.6)
            ax.tick_params(labelsize=6.5, colors=ps.INK2)
            if r == 0:
                ax.set_title(ttl, fontsize=8.5, pad=12)
        axs[r, 0].text(-0.32, 0.5, f"{lab}\npeak {gmax:.1f} dBi\nη_rad {100*a['eta'][k]:.0f} %",
                       transform=axs[r, 0].transAxes, ha="right", va="center", fontsize=8.5,
                       color=ps.INK)
    fig.suptitle("Gain at 2.44 GHz (IEEE gain: directivity × radiation efficiency, before mismatch)",
                 fontsize=10, color=ps.INK)
    fig.tight_layout(rect=(0.08, 0, 1, 0.96))
    save(fig, "fig_patterns.png")


def fig_sensitivity():
    ps.setup()
    fams = [("ghost", "ghost, bare", None), ("batpm", "bat + its nominal pi match", True)]
    groups = [("shape scaled ±5 %", [("scale0.95", "−5 %"), ("scale1.05", "+5 %")]),
              ("FR4 εr 4.2 / 4.6", [("er4.2", "εr 4.2"), ("er4.6", "εr 4.6")]),
              ("2 mm PLA lid on it; a hand 15 mm over it", [("pla2mm", "PLA lid"),
                                                            ("hand15mm", "hand")])]
    fig, axs = plt.subplots(2, 3, figsize=(11.5, 6.8), sharey=True)
    for r, (fam, flab, use_match) in enumerate(fams):
        try:
            _, a0 = find(f"S_{fam}_nominal")
        except KeyError:
            continue
        net = None
        if use_match:
            net, _ = matching.best_match(a0["f"], a0["zin"])

        def curve(a):
            if net is None:
                return s11db(a)
            return 20 * np.log10(np.abs(matching.s11(matching.apply(a["zin"], a["f"], net))))
        for c, (ttl, cases) in enumerate(groups):
            ax = axs[r, c]
            ps.band(ax, label=False)
            ax.plot(a0["f"] / 1e9, curve(a0), color=ps.INK, lw=1.4, label="nominal")
            for (suffix, lab), col in zip(cases, ps.SERIES):
                try:
                    _, a = find(f"S_{fam}_{suffix}")
                except KeyError:
                    continue
                ax.plot(a["f"] / 1e9, curve(a), color=col, label=lab)
            ax.axhline(-10, color=ps.MUTED, lw=0.8)
            ax.set_xlim(1.9, 3.0)
            ax.set_ylim(-40, 0)
            if r == 0:
                ax.set_title(ttl, fontsize=9.5)
            ax.legend(loc="lower right", fontsize=7.5)
            if r == 1:
                ax.set_xlabel("frequency (GHz)")
        axs[r, 0].set_ylabel(f"{flab}\n|S11| (dB)")
    fig.tight_layout()
    save(fig, "fig_sensitivity.png")


def fig_current():
    import h5py
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    ps.setup()
    D = designs()
    rows = [("C_ghost", "ghost", "ghost"), ("C_bat_pm", "bat_pm", "bat (tail-fed)")]
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw=dict(width_ratios=[0.8, 1.6]))
    cm = LinearSegmentedColormap.from_list("seq", ["#f6f9fd", "#9ec5f4", "#3987e5", "#184f95",
                                                   "#0d366b"])
    for ax, (case, key, lab) in zip(axs, rows):
        try:
            sm, _ = find(case)
        except KeyError:
            continue
        fn = os.path.join(antsim.OUT, sm["tag"], "Hplane.h5")
        if not os.path.exists(fn):
            continue
        with h5py.File(fn, "r") as h:
            x = np.array(h["Mesh/x"]) * 1e3
            y = np.array(h["Mesh/y"]) * 1e3
            H = np.array(h["FieldData/FD/f0"])          # complex, order N(comp), X, Y, Z
        mag = np.sqrt(np.sum(np.abs(H[:2]) ** 2, axis=0)).squeeze()   # tangential |H|
        m = mag / np.percentile(mag, 99.5)
        pc = ax.pcolormesh(x, y, np.clip(m, 1e-3, 1).T, shading="auto", cmap=cm,
                           norm=LogNorm(vmin=1e-2, vmax=1))
        from matplotlib.path import Path
        gx, gy = np.meshgrid(np.linspace(x.min(), x.max(), 600), np.linspace(y.min(), y.max(), 400))
        pts = np.c_[gx.ravel(), gy.ravel()]
        mask = np.zeros(len(pts), bool)
        for P in D[key]["polys"]:
            mask |= Path(np.asarray(P, float)).contains_points(pts)
        ax.contour(gx, gy, mask.reshape(gx.shape).astype(float), levels=[0.5], colors=[ps.INK],
                   linewidths=0.6)
        ax.axhline(0, color=ps.INK, lw=0.8)
        ax.set_aspect("equal")
        ax.grid(False)
        ax.set_xlabel("x (mm)")
        ax.set_title(lab, fontsize=9.5)
    axs[0].set_ylabel("y (mm)")
    cb = fig.colorbar(pc, ax=list(axs), shrink=0.85)
    cb.set_label("normalised, log scale")
    fig.suptitle("Tangential |H| in the copper plane at 2.44 GHz: dark = strong field, "
                 "i.e. where the current crowds", fontsize=10, color=ps.INK)
    save(fig, "fig_current.png")


if __name__ == "__main__":
    which = sys.argv[1:] or ["validation", "candidates", "winner", "bat", "patterns",
                             "sensitivity", "current"]
    for w in which:
        globals()[f"fig_{w}"]()
