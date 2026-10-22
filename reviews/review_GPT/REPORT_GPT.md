# OWLternating Current design review — GPT

Reviewer: **GPT** (AI assistant using Copilot SDK in VS Code)  
Date: 2026-10-08

## 1) Verdict

**Order after named fixes/checks**, not as-is. Confidence: **moderate**.

I did not find a clear board-fabrication blocker in the electrical/layout generators, and DRC/ERC artifacts are clean, but there are two pre-order risks that should be closed first: (1) familiar-token LED current safety evidence does not match the stated “always <20 mA” claim, and (2) placement rotation verification is still prediction-heavy for many parts and must be closed in JLC preview before confirming assembly.

## 2) Findings (most severe first)

### 1. **major** — Familiar LED overcurrent safety claim is not proven and appears inconsistent
- **Where:** `gen/sch_boards.py` (~lines 297-313), `sim/physics/familiar_resistors.py` (~lines 10-22), `sim/physics/results/familiar_resistors.json`
- **What is wrong:** The owl/cat token note claims 150 Ω “cannot push either LED past about 20 mA, whatever the firmware does,” but the resistor-sweep evidence currently committed does not validate the actual 150 Ω choice and shows >20 mA at nearby values (e.g., 100 Ω) under plausible drive conditions.
- **Evidence:**
  - Design claim: `gen/sch_boards.py` text for owl/cat.
  - Validation script does **not include 150 Ω** in the sweep (`(0, 22, 47, 68, 100)`).
  - Committed results show high currents at 330 kHz, 0.2 A and above for lower resistors (e.g., 100 Ω: orange 30.6 mA, violet 25.5 mA at 0.2 A; much higher at 0.4 A).
- **Proposed fix:**
  1. Extend `familiar_resistors.py` to include the actual BOM value(s), especially **150 Ω**.
  2. Add explicit acceptance criteria in script output for normal and fault drive limits.
  3. Update schematic prose to match validated limits (or increase series R if needed).
- **Confidence:** 8/10

### 2. **major** — CPL rotation closure is still incomplete pre-order
- **Where:** `mfg/release/PLACEMENT_CHECKS.txt` (“NOT YET SEEN RIGHT … 26 part numbers, 84 placements”), `mfg/jlc_rotation.py`, `mfg/make_release.py`
- **What is wrong:** Rotation/placement logic is sophisticated, but many placements remain “predicted, not yet seen right” in actual JLC preview. This is an execution risk at order time.
- **Evidence:**
  - `PLACEMENT_CHECKS.txt` explicitly lists unresolved predicted rotations.
  - The flow depends on final human preview confirmation; this closure is not yet reflected in artifacts.
- **Proposed fix:**
  1. Treat preview confirmation as a required gate before order (not optional checklist).
  2. Feed all confirmed deltas back into `mfg/jlc_rotation.py` with “read” confidence.
  3. Re-export release package after closure.
- **Confidence:** 9/10

### 3. **minor** — IMU axis mapping remains known-open and can produce wrong behavior in scenes
- **Where:** `firmware/src/sensors.h` (`IMU_AXIS_X/Y/Z` all +1 with `[ASSUMED]`), DESIGN_REVIEW known-risks text
- **What is wrong:** Axis signs are intentionally unresolved and still hardcoded as assumptions.
- **Evidence:** Source comments explicitly state this is pending first-board tilt validation.
- **Proposed fix:** Add a first-article bring-up checklist item to measure gravity sign/orientation and commit corrected `IMU_AXIS_*` before final firmware release.
- **Confidence:** 10/10

### 4. **minor** — Design-review prompt references a missing file name
- **Where:** `DESIGN_REVIEW.md` references `CLAUDE_PCB.md`; repository contains `CLAUDE_CODE_CHAT.md` instead.
- **What is wrong:** Review package points reviewers to a non-existent path for safety section references.
- **Evidence:** Missing file at repo root; similarly named file exists with relevant content.
- **Proposed fix:** Update `DESIGN_REVIEW.md` to current filename/path.
- **Confidence:** 10/10

