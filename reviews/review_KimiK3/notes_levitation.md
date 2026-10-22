# Review: the levitation (DESIGN_REVIEW.md question 3)

Reviewer: sub-agent for question 3. All numbers below were recomputed, not taken from
comments. Simulations were run in the copy at `review_KimiK3/project/` (numpy/scipy/
matplotlib present); the probe scripts are `review_KimiK3/probe_*.py`. The
magnetics toolkit passes its own closed-form self-tests (loop on-axis B, disc-magnet
on-axis B, Neumann vs elliptic mutual inductance, Lorentz vs I1·I2·dM/dz force,
sphere=dipole) to ≤0.02 %, and my two independent integrations of the bias–bat force
(Lorentz-on-surface-currents vs summed elliptic-integral dM/dz) agree to 0.3 %
(35.35 vs 35.46 mN), so the field math itself is trustworthy.

## Answers to the five questions (summary)

1. **Small-signal: yes, the margin is real.** My own Bode of the linearised loop with
   the shipped gains (bw 10 Hz, ζ 0.7, ki_div 8, dfilt 50 Hz, k_neg 5.008 N/m,
   m 3.6 g) gives crossover 15.3 Hz, phase margin 42.8°, and adding the 1-tick delay,
   the coil L/R pole (2.76 Ω/30.1 µH → 14.6 kHz) and the DRV5055's 20 kHz bandwidth
   costs 0.65° total — everything electrical is ≥600× above crossover. **But the
   large-signal behaviour is mis-modelled everywhere**: with 40 kHz PWM on a 30.1 µH
   coil the current ripple is amperes peak-to-peak, the DRV8874's fixed-off-time
   ITRIP (3.3 A) engages above ≈2.0 A *mean*, and the actuator goes non-monotonic
   (see finding 2). No sim or test models this.
2. **Yes.** The coil's own field at the sensor (≈3 mT/A, ~1 mm of apparent gap per
   amp — not negligible) is modelled and subtracted in both the sim and the firmware,
   the firmware's coupling constant is measured at runtime by CAL, and the sensor
   (DRV5055A4 = the *low*-sensitivity variant, 7.5 mV/mT, ±176 mT linear range at
   3.3 V — verified against the datasheet in `datasheets/txt/`) has huge headroom
   over the ~40 mT total field at the float gap. Details below.
