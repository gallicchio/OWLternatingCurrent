#!/usr/bin/env python3
"""
mom_dipole.py -- an independent reference for the openEMS free-space dipole check.

A thin-wire method-of-moments solve of a centre-fed straight dipole in free space:
mixed-potential EFIE, piecewise-linear (triangle) basis and Galerkin testing, the
reduced kernel exp(-jkR)/(4 pi R) with R = sqrt((z-z')^2 + a^2), and a delta-gap
source at the centre node.  It shares nothing with the FDTD code -- different
method, different discretisation, different source model -- so agreement between
the two is evidence about the openEMS set-up (port, mesh, boundaries), not a
tautology.

A flat strip of width w is replaced by its equivalent wire, radius a = w/4
(the classical conformal-mapping result for a thin strip).

usage:  em-env python mom_dipole.py [--L 58] [--w 1.0]
"""
import argparse

import numpy as np

C0 = 299792458.0
MU0 = 4e-7 * np.pi
EPS0 = 1.0 / (MU0 * C0 ** 2)
ETA0 = MU0 * C0


def zin_dipole(f, L, a, nseg=121, ngauss=8):
    """Input impedance (ohm) of a centre-fed dipole, length L and radius a (metres)."""
    if nseg % 2 == 0:
        nseg += 1                               # odd segment count -> no node at z=0
    nseg += 1                                    # even -> a node exactly at the gap
    k = 2 * np.pi * f / C0
    w = 2 * np.pi * f
    z = np.linspace(-L / 2, L / 2, nseg + 1)     # nodes; basis on interior nodes
    d = z[1] - z[0]
    gx, gw = np.polynomial.legendre.leggauss(ngauss)
    # quadrature points/weights on every segment
    zs = (z[:-1, None] + z[1:, None]) / 2 + gx[None, :] * d / 2      # (nseg, ng)
    ws = gw[None, :] * d / 2
    zq = zs.ravel()
    wq = np.broadcast_to(ws, zs.shape).ravel()
    seg = np.repeat(np.arange(nseg), ngauss)
    # basis n (interior node n=1..nseg-1): rises on segment n-1, falls on segment n
    nb = nseg - 1
    T = np.zeros((nb, zq.size))
    dT = np.zeros((nb, zq.size))
    for n in range(1, nseg):
        up = seg == n - 1
        dn = seg == n
        T[n - 1, up] = (zq[up] - z[n - 1]) / d
        T[n - 1, dn] = (z[n + 1] - zq[dn]) / d
        dT[n - 1, up] = 1.0 / d
        dT[n - 1, dn] = -1.0 / d
    R = np.sqrt((zq[:, None] - zq[None, :]) ** 2 + a ** 2)
    G = np.exp(-1j * k * R) / (4 * np.pi * R)
    Wt = wq[:, None] * wq[None, :] * G
    Z = 1j * w * MU0 * (T @ Wt @ T.T) + (1.0 / (1j * w * EPS0)) * (dT @ Wt @ dT.T)
    V = np.zeros(nb, complex)
    mid = nb // 2                                 # the node at z = 0
    assert abs(z[mid + 1]) < 1e-12 * L
    V[mid] = 1.0
    I = np.linalg.solve(Z, V)
    return 1.0 / I[mid]


def sweep(L, a, freqs, nseg=121):
    return np.array([zin_dipole(f, L, a, nseg) for f in freqs])


def resonance(freqs, Z):
    """First zero crossing of X (low-to-high), linearly interpolated."""
    X = Z.imag
    i = np.where((X[:-1] < 0) & (X[1:] >= 0))[0]
    if not len(i):
        return np.nan, np.nan
    i = i[0]
    t = -X[i] / (X[i + 1] - X[i])
    return freqs[i] + t * (freqs[i + 1] - freqs[i]), Z.real[i] + t * (Z.real[i + 1] - Z.real[i])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--L", type=float, default=58.0, help="tip-to-tip length, mm")
    ap.add_argument("--w", type=float, default=1.0, help="strip width, mm (a = w/4)")
    a_ = ap.parse_args()
    L, a = a_.L * 1e-3, a_.w / 4 * 1e-3
    f = np.linspace(2.0e9, 3.0e9, 201)
    for n in (61, 121, 241):
        Z = sweep(L, a, f, n)
        fr, rr = resonance(f, Z)
        z244 = Z[np.argmin(abs(f - 2.44e9))]
        print(f"nseg={n:4d}: f_res = {fr/1e9:.4f} GHz, R_res = {rr:.2f} ohm, "
              f"Z(2.44 GHz) = {z244.real:.2f}{z244.imag:+.2f}j ohm")
    # textbook check: a thin half-wave dipole -> ~73 + j42 ohm (induced EMF, a->0)
    lam = C0 / 1e9
    print("half-wave, a = lambda/1e4 :", np.round(zin_dipole(1e9, lam / 2, lam * 1e-4, 201), 2))
