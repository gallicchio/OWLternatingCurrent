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
| Same, new owl (to be printed) | 12.45 mm | `OWL_LIFT` 12.5 | computed | `check.py`, 2026-11-09 | `print/out/owl.stl` |
| Owl's slot for the magnet | 10.25 × 2.2 mm | magnet 10 × 2 | computed | `check.py` | `print/out/owl.stl` |
| Float gap with no current, 14.05 mm lift, 4.70 g bat | 6-6.6 mm | 8.5 mm designed | board | the zero-power walk's end point | `results/2026-11-08/*_lev_try.json` |
| Same, from the model at 4.70 g | 6.7 mm | | fit | `sim/physics/levitation_onemagnet.py` (gap + lift = 23.1 mm) | REVB 1.11 finding 8 |
| Expected with the new owl, a bat of 4.2-4.3 g | about 8.9 mm | | fit | same model | HANDOFF.md |
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
- The new owl's float gap.
- The eye carrier's real loss.
- The pendulum coils' resistance with a meter (2.29 Ω drawn; 3.0 Ω from the single-duty step).
- The rest of REVB 3.4.