3. **The magnetics check out — but the question's own geometry parenthetical is
   wrong.** The magnets are on *opposite* faces of the 1.6 mm perch: face-to-face
   separation is 14.05 + ~1.5 + 8.54 ≈ **24 mm, not 5.55 mm** (14.05 − 8.5 mixes a
   height above the board with a depth below it). At 5.55 mm the force would be
   ~1.66 N (47× the bat's weight). The sims use the correct 24 mm geometry
   (verified: their g0, k_neg, B_bias, B_bat reproduce only with the correct
   stack-up). The coil's force authority, however, is overstated in the shipped
   tables because the tables were computed for the *previous* coil (finding 1).
4. **The host tests are genuinely adversarial** (off-equilibrium catches on an
   unstable plant from both sides, taps, 3×-weight pulls, hand removal, open coil,
   reversed coil/sensor, no-bat, VQ error, thermal). Two blind spots: the plant and
   the controller tables come from the same generator run (common-mode table errors
   are invisible — exactly what happened in finding 1), and VQ is only tested at
   ±3 mT while the datasheet allows ±8 mT (finding 4).
5. **No unit or sign errors found** in `lev_ctrl.c` (I checked every term's units and
   the signs of the error, integrator, zero-power loop, polarity logic, anti-windup,
   and the CAL arithmetic). Constants are physically plausible with one stale set
   (finding 1) and one wrong-coil resistance (finding 6). One documentation mass
   mismatch (3.6 vs 3.7 g, nit).

## Findings

### 1. MAJOR — the shipped levitation tables were computed for the wrong coil, and the generator can no longer run

- Where: `firmware/src/lev_table.h:16,19` (and the whole `LEV_TAB_KCOIL_N_PER_A`
  array), `firmware/test/lev_plant.h:16` (and `PLANT_FCOIL_N_PER_A`),
  `firmware/tools/gen_lev_tables.py:53`; coil definition `gen/parts.py:226`.
- What: the committed coil-derived numbers — `LEV_KCOIL_N_PER_A` = 20.410 mN/A,
  `LEV_BCOIL_MT_PER_A` = 3.1118 mT/A, `KCOIL(1.5 mm)` = 75.553 mN/A — match the
  *previous* coil (4 layers, 11 turns, r 4–15 mm) **digit for digit** when I
  recompute them (my values: 20.409 mN/A, 3.1118 mT/A, 75.553 mN/A). The coil as
  drawn today (`gen/parts.py`: 3 layers, 14 turns + fractions ≈ 42.6 turns, r 4–15,
  0.5 mm track) gives **19.15 mN/A (−6.2 %)** and **2.933 mT/A (−5.7 %)**; even the
  idealized 3×14-turn spiral gives 18.62 mN/A. History: `lev_table.h` added in
  1f893d9 with 21.18 mN/A (the canonical 4-layer sim coil!), updated in f314c47 to
  the 11-turn/4-layer value; the coil was redesigned to 3-layer/14-turn in c43bab5
  and the tables were never regenerated.
- The generator now **fails its own assertion**: `gen_lev_tables.py:53` asserts
  `COIL_LEV["layers"] (3) == len(Z) (4)` — rerunning it crashes before writing
  anything. A naive fix (passing all of `levitation.py`'s 4-entry Z) would model a
  nonexistent 4th layer on B.Cu; the correct model is the spiral on `Z[:3]` (F.Cu,
  In1, In2) while keeping ZB = −1.485 mm for the bat/sensor geometry.
- The magnet-side columns (`LEV_TAB_FBIAS_N`, `LEV_TAB_BBAT_MT`, g0, k_neg, B_bias)
  are **not** affected: I reproduced g0 = 8.5370 mm, k_neg = 5.0080 N/m,
  B_bias = 6.3638 mT, B_bat(g0) = 33.67 mT exactly with the current geometry.
- Impact: loop gain is ~6.5 % low (phase margin drops ~1–2°; I re-ran the full
  `test_lev` suite against a plant patched with the true drawn coil — all cases
  still pass, CAL correctly measures 2.94 mT/A vs the plant's 2.933). `kcs` is
  measured by CAL at runtime (auto_cal defaults on), so the feedthrough subtraction
  self-corrects; the force table `LEV_TAB_KCOIL_N_PER_A` used in `i = f/kc`
  (lev_ctrl.c) does not. All step-catch peak currents the tests report are
  understated by ~6 %.
- Proposed fix: fix the generator (coil on `Z[:3]`, ZB kept from the full stack;
  ideally use the drawn per-layer turns 14.5/14.07/14.07 and track-centre radii
  14.75→4.25 mm), regenerate both headers, and add a regeneration check to the
  build so the tables can't silently go stale again.
- Confidence: very high (digit-for-digit match to the old coil; direct
  recomputation with a self-tested field solver).

### 2. MAJOR — 40 kHz PWM on a 30.1 µH coil: ITRIP chopping engages above ~2.0 A mean; the actuator goes non-monotonic; modelled nowhere

- Where: `config.h:39` (LEV_PWM_HZ 40 kHz), `config.h:33` (DRV_ITRIP_A 3.3 A,
  IMODE=GND = fixed off-time, t_off = 25 µs per the DRV8874 datasheet, slow decay);
  plant models that assume mean voltage: `sim/physics/levitation_loop.py`
  (`L dI/dt = V − R I` with `V = R·I_cmd`), `firmware/test/lev_plant.h`/`test_lev.c`
  (per-step exponential toward `u·V12/R`), `lev_ctrl.c:601` (`u = i·R/v12`).
- What: volt-second balance on 30.1 µH / 2.76 Ω at 12 V gives enormous ripple. A
  switching-level simulation (`probe_pwm.py`, 10 ns steps, centre-aligned pulses,
  brake off-time, fixed 25 µs off-time chopping at 3.3 A):

  | commanded mean (A) | actual mean (A) | peak (A) | ripple p-p (A) |
  |---:|---:|---:|---:|
  | 0.3 | 0.30 | 0.71 | 0.63 |
  | 1.0 | 1.00 | 1.98 | 1.64 |
  | 2.0 | 2.00 | 3.15 | 2.24 |
  | 2.4 | **1.62** | 3.30 (chops) | 2.98 |
  | 3.0 | **1.50** | 3.30 (chops) | 2.97 |

  Above ≈2.05 A commanded mean, the peak hits ITRIP and the fixed 25 µs off-time (a
  whole PWM period, during which the current collapses most of the way to zero)
  makes the delivered mean *fall* to ~1.5 A. The actuator gain **inverts** exactly
  where the controller pushes hardest. Consequences:
  - The usable force ceiling is ≈ 2.0 A × 19.1 mN/A ≈ 38 mN against the bat's
    35.3 mN weight — about 8 % margin for recovery acceleration, not the
    57 mN (3.0 A × 19.1) the numbers suggest. README's "the bridge's 12 V/3.35 Ω
    limit is 3.6 A" and `config.h:62`'s `LEV_I_MAX_A 3.0 /* catches peak at 2.4 A */`
    are unreachable as mean currents.
  - Every host-test case peaking above ~2.1 A is unphysical on hardware: all four
    "step to g0" catches (2.14–2.87 A) and the VQ-error catches (2.2 A). Only the
    shipped default — the soft catch with `ramp_mm_s = 6` (peaks ≤1.6 A, even with
    a +10 % bat) — stays in the linear regime. A hard pull or sloppy placement that
    drives the command past 2.1 A may drop the bat where the sims say it holds.
  - The mean-current estimate `i_now` still uses the mirror above 0.4 A
    (lev_ctrl.c), so the loop is not lied to about the current; but nothing
    protects against the gain collapse/inversion between 2.1 and 3.0 A of command.
- Proposed fix (best): raise the levitation PWM to 150–200 kHz — the DRV8874
  tolerates it (tPD 400 ns, t_rise/fall 150 ns ≪ 5 µs period), the tick is already
  phase-locked (`rt.c` `align_lev_and_tick`), and ripple scales 1/f: at 160 kHz the
  ripple at 2.4 A mean is ≈0.6 A p-p, peak ≈2.7 A < 3.3 A, so the mean model holds
  to the full i_max. (Note the 80 kHz bat-power carrier mode already runs the same
  slice faster with no levitation problem reported.) If the frequency stays 40 kHz,
  cap `LEV_I_MAX_A` at ~1.8 A, document the reduced catch envelope, and never ship
  `ramp_mm_s = 0`. Either way, add ripple/ITRIP to the test plant before trusting
  the ±3 mm catch claims.
- Confidence: high on the physics (arithmetic cross-checked two ways); the exact
  clipped-mean values depend on decay-mode details, so the ~1.5 A figure is ±20 %.

### 3. MINOR — worst-case DRV5055 VQ defeats the catch window (fail-safe)

- Where: `firmware/test/test_lev.c:326` tests VQ error only at ±3 mT; the datasheet
  allows VQ = 1.59–1.71 V, i.e. ±60 mV = **±8 mT** at 7.5 mV/mT (config.h:73-75
  quotes this). `lev_ctrl.c` `catch_mm` default 5.0 mm.
- Evidence: I ran the copy's suite with `vqs = {−8, +8}`: **+8 mT catches fine;
  −8 mT never catches** a bat resting at g0+3 mm (the field there changes only
  ~3 mT/mm, so −8 mT reads as ~14.2 mm — outside the ±5 mm window; the loop never
  engages, no current driven).
- Impact: at the datasheet corner the effective catch window shrinks by ~2.5–2.7 mm;
  a hand-placed or cradle-resting bat near the window's edge simply isn't caught.
  Benign (fail-safe), and recoverable with `lev cal zero` (bat removed), but the
  firmware's own comment ("the DRV5055's VQ tolerance (8 mT: ~2 mm there)") shows
  the window was sized for this and it doesn't quite cover it.
- Proposed fix: run the zero calibration automatically before the first enable when
  no bat is seen (the `range=+1` "no bat" detector already exists), or widen
  `catch_mm` to ~7 mm, or document that a bat that won't catch needs `lev cal zero`.
- Confidence: high (reproduced in the shipped test harness, one-line change).

### 4. MINOR — `levitation_loop.py` (the sim the firmware says it ports) simulates the old design

- Where: `sim/physics/levitation_loop.py:31-32,38` — M_BAT 2.7 g, L 31.5 µH,
  R 3.35 Ω, bias magnet 4×1 mm at 3 mm lift, canonical 4-layer coil (B_coil
  3.69 mT/A), sensor "25 mV/mT (A3-like)". The shipped design is 3.6 g, 30.1 µH,
  2.56 Ω, 10×2 mm at 14 mm, 3-layer coil (2.93 mT/A), DRV5055A4 7.5 mV/mT.
- Evidence: ran it in the copy — equilibrium 8.38 mm, k_neg 6.4 N/m, coil
  −21.8 mN/A, B_bat(g0) ≈ −39 mT: the old two-magnet design throughout. The README
  results table (jitter 0.4 µm, "3 mm off → 2.4 A peak") and the firmware's
  bw/dfilt defaults trace to this plant, not the shipped one.
- Impact: limited — `lev_ctrl.c` was re-validated by the C host test against the
  one-magnet plant (`lev_plant.h`), which passes. But anyone re-running the Python
  sim to retune gains gets numbers for a different product.
- Proposed fix: port `levitation_loop.py` to the one-magnet tables (or make it read
  `lev_plant.h`-equivalent data) and mark the old results as superseded.
- Confidence: very high.

### 5. MINOR — plant and controller tables share one generator run: common-mode errors are invisible to the tests

- Where: `firmware/tools/gen_lev_tables.py` writes both `src/lev_table.h` (the
  controller's calibration) and `test/lev_plant.h` (the test plant) from the same
  arrays. Finding 1 sat undetected partly because of this: the test passed with a
  wrong coil because controller and plant were wrong together.
- Evidence: with the copy's plant patched to the true coil (kc −6.5 %, B_coil
  −5.7 %), the full suite still passes (CAL self-corrects kcs; gains absorb kc);
  with a +10 % heavier bat (3.96 g plant vs 3.6 g controller) every case still
  holds and zero-power pulls the mean current to ≤4 mA — the only "failures" are
  the test's own `gap_err < 0.1 mm` assertion referenced to the nominal g0, while
  the true float point legitimately moved 0.65 mm (ΔW/k_neg = 3.5 mN / 5 N/m
  ✓ physics consistent).
- Proposed fix: add standard perturbation cases (kc/kcs/mass/Br ±10 %) as explicit
  plant-vs-controller mismatches so the suite proves robustness rather than
  identity.
- Confidence: high.

### 6. NIT — the levitation loop's coil resistance is the pendulum coil's

- Where: `firmware/src/thermal.c:33` sets every coil's `r20_ohm = COIL_R20_OHM`
  (2.29 Ω, the pendulum coil; `config.h:46`); the levitation coil is 2.56 Ω
  (`config.h:49` comment, consistent with my estimate 2.49 Ω + vias).
  `test_lev.c:198` likewise feeds the controller `COIL_R20_OHM` with a 2.4 Ω plant.
- Impact: until the thermal module's cold calibration measures the lev coil's true
  R (it does, from the CAL pulses — rt.c:403), `u = i·R/v12` under-delivers ~10 %
  of current (2.49/2.76): a transient −10 % loop-gain error. The integrator absorbs
  it; phase margin impact ~1°. 
- Proposed fix: per-coil `r20` in `thermal_default_params` (lev = 2.56 Ω).
- Confidence: high.

### 7. NIT — bat mass: 3.6 g (code) vs 3.7 g (DESIGN_REVIEW.md question 3 and task text)

- `sim/physics/levitation_onemagnet.py` (M_BAT 3.6e-3, budget 2.0 PCB + 1.18 magnet
  + 0.4 cap = 3.58 g) and `lev_table.h` (LEV_MASS_KG 0.0036) vs "3.7 g" in the
  review doc. 0.1 g moves the float point 0.2 mm; absorbed by the zero-power loop.
  Also "43 turns" vs the drawn ≈42.6 — fine as rounding. Pick one number for the
  docs.
- Confidence: high.

## Checked and found right

- **DRV5055A4 sensitivity/range** (config.h:73): datasheet (datasheets/txt/
  DRV5055A4QDBZR.txt electrical table) gives A4 = 7.1/7.5/7.9 mV/mT and ±176 mT
  linear range at 3.3 V — config.h's "7.5 (7.1–7.9)" is exactly right, and A4 is
  correctly the *low*-sensitivity variant (A1 = 60 mV/mT would rail at ~27 mT; the
  float-gap field is ~40 mT total: bat 33.7 + bias 6.4). VQ 1.59–1.71 V matches the
  firmware's ±60 mV/±8 mT assumption. Sensor noise in the test (0.03 mT rms)
  matches the datasheet (BND 215 nT/√Hz at 3.3 V → 0.20 mTpp ≈ 0.03 mT rms).
- **DRV8874 constants**: A_IPROPI = 450 µA/A (datasheet) → 0.99 V/A on 2.2 kΩ and
  ITRIP = 3.3/0.99 = 3.33 A ✓; mirror offset ±30 mA below 0.4 A matches the
  firmware's MIRROR_LO/HI blending; fixed off-time = 25 µs slow decay with
  IMODE=GND ✓ as the design doc says.
- **Magnet–magnet force at the true 24 mm separation**: 35.35 mN (Lorentz path,
  mesh-converged to 0.1 %: 35.354/35.434/35.454 mN for nz/nseg 8/64 → 40/256) and
  35.46 mN (independent elliptic-integral dM/dz sum) vs the bat's weight
  35.32 mN (3.6 g) — equilibrium gap 8.537 mm reproduced independently. Magnet mass
  1.18 g for a 10×2 mm disc at 7.5 g/cm³ ✓. Br = 1.43 T is a fair N52 nominal.
- **The geometry**: bias bottom face 14.0 mm (OWL_LIFT; 14.05 mm with the 0.2 mm
  print layer grid — documented in print/README) above top copper; bat top face
  8.537 mm below bottom copper (−1.485 mm). The review question's "~5.55 mm
  separation (14.05 − 8.5)" is wrong — those are opposite sides of the board —
  but the sims model it correctly (the numbers only reproduce with the correct
  24 mm separation; at 5.55 mm the force would be ~1.66 N).
- **Coil force authority in the linear regime**: 19.1 mN/A (drawn coil) at g0 →
  2.0 A gives 38 mN > weight 35.3 mN; fine *below* the ITRIP onset (finding 2).
- **Feedthrough subtraction math**: bat 33.7 mT + bias 6.4 mT + coil 3.11 mT/A·I at
  the sensor; the firmware subtracts bias and kcs·i_now; CAL measures kcs with a
  1–10 mT/A validity window; my recomputation of the true coil's field at the
  sensor (2.93 mT/A) passes that window and CAL in the patched-plant test measured
  2.94 vs plant 2.933 mT/A. The Hall-sign/coil-polarity auto-detection works
  (tested both reversed ways in the suite).
- **Linearized loop vs simulated plant**: the firmware's gain scheduling reads
  k_neg(gap) and kc(gap) from the same tables the plant uses (sched=1); my Bode of
  the shipped gains: PM 42.8° at 15.3 Hz; ±15 % gain error moves PM to ~41–44° —
  no cliff. Kp/Ki/Kd formulas in `update_gains` match the sim's (Ki includes
  k_neg in both).
- **Phase-locking of the ADC burst to the PWM** (`rt.c` `align_lev_and_tick`,
  TOP_TICK = 4× the lev PWM period): the 40 kHz ripple aliases to a *constant*,
  absorbed by calibration/zero-power — the right design. Minimum-pulse dead-band is
  handled by the `min_alt` dither (rt.c:359-371, DRV_MIN_PULSE_S 300 ns).
- **The host test suite is not happy-path-only** (see Q4 summary): catches from
  ±2/±3 mm on both sides of an unstable equilibrium, 5 mN tap, 0.1 N pull-down
  (3× weight) and pull-up release timing, hand removal at 0.2 m/s, open-coil and
  short detection, thermal trip, INHIBIT, no-bat (no false flip), zero-CAL, and
  console parameter bounds. All pass as committed (ran them).
- **lev_ctrl.c units/signs**: checked the measurement frame, error sign
  (gap-too-big → lift), integrator init at catch (m·g − F_bias(gap)), anti-windup
  condition, zero-power loop direction (positive lifting current → smaller gap
  set-point), the float trip-window cap, and `gap_of_field`'s out-of-table paths.
  No defects.
- **levitation_onemagnet.py vs the tables**: its printed k_neg (4.8 N/m) differs
  from the table's 5.008 only by its coarse 0.5 mm secant grid — the generator's
  own cross-check asserts <15 % and notes this. Its "coil grip" column, however,
  uses the canonical 4-layer coil, not the drawn one (part of finding 1).

## Could not check

- **The real DRV8874 + 30 µH coil behaviour in chopping** (device-level details of
  fixed off-time with a near-ideal inductor — my switching model is idealised;
  bench measurement needed). This is the verification gap behind finding 2.
- **Magnet tolerances**: N52 Br spread (±5–10 % on cheap discs) not swept anywhere;
  reasoning says the zero-power loop absorbs it (float point moves ~0.7 mm per
  −10 % force, within zp_range ±2 mm), but untested.
- **Tilt/yaw dynamics of the floating bat** (only vertical and lateral stiffness
  are computed; lateral is +2.5 N/m restoring, a ~4 Hz undamped lateral mode
  exists; tilt relies on dipole alignment torque, not analysed in the repo).
- **The 80 kHz wireless-power carrier running while levitating** (bat's eyes):
  its ±~1 A ripple's feedthrough into the gap estimate (phase-locked, so mostly a
  static offset) is not simulated; `bat_power.py` is another subsystem's review.
- **Mechanical tolerances** of the printed owl (print/README itself notes the base
  may sit ~0.15 mm high, moving the float gap 1:1 — absorbed by the loop).
- **EMI/thermal long-run behaviour** of the levitation coil at 40 kHz ripple
  (ripple RMS ~0.2–0.7 A adds tens to hundreds of mW of copper heating during
  disturbances; zero-power hold is unaffected since I≈0 there).
