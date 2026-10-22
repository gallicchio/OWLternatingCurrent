# Review: the wireless familiars (DESIGN_REVIEW.md question 4)

Scope: `sim/physics/{familiar,familiar_resistors,wpt_link,bat_power}.py`,
`firmware/src/{familiar.c,familiar.h,config.h,coils.c,rt.c,thermal.c,board.c,main.c}`,
`firmware/test/test_familiar.c`, `gen/{sch_base.py,sch_boards.py,coils.py,parts.py,placement.py}`,
`datasheets/UCC27524DR.pdf`. Sims were re-run in the copy (`review_KimiK3/project/`),
plus two extra scripts written for this review (`run_fam150.py`, `run_sweepdark.py`).
`test_familiar` was built and run in the copy: **all tests pass**, including the
board's 10.3 V/A ADC case (no warning printed).

## Short answers to the six questions

1. **Drop or rise? RISE.** A token absorbs power, so the bridge's supply current goes
   *up* (a conductance peak at the coupled mode). The firmware detects a positive peak
   above the learned empty-perch baseline. The words "drop in its own supply current" in
   `DESIGN_REVIEW.md:96` and `README.md:22` are a sign error (docs only; firmware is right).
2. **Robustness:** non-resonant metal (a coin, keys) is rejected by construction (no peak /
   fit r² < 0.8; host-tested). Any *resonant* in-band object (e.g. a phone's Qi coil at the
   sweep's 100 kHz edge) that fits the coupled-tank model **is** driven forever at ≤0.25 W,
   including `FAM_UNKNOWN`. There is no drive timeout, but the physics bounds the hazard
   (≤0.184 A coil current, ~40–70 mW coil heating, ~0.2 W in the object) — benign.
3. **Token LEDs are safe** with the built 150 Ω legs: at the largest perch current the
   4.8 V bridge can *physically* make (0.24 A at 142 kHz, 0.11 A at 303 kHz — duty 0.5,
   verified from |Z|), mean LED currents are ≤ ~9 mA (owl) / ~13 mA (cat); half-cycle
   peaks reach ~33 mA (owl) / ~46 mA (cat), above the 20 mA DC rating only instantaneously.
4. **The UCC27524 "bridge" is legitimate**: the two totem-pole outputs drive the coil
   directly (A through the 10 µF cap), no external FETs, so no shoot-through is possible;
   the PWM (phase-correct, B channel inverted) really does make the ±4.8 V 3-level wave the
   firmware models. One real gap: the driver's output resistance (datasheet ROH 5 Ω typ at
   12 V, higher at 4.8 V) is modelled nowhere — see finding 2.
5. **The sense chain works**: the 10 k·100 n (1 ms, fc = 159 Hz) filter kills the 142/303 kHz
   ripple *before* the OPA2333 (0.1 V → ~0.1 mV), so the amp's 350 kHz GBW (which caps its
   gain at ~2.5 at 142 kHz, not 20.6) is irrelevant; residual output ripple ~0.3 mV vs a
   0.8 mV count. Mux refresh per channel is 0.8 ms — fine against the 1 ms filter.
6. **Unit/sign errors:** the "drop" doc error (finding 1); stale numbers in the sims
   (finding 4); everything else checked dimensionally correct.

## Findings

### 1. minor — "drop in its own supply current" is the wrong sign (documentation)

