# OWLternating Current — design review (Kimi K3)

Reviewer: Kimi K3. The first session of this review stalled after producing deep
sub-investigations (levitation, familiars, GPIO binding, panel/manufacturing); this
report completes the job. Every headline claim from the first session that I fold in
was either re-derived or spot-checked in this session (each is marked); the rest of
the questions (power entry, the buck, the theremin, the RP2354A corner, child
safety, publishing) are this session's own work. All scripts, data dumps and patches
are in `review_KimiK3/trial2/`; the project copy used for running things is
`review_KimiK3/trial2/project/`. The live tree was never modified (verified: only
`review_*` paths differ).

## 1. Verdict

**Order after named fixes — no blockers found, but fix the panel before ordering,
and fix the levitation firmware/tables before bring-up.** Concretely: (a) the panel
puts mouse bites inside the perch's owl-cap notch and leaves the assembly-critical
header overhang and top-only fiducials for JLCPCB to query — all three are gerber/
order-note fixes that cost nothing now and annoy later (findings 3–5);
(b) the levitation's shipped tuning tables belong to a coil that no longer exists
and its generator cannot run (finding 1), and above ~2.0 A mean the actuator's gain
inverts under ITRIP chopping (finding 2) — both are firmware/generator fixes, no
board change; (c) everything electrical I checked — power entry, the buck, the
RP2354A corner, the theremin, the sense chains — is right or better. My confidence
is medium-high. The residual risk is exactly the one the authors already carry:
the levitation working first time at all (their own ~65 %), and it degrades
gracefully into the pendulum.

## 2. Findings (most severe first)

### 1. MAJOR — the shipped levitation tables were computed for a coil that no longer exists, and the table generator crashes

- **Where:** `firmware/src/lev_table.h` (the whole `LEV_TAB_KCOIL_N_PER_A` array),
  `firmware/test/lev_plant.h`, `firmware/tools/gen_lev_tables.py:53`; coil
  definition `gen/parts.py` (3 layers, ~42.6 turns).
- **What:** the committed coil constants (`LEV_KCOIL_N_PER_A` 20.41 mN/A,
  `LEV_BCOIL_MT_PER_A` 3.112 mT/A) match the *previous* 4-layer/11-turn coil digit
  for digit (first session recomputed both); the drawn 3-layer coil gives
  19.15 mN/A (−6.2 %) and 2.93 mT/A (−5.7 %). Git history corroborates: the coil
  moved to 3 layers in c43bab5 (Oct 7 14:22) and the tables were last touched by
  f314c47 with the old values. The magnet-side columns (g0, k_neg, B_bias, B_bat)
  are unaffected — they reproduce exactly with the current geometry.
- **Evidence (this session):** ran the generator in the copy:
  `python3 firmware/tools/gen_lev_tables.py` dies at
  `assert _C["layers"] == len(Z)` — "the coil's layers and the stack-up's". So the
  tables cannot be regenerated as committed, and they were not. Independently,
  the host test prints `CAL found 3.185 mT/A (plant 3.11)` — the plant carries the
  stale 3.11 mT/A constant.
- **Impact:** loop gain ~6.5 % low (phase margin −1–2°; the first session re-ran
  the full `test_lev` suite against a plant patched to the true coil — all cases
  pass, and CAL measures the true 2.93 mT/A at runtime). The force table used for
  `i = f/kc` does *not* self-correct; all reported catch peak currents are
  understated ~6 %.
- **Fix:** fix the generator (spiral on the stack's first three layers, bat/sensor
  geometry from the full stack), regenerate both headers, and add a regeneration
  check to the build so the tables cannot go stale silently again.
- **Confidence:** very high.

### 2. MAJOR — 40 kHz PWM on a 30.1 µH coil: ITRIP chopping engages above ≈2.0 A mean and the actuator goes non-monotonic; modelled nowhere

