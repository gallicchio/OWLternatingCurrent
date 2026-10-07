#!/usr/bin/env python3
"""
analyze.py -- the numbers in README.md, from the cached results (no solving here).

    em-env python analyze.py            # prints the markdown tables

For every case: f(S11 min), the -10 dB band, worst |S11| in 2.400-2.484 GHz, Zin at
2.44 GHz, radiation efficiency and peak gain (NF2FF), and -- where the bare antenna
needs it -- the antenna-side pi network (real 0402 values, inductor Q 40) and what
the matched band looks like, including a +/-0.1 pF capacitor tolerance spread.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matching as M  # noqa: E402
from make_figs import find  # noqa: E402

BAND = (2.400e9, 2.4835e9)


def band_stats(f, sdb, thr=-10.0):
    m = sdb < thr
    i = int(np.argmin(abs(f - 2.442e9)))
    if not m[i]:
        return np.nan, np.nan
    lo = hi = i
    while lo > 0 and m[lo - 1]:
        lo -= 1
    while hi < len(f) - 1 and m[hi + 1]:
        hi += 1
    return f[lo], f[hi]


def summarize(name, match=False):
    s, a = find(name)
    f, z = a["f"], a["zin"]
    sdb = 20 * np.log10(np.abs(a["s11"]))
    inb = (f >= BAND[0]) & (f <= BAND[1])
    lo, hi = band_stats(f, sdb)
    k = int(np.argmin(abs(a["f_nf"] - 2.44e9)))
    out = dict(name=name, fmin=f[np.argmin(sdb)], smin=sdb.min(), lo=lo, hi=hi,
               worst=sdb[inb].max(), z=z[np.argmin(abs(f - 2.44e9))],
               eta=a["eta"][k], gain=10 * np.log10(a["Dmax"][k] * a["eta"][k]),
               D=10 * np.log10(a["Dmax"][k]), cells=s["cells"], t=s["t_run"] / 60,
               f_hi_edge=f[-1])
    if match:
        net, msdb = M.best_match(f, z)
        mlo, mhi = band_stats(f, msdb)
        eff = M.network_efficiency(z, f, net)
        spread = []
        for dC in (-0.1e-12, +0.1e-12):
            net2 = [(t, k_, v + (dC if k_ == "C" else 0.0)) for (t, k_, v) in
                    [(t, k_, M.snap(k_, v)) for (t, k_, v) in net]]
            zz = M.apply(z, f, net2, snapped=False)
            spread.append(20 * np.log10(np.abs(M.s11(zz)))[inb].max())
        out.update(net=M.describe(net), mworst=msdb[inb].max(), mlo=mlo, mhi=mhi,
                   neteff=float(np.mean(eff[inb])), spread=spread)
    return out


def row(o):
    hi = f"{o['hi']/1e9:.3f}" if o["hi"] < o["f_hi_edge"] - 1 else f">{o['f_hi_edge']/1e9:.1f}"
    band = f"{o['lo']/1e9:.3f}–{hi}" if np.isfinite(o["lo"]) else "—"
    return (f"| {o['fmin']/1e9:.3f} | {o['smin']:.1f} | {band} | **{o['worst']:.1f}** | "
            f"{o['z'].real:.0f} {o['z'].imag:+.0f}j | {100*o['eta']:.0f} % | {o['gain']:.1f} |")


if __name__ == "__main__":
    groups = sys.argv[1:] or ["all"]
    print("| case | f(S11 min) GHz | S11 min dB | −10 dB band GHz | worst in band dB | "
          "Z(2.44) Ω | η_rad | gain dBi |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    names = [l.strip() for l in sys.stdin] if not sys.stdin.isatty() else []
    for n in names:
        try:
            o = summarize(n, match=True)
        except KeyError:
            print(f"| {n} | (missing) |")
            continue
        print(f"| {n} " + row(o))
        if "net" in o:
            print(f"|   ↳ pi network: {o['net']} | | | "
                  f"{o['mlo']/1e9:.3f}–{o['mhi']/1e9:.3f} | {o['mworst']:.1f} "
                  f"(±0.1 pF: {o['spread'][0]:.1f}/{o['spread'][1]:.1f}) | | "
                  f"net loss {-10*np.log10(o['neteff']):.2f} dB | |")


def sensitivity_table(fam, use_match):
    """Rows: variant, worst in-band |S11| (bare or through the NOMINAL network), the
    -10 dB band, f(S11 min) shift vs nominal, eta_rad, gain."""
    s0, a0 = find(f"S_{fam}_nominal")
    net = None
    if use_match:
        net, _ = M.best_match(a0["f"], a0["zin"])

    def curve(a):
        if net is None:
            return 20 * np.log10(np.abs(a["s11"]))
        return 20 * np.log10(np.abs(M.s11(M.apply(a["zin"], a["f"], net))))
    f0 = a0["f"][np.argmin(curve(a0))]
    lines = []
    hdr = ("| variant | worst in band (dB) | −10 dB band (GHz) | f(S11 min) shift | η_rad | "
           "gain (dBi) |")
    lines.append(hdr)
    lines.append("|---|---:|---:|---:|---:|---:|")
    for suffix, lab in [("nominal", "nominal"), ("scale0.95", "shape −5 %"),
                        ("scale1.05", "shape +5 %"), ("er4.2", "FR4 εr 4.2"),
                        ("er4.6", "FR4 εr 4.6"), ("pla2mm", "2 mm PLA lid on the copper"),
                        ("hand15mm", "tissue block 15 mm over it"),
                        ("culoss", "copper loss (35 µm Cu sheet)"),
                        ("mesh0.18", "mesh 0.18 mm"), ("mesh0.35", "mesh 0.35 mm")]:
        try:
            s, a = find(f"S_{fam}_{suffix}")
        except KeyError:
            continue
        f = a["f"]
        sdb = curve(a)
        inb = (f >= BAND[0]) & (f <= BAND[1])
        lo, hi = band_stats(f, sdb)
        hi_s = f"{hi/1e9:.2f}" if hi < f[-1] - 1 else f">{f[-1]/1e9:.1f}"
        band = f"{lo/1e9:.2f}–{hi_s}" if np.isfinite(lo) else "—"
        k = int(np.argmin(abs(a["f_nf"] - 2.44e9)))
        fm = f[np.argmin(sdb)]
        lines.append(f"| {lab} | {sdb[inb].max():.1f} | {band} | {100*(fm/f0-1):+.1f} % | "
                     f"{100*a['eta'][k]:.1f} % | {10*np.log10(a['Dmax'][k]*a['eta'][k]):.2f} |")
    return net, "\n".join(lines)