- **Where:** `DESIGN_REVIEW.md:96`, also `README.md:22`.
- **What:** the docs say a token is found "by the drop in its own supply current". The
  physics is the opposite: a resonant token absorbs power, the perch's conductance peaks
  (firmware model: peak at the coupled mode `ft/sqrt(1−k²)` ≈ 1.13–1.15 × ft), and the
  supply current **rises**. The firmware is correct and self-consistent:
  `familiar.h:1-13` ("more when a token sits on it"), `board_pins.h:61,64` ("rises when
  the owl/cat sits on it"), `fit_begin()` looks for a positive excess ≥ 6σ above
  1.6×baseline (`familiar.c:188-208`).
- **Evidence:** `test_familiar` output (run in the copy): empty perch ≈ 2.5 mA quiescent;
  owl lit: supply 54.0 mA / 242 mW. Reproduced sim: `familiar.py` prints k = 0.47 and the
  token drawing up to ~35 mA of LED current from the perch's field — power must come from
  the bridge.
- **Fix:** s/drop/rise/ in both docs.
- **Confidence:** high.

### 2. major — UCC27524 output resistance is in the measured loop but modelled nowhere

- **Where:** sim `familiar.py` (pure current drive), test `test_familiar.c:134-170`
  (`Z = R1(f) + jwL1`, no driver resistance), firmware `config.h` `FAM_R1_OHM = 4.2`
  (`familiar.c:67-73` `ge_model`/`gt_model`).
- **What:** during a pulse the coil current flows through one pull-up and one pull-down of
  the driver: `R_drv = ROH + ROL` sits in series with the coil's 4.2 Ω (AC). The datasheet
  (`UCC27524DR.pdf`, EC table) gives ROH = 5 Ω typ / 7.5 Ω max (PMOS only; the NMOS boost
  acts only at the switching instant) and ROL = 0.5 Ω typ / 1 Ω max — **at VDD = 12 V**.
  At VDD = 4.8 V the PMOS gate drive is 2.5× weaker, so ROH plausibly rises to ~10–20 Ω.
  The loop's real R could be ~2–4× the modelled 4.2 Ω.
- **Consequences:**
  - The empty-perch conductance model `ge_model` is off by up to ~2–4×. The baseline is
    nominally learned from empty sweeps, **but learning only happens when the sweep shows
    < 3σ excess** (`familiar.c:490`). With a large permanent R mismatch every sweep has
    large excess → `fit_begin` can flag the 100 kHz edge as a "peak" (edge peaks are
    allowed, `familiar.c:204` uses −1e9 for missing neighbours) → fit fails r² → IDLE →
    *never learned*. In that corner the baseline is stuck at the wrong model forever, and
    the fit's R1 assumption (`gt_model`) is also wrong by the same factor; the test only
    covers ±15 % R1 error (`test_familiar.c:325-328`), so this regime is unverified.
  - The power loop is closed on *supply* power (`p_meas = 4.8 V × (I − Iq)`), so driver
    conduction loss (~I_rms² × R_drv, order 0.05–0.2 W at drive) is counted as "delivered":
    the tokens will light, but dimmer than the 0.25 W target suggests.
  - Safe direction: the duty cap computed from the too-small model R1 is *conservative*
    (real |Y| is smaller, so real current at the cap duty is under 0.184 A).
- **Fix:** measure the loop resistance (or the driver drop) on the first board and fold
  `R_drv` into `FAM_R1_OHM` (it is exactly equivalent there); add an `r1_scale = 2..4` case
  to `test_familiar.c`; check the no-learning corner above. If ROH at 4.8 V turns out
  small, downgrade this to a nit.
- **Confidence:** medium that R_drv is several Ω (datasheet + Vgs scaling), low-medium on
  whether it actually breaks detection; that's the point — it's unbounded by any test.

### 3. minor — UCC27524 UVLO start threshold vs the 4.8 V rail

- **Where:** `gen/sch_base.py:892-896` (VDD from "+5V" = 4.8 V), `firmware/src/config.h:68`
  (`V5_PRESENT_V = 4.4`), datasheet UVLO table.
- **What:** UCC27524 "supply start threshold" VON is 3.7/4.2/**4.65 V max** (and "minimum
  operating voltage after start" max 4.40 V). The rail is 4.80 V nominal; with the
  TPS54302's reference and divider tolerance the rail minimum is ~4.68–4.70 V, leaving
  only ~30–50 mV over a worst-case (4.65 V) part. A max-UVLO unit on a min-rail board may
  never enable. It **fails safe** (outputs held low during UVLO, per the datasheet), so the
  familiars would simply be dead on such a unit; once started, 4.8 V is comfortably above
  the falling threshold. Note the firmware gate `v5 > 4.4 V` is *below* the 4.65 V worst-case
  start threshold — harmless (PWM into a held-low driver does nothing).
- **Fix:** accept (typical VON 4.2 V gives 0.6 V margin), or note it for first-board bring-up.
- **Confidence:** high on the numbers; low that any real unit fails.

### 4. minor — sim/firmware inconsistencies (stale frequencies, stale "12 V" bridge, unreachable fault case)

- **Where:** `familiar.py:91` (`f_owl, f_cat = 150e3, 330e3`), `familiar.py:120`
  ("a 12 V full bridge's fundamental is 15.3 V"), `familiar_resistors.py:18`
  (Rs sweep stops at 100 Ω), `test_familiar.c:74-75` (LED legs 77/82 Ω ≈ 68+10),
  `wpt_link.py:32` (token geometry 2-layer, 8 turns, r 4–12 mm — stale).
- **What vs as-built:** the drawn token coil is 12.52 µH (ran `gen/coils.py physics()` in
  the copy: L = 12.52 µH, R = 1.21 Ω; perch = 30.30 µH / 2.129 Ω — matches
  DESIGN_REVIEW §5.2 "30.3 uH, 2.13 ohm"), so the tanks are 142.2 kHz (100 nF) and
  303.2 kHz (22 nF) = `FAM_OWL_HZ`/`FAM_CAT_HZ` exactly. The sim instead idealizes the
  token as 11.51 µH and drives 150/330 kHz; the test's tokens also sit at 150/330 kHz.
  Everything still works (±18 % classify window, ±5 % naming assertion passes), but the
  sims are ~5–8 % off the copper. The "12 V full bridge" print is stale: the bridge is
  4.8 V (fundamental 6.11 V), and the sim's own line "0.2 A needs 11.8 V at 330 kHz" shows
  its 0.2–0.4 A sweep points are physically unreachable at the cat frequency
  (max ≈ 0.11 A) — so `familiar_resistors.py`'s "firmware fault, 0.4 A" case cannot occur,
  and its Rs sweep never included the shipped 150 Ω.
- **Evidence (re-ran with the built 150 Ω legs, `run_fam150.py`):**
  - owl, max possible I1 = 0.237 A: orange 8.8 mA / violet 6.2 mA mean, tank 7.1 Vpk;
  - cat, max possible I1 = 0.112 A: orange 12.8 / violet 9.9 mA mean, tank 9.1 Vpk;
  - LED half-cycle peaks: owl ≈ 33/26 mA, cat ≈ 46/35 mA (orange/violet).
- **Fix:** point `familiar.py` at the drawn-coil inductances (or the 142/303 kHz tanks),
  delete the 12 V print, extend the resistor sweep to 150 Ω, and use 150 Ω in
  `test_familiar.c`'s describing function.
- **Confidence:** high.

### 5. minor — resonant foreign objects are driven forever; no drive timeout (but no hazard)

- **Where:** `familiar.c` state machine (DRIVE has no time limit; `familiar.c:524-530`
  ramps up *any* good fit, including `FAM_UNKNOWN`), `test_familiar.c:322` (a 240 kHz
  "unknown" token is expected to be driven and lit).
- **What:** keys/coins are rejected (no resonance; host-tested, passes). But any object
  whose loop resonates in 100–400 kHz and fits the coupled-tank model at r² ≥ 0.8 — a
  phone's Qi receiver coil resonates around ~100 kHz, at the sweep's lower edge — will be
  announced as a familiar and driven at ≤0.25 W indefinitely. Detection *is*
  frequency-discriminating (peak + model fit + classification window), so a random
  conductor won't trigger, but a random *resonator* will.
- **Hazard bound (verified):** duty is capped so an *empty* perch at that frequency carries
  ≤ 0.92 × 0.2 A (`duty_cap_at`, `familiar.c:346-352`; test asserts ≤ 184 mA in every
  case); the delivered power is closed-loop capped at 0.25 W. Worst continuous perch-coil
  heating ≈ I_rms²·R_AC ≈ (0.1 A)² × 4.2 Ω ≈ 40 mW; token heating ~0.2 W ≈ a few K
  (`familiar.h` header). `thermal.c` does not cover the perch coils — acceptable at these
  powers. So the false trigger is a scene glitch (board says "owl arrived" for a phone),
  not a safety issue.
- **Fix (optional):** don't ramp up `FAM_UNKNOWN`, and/or add a DRIVE on-time limit with
  re-sweep. Cheap insurance.
- **Confidence:** high on the mechanism, medium on a real phone fitting the model.

### 6. minor — ISENSE ADC margin is by construction thin (authors know)

- **Where:** `test_familiar.c:12,351-358` (the board's 10.3 V/A case is "reported, not
  asserted"), `config.h:80-82`, `gen/sch_base.py:924-926`.
- **What:** a count is 78 µA; the sweep's token signal is 0.2–0.5 mA (3–6 counts) with
  ~1.5 counts of noise per sample, rescued by 8× burst oversampling and the 8× 1 ms
  averaging in the sweep. In the copy the board-gain case **passed** (owl found at
  154 kHz), but it is the one case the authors declined to assert. Everything else
  (gain ±10 %, 3× noise, 15 % R1 error) is asserted and passes.
- **Fix:** none required; consider asserting the 10.3 V/A case now that it passes, and keep
  the ADC quiet (the mux settles 100 µs per channel — fine).
- **Confidence:** high.

### 7. nit — leave-detection blind window during RAMP_UP

- **Where:** `familiar.c:537-570`: the leaving logic (slope/conductance drop) only runs in
  `FAM_ST_DRIVE`, not during the 2.5 s `FAM_ST_RAMP_UP`.
- **What:** a token placed and removed within the ramp leaves the bridge driving the empty
  perch at ft until DRIVE's slope logic catches it (~≤1.5 s later); the duty cap makes this
  ≤ 72 mW supply power — harmless, slightly odd behaviour.
- **Fix:** optional; run the same leaving check in RAMP_UP.
- **Confidence:** high.

### 8. nit — fragile coupling: the perch PWM inherits the pendulums' B-inversion

- **Where:** `coils.c:17-21` (`slice_setup` sets phase-correct **and**
  `pwm_config_set_output_polarity(&c, false, true)`), `coils.c:115-119` (`perch_init` calls
  `slice_setup`), `coils.c:157-158` (`pwm_set_both_levels(s, cc, P - cc)`).
- **What:** the perch waveform is only correct *because* channel B is inverted: with
  output = (ctr < CC) XOR inv, A (CC = cc) is a pulse of width 2cc centred on the period
  boundary and B (CC = P−cc, inverted) is a pulse of width 2cc centred on TOP — the
  intended ±4.8 V 3-level drive with fundamental (4/π)·4.8·sin(πd). Without the inversion
  the two pulses would sit a half-period apart with the *same* sign and the fundamental at
  the commanded frequency would be exactly zero (verified by Fourier expansion: both
  non-inverted candidates cancel at f; drive would be all 2f). This is correct today and
  host-tested (`test_rt.c:199-221` checks non-overlap, duty, and models the inversion), but
  a comment at `perch_init` saying "relies on slice_setup's B inversion" would prevent a
  future refactor from silently killing the familiars.
- **Confidence:** high (verified against the RP2350 phase-correct semantics and the
  `test_rt` stub, which implements `(ctr < cc) XOR inv` at `test_rt.c:205-206`).

### 9. nit — assorted small doc/comment mismatches

- `familiar.h:3`: "FAMn_ISENSE is the perch bridge's 5 V supply current" — the rail is
  4.8 V (the same file's math correctly uses FAM_VDRIVE_V).
- `rt.h:64`: "perch current amplitude, A" — it is the *average supply* current, not the
  coil amplitude.
- `sch_base.py:855`: `X_ISENSE` dict is defined and never used.
- The driver's GND pin rides the 0.5 Ω shunt (≤0.1 V at 0.2 A), so the MCU's logic levels
  arrive with ±0.1 V common-mode bounce; UCC27524's fixed TTL thresholds with hysteresis
  make this a non-issue, but it's worth a schematic note.

## Checked and found right

- **Detection sign and threshold (Q1).** Rise, not drop — see finding 1. The two-duty
  sweep algebra `G1 = V(I_hi−I_lo)/((V1²hi−V1²lo)/2)` is dimensionally and numerically
  right, and cancels the drivers' quiescent draw by construction (`familiar.c:466-479`);
  `w3 ≈ 0.97` for the 3rd harmonic at these narrow pulses checks out
  (sin²(3πd)/9/sin²(πd) → 1 as d→0). `gt_model`'s reflected-impedance algebra verified
  symbolically (Re = a·iq/d, Im = −a·x/d — correct).
- **Sim numbers reproduced** (in the copy): L1 = 28.5 µH (idealized), L2 = 11.51 µH,
  M = 8.53 µH, k = 0.47 at 3 mm gap; token Q2 = 4.6 at 150 kHz, 10.0 at 330 kHz; cross-talk
  at 0.2 A drive: wrong token gets ≤0.66 mA (dark). Drawn-copper values via `gen/coils.py`:
  perch 30.30 µH / 2.129 Ω (matches DESIGN_REVIEW §5.2), token 12.52 µH → tanks 142.2 /
  303.2 kHz = the firmware's `FAM_OWL_HZ` / `FAM_CAT_HZ` exactly.
- **Firmware behaviour reproduced:** `make run_test_familiar` passes all cases in the copy
  (empty, coin, owl/cat at 3 mm and 5 mm, gain ±10 %, R1 ±15 %, 3× noise, 2 and 10 V/A ADC
  quantization, and the board's 10.3 V/A). Detection latency ~1.4 s; lift-off noticed in
  ~0.46 s; perch current never above 184 mA; sweep keeps the token's tank ≤ 1.6 V
  (< 1.85 V orange Vf).
- **Sweep keeps tokens dark with the as-built 150 Ω legs too** (`run_sweepdark.py`): worst
  sweep point lands ≤ 0.68 Vpk on the tank, and the cat hit by the 3rd harmonic of a
  101 kHz sweep point gets 0.67 Vpk — both far under the orange LED's 1.85 V.
- **Bridge topology (Q4).** UCC27524D pinout as wired is correct (1 ENA, 2 INA, 3 GND,
  4 INB, 5 OUTB, 6 VDD, 7 OUTA, 8 ENB), non-inverting part; ENs tied to FAM_EN with a 4.7 k
  pull-down that beats the internal pull-up; inputs have internal pull-downs; outputs held
  low in UVLO; TTL thresholds accept the 3.3 V logic despite the shunt bounce. No external
  FETs → no shoot-through; `cc ≤ P/2` (`coils.c:162`) guarantees the legs are never high
  together (asserted in `test_rt.c:212-221` even at duty 0.5). Peak coil current ~0.24 A ≪
  the 5 A peak rating.
- **Blocking cap.** C10U = CL21A106KAYNNNE (10 µF/25 V X5R 0805): DC bias ≤ 2.4 V
  (mean of one leg's PWM), ripple ≈ I·Δt/C ≈ 40–70 mV, Xc = 0.11 Ω at 142 kHz ≪ the
  ~26 Ω loop; ripple current is trivial for a ceramic. "A stuck output cannot pass current"
  (sch_base.py:888-891) is true in steady state for faults on either leg (the cap is in
  series with the only path).
- **Sense chain (Q5).** 0.5 Ω × (1 + 100 k/5.1 k) = 10.3 V/A ✓ (`config.h:80`); count =
  78 µA ✓; output at 0.2 A = 2.06 V < 3.3 V rail ✓. The 1 ms RC (fc = 159 Hz) attenuates
  the ≤0.1 V shunt ripple ~−59 dB to ~0.1 mV at the amp input; the OPA2333 (GBW 350 kHz,
  so closed-loop gain only ~2.5 at 142 kHz, −18 dB more) leaves ~0.3 mV at the ADC ≪ 1
  count. No rectification hazard at 0.1 mV input amplitude. OPA2333 offset (10 µV) → 20 µA
  referred — negligible. Shunt dissipation ≤ 20 mW.
- **Mux/ADC timing (Q5).** 10 kHz tick, 8 mux channels → each FAM_ISENSE refreshed every
  0.8 ms; the mux is advanced *after* sampling (`rt.c:232-234`), giving a full 100 µs of
  settling; 8-sample bursts; `FAM_SETTLE_S` = 4 ms ≥ 4τ of the 1 ms filter. Sound.
- **Token LED topology (Q3).** Anti-parallel orange/purple, each with its own 150 Ω
  (`sch_boards.py:297-312`, "each direction through its own resistor"; `familiar.py:60`
  models anti-parallel). Each LED's reverse voltage is clamped by the other; mean currents
  ≤ ~13 mA at any physically possible drive (finding 4's numbers), so the 20 mA class DC
  rating holds with margin; the brief ~33–46 mA half-cycle peaks are within typical 0603
  pulse ratings.
- **Duty cap / thermal safety (Q2).** `duty_cap_at` verified numerically: cap ≈ 0.287 at
  142 kHz (test: owl drives at duty 0.29, ≤184 mA); at 303 kHz the cap saturates at 0.5
  because the bridge physically cannot reach 0.2 A there (max ≈ 0.11 A) — the cat simply
  can't hit the 0.25 W target (test: 177 mW), which is a light-level note, not a bug.
  Worst-case continuous coil heating ~40–70 mW; no timeout is thermally acceptable.
- **Perch-to-perch coupling.** Coil centres (63, 92) and (178, 66) mm (`placement.py:133`)
  are 131 mm apart vs 15 mm coil radius → mutual k ~ 10⁻³; simultaneous sweeps don't
  measurably interact.
- **Boot safety.** `test_rt.c:166` asserts the perch drivers are disabled in the safe
  state; `perch_set(off)` parks both legs as plain low GPIOs and drops FAM_EN
  (`coils.c:128-143`).

## Could not check

- **UCC27524 ROH/ROL at VDD = 4.8 V** (the datasheet only specifies at 12 V; no extractable
  typical curve) — this sets the size of finding 2. Measure the perch loop resistance or the
  driver drop on the first board.
- **Realized M/k against the 3D-printed floor thickness** (3 mm assumed: 2 mm print + 1 mm
  air/mask); the fit's k² grid (0.10–0.40) and the 5 mm test give margin, but the true gap
  stack-up is unverified.
- **Phone/Qi-coil false fit** (finding 5): no model of a foreign resonator; recommend a
  bench test with a phone on each perch.
- **Tank tolerance stack-up**: C0G ±5 % plus drawn-coil spread — the firmware's own claim
  is ~±7 % vs an ±18 % classify window; consistent, but not verified against real parts.
- **Layout/parasitics** of the shunt–filter–amp routing (only the schematic generator was
  reviewed, not the routed copper).
- `bat_power.py` is the levitation-bat link, not the familiar perches; reviewed only for
  shared machinery (`familiar.simulate`), which behaves as documented.