- **Where:** `firmware/src/config.h` (LEV_PWM_HZ 40 kHz; DRV_ITRIP_A 3.3 A;
  IMODE=GND = fixed off-time, t_off = 25 µs); every plant model assumes mean
  voltage (`sim/physics/levitation_loop.py`, `firmware/test/lev_plant.h`,
  `lev_ctrl.c`'s `u = i·R/v12`).
- **What:** volt-second balance on 30.1 µH/2.76 Ω at 12 V gives amperes of ripple.
  Reproduced this session (`probe_pwm.py`, switching-level, 10 ns steps,
  centre-aligned pulses, fixed 25 µs off-time chopping at 3.3 A):

  | commanded mean (A) | actual mean (A) | peak (A) | ripple p-p (A) |
  |---:|---:|---:|---:|
  | 1.0 | 1.00 | 1.98 | 1.64 |
  | 2.0 | 2.00 | 3.15 | 2.24 |
  | 2.4 | **1.62** | 3.30 (chops) | 2.98 |
  | 3.0 | **1.50** | 3.30 (chops) | 2.97 |

  Above ≈2.05 A commanded, the peak hits ITRIP and the 25 µs off-time (a whole PWM
  period) collapses the delivered mean to ~1.5 A: **the actuator gain inverts
  exactly where the controller pushes hardest.** The usable force ceiling is
  ≈2.0 A × 19.1 mN/A ≈ 38 mN against the bat's 35.3 mN weight — ~8 % margin, not
  the 3.0 A the constants suggest. Host-test cases peaking above ~2.1 A (all four
  "step to g0" catches, the VQ-error catches) are unphysical on hardware; only the
  shipped default soft catch (peaks ≤1.6 A) stays in the linear regime.
- **Fix (firmware only, no board change):** raise the levitation PWM to
  150–200 kHz — the DRV8874 tolerates it (tPD 400 ns ≪ period), the tick is
  already phase-locked, ripple scales 1/f (at 160 kHz the peak at 2.4 A mean
  ≈2.7 A < 3.3 A, so the mean model holds to full current). Alternatively cap
  `LEV_I_MAX_A` ≈1.8 A and never ship `ramp_mm_s = 0`. Either way, add
  ripple/ITRIP to the test plant before trusting the ±3 mm catch claims.
- **Confidence:** high on the physics (reproduced twice; the exact clipped means
  are ±20 % depending on decay-mode details — bench-verify on the first board).

### 3. MAJOR — a tab's mouse bites land inside the perch's owl-cap notch, a CLEAN-listed edge; the clean-edge check never looks at the far board

- **Where:** `gen/panel.py:110` (`_clean_conflict(name, side, s, d)` — only the
  originating board), `_clean_conflict` at `panel.py:150-170` (one board only).
- **What:** the tree↔perch tab at panel y≈157.9 carries bite rows at panel
  x=119.55 and x=**122.64**. The perch's left edge is at x=121.80 with the owl-cap
  notch cut to x≈122.80 between panel y=154.80 and 160.80
  (`CLEAN["perch"]` lists exactly this edge, `("left", -5, 5)`). The tab search
  walked into the notch and placed the far bite row 0.16 mm off the notch bottom —
  inside the notch void (hole span 122.39–122.89 crosses the notch bottom edge).
  `CLEAN["perch"]` would have rejected it had the check ever run for the perch;
  the tab was found from the tree side, whose own clean band does not cover it.
- **Evidence (this session, from the built board):** bite holes at panel
  (119.55, 156.75–159.0) and (122.64, 156.75–159.0) confirmed in
  `hardware/OWLternatingCurrent.kicad_pcb`; the perch's notch edge confirmed at
  panel x 121.80→122.80, y 154.80–160.80. Consequence: the notch's seating
  surface (the printed owl's arms hook into it) carries ~0.25–0.35 mm bite
  scallops on every panel, and the tab fills a functional feature.
- **Fix:** `patches/panel_far_side_clean_check.patch` (applies with `patch -p1`;
  dry-run verified). It maps each candidate tab onto the far board and runs
  `_clean_conflict` for it too. Rebuilt `gen/board.py --place` in the copy with
  the patch: both bad tabs disappear (23→21 tabs, 140→124 holes, verified in the
  regenerated board). **Caveat:** the perch then keeps only 1 tab — mechanically
  too few for a 34×56 mm board through reflow. The patch should land together
  with a nudge that gives the perch a second clean attachment (e.g. shift the
  perch or the tree so a clean stretch of the perch's left edge faces the tree,
  or add a frame tab spot on a clean span).
- **Confidence:** high (geometry verified numerically; patch tested end-to-end in
  the copy).

### 4. MAJOR (process risk) — the tree's right-angle header pins overhang the panel: J102's pins end 1.4 mm from the panel edge over the left rail; J101's reach 3.6 mm over the perch

- **Where:** `gen/layout.py` + the 6 mm pin reach of the PZ254 right-angle
  headers; verified against the built board (first session).
- **What:** J102's pins span panel x=1.4–7.4 (under the 5 mm rail, 1.4 mm from the
  panel outline); J101's pins span panel x=119.4–125.4, i.e. 3.6 mm over the
  perch's left strip, at best zero clearance to its bottom face (masked, so
  shorting risk is low; the only bottom-side perch part, J201, is well clear).
  These are through-hole parts JLCPCB hand-solders after reflow, so this is a
  fixturing/handling problem, not a reflow conflict — but pins 1.4 mm from the
  panel edge are inside any sane component-to-edge clearance, and bent pins here
  must later plug into the base. Expect a DFM/engineering query on a
  fully-assembled order.
- **Fix options:** mark J3/J101/J102/J201 as customer-supplied (the boards plug
  together at home anyway — soldering four 2×8 headers at home deletes the whole
  risk class); or move the tree ≥5 mm right; or keep "Confirm Production file:
  Yes" and ask JLCPCB about the overhang in the order remark before paying.
