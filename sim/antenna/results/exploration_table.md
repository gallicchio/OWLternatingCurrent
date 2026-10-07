# Every simulated candidate (0.5 mm mesh unless the name starts with C_ = 0.25 mm)

Columns as in README §4. The second row of each case is the best two-element pi/L match on real 0402 values (inductors <= 10 nH, Q_L 40, Q_C 200), with its matched -10 dB band, matched worst in-band |S11|, the spread for a +/-0.1 pF capacitor error, and the loss in the network.

| case | f(S11 min) GHz | S11 min dB | −10 dB band GHz | worst in band dB | Z(2.44) Ω | η_rad | gain dBi |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_batifa_span36 | 1.800 | -3.9 | — | **-1.4** | 14 +75j | 97 % | 2.6 |
|   ↳ pi network: shunt C 0.4 pF, series C 0.5 pF | | | 2.338–2.571 | -17.5 (±0.1 pF: -3.9/-6.3) | | net loss 0.12 dB | |
| A_batifa_span44 | 1.800 | -2.1 | — | **-1.6** | 14 +73j | 95 % | 3.1 |
|   ↳ pi network: series C 1.3 pF, shunt C 2 pF | | | 2.298–2.603 | -21.2 (±0.1 pF: -12.6/-14.1) | | net loss 0.11 dB | |
| A_batifa_span52 | 2.096 | -1.4 | — | **-0.8** | 8 +74j | 95 % | 2.3 |
|   ↳ pi network: series C 0.7 pF, shunt L 1.5 nH | | | 2.384–2.504 | -12.7 (±0.1 pF: -2.7/-3.6) | | net loss 0.50 dB | |
| B_batifa_scale0.62 | 2.061 | -5.4 | — | **-2.1** | 9 +31j | 97 % | 2.8 |
|   ↳ pi network: shunt C 1.3 pF, series C 1.1 pF | | | 2.251–2.607 | -20.2 (±0.1 pF: -14.8/-14.1) | | net loss 0.08 dB | |
| B_batmono_span46 | 2.890 | -4.7 | — | **-3.9** | 113 +106j | 98 % | 2.5 |
|   ↳ pi network: shunt C 0.8 pF, series L 5.6 nH | | | 2.297–2.760 | -15.8 (±0.1 pF: -10.5/-18.7) | | net loss 0.22 dB | |
| A_batdip_span40 | 2.873 | -37.6 | — | **-5.1** | 17 -13j | 94 % | 5.0 |
|   ↳ pi network: series C 5.6 pF, shunt L 2.4 nH | | | 2.306–2.661 | -21.2 (±0.1 pF: -20.7/-21.1) | | net loss 0.17 dB | |
| A_batdip_span46 | 2.494 | -31.8 | 2.286–2.804 | **-17.2** | 43 +2j | 96 % | 5.1 |
|   ↳ pi network: series C 3.3 pF, shunt L 8.2 nH | | | 2.253–2.739 | -23.3 (±0.1 pF: -23.0/-23.6) | | net loss 0.05 dB | |
| A_batdip_span52 | 2.260 | -24.8 | 2.089–2.508 | **-10.7** | 83 -5j | 96 % | 5.1 |
|   ↳ pi network: shunt C 0.6 pF, series L 2.7 nH | | | 2.206–2.715 | -24.2 (±0.1 pF: -19.2/-19.6) | | net loss 0.11 dB | |
| B_legfed_span46 | 3.062 | -9.2 | — | **-2.4** | 26 +77j | 91 % | 5.2 |
|   ↳ pi network: series C 1.3 pF, shunt C 1.3 pF | | | 2.357–2.524 | -14.3 (±0.1 pF: -13.4/-11.5) | | net loss 0.07 dB | |
| B_legfed_span50 | 2.922 | -13.9 | — | **-3.6** | 61 +91j | 93 % | 5.3 |
|   ↳ pi network: shunt C 1.1 pF, series L 5.6 nH | | | 2.336–2.537 | -15.1 (±0.1 pF: -12.7/-10.4) | | net loss 0.27 dB | |
| B_splitifa_span46 | 2.990 | -7.4 | — | **-2.5** | 28 +78j | 94 % | 4.7 |
|   ↳ pi network: shunt C 0.2 pF, series C 0.7 pF | | | 2.348–2.567 | -17.2 (±0.1 pF: -7.7/-9.3) | | net loss 0.06 dB | |
| B_splitifa_span50 | 2.849 | -9.9 | — | **-3.6** | 54 +86j | 94 % | 5.0 |
|   ↳ pi network: shunt C 1.1 pF, series L 5.6 nH | | | 2.348–2.570 | -16.3 (±0.1 pF: -10.8/-12.7) | | net loss 0.24 dB | |
| B2_splitifa_span48_yb7 | 3.007 | -15.6 | — | **-3.4** | 26 +58j | 93 % | 4.9 |
|   ↳ pi network: series C 2 pF, shunt C 1.2 pF | | | 2.351–2.566 | -16.7 (±0.1 pF: -14.4/-15.5) | | net loss 0.05 dB | |
| B2_batpm_span36 | 2.986 | -9.8 | — | **-7.7** | 85 +48j | 98 % | 2.4 |
|   ↳ pi network: shunt C 1 pF, series L 3.6 nH | | | 2.163–2.772 | -25.3 (±0.1 pF: -18.3/-17.3) | | net loss 0.16 dB | |
| B5_batpm_span40 | 2.954 | -8.5 | — | **-6.7** | 90 +56j | 98 % | 2.4 |
|   ↳ pi network: shunt C 1 pF, series L 3.9 nH | | | 2.176–2.739 | -23.8 (±0.1 pF: -18.0/-16.1) | | net loss 0.18 dB | |
| B2_batpm_span44 | 2.929 | -7.4 | — | **-6.0** | 96 +66j | 98 % | 2.4 |
|   ↳ pi network: shunt C 0.9 pF, series L 4.3 nH | | | 2.241–2.804 | -18.7 (±0.1 pF: -13.5/-20.3) | | net loss 0.17 dB | |
| B5_batpm_span44_fw3.5 | 2.933 | -7.7 | — | **-6.4** | 104 +57j | 97 % | 2.3 |
|   ↳ pi network: shunt C 0.9 pF, series L 4.3 nH | | | 2.206–2.727 | -24.1 (±0.1 pF: -16.0/-16.4) | | net loss 0.18 dB | |
| B2_batpm_span52 | 2.880 | -5.4 | — | **-4.6** | 114 +88j | 97 % | 2.2 |
|   ↳ pi network: shunt C 0.9 pF, series L 5.1 nH | | | 2.228–2.652 | -21.0 (±0.1 pF: -15.5/-13.3) | | net loss 0.24 dB | |
| B2_batpm_span44_yb10 | 1.800 | -6.1 | — | **-4.8** | 143 +74j | 98 % | 2.2 |
|   ↳ pi network: shunt C 0.8 pF, series L 5.1 nH | | | 2.209–2.690 | -23.0 (±0.1 pF: -15.3/-14.0) | | net loss 0.23 dB | |
| A_ghost_R9.5 | 3.200 | -13.3 | — | **-9.2** | 98 +17j | 98 % | 2.3 |
|   ↳ pi network: shunt C 0.8 pF, series L 3.3 nH | | | 2.078–2.805 | -25.5 (±0.1 pF: -20.1/-17.8) | | net loss 0.14 dB | |
| A_ghost_R8 | 3.185 | -14.5 | 1.922–>3.2 | **-11.1** | 79 +20j | 98 % | 2.5 |
|   ↳ pi network: shunt L 10 nH, series C 1.6 pF | | | 2.159–3.200 | -27.0 (±0.1 pF: -24.9/-25.3) | | net loss 0.08 dB | |
| B_ghost_R8_stub0.3_fw1.8 | 2.200 | -17.4 | 1.946–>3.2 | **-13.0** | 75 +8j | 98 % | 2.4 |
|   ↳ pi network: shunt L 8.2 nH, series C 1.8 pF | | | 2.158–3.200 | -27.2 (±0.1 pF: -24.3/-27.9) | | net loss 0.08 dB | |
| B_ghost_R8.5_stub0.3_fw2.4 | 2.149 | -17.2 | 1.906–>3.2 | **-11.9** | 81 +5j | 98 % | 2.4 |
|   ↳ pi network: shunt C 0.7 pF, series L 2.7 nH | | | 2.075–2.910 | -27.0 (±0.1 pF: -20.2/-20.5) | | net loss 0.11 dB | |
| B2_ghost_R8_stub0_fw2.4 | 2.215 | -20.1 | 1.957–>3.2 | **-13.6** | 73 +3j | 98 % | 2.4 |
|   ↳ pi network: shunt L 7.5 nH, series C 2 pF | | | 2.140–3.200 | -28.1 (±0.1 pF: -27.3/-26.2) | | net loss 0.08 dB | |
| B3_ghost_R8_flat0.3 | 2.239 | -23.3 | 1.974–>3.2 | **-14.5** | 70 -1j | 98 % | 2.4 |
|   ↳ pi network: shunt C 0.6 pF, series L 2 nH | | | 2.057–3.200 | -27.0 (±0.1 pF: -23.9/-20.5) | | net loss 0.08 dB | |
| B3_ghost_R8_flat0.15 | 2.254 | -28.2 | 1.987–>3.2 | **-15.0** | 67 -5j | 98 % | 2.4 |
|   ↳ pi network: shunt L 6.8 nH, series C 2.2 pF | | | 2.139–3.200 | -28.0 (±0.1 pF: -26.3/-27.8) | | net loss 0.08 dB | |
| B3_ghost_R7.5_flat0.3 | 2.290 | -27.2 | 2.018–>3.2 | **-16.5** | 64 -1j | 98 % | 2.5 |
|   ↳ pi network: shunt L 7.5 nH, series C 2.4 pF | | | 2.145–3.200 | -26.7 (±0.1 pF: -25.5/-27.4) | | net loss 0.07 dB | |
| B4_ghost_R7.5_flat0.15 | 2.301 | -33.1 | 2.028–>3.2 | **-16.9** | 63 -3j | 98 % | 2.5 |
|   ↳ pi network: shunt L 7.5 nH, series C 2.7 pF | | | 2.128–3.200 | -28.7 (±0.1 pF: -28.6/-28.0) | | net loss 0.07 dB | |
| B4_ghost_R7_flat0.3 | 2.342 | -34.7 | 2.064–>3.2 | **-19.1** | 59 -1j | 98 % | 2.5 |
|   ↳ pi network: shunt C 0.5 pF, series L 1.5 nH | | | 2.108–3.200 | -28.1 (±0.1 pF: -23.7/-23.2) | | net loss 0.06 dB | |
| C_ghost | 2.348 | -36.7 | 2.069–>3.2 | **-19.5** | 58 -1j | 98 % | 2.5 |
|   ↳ pi network: shunt L 9.1 nH, series C 3.3 pF | | | 2.134–3.200 | -28.9 (±0.1 pF: -28.2/-29.2) | | net loss 0.05 dB | |
| C_bat_pm | 2.932 | -7.5 | — | **-6.0** | 95 +65j | 98 % | 2.3 |
|   ↳ pi network: shunt C 0.9 pF, series L 4.3 nH | | | 2.241–2.805 | -18.7 (±0.1 pF: -13.5/-20.5) | | net loss 0.17 dB | |
| C_dn007_onboard | 2.300 | -14.9 | — | **-8.6** | 35 +24j | 95 % | 3.3 |
|   ↳ pi network: shunt C 1.1 pF, series L 0.6 nH | | | 2.306–2.624 | -20.3 (±0.1 pF: -19.9/-19.0) | | net loss 0.04 dB | |
