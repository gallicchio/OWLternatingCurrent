# Measurements on rev A (board 1)

The numbers measured on the bench, in one place, for making rev A work better and for
sizing rev B. Each row says how the number was got and where the record is. What the
numbers mean for rev B is argued in `REVB.md`; this file only keeps the numbers.

**Kinds of numbers:**
- **Jason:** measured by hand, with a meter, a scale or the IR camera.
- **board:** measured by the board's own sensors, recorded by a script in `results/`.
- **fit:** derived from several measurements by a model or a fit; it is only as good as
  its inputs.
- **computed:** arithmetic on other rows, not measured.

The design values come from `gen/mech.py`, `gen/coils.py` and `firmware/src/config.h`.
Paths in the "Record" column are under `bringup/` unless they start with `references/`.

## The bat and its magnets (2026-11-09)

| Quantity | Value | Design | Kind | How | Record |
|---|---|---|---|---|---|
| Magnet size | 10.0 mm × 2.0 mm disc, N52, axial | 10 × 2 N52 (`MAGNET_D`, `MAGNET_T`) | Jason | stated from the pack (AMF 20053A) | `ORDER_LIST.md` item 3 |
| One magnet's mass | **1.23 g** | | Jason | scale, on a tall cardboard box, tared | REVB 1.11 finding 8 |
| Bat PCB alone | **3.00 g** | | Jason | same stand | REVB 1.11 finding 8 |
| Bat cap (the printed head with the ears) + glue + magnet | **1.72 g** | | Jason | same stand, the cap off the PCB | REVB 1.11 finding 8 |
| Cap print + glue | 0.49 g | 0.45-0.50 g of PLA (`check.py`) | computed | 1.72 − 1.23 | |
| Bat as flown (PCB + cap + magnet) | **4.70 g** | 3.6 g assumed (`sim/physics`) | Jason | same stand, cap clipped on | REVB 1.11 finding 8 |
| Bat with its magnet, no cap | 4.23 g | | computed | 3.00 + 1.23; weigh it once the magnet is taped on | |
| A wrong reading | ~~5.26 g~~ | | Jason | on the scale's metal pan: the magnet pulled toward the table. **Weigh anything magnetic on a tall non-magnetic stand.** | REVB 1.11 finding 8 |

Magnet density: 1.23 g / 157 mm³ = 7.8 g/cm³, which is about right for NdFeB (7.5).

**The cap turned round** (Jason, 2026-11-09). Clipped on the other way, with the ears away
from the eyes, the bat hovered flatter. The magnet then sat off the coil's centre, toward
the eyes, and catching was harder. Jason's reading: the original way, the tilted magnet's
raised edge gave more lift and the loop drew less current.
- Rev A: tape the magnet straight to the PCB, where it balances.
- Rev B: put the coil's centre at the bat's centre of mass, with the notches symmetric
  about it (REVB 2.2).

## The owl and the float gap