- **Confidence:** geometry high; JLCPCB's reaction medium (their THT-overhang
  tolerances are not published precisely enough to call this a certain
  rejection).

### 5. MAJOR (process risk) — all three panel fiducials are top-side only on a both-sides assembly

- **Where:** `Fiducial_1mm_Mask2mm.kicad_mod` (single pad, F.Cu/F.Mask only);
  `mfg/release/PLACEMENT_CHECKS.txt` confirms FID1/2/3 on F.Cu.
- **What:** the bottom pass — which places the panel's finest parts (VQFN-46
  0.4 mm pitch U3/U101, LGA-14 U15, all bottom) — has no fiducials once the panel
  is flipped. Expect an engineering query or reduced bottom-side placement
  accuracy via tooling-hole alignment.
- **Fix:** mirror the fiducial footprint to B.Cu/B.Mask (a 1 mm dot in a 2 mm
  mask opening on both sides is standard).
- **Confidence:** high that the bottom side has no fiducial; medium that JLCPCB
  raises it (their machine may align the second side on tooling holes).

### 6. MAJOR — the familiar-perch loop's real resistance includes the UCC27524's output resistance, which is modelled nowhere and is specified only at 12 V

- **Where:** sim `sim/physics/familiar.py` (pure current drive), test
  `firmware/test/test_familiar.c:134-170` (`Z = R1 + jwL1`, no driver R),
  firmware `config.h` `FAM_R1_OHM = 4.2`.
- **What:** during a pulse the coil current flows through one pull-up and one
  pull-down of the driver: R_drv = ROH + ROL in series with the coil's 4.2 Ω. The
  datasheet gives ROH = 5 Ω typ/7.5 Ω max, ROL = 0.5/1 Ω — **at VDD = 12 V**. At
  VDD = 4.8 V the PMOS gate drive is 2.5× weaker; ROH plausibly rises to ~10–20 Ω,
  so the loop's real R could be 2–4× the modelled 4.2 Ω.