## 3) Section 10 questions — answers

1. **Power entry:** Topology is correct (P-MOS reverse protection orientation, gate clamp, TVS placement after MOSFET). 12 V routing strategy (0.4 mm into fine pins, widened elsewhere) is reasonable for pulsed loads; no obvious layout fault found. **Confidence: medium-high.**
2. **4.8 V buck:** Placement/routing intent is good (tight VIN/SW loop, local caps, output vias to plane). I did not find a control-loop design red flag in code/docs, but no bench Bode/step data is present. **Confidence: medium.**
3. **Levitation loop margin/Hall observability:** Sim artifacts support feasibility (stable hold, low steady RMS current). Catch-range evidence shows margin is finite (higher release offsets raise peak current). Overall plausible but still first-article tuning-sensitive. **Confidence: medium.**
4. **Familiars robustness and LED safety:** Token identification/filtering approach is technically strong; robustness vs random metal objects is plausible by resonance-fit rejection. LED current safety needs closure per Finding #1. **Confidence: medium.**
5. **Theremin drift vs hand signal:** Firmware includes calibration, smoothing, hysteresis, and slow idle drift compensation; architecture is sensible. No direct environmental drift dataset found in repo. **Confidence: medium-low.**
6. **RP2354A GPIO binding/crossings:** Assignment approach is systematic and constraint-aware; reported U4 crossings (84) appear to come from an exhaustive constrained search flow, not ad-hoc mapping. No obvious constraint violation seen. **Confidence: high.**
7. **Panel and overhanging right-angle headers:** Geometry and tab/courtyard avoidance logic are careful; however manufacturability acceptance for protruding pins under panel plane should be explicitly confirmed with JLC prior to release lock. **Confidence: medium.**
8. **Bottom CPL rotations:** Methodology is robust and self-tested, but many placements remain “predicted” in this release package; requires preview closure before order (Finding #2). **Confidence: high.**
9. **RP2354A corner, decoupling displacement, crystal routing:** For 12 MHz crystal and this architecture, layout appears acceptable; no obvious anti-pattern (e.g., long meanders through noisy regions) found in generator intent. Still merits first-article bring-up checks. **Confidence: medium.**
10. **Child safety:** Good design intent (embedded magnets, limits, rounded corners, fused input), but I did not find objective pass/fail test records for magnet retention/mechanical abuse in-repo. **Confidence: medium-low.**

## 4) What I checked and found right

- Generator-centric architecture is coherent and internally consistent (`gen/` + manufacturing + firmware generated headers).
- DRC/ERC artifacts are clean:
  - `hardware/checks/drc.json`: no violations/unconnected items/parity errors.
  - `hardware/checks/erc.json`: no violations.
- Familiar firmware design is sophisticated (sweep + model fit + power-loop + dither-based leave detection), not simplistic thresholding.
- Levitation firmware has explicit safety/fault paths (thermal trip, current mirror plausibility checks, coil-allowed inhibit, fault latching).
- CPL generation and placement verification machinery are unusually thorough for hobby-scale hardware (datum offsets + side transforms + self-test + per-part corrections).

## 5) What I could not check

- I did **not** run full board regeneration/build scripts in-place (to avoid writing outside review directory and avoid impacting concurrent reviewers).
- I did not perform fresh physical simulation reruns in an isolated copied workspace during this pass.
- I did not perform JLC live preview verification (requires human-in-the-loop in JLC UI and account context).
- I did not conduct bench measurements (obviously unavailable in repo-only review).

## 6) Publishing concerns

- No secrets/keys found in files reviewed.
- One documentation hygiene issue: stale filename reference (`CLAUDE_PCB.md`) should be corrected to avoid confusion.
- Datasheet/reference copyright constraints noted in review prompt should continue to be observed.

## 7) Patches

None produced in this review pass.

