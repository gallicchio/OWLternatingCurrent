#!/usr/bin/env python3
"""
matching.py -- what the antenna-side pi network has to do.

Espressif's hardware guidelines (and TI's DN007) reserve a pi network (shunt -
series - shunt) right at the antenna feed for tuning.  Given a simulated Zin(f),
this finds the two-element L-network solutions that put Zin(f_c) exactly on 50 ohm,
maps each onto the pi footprint (one shunt position left unpopulated), snaps the
values to the E24-ish 0201/0402 series that exist at 2.4 GHz, and evaluates the
matched S11(f) with finite component Q.

All values are ideal two-terminal elements; the pads, the 0402 parasitics and the
trace between them are the bench's job (README, tuning plan).
"""
import numpy as np

Z0 = 50.0

# what you can actually buy as 0402 RF parts (Murata GJM / LQW15/LQP15 series)
C_SERIES = np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8,
                     2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5,
                     8.2, 9.1, 10.0, 12.0, 15.0, 18.0, 22.0]) * 1e-12
L_SERIES = np.array([0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
                     4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10.0, 12.0, 15.0, 18.0, 22.0]) * 1e-9


def _z_elem(kind, val, f, q):
    w = 2 * np.pi * f
    if kind == "L":
        x = w * val
        return x / q + 1j * x
    x = -1 / (w * val)
    return abs(x) / q + 1j * x


def snap(kind, val):
    s = L_SERIES if kind == "L" else C_SERIES
    return float(s[np.argmin(abs(np.log(s / val)))])


def l_networks(zl, f):
    """Lossless L-sections matching zl -> Z0 at f.  Each: list of (topo, kind, value)
    from the antenna outward: ('shunt'|'series', 'L'|'C', value)."""
    w = 2 * np.pi * f
    rl, xl = zl.real, zl.imag
    sols = []
    # (a) shunt element at the antenna, then series element toward the source
    yl = 1 / zl
    gl, bl = yl.real, yl.imag
    if gl > 0 and 1 / gl >= Z0 * (1 - 1e-12):          # need G_l <= 1/Z0
        # want Re{1/(gl + j(bl+b))} = Z0
        for sgn in (+1, -1):
            disc = gl / Z0 - gl ** 2
            if disc < 0:
                continue
            b = -bl + sgn * np.sqrt(disc)
            y1 = gl + 1j * (bl + b)
            z1 = 1 / y1
            x = -z1.imag
            sols.append([("shunt", b), ("series", x)])
    # (b) series element at the antenna, then shunt element toward the source
    if rl > 0 and rl <= Z0:
        for sgn in (+1, -1):
            x = -xl + sgn * np.sqrt(rl * (Z0 - rl))
            z1 = rl + 1j * (xl + x)
            y1 = 1 / z1
            b = -y1.imag
            sols.append([("series", x), ("shunt", b)])
    nets = []
    for s in sols:
        net = []
        for topo, v in s:
            if abs(v) < 1e-12:
                continue
            if topo == "series":            # reactance x
                net.append((topo, "L", v / w) if v > 0 else (topo, "C", -1 / (w * v)))
            else:                            # susceptance b
                net.append((topo, "C", v / w) if v > 0 else (topo, "L", -1 / (w * v)))
        nets.append(net)
    return nets


def apply(zl, f, net, qL=40.0, qC=200.0, snapped=True):
    """Input impedance seen through `net` (antenna first) at frequencies f."""
    z = np.array(zl, complex)
    for topo, kind, val in net:
        v = snap(kind, val) if snapped else val
        ze = _z_elem(kind, v, f, qL if kind == "L" else qC)
        z = z + ze if topo == "series" else 1 / (1 / z + 1 / ze)
    return z


def s11(z):
    return (z - Z0) / (z + Z0)


def describe(net, snapped=True):
    out = []
    for topo, kind, val in net:
        v = snap(kind, val) if snapped else val
        unit = "nH" if kind == "L" else "pF"
        out.append(f"{topo} {kind} {v*1e9 if kind == 'L' else v*1e12:.2g} {unit}")
    return ", ".join(out) if out else "nothing (0 ohm link)"


# 0402 inductors above ~10 nH self-resonate near 3 GHz, so their value at 2.44 GHz is
# far from nominal: networks needing one are not offered.
L_MAX = 10e-9


def best_match(f, zin, fc=2.442e9, qL=40.0, qC=200.0, l_max=L_MAX):
    """Pick the L-network that maximises the worst-case in-band return loss
    (2.400-2.484 GHz) after snapping to real part values.  Returns (net, s11dB_matched)."""
    band = (f >= 2.400e9) & (f <= 2.484e9)
    zc = np.interp(fc, f, zin.real) + 1j * np.interp(fc, f, zin.imag)
    best = None
    cands = [n for n in l_networks(zc, fc)
             if all(not (k == "L" and v > l_max) for (_, k, v) in n)]
    # also allow the pure single-element fixes (series or shunt only) and nothing
    cands.append([])
    for net in cands:
        zm = apply(zin, f, net, qL, qC)
        sdb = 20 * np.log10(np.abs(s11(zm)))
        worst = sdb[band].max()
        if best is None or worst < best[2]:
            best = (net, sdb, worst)
    return best[0], best[1]


def mismatch_loss_db(s11db):
    return -10 * np.log10(1 - 10 ** (s11db / 10))


def network_efficiency(zl, f, net, qL=40.0, qC=200.0, snapped=True):
    """Fraction of the power accepted at the network input that reaches the antenna."""
    zl = np.array(zl, complex)
    A = np.ones_like(zl)
    B = np.zeros_like(zl)
    C = np.zeros_like(zl)
    D = np.ones_like(zl)
    # cascade from the source side: the net is listed antenna-first
    for topo, kind, val in reversed(net):
        v = snap(kind, val) if snapped else val
        ze = _z_elem(kind, v, f, qL if kind == "L" else qC)
        if topo == "series":
            a, b, c, d = 1, ze, 0, 1
        else:
            a, b, c, d = 1, 0, 1 / ze, 1
        A, B, C, D = A * a + B * c, A * b + B * d, C * a + D * c, C * b + D * d
    IL = 1.0
    VL = zl * IL
    Vin = A * VL + B * IL
    Iin = C * VL + D * IL
    return np.real(VL * np.conj(IL)) / np.real(Vin * np.conj(Iin))