- **Consequences (first session's analysis, which I find sound):** the
  empty-perch conductance model can be off 2–4×, and baseline learning only
  happens when a sweep shows < 3σ excess (`familiar.c:490`) — a large permanent
  mismatch can wedge the perch into never-learned (edge peak → fit fails r² →
  IDLE forever); the fit's own R1 assumption is wrong by the same factor, and the
  tests cover only ±15 % R1 error. The power loop is closed on supply power, so
  driver conduction loss is counted as delivered: tokens light, but dimmer than
  the 0.25 W target. The safe direction: the duty cap computed from the
  too-small R1 is conservative.
- **Fix:** measure the loop resistance (or the driver's drop) on the first board
  and fold it into `FAM_R1_OHM` (exactly equivalent there); add an
  `r1_scale = 2..4` case to `test_familiar.c`; check the never-learned corner.
- **Confidence:** medium that R_drv is several ohms; low-medium that it breaks
  detection — which is the point: the regime is unbounded by any test.

### 7. MINOR — worst-case DRV5055 VQ defeats the catch window (fail-safe)

- `test_lev.c:326` tests VQ error only at ±3 mT; the datasheet allows ±60 mV =
  **±8 mT** at 7.5 mV/mT. First session ran the suite with ±8 mT: +8 mT catches
  fine, **−8 mT never catches** a bat resting at g0+3 mm (the field slope there is
  ~3 mT/mm, so −8 mT reads ~2.7 mm outside the ±5 mm window; the loop never
  engages — no current, fail-safe, recoverable with `lev cal zero`).
- Fix: run zero-calibration automatically before first enable when no bat is
  seen (the `range=+1` no-bat detector exists), or widen `catch_mm` to ~7 mm.
- Confidence: high (reproduced in the shipped harness).

### 8. MINOR — UCC27524 UVLO start threshold vs the 4.8 V rail

- Datasheet VON max 4.65 V; the rail's worst-case minimum is ~4.68–4.70 V
  (TPS54302 reference + divider tolerance) — ~30–50 mV of margin against a
  worst-case part. Fails safe (outputs held low in UVLO): a max-UVLO unit on a
  min-rail board has dead familiars, nothing worse. Note for bring-up.
- Confidence: high on the numbers, low that any real unit fails.

### 9. MINOR — the familiar sims are stale against the copper

- `familiar.py:91` uses 150/330 kHz tanks (the drawn coils give 142.2/303.2 kHz =
  the firmware's constants exactly); `familiar.py:120` prints a "12 V full
  bridge" (the bridge is 4.8 V); `familiar_resistors.py` sweeps Rs to 100 Ω and
  never includes the shipped 150 Ω; `test_familiar.c:74-75` models 77/82 Ω LED
  legs. First session re-ran with the built values (`run_fam150.py`): at the
  largest physically possible drive, token LED means ≤ ~9 mA (owl) / ~13 mA (cat)
  with half-cycle peaks ~33–46 mA — the 20 mA DC rating is exceeded only
  instantaneously; safe. Fix: point the sims at the drawn coils and 150 Ω legs.
- Confidence: high.

### 10. MINOR — resonant foreign objects are driven forever; no drive timeout (bounded hazard)

- `familiar.c` ramps up any good model fit including `FAM_UNKNOWN`, with no DRIVE
  time limit. Coins/keys are rejected (no resonance; host-tested); a resonant
  in-band object (e.g. a phone's Qi coil near the 100 kHz sweep edge) that fits
  the coupled-tank model at r² ≥ 0.8 would be announced and driven at ≤0.25 W
  indefinitely. Hazard bound verified: duty cap ≤184 mA, worst coil heating
  ~40–70 mW, object ~0.2 W — a scene glitch, not a safety issue.
- Fix (optional): don't ramp up FAM_UNKNOWN; add a DRIVE on-time limit with
  re-sweep.
- Confidence: high on the mechanism, medium on a real phone fitting the model.

### 11. MINOR — no feedforward capacitor on the buck

- `gen/sch_base.py:139-144`: the TPS54302's feedback divider is bare 36 k/5.1 k.
  Datasheet §7.2.3.5.3: with ceramic-dominated COUT the internal compensation
  "could result in low phase margin"; Table 7-2's 75 pF at 100 k scales to
  ≈180–220 pF for 36 k. With derated 2×22 µF the crossover estimate (eq. 14) is
  24 kHz nominal, ~38 kHz derated — at the 40 kHz no-Cff guideline. Worst case:
  load-transient ringing on the 4.8 V rail. Fix: a 0603 Cff footprint across R4,
  stuff 220 pF or DNP after a bring-up load-step test. Free either way.
- Confidence: high that the datasheet recommends it for exactly this
  configuration; medium that its absence is observable.

### 12. MINOR — the 12 V distribution has long 0.4 mm runs, not just "0.4 mm into the pins"

- This session, from the built board with pcbnew (`kicad_12v.py`, `z17.py`):
  the +12V pour is small (≈80 mm² at the input) and the cheapest path from each
  DRV8874 VM pin to it runs through 34 mm (U8, levitation), 44 mm (U7), 98 mm
  (U6) and **160 mm (U5)** of 0.4 mm-wide copper. 0.4 mm/1 oz ≈ 1.2 mΩ/mm → U5's
  feed ≈0.19 Ω; a 3.3 A ITRIP pulse drops ≈0.65 V. Not a functional problem
  (short pulses, 10 µF + 100 nF local bulk at each VM, DRV8874 UVLO at 6.3 V on a
  12 V rail; continuous current is the levitation's ~0.3–0.5 A on the short
  34 mm run ≈40 mΩ), and the layout sensibly gave the levitation the shortest
  path. But the doc's "widened to 1 mm where it fits and 0.4 mm into the pins" is
  not what got built — the widening pass left long runs thin.
- Fix: improve the widening pass or plan a 1 mm trunk per bridge; update the doc.
- Confidence: high on the geometry (authoritative pad/track positions via pcbnew,
  touch-graph + Dijkstra); medium that it matters beyond millivolts.

### 13. MINOR — the theremin antennas are wired straight into the LVC1G14 inputs

- `sch_base.py:507-515`: AE1/AE2 (ENIG shapes that children *will* touch) sit on
  the gate's input node; the only DC paths are 15 pF to ground and 100 k to the
  output. The 74LVC1G14 is 2 kV HBM rated; a dry finger carries more. A 4.7–10 k
  series resistor between the antenna pad and the input node is free (high-Z
  input, 500 kHz, negligible phase effect) and makes ESD a non-event. Worst case
  today: the theremin feature dies.
- Confidence: high on the topology, medium on real-world failure rate.

### 14. MINOR — the GPIO search minimizes a fixed-cut proxy, not the crossing count it reports

- First session, cross-checked this session: `gen/assign.py:427-437` scores the
  inversion count with both circles cut at one fixed place; `crossings()`
  (`:316`, the reported "84") takes the min over every cut. The search is a
  correct optimum of its proxy (their enumeration of the restricted space
  reproduces its exact answer) but never sees the real metric: a
  constraint-valid binding with fixed-cut 106 — scored worse, discarded — has a
  true count of **76 < 84**. The repo already contains the right algorithm,
  `cyclic_crossings()` (`:386-407`), as dead code (verified this session: defined
  at line 386, never called). Fully relaxing the "PWM on GPIO0-15 only" rule
  reaches 48 (datasheet-legal; puts fast PWM beside the ADC corner pins — a real
  noise trade-off, not obviously wise).
- Impact: none functional — the board routed 100 % with 0 DRC at 84 crossings;
  this is a few vias and some elegance. (The first session rated this major; I
  downgrade it to minor because nothing on the board is wrong, only 8 crossings
  worse than a known-better valid binding.)
- Fix: wire `cyclic_crossings` into `score()` (at least to re-rank the best few
  hundred candidates); no constraint change needed for 84→76.
- Confidence: high (reproduced twice with an independent counter).

### 15. MINOR — second tree↔perch tab sits inside the tree's own header-pin protection band (latent, harmless this time)

- The tab at panel y≈190.6 (rows x=119.55/121.65, bites y 189.47–191.72 —
  confirmed this session in the built board) lies inside `CLEAN["tree"]
  ("down", 24, 52)` = panel y 163.8–191.8 plus margin. It survives only because
  it was found from the perch side (finding 3's bug) and is ~2 mm clear of J101's
  actual pins, which the courtyard check legitimately verified. Same patch fixes
  it. Confidence: high.

### 16. MINOR — the bat is held by only 2 tabs, both on its head edge; the bite web is 0.25 mm

- The wing/tail edges are too curved for the 0.4 mm straightness test, so nothing
  else attaches; 2 tabs × ~1.25 mm of residual web on a 48×25 mm board through
  two reflows is the panel's highest premature-break risk. BITE_D/BITE_PITCH give
  a 0.25 mm web — inside the range the code cites (0.2–0.3 mm apart) but below
  common 0.3–0.5 mm practice. Fix (optional): accept, or add a frame tab on the
  tail side / widen the gap locally. Confidence: high on geometry, low-medium on
  actual breakage.

### 17. MINOR (known and managed) — bottom-side polarity marks are predicted by eye, not yet seen in a preview

- The CPL transform itself is correct and triple-gated (pos-export diff vs
  KiCad's own exporter at ±0.002 mm, pin-for-pin placement simulation, gerber-box
  check; the 10 bottom-side rotation readings re-pass; 180−θ provably the unique
  map fitting them — first session, and I verified the spot-checks against the
  release CPL: J2's datum shift, U1 180→270 prediction, D1's fixed point, the
  J101/J102 90°-after-flip, the 8.89 mm datum = half the 2×08 pattern). The soft
  spot: two-pad parts' polarity corrections were read by eye off JLCPCB's drawing
  PNGs, and a 180° error is a reversed LED/diode. PLACEMENT_CHECKS.txt
  operationalizes the preview step — keep "Confirm Parts Placement" mandatory.
- Confidence: high that the pipeline is consistent; medium on the eye-reads.

### Nits (each verified; grouped to keep the list honest)

18. Docs say the familiars are detected "by the **drop** in its own supply
    current" (DESIGN_REVIEW.md:96, README.md:22). The physics and the firmware
    are the opposite: a resonant token absorbs power, the perch's conductance
    peaks, the supply current **rises**. Firmware is right; docs are wrong.
    Patch: `patches/docs_drop_to_rise.patch`.
19. DESIGN_REVIEW.md §10 Q2 says "two 10 uF outputs" on the buck — built and
    correct: 2×22 µF (`sch_base.py:145-146`, matching datasheet Table 7-2).
20. DESIGN_REVIEW.md §10 Q3's parenthetical "(14.05 − 8.5)" mixes a height above
    the perch with a depth below it; the magnets are on opposite faces of the
    board, face-to-face ≈24 mm. The sims use the right geometry (their numbers
    only reproduce at 24 mm; at 5.55 mm the force would be ~47× the bat's
    weight). Doc bug only.
21. Bat mass: 3.6 g in code and sims, 3.7 g in the review doc; "43 turns" vs the
    drawn 42.6. Harmless; pick one.
22. `assignment.json`'s `crossings_before` is a fixed point (the netlist already
    carries the previous binding, so it reports "84 → 84"); regenerate before
    ordering so the report is current.
23. `firmware/boards/owlternating.h:10,15` comments say "UART0 on GPIO12/13" and
    "I2C0 on GPIO16/17"; the defines are TX/RX 16/17 and SDA/SCL 20/21. The
    regex updates numbers, not prose.
24. `gen/assign.py:26` docstring says "simulated annealing"; the implementation
    is exhaustive search. `cyclic_crossings` is dead code (also finding 14's
    fix).
25. `familiar.h:3` says "5 V supply current" (the rail is 4.8 V); `rt.h:64` says
    "perch current amplitude" (it is the average supply current);
    `sch_base.py:855` defines `X_ISENSE` and never uses it; `coils.c`
    `perch_init` silently relies on `slice_setup`'s channel-B inversion for the
    ±4.8 V 3-level drive — correct and host-tested today, one comment away from a
    future refactor killing the familiars.
26. `panel.py`: the base↔bat tab clears the sound-switch keep-out by 0.63 mm
    (within the design's own margin, tight against a lever that must stay clean);
    `find_tabs`' `holes_of` parameter is never used; `make_release.py:601-617`
    computes the fiducial mask opening but never tests it.
27. RUN (U4 pin 26) is unconnected: internal pull-up, no reset button — as
    documented; noting only because BOOT exists but RESET doesn't.
28. The IMU is on the bottom and the firmware's `IMU_AXIS_*` signs still assume a
    top-side chip (known open item; the wisps rolling the wrong way is the
    tell). Already in §11; confirmed the mismatch exists.
29. `.vscode/settings.json` holds a stale absolute path into an old project
    (`/home/jason/mnt/.../halloween1/firmware`). Untracked, so it will not
    publish — but the same pattern anywhere tracked would leak layout.

## 3. Section 10's questions, answered by number

1. **Power entry.** The AO4407A stage is right: drain to the jack (pin 5 → F1),
   source to the load (pins 1-3 → +12V), gate pulled down through 100 k, and the
   10 V zener's cathode to source / anode to gate (pin polarities verified in the
   built schematic's symbol definitions), so Vgs clamps at −10 V against a ±20 V
   gate rating. SMBJ15A (cathode to +12V) plus 470 µF polymer is a reasonable
   hot-plug snubber for a long cord: VRWM 15 V > 12 V, Vc ≈ 24.4 V vs the
   MOSFET's −30 V (≈5.6 V margin — thin but conventional). F1 (5 A hold / 10 A
   trip, 16 V) is sized fine for these loads and sees only 12 V when tripped.
   The 12 V copper *works* for 3.3 A pulses (local 10 µF + 100 nF at each VM,
   6.3 V UVLO) but is not what the doc claims: see finding 12.
2. **The buck.** Values match datasheet Table 7-2 (10 µH, 2×22 µF, and the EN
   divider gives 6.7 V start; FB gives 4.803 V). Ripple 0.72 A p-p, peak
   ≈1.9 A vs 4.5 A Isat. The layout is good, measured on the built board: input
   caps 1–2 mm from VIN/GND with adjacent ground vias closing the hot loop in a
   few mm, BOOT cap directly across pins 6→2, SW 9 mm at 1.0 mm to the inductor,
   FB never under the inductor (the schematic comment "runs under the inductor"
   describes the schematic drawing). One gap: no feedforward capacitor —
   finding 11. Stable? Probably, with less margin than TI recommends; the Cff
   footprint makes it certain.
3. **The levitation.** Small-signal margin is real (first session's independent
   Bode of the shipped gains: crossover 15.3 Hz, phase margin 42.8°; the
   electrical poles are ≥600× away). The Hall chain is sound: the coil's
   feedthrough (~3 mT/A) is modelled and subtracted, CAL measures it at runtime,
   and the A4 variant (7.5 mV/mT, ±176 mT range — verified against the
   datasheet) has huge headroom over the ~40 mT at the gap. **But:** the force
   tables belong to the old coil (finding 1) and the 40 kHz PWM makes the real
   actuator non-monotonic above ~2 A mean (finding 2) — neither is modelled in
   any sim or test. The loop's margin as computed is real; the catch envelope as
   tested is not. Fix both in firmware/generator (no board change), then re-run
   the suite.
4. **The familiars.** Detection is by current *rise*, not drop (doc bug, finding
   18). Foreign non-resonant metal is rejected by construction and host-tested;
   resonant objects are a bounded benign hazard (finding 10). Token LEDs are
   safe at any physically possible drive (≤13 mA mean through the built 150 Ω
   legs; finding 9). The one real gap is the UCC27524's output resistance at
   4.8 V, modelled nowhere (finding 6) — measure on the first board.
5. **The theremin's antennas.** Yes, drift is small next to a 3 % hand change:
   the R (±100 ppm/°C) and C0G timing cap (±30 ppm/°C) plus Schmitt threshold
   drift total ≲0.5 % over a 10 °C evening, moving at minutes-per-percent, while
   the firmware tracks the baseline with a 10 s constant after 5 s idle
   (`theremin.c:57-64`) and gates 0.3 % as noise. Verified on the built board:
   the keep-outs cover all four copper layers and contain zero foreign tracks or
   vias. The host test passes a 1 %/2 min drift case. The one weakness is ESD,
   not drift — finding 13.
6. **The GPIO binding.** The constraints are right for the RP2350's function
   table (first session checked every one against the datasheet: PWM slice
   `(n>>1)&7`, ADC = GPIO26–29 exactly, I2C0/UART0 pin sets including 24/25, the
   mux's consecutive selects, PIO on any pin; `net_check.txt` confirms the
   shipped binding pin-for-pin). Fewer crossings exist: 76 within the shipped
   rules, 48 fully relaxed — finding 14. Not worth a reroute; worth wiring the
   dead `cyclic_crossings` into the scorer for the next board.
7. **The panel.** Counts and positions all verified against the built board and
   drill data (23 tabs, 140 bites, fiducials 3.85 mm from the edge, 4×2 mm
   tooling holes, 245.2×223.2 mm outline). Three problems: the notch tab
   (finding 3), the latent clean-band tab (finding 15), the header overhang and
   top-only fiducials (findings 4, 5). The last two are "will JLCPCB accept
   that" — my answer: expect an engineering query; pre-empt it with a remark or
   by marking the connectors customer-supplied.
8. **CPL rotations.** Correct, and I verified the verification: the transform
   (flip native angle, then add the library correction) is cross-gated three
   independent ways and the 10 bottom-side readings re-pass. The residual risk
   is exactly the one the authors carry — eye-read polarity marks on two-pad
   parts (finding 17) — and the mandatory preview step is the right control for
   it.
9. **The RP2354A's corner.** Good. Decoupling count is exactly right (3 DVDD
   pins → 3×100 nF + 4.7 µF; ten 3.3 V pins each with 100 nF; VREG_AVDD's
   33 Ω/4.7 µF; VREG_LX reaches the inductor through a pour). Distances: 8 of 13
   supply pins at 1.2–2.3 mm, the worst four at 4.5–5.9 mm — worse than the
   doc's "1.5–3 mm" but harmless with the In1 ground island 0.21 mm below F.Cu.
   Crystal: XIN 4.05 mm / XOUT 6.41 mm, single layer, no vias, 15 pF C0G loads,
   1 k series on XOUT per Raspberry Pi's reference, ground pour around. Fine at
   12 MHz.
10. **Child safety.** Sound against §16: both magnets fully encapsulated in the
    print (one pause closes both pockets, layer 97 — `print/README.md`), 405 nm
    rather than 365–395 nm violet, ≤22 mA LED channels, quiet-by-design audio
    (0.25 volume ceiling, hardware shutdown switch), 12 V SELV certified brick
    with PTC + reverse-polarity + TVS, tab-nub filing already documented
    (ORDER_LIST.md:30), thermal guards host-tested (test_rt: 1 A for ten minutes
    → 43 °C model vs 45 °C limit). One action item: a tug-and-twist test on the
    first prints (F963 use-and-abuse can't be verified from files), especially
    the bat cap's 0.8 mm hooks — the bat is the most-mouthable part.

## 4. What I checked and found right

- **Power entry topology and polarities** (this session, from the schematic
  generator and the built schematic's symbol definitions): MOSFET orientation,
  zener orientation, TVS orientation, EN divider, PTC sizing, the note's
  arithmetic (9.5 mΩ → 0.15 W at 4 A; 6.7–6.8 V EN start).
- **The buck's values and layout** (this session, pcbnew geometry dump).
- **Theremin topology, constants, keep-outs, and firmware drift tracking** (this
  session; includes a polygon scan of all 2998 segments and every via against
  both antenna keep-outs: zero foreign copper).
- **RP2354A corner** (this session): decoupling counts and distances, VREG_LX
  pour, crystal routing, USB-C CC pull-downs present (5.1 k), I2C pull-ups 2.2 k.
- **DRC/ERC state**: 0 violations, 0 unconnected, 0 schematic-parity errors,
  0 ERC violations (`hardware/checks/{drc,erc}.json`); no duplicate reference
  designators across all 412 footprints (checked — the DRV8874/UCC27524 ref
  sequences looked collision-prone in the generator and are not).
- **Firmware host tests** (this session, fresh build in the copy): `make -C
  firmware/test` — **all suites pass** (test_console, test_theremin, test_rt,
  and the rest; make exits 0 only if every suite passes). Notable corroborations
  in the output: "perch bridge: legs never high together", brown-out and nFAULT
  behaviour, thermal 43 °C at the 45 °C limit, and the stale `plant 3.11 mT/A`
  of finding 1.
- **Levitation magnetics** (first session, cross-checked twice by independent
  integration paths agreeing to 0.3 %): magnet-magnet force 35.4 mN vs weight
  35.3 mN, g0 = 8.537 mm, k_neg = 5.008 N/m, B_bias = 6.36 mT — all reproduce
  with the correct 24 mm magnet separation; the magnetics toolkit passes its own
  closed-form self-tests to ≤0.02 %. DRV5055A4 variant choice and noise numbers
  match the datasheet. DRV8874 IPROPI/ITRIP constants match the datasheet
  (450 µA/A, 0.99 V/A on 2.2 k, 3.33 A trip).
- **Familiar sense chain** (first session): 10.3 V/A = 0.5 Ω × 20.6 ✓, the 1 ms
  filter kills the 142/303 kHz ripple before the OPA2333 (whose 350 kHz GBW is
  then irrelevant), mux refresh 0.8 ms per channel against the 1 ms filter, the
  two-duty sweep algebra, the duty-cap numbers (≤184 mA every case), token LED
  topology and safety at the built 150 Ω, perch-to-perch coupling ~10⁻³, boot
  safety (drivers disabled in the safe state). All re-run in the copy; all pass.
- **CPL/rotation pipeline** (first session; I re-verified the spot-checks
  against the release CSVs): frame, flip, correction order, datum shifts, the
  three independent gates, and the $366.11 cost arithmetic (including the
  explained 6941-piece 27 Ω minimum-buy oddity — JLCPCB's data, not a bug).
- **Panel counts** (both sessions): 23 tabs/140 holes/3 fiducials/4 tooling
  holes all confirmed in the built board; courtyard rejection and tab dedup work
  as intended; every clean edge except the perch's notch is respected.
- **GPIO constraints vs the RP2350 datasheet** (first session, 44/44 static
  checks): PWM slice math, ADC pins, I2C0/UART0 sets, mux consecutiveness, no
  double-assignment, special pins (USB/XIN/SWD/RUN), QSPI left unconnected
  correctly for the in-package flash, the E9-erratum resistor choices.

## 5. What I could not check

- **The DRV8874's real chopping behaviour** into a near-ideal 30 µH inductor
  (finding 2's exact clipped means are model-dependent ±20 %; bench only).
- **UCC27524 ROH/ROL at VDD = 4.8 V** (datasheet specifies at 12 V only) — the
  size of finding 6. Measure on the first board.
- **JLCPCB's current panel-assembly rules** (overhanging THT pins, bottom-side
  fiducial requirements) — offline; treated as process risks, findings 4–5.
- **JLCPCB's drawing PNGs for two-pad polarity marks** (finding 17) — the
  by-eye reads were not re-fetched; the preview step covers them.
- **Magnet tolerances** (N52 Br spread ±5–10 % not swept anywhere; the
  zero-power loop should absorb it, untested), **tilt/yaw dynamics** of the
  floating bat, and the **80 kHz bat-power carrier running while levitating**
  (its feedthrough into the gap estimate is not simulated).
- **F963 use-and-abuse** of the printed parts (tug/soak/torque) — physical test.
- **EMI** of the whole scene (no radiated/consumed analysis exists; a home
  display at these powers and edges is low-risk, but unmeasured).
- The first session's levitation/familiar findings rest on sims run in
  `review_KimiK3/project/`; I re-ran the cheap decisive ones (generator crash,
  PWM chopping, host suites, board-geometry checks) and read the rest for
  internal consistency, but I did not re-derive every number in their tables.

## 6. Publishing

- Clean: `datasheets/`, `references/`, `reference/`, `firmware/external/`,
  `tools/jlc_cache.json`, `mfg/jlc_footprint_cache.json`, `.vscode/` and
  `QUESTIONS.md` are all git-ignored or untracked; the gerber zip contains only
  KiCad generator stamps (no absolute paths); no secrets, keys or personal data
  found in tracked files (scanned for paths, keys, tokens).
- The only absolute path found anywhere is in the *untracked*
  `.vscode/settings.json` (stale, points at an old project) — it will not
  publish, but is worth deleting locally.
- This review directory contains no datasheet excerpts — only my measurements
  and short paraphrases with datasheet figure/section references.

## 7. Patches

In `review_KimiK3/trial2/patches/` (both apply with `patch -p1` from the repo
root; both dry-run-verified against the pristine tree):

1. **`panel_far_side_clean_check.patch`** — `gen/panel.py`: check the far
   board's CLEAN list when a tab lands on another board (fixes findings 3 and
   15). Tested end-to-end in the copy: `gen/board.py --place` with the patch
   produces 21 tabs/124 holes with no bites in the perch notch or the tree's
   header band. **Ship it with a follow-up**: the perch drops to 1 tab, so also
   give it a second clean attachment (shift the tree/perch or add a frame-tab
   spot on a clean span) before regenerating the release.
2. **`docs_drop_to_rise.patch`** — DESIGN_REVIEW.md:96 and README.md:22: the
   familiars are found by the *rise* in supply current (finding 18).

Deliberately not patched (need a decision or a board, not an edit): the
levitation table generator's layer handling (finding 1 — the right fix models
the spiral on the stack's first three layers and I did not want to hand Jason an
untested physics patch), the levitation PWM frequency (finding 2 — firmware
constant, but deserves the test-plant ripple model first), and the buck's Cff
footprint (finding 11 — trivial for the authors, awkward to bolt on by diff).

---

### Appendix: evidence files in this directory

- `kicad_12v.py`, `net12.json`, `z17.py` — +12V copper extraction (via KiCad
  10's pcbnew) and the pad-to-pour thin-copper path analysis (finding 12).
- `kicad_buck.py`, `kicad_rp3.py`, `kicad_rp4.py`, `kicad_fb2.py`,
  `kicad_refs.py` — buck layout, RP2354A decoupling/crystal geometry, FB/SW
  routing, and the duplicate-reference check (Q2, Q9).
- `probe_pwm.py` — switching-level ITRIP-chopping model, re-run output in this
  report (finding 2).
- Antenna keep-out scan, tab/notch geometry extraction — scripts run inline,
  outputs quoted in findings 3, 15 and Q5.
- `patches/` — the two patches above.
- First session's artifacts (same review, earlier session, one directory up):
  `../notes_levitation.md`, `../notes_familiars.md`, `../notes_gpio.md`,
  `../notes_mfg.md` and their probe scripts — the full evidence chains for
  findings 1, 2, 6–10, 14–17.