| Quantity | Value | Design | Kind | How | Record |
|---|---|---|---|---|---|
| Owl magnet's bottom above the perch's top copper, first print | 14.05 mm | `OWL_LIFT` 14.0 | computed | printed geometry (`check.py`) | `print/README.md` |
| Same, second owl (flying since 2026-11-10) | 12.45 mm | `OWL_LIFT` 12.5 | computed | `check.py`, 2026-11-09 | git `34c519a`'s `print/out/owl.stl` |
| Same, third owl (printed next) | 11.45 mm | `OWL_LIFT` 11.4 | computed | `check.py`, 2026-11-10 | `print/out/owl.stl` |
| Owl's slot for the magnet | 10.25 × 2.2 mm | magnet 10 × 2 | computed | `check.py` | `print/out/owl.stl` |
| Float gap with no current, 14.05 mm lift, 4.70 g bat | 6-6.6 mm | 8.5 mm designed | board | the zero-power walk's end point | `results/2026-11-08/*_lev_try.json` |
| Same, from the model at 4.70 g | 6.7 mm | | fit | `sim/physics/levitation_onemagnet.py` (gap + lift = 23.1 mm) | REVB 1.11 finding 8 |
| Expected with the new owl, a bat of 4.2-4.3 g | about 8.9 mm | | fit | same model | HANDOFF.md |
| **Float gap with no current, 12.45 mm lift, 4.70 g bat (cap on, the magnet flipped)** | **7.40-7.44 mm**, sd 0.015-0.02 mm | about 8.3 mm (the model's 20.75 − 12.45) | board | the zero-power walk's end point, 40 s and 120 s | `results/2026-11-10/151305_lev_setpoint.json`, `153907_lev_eyes_ir.json` |
| Gap + lift, measured | 19.85 mm (14.05 owl: 20.1-20.65) | 20.75 mm (model at 4.70 g) | computed | the rows above | |
| Expected with the third owl (11.45 mm), same bat | about 8.4 mm with no current | | computed | 19.85 − 11.45 | |
| Owl magnet's field at the perch's sensor, second owl | 1.37 mT zero offset | | board | `lev cal zero`, bat away | `results/2026-11-10/150904_lev_try.json` |
| Owl magnet's field at the perch's sensor | 7.48 mT, of which about 1.1 mT is the desk's stray field | 6.36 mT modelled | board | `lev cal` with the bat away | REVB 1.11 |

**What a lower float costs:**

| Float gap | Coil force | Current per mm of correction |
|---|---|---|
| 8.5 mm | 21 mN/A | 0.9 A |
| 10.5 mm | 15 mN/A | 1.3 A |
| 12.5 mm | 11 mN/A | 1.8 A |

These are model figures; stay under about 10 mm.

## The levitation coil (on the perch)

| Quantity | Value | Design | Kind | How | Record |
|---|---|---|---|---|---|
| Coil resistance, Fluke | **3.24 Ω** (3.38 − 0.14 for the leads) | 2.56 Ω (`LEV_COIL_R20_OHM`) | Jason | perch off, J201 pins 10-14 (also 8-16, same range); contact resistance varies with probe pressure | REVB 1.11 finding 5 |
| Coil resistance, Astron DM6000AR | 3.5-3.6 Ω, minus about 0.3 for the leads | | Jason | same pins | REVB 1.11 finding 5 |
| Two-duty pulse fit | 2.51 Ω in the sense's units, so 3.18 Ω true | | board | duty 0.08 and 0.15 at 100 kHz | `results/2026-11-08/215828_coils.json`, `215851_coils.json` |
| Steady V/I, no bat | 4.3-4.6 Ω in the sense's units, so 3.5 Ω true including wiring | | board | console drive 0.2-0.8 A, 1.5 s each | `results/2026-11-09/091250_coil_thermo_sweep.json`, `092521_…` |
| **Current sense gain (IPROPI)** | **0.79 of the true current** | 1.0 | fit | three agreeing ways: V/I, the two-duty fit, and kcs below | REVB 1.11 finding 5 |
| Coil field at the sensor (kcs) | 3.64 mT/A, in the sense's units | 2.89 modelled (2.88 at a gain of 0.79) | board | `lev cal` | REVB 1.11 |
| Wiring, LEV_A and LEV_B through the tree | 0.32 Ω at most | | computed | 0.4 mm, 1 oz, about 200 mm, from the layout | REVB 1.11 finding 3 |
| Coil inductance | 30 µH | 30 µH | design | not measured | `config.h` |
| Bridge pulse loss | 0.50 µs per PWM pulse | | fit | two-duty fit; compensated with `DRV_PULSE_LOSS_S` | REVB 3.3 |
| Steady drive for the Fluke volts | duty 0.158, 0.39 A sensed, V12 11.7 V | | board | 90 s | `results/2026-11-09/104036_coil_hold_fluke.json` |

The coil is 25 % over its design value. One likely cause: inner copper of 0.5 oz where
`gen/coils.py` assumed 1 oz (REVB 1.11 finding 5).

**Still to do in the firmware:** change these three together, then run `lev cal` again:
- `LEV_COIL_R20_OHM` to about 3.18;
- the levitation sense's gain to 0.79;
- the thermal constants below.

## Heat

| Quantity | Value | Assumed | Kind | How | Record |
|---|---|---|---|---|---|
| Heat run, no bat | +24.9 K (R +9.7 %) after 340 s at duty 0.158; back within about 2 K in 10 min | | board | coil thermometer | `results/2026-11-09/092935_coil_thermo_heat.json`, `093544_…cool.json`, `coil_thermo_heat_cool.png` |
| Board node's heat capacity | 8.0 J/K | 2.5 | fit | both runs, with the true power, 1.6 K rms | REVB 1.11 finding 5; `config.h` `LEV_THERMAL_C_BOARD_J_PER_K` |
| Copper to board | 7.5 K/W | 3 | fit | same | `LEV_THERMAL_R_CU_BOARD_K_PER_W` |
| Board to room | 38 K/W | 40 | fit | same | `LEV_THERMAL_R_BOARD_AMB_K_PER_W` |
| Room, by the IR camera | 24.5 °C, perch and pendulum coils 24.5-25 °C | | Jason | IR camera | REVB 1.11 finding 6 |
| Room, by the IMU | 18.1-19.6 °C (reads 5-6 K low) | | board | | REVB 1.11 findings 4, 6 |
| Room, by the TMAG5273 | 27.5 °C | | board | | REVB 1.11 finding 4 |
| 10-minute hover, no eyes, 0.25 A mean sensed (0.31 A true) | IR 40 °C on the perch above the bat at about 320 s; 41-42 °C from another angle; 44 °C at the end. Thermometer 38.5 °C (about 45 °C with the IR's room temperature). | | Jason, board | | `results/2026-11-09/112012_lev_try.json`, `references/20261109_112109_bat_hover.mp4` |
| Hover with the eyes, walk floor 8.0 mm | 0.41 A mean (against 0.25 A at 7.5 mm); stopped thermally in 112 s; IR 44 °C after | | board, Jason | | `results/2026-11-09/140553_lev_try.json`, `141657_lev_try.json` |
| Thermometer in carrier blinks | read about 17 K high (61 °C against IR 44 °C) | | board, Jason | | REVB 1.11 finding 8 |
| **Hover with the eyes at 0.3, 0.49 A mean** | **IR 67 °C on the owl's underside**, then 52 °C; the model said 45 °C | | Jason, board | IR camera; the model's values from `status` after the stop. No script was logging this hover: `143240_lev_try.json` before it has no catch | REVB 1.11 finding 9 |

PLA softens at about 55-60 °C, a datasheet figure, not measured. The eyes stay off until
the 80 kHz carrier's loss is measured.

## The levitation loop: settings that worked and settings that failed

| Setting | Result | Record |
|---|---|---|
| `g0_mm 9.5`, walk floor 7.5 mm | 10-minute hover at 7.5 ± 0.23 mm, 0.25 A mean sensed, peaks at the 2.6 A limit as the bat sways | `results/2026-11-09/112012_lev_try.json` |
| `g0_mm 9.0` (floor 7.0 mm) | failed: catches began near 5 mm and were lost | REVB 1.11 |
| Fixed set-point (`zp_range_mm 0`) at 9.5 mm | over the mean-current limit | REVB 1.11 |
| Derivative filter at 25 Hz | worse, catches lost within a second; 50 Hz (the design) is right | REVB 1.11 |
| Eyes blinking by switching the carrier | the gap's sd went to 0.34 mm, against 0.23 mm; fading instead fixed it | REVB 1.11 finding 8 |
| Loop turned off at 7.5-8 mm | the bat is pulled up to the perch, not dropped | REVB 1.11 finding 8 |

**The bat's motion** (Jason): it turns about the vertical, sways and bobs, tilted 10-20°.
Stopped with a finger, it starts again.

## The second owl (12.45 mm), 2026-11-10

Bat 4.70 g with its cap, the magnet clipped the flipped way (flatter). `kcs` 3.64 by hand,
zero offset 1.37 mT, `mass_g` 3.6, eyes off, thermal cutoff on. The set-point fixed
(`zp_range_mm 0`), 25 s at each, the first 4 s left out. Record:
`results/2026-11-10/151305_lev_setpoint.json`.

| Set-point | Gap sd | Gap p-p | Mean current (sensed) | rms | Model copper at the end |
|---|---|---|---|---|---|
| natural float, 7.44 (zero-power walk) | 0.017 mm | 0.105 mm | 0 | 91 mA | 24.9 °C |
| 7.50 | 0.020 | 0.123 | 18 mA | 98 mA | 25.1 |
| 7.75 | 0.022 | 0.124 | 111 mA | 150 mA | 25.2 |
| 8.00 | 0.021 | 0.112 | 190 mA | 209 mA | 26.4 |
| 8.25 | 0.022 | 0.139 | 242 mA | 254 mA | 28.8 |
| 8.50 | 0.021 | 0.141 | 300 mA | 310 mA | 32.8 |
| 8.75 | 0.028 | 0.179 | 378 mA | 389 mA | 41.4 |
| 9.00 | 0.031 | 0.192 | 471 mA | 483 mA | 51.3 (rising fast) |
| 9.50 | lost | | the mean-current trip (0.6 A, `MEAN_TRIP_A`) released the bat | | |

- About **0.36 A sensed per mm** below the natural float. The bat is just as steady at
  every set-point to 8.5 mm; past that the gap's spread grows with the current.
- **The firmware's default since 2026-11-10:** the zero-power walk aims at 0.2 A
  (`LEV_ZP_I_A`, Jason: "as low as possible while maintaining stability and only moderate
  temperature"). With this owl that is about 7.95 mm. Not yet flown.
- Peaks reach the 2.6 A limit at every set-point (the bat's sway).

**The eyes (80 kHz carrier)** at the natural float, Jason reading the IR camera (the
hottest spot on the perch board he can see from above or the side; the flat bat hides
the underside). Record: `results/2026-11-10/153907_lev_eyes_ir.json`.

| Eyes | Seconds | Gap sd | rms current | IR | Jason |
|---|---|---|---|---|---|
| 0 | 120 | 0.015 mm | 59 mA | 36 °C (heat left from the 8.6 mm run), 31-32 at the end | |
| 0.05 | 180 | 0.017 | 72 mA | 30, then 28 | visible; one eye slightly brighter |
| 0.1 | 180 | 0.019 | 73 mA | 29, then 29 | "dim, but visible" |
| 0.15 | 180 | **0.033** | 77 mA | not read | |
| 0 | 120 | 0.016 | 68 mA | not read | |

- The coil's model ended each stage at 23-27 °C: at 0.1 the IR reads about 4-5 K over it.
- 0.15 doubles the gap's spread. **The firmware's default since 2026-11-10: 0.1, breathing**
  (a raised cosine with a 2 s period, `LEV_EYE_PERIOD_TICKS`).
- At a fixed 8.6 mm (0.32 A) the coil's thermometer rose 34 to 42 °C in the 60 s baseline,
  so the ladder stopped (at 42 °C) after the 0.05 burst, which added nothing measurable
  (`153625_lev_eyes.json`). `153521_lev_eyes.json` lost the bat: `zp_range_mm 0` was set
  before `g0_mm` (the scripts now fix `g0_mm` first).

**The coil's calibration on this owl:** `lev cal coil` says "IPROPI disagrees" and gives
`kcs` 2.18-2.25 mT/A; a console drive gives 3.9 per sensed A; 3.64 (the 2026-11-08 value)
flies. Not understood (`results/2026-11-10/150820_coil_probe.json`); found and fixed on
2026-11-11 (below).

**The tokens on their perches** (bat hovering, eyes off).

| Mode | Token | Owl perch (fam1) | Cat perch (fam2) | Record |
|---|---|---|---|---|
| live | none, owl, both, cat, none | 63.40-63.60 mA, 183 mW; `present` always true | 25.0 mA, 94 mW; `present` always true | `results/2026-11-10/155222_fam_token.json` |
| sweep | none | 1.4 mA mean | 1.1-1.2 mA | `161345_fam_token.json` |
| sweep | on | owl found at **147.6 kHz** about 10 s after the prompt | cat at **353.8 kHz**, within the 12 s | same |
| sweep | taken off | owl still `present` 30 s and more after it was lifted | cat `left` about 10 s after | same |

In live mode the averaged current moves 0.2 mA at most with a token on: nothing to see.
Sweep mode sees the tokens but is slow to see them go. Explained and solved on 2026-11-11
(below).

## The coil's calibration, the defaults flown, the token probe (2026-11-11)

**`lev cal coil` fixed.** With the bridge asked for 0 A, the 100 kHz PWM still makes its
minimum pulses both ways: a zero-mean ripple of about 0.07 A. The IPROPI mirror reads |I|,
so the ripple read as an offset of the same size, and the cal subtracted it from each
pulse ("IPROPI disagrees", `kcs` 2.2). The cal now coasts the bridge in its off windows.
With the bat away it gives **`kcs` 3.566 mT/A** (h+ 8.98, h− 10.27 mT at +0.195 / −0.175 A;
off 9.63 / 9.65 mT; i_off 4 mA), and the zero offset **1.40 mT**; both saved. Records:
`results/2026-11-11/110606_*` to `110959_lev_cal_coil_coast.txt` (the last is the fix).

**The defaults flown** (`zp_i` 0.2 A, eyes 0.1 breathing, rings' chase): the bat floats at
**8.46 mm, 0.13-0.16 A sensed** mean, 0.19-0.22 A rms. The sway grows over minutes with the
eyes on or off: gap sd 0.05, 0.08, 0.10, 0.17, 0.17, 0.23 mm in six 30 s stages that
alternate eyes 0 and 0.1 (`111448_lev_eyes_ab.json`; `111038_lev_try.json`). Jason: "Rocking
the loop a little bit isn't bad"; left as it is.

**The perch current against frequency** (`fam scan`, bat off; drive at a duty fraction of
the cap and a third of it, 6 ms settle, 12 ms average; records `112515_fam_scan_none.json`,
`112557_fam_scan_owl.json`, `112713_fam_scan_owl+cat.json`). At a fixed duty the sensed
supply current is the real power over 4.8 V, so it follows Re(1/Z):
- At the token's own tuning (the live drive, 142 / 303 kHz) the reflected load is
  resistive: the perch's current redistributes and the net change is about zero. That is
  why live mode saw nothing (2026-11-09, 2026-11-10).
- Below the token's tuning the reflection is inductive (current down). Above it the
  reflection cancels the perch coil's inductance and the current peaks at the coupled mode,
  ft/√(1−k²), about **1.5 ft** for a token lying on the copper (k about 0.75).
- Owl perch at 213 kHz: 1.8 → 12.4 mA at duty about 0.05; 33 → 325 mA at the full cap.
  Cat perch at 146 kHz (its 3rd harmonic lands on 1.5 ft): 2.5 → 11 mA; at 426 kHz
  1.65 → 8.9 mA. The two perches don't see each other's tokens.

**The live probe** (firmware since 2026-11-11, `familiar.h` `FAM_PROBE_*`): live drive
breathes (a 3 s raised cosine, 0.3 of the cap to the cap); in each trough, 20 ms at 1.5 ft
(the cat's perch at a third of that), at duty 0.06 then 0.03, and the difference of the two
currents cancels the drivers' own draw. Arrival above max(2.5 × the learned empty, 3 mA);
leaving below max(0.35 × the token's own level, 1.5 × empty). Jason: "The Breathing is fine".

| Perch | Empty | Token on | Record |
|---|---|---|---|
| owl (fam1) | 0.3-0.9 mA | 8-13 mA | `120007_fam_watch.json`, `131321_fam_watch.json` |
| cat (fam2) | 1.4-1.9 mA (higher with the owl on) | 6-11 mA | same |

- The last run (`131321`): both off and empty, owl on (seen at 10.5 mA), cat on (6.8 mA),
  cat off, owl off: every edge seen, nothing false. The first two tries (`113258`, a probe
  every 0.5 s, which blinked the tokens; `114155`, no floor) read empty perches at 0.9 and
  1.6 mA as tokens, so the rings never showed.
- Known limit, from the simulation: a token raised 3 mm or more lights but reads absent.

## The third owl (11.4 mm), 2026-11-11

Jason's print of `OWL_LIFT` 11.4, magnet glued in; bat 4.70 g, cap on. Tables regenerated
(the model's 3.6 g bat floats at 11.14 mm). With the bat away: `lev cal zero` gives an
offset of **0.83 mT**, `lev cal coil` **3.553 mT/A** (h+ 10.24, h− 11.52 mT at
+0.193 / −0.174 A); saved (`results/2026-11-11/131806_lev_cal_third_owl.txt`).

- **The catch:** the owl pulls the bat off a flat palm up to the perch, and the loop lets
  it down gently (Jason: "which is great"). The first one or two catches can end "the current
  stayed at its limit" while the bat snaps up; the next catch holds.
- **The hover on the defaults** (`zp_i` 0.2, eyes 0.1 breathing), 12.5 minutes
  (`132110_lev_try.json`; the first flight, `131855_lev_try.json`, held the same way until
  an agent's `lev off`): gap **8.77 mm** mean, sd 0.086 mm overall (8.55-9.05); the
  per-minute sd grew from 0.04 to 0.10 mm. Mean current **162 mA** sensed (134-177), rms
  193 mA, peaks to 1.8 A. The coil's model went 22.9 to 28.0 °C, levelling off; the
  board's sensor 21.1 to 26.6 °C. The resistance thermometer doesn't read while the eyes
  are on (by design, `rt.c`), so it gave nothing.
- Gap + lift: 8.77 + 11.4 = 20.2 mm at 0.16 A. On the second owl, 0.2 A hung the bat about
  0.55 mm under the natural float, so this owl's natural float is about 8.2-8.4 mm, as
  forecast from 19.85 mm.
- Jason: "This all looks great ... Keep this for the demo."

## The rest of the board

| Quantity | Value | Kind | Record |
|---|---|---|---|
| Familiar perches' drive current, live mode | owl 65 mA, cat 31 mA, the same with the tokens on or lifted off: presence can't be seen this way | board | `results/2026-11-09/125924_fam_presence.json` |
| Tap threshold (LSM6DS3) | 0.75 g never fired; 0.31 g needed firm taps; 0.19 g is the current setting | board, Jason | `firmware/src/sensors.c` |
| Theremin pad | set off by fingers wrapped round the owl token's edges | Jason | REVB 1.6 |
| LEDs round the token targets (D12, D14, D18; D34, D35, D28) | At full they drown the tokens' own LEDs. Off, they lose the circling "put it here" effect and the x-ray view of the coil through a token. Play mode now gives them a soft turning glow; Jason hasn't judged it yet | Jason | REVB 1.7 |
| Wisps D30, D31 (cat) and D10 (owl) | read as legs | Jason | REVB 1.7 |
| The bat's eye tank | about 82 kHz; the 100 kHz levitation PWM makes the eyes flicker; the 80 kHz carrier (`lev eyes`) lights them | board, Jason | REVB 1.11 finding 7 |
| Board 1's TP1-TP6 to the USB shell | 800 k, 10 k, 2 M, 280 k, 105 k, 20 k | bench, day 1 | REVB 3.4 |

## Not yet measured

- The cap-less bat's real weight, with the magnet taped on.
- The third owl's natural float (`zp_i` 0): about 8.2-8.4 mm by the second owl's slope, not flown.
- The eye carrier's real loss in watts (the IR says a few kelvin at 0.1; nothing measured
  at 0.2 and over since the 67 °C of 2026-11-09).
- The pendulum coils' resistance with a meter (2.29 Ω drawn; 3.0 Ω from the single-duty step).
- The rest of REVB 3.4.
