# Rev B: what to change, and what is still open

Started 2026-11-06, the evening of the first bench day on rev A board 1 (`BRINGUP.md`,
results in `bringup/results/2026-11-06/`). This is the one list to add to: anything found
on the bench, in the firmware or in the docs that rev B should change, and every question
that a measurement has not yet answered. Older rev B notes live in `PLAN.md` §10,
`DESIGN_REVIEW.md` §10-11, `HANDOFF.md` and `firmware/README.md` ("Still open"); they
are folded in here so nothing has to be chased.

Stages 0-5 and 6.2 of the bring-up ran on 2026-11-06. Stages 6.1 (tanks alone), 7 (tree,
perch) and 8 (the real firmware: pendulum, levitation, scenes) have not.

## 1. Changes for rev B, from the bench

### 1.1 Test points
- **Put every test point on one side, with a ground beside each.** Rev A has TP1 (+1V1)
  and TP2 (+4.8V) on the bottom and TP3-TP6 on the top. With the supply and USB plugged in
  the board lies scene-up, so half the rails need the board flipped, and one ramp was
  aborted because a probe hook had landed on TP6 instead of TP3. A hook on TP2 also lost
  contact and read 4.78 V sliding to 4.00 V while the current never moved; the Fluke read
  4.806 V once reseated. Loops or pads a hook holds, labelled with the net name in silk.
- Add test points on the audio path (the PWM filter's output, the amplifier's input and
  CTRL) and on the familiar current senses; see 1.2 and 2.1.

### 1.2 Audio
- **Nothing was heard at `run.py tone`** (440 Hz, amplitude 0.25 of full scale) in either
  position of SW3, and the first reading was a broken path. The evening's measurements
  (`212529_audio.json`, `213*_speaker_scan.json`) say otherwise: the amplifier wakes with
  SW3 (+1.8 mA at 12 V), a full-scale tone adds 26 mA at 12 V (0.2 W into about 7 Ω,
  exactly a speaker), and the current against frequency shows the voice coil's own
  mechanical resonance as an impedance peak at 1.8 kHz and its inductance above it. The
  chain GPIO8 → R18/C29 → R19/C30 → C28/R20 → U14 → LS1 is intact and the cone moves. The
  likely reason nothing was heard: 13 mW at 440 Hz, two octaves under a 23 mm speaker's
  resonance, in a lab. To confirm by ear: `run.py console tone 1800 3000 1.0`.
- If that is it, the firmware's ceiling (`AUDIO_VOLUME_CEILING` 0.25) and the voice's
  pitch range want revisiting against this speaker: it is a tweeter. Rev B could use a
  larger speaker, or an enclosure/port in the print, for anything under 1 kHz.
- Still worth having in rev B: test points at GPIO8's PWM, after the RC filters and at
  INP, and speaker pads a probe tip can reach from the top, so this takes a minute, not
  an evening. And the amplifier's CTRL from a GPIO with SW3 read by a GPIO, so the
  firmware knows the switch and can mute by itself.

### 1.3 The tokens
- **The tokens are almost certainly right; the first reading (wrong capacitors) was
  not.** The bump a sweep sees is the coupled mode at ft / sqrt(1 − k²), and a bare token
  lying on its perch couples far harder than the 3 mm gap the model assumed (k 0.47,
  `sim/physics/README.md`). The evening's 90-500 kHz sweeps (`212627`, `212631_sweep.json`)
  with the perch numbering verified from the netlist (U9 → L6 left, owl; U10 → L7 right,
  cat):

  | token, bare on its coil | bump | design ft | k² = 1 − (ft/f)² |
  |---|---|---|---|
  | owl (C401 100 nF) | 214 kHz | 142 kHz | 0.56 |
  | cat (C501 22 nF) | 452 kHz, and an image at 150 kHz | 303 kHz | 0.55 |

  One coupling (k ≈ 0.75) explains both, where the wrong-capacitor story needed two
  unrelated wrong values (44 nF and 10 nF). The cat's 150 kHz bump is the drive's 3rd
  harmonic reaching 450 kHz: the sweep's narrow pulses carry it almost fully
  (`familiar.c`'s w3 ≈ 0.97), which is why `run.py perch`, stopping at 400 kHz, saw only
  the image and called the cat 145 kHz. The 3rd-harmonic image is sharper than the
  fundamental's bump because the frequency axis is compressed by 3.
- **To settle it with hands** (section 3.2): a 2-3 mm non-metallic spacer, or the
  printed figure, under each token and `run.py sweep` again; the bumps should move down
  toward 161 and 343 kHz (k 0.47). Stage 6.1 (`run.py tank`) gives each tank's own ft.
- **Firmware, not copper:** `familiar.c` fits k² only up to 0.40 and ft from 78 % of the
  peak (k ≤ 0.63). A bare token (k² 0.55, ft at 67 % of the peak) is outside the fit, so
  the real firmware would misname or miss tokens without their printed floor. Extend
  `K2C` to 0.6 and the ft range to 0.62, or keep the floor and say so in the print. The
  sweep's 400 kHz ceiling also hides a hard-coupled cat; the 3rd-harmonic path in
  `familiar.c` (line 227) is what finds it.
- **The sweep's duty is quantised:** at 200-500 kHz the PWM period is 150-375 counts, so
  duty 0.03 jumps by 10-20 % between adjacent frequencies and the curves show steps
  (`212626_sweep1.png`). `perch_set` could keep the commanded duty by rounding the
  period, or the reading could be normalised by the duty actually set (`fduty`).
- Rev B: still worth measuring the coils' inductance on rev A before rev B's capacitors
  are chosen, and keeping the two frequencies far enough apart that coupling cannot swap
  them; but rev A's tanks do not need changing on this evidence.

### 1.4 The coils
- **Pendulum coils read 3.0 Ω, not 2.29 Ω** (all three, +31-33 %, from the DRV8874's
  current mirror in `163145_coils.json`). Systematic, so either the copper is thinner
  than the model or the mirror's gain is off. Confirm with the Fluke across a coil, power
  off (section 3.3). Then fold the right number into `COIL_R20_OHM` and `FAM_R1_OHM`
  (`firmware/src/config.h`), and into the coil generator's resistance model, so the
  pendulum's kicks and the resistance thermometer start right.

### 1.5 Power
- Idle at 12 V is 8.6 mA with the ROM bootloader (estimated 15-40 mA): update
  `bringup/expect.py`. Rails: 12.013 / 4.806 (Fluke) / 3.298 / 1.091 V, VSYS 4.525 V,
  4.8 V ripple 22 mVpp. All within windows.
- One scope sample of 3.60 V on +3V3 at turn-on (the ramp's 7 V step). One sample, so
  maybe noise; worth a proper turn-on capture before deciding anything. If real, the
  3.3 V regulator overshoots and the RP2354A's absolute maximum is 3.63 V.

### 1.6 The theremin
- Both oscillators run at about 310 kHz (moon, pitch) and 356 kHz (ghost, volume), not
  the 0.5-1 MHz assumed. A finger on the moon pulls it to 33 kHz, on the ghost to
  29.7 kHz: a 90 % drop, far more than the 3 % assumed for a hand nearby. The firmware's
  `THEREMIN_*` constants and `bringup/expect.py` want the measured numbers; the
  oscillator's range may want re-centring once the hand-near (not touching) span is
  measured.

### 1.7 LEDs
- All 31 LEDs light, in the right order, 4.8-4.9 mA each on 12 V at duty 0.5 (the
  estimate was 5.2 mA). No change needed.
- The violet stars are 400-410 nm (HL-A-3528S7VC). A rough IEC 62471 estimate puts them
  in the exempt group at these currents and distances, but it is an estimate; measure
  before a child sleeps under it, or move to ≥420 nm parts, or diffuse them.

## 2. Changes for rev B, known before the bench

### 2.1 Documentation and generator fixes (cheap, do first)
- `gen/pins.py` says the perch current sense is "0.5 R, ×20.6, 10.3 V/A"; as built it is
  0.1 Ω × 101 = 10.1 V/A, which `config.h` already uses. Fix the comment and regenerate
  `board_pins.h` (`python3 gen/firmware_pins.py`).
- `DESIGN_REVIEW.md` §10 says "a 5 A PTC"; F1 holds 3 A and trips by 6 A.
- `bringup/expect.py`: idle current, theremin frequencies, coil resistance, token
  frequencies once measured.

### 2.2 Board
- **USB alone lights nothing:** the LEDs' anodes are on the 4.8 V rail, fed only from
  the 12 V adapter. Rev B could feed the LED rail from VBUS too (a diode-OR or the buck
  from either source) so the board shows life on a laptop.
- **The GPIO binding:** `gen/assign.py` scored a fixed-cut proxy; re-ranking with
  `cyclic_crossings` finds 76 crossings where rev A kept 84, and letting bridges use
  GPIO16-25 finds 48-63. Rebind for rev B.
- **The panel:** the bat hangs by two tabs on its head edge; a third if one ever breaks
  loose in reflow.
- **The light sensor** U16 looks up, 11 mm from a star and next to the tree's own LEDs.
  If it chases the board's own light (stage 8), move it or hood it.
- **The IMU** U15 is on the bottom, so KiCad mirrors it and only its X keeps the board's
  sense. Harmless (signs set in firmware once tilted), but on top it is simpler.
- **A temperature sensor beside the coils** (PLAN.md §7): the firmware uses the IMU's
  die as the coils' ambient, which is nowhere near them.
- **LP5036:** EN tied high, VCC on USB alone? (firmware README question 2.)
- **USB VID:PID** 1209:0001 is a test PID; a release needs its own.
- The familiar drive has no time limit on driving a "token" (a phone's Qi coil fits the
  model): a firmware limit, and the leave check during the ramp.

### 2.3 Features deferred from rev A
- WiFi on an ESP32 with the ghost-shaped monopole antenna (`sim/antenna/`, no matching
  parts needed); a phone "spell book"; the time for the moon phase.
- Owl eyes that follow you (time-of-flight).
- An echolocating bat (ultrasound).
- Back-EMF sensing of the pendulum; multi-board synchrony.

### 2.4 Not the board: the prints and the bench scripts
- The levitation still has no printed cradle holding the bat 2-3 mm below the float gap
  (PLAN.md §10).
- `run.py rails` takes the Fluke's rail as a positional (`rails +4.8V`); `--dmm` is the
  Fluke's serial port. Rename one.
- `run.py tone` has no frequency or amplitude options, and the image caps the amplitude
  at 0.25.
- A helper that opens the supply without `keep_on()` turns it off on exit; `capture`
  leaves the scope in SINGLE trigger. Both bit us once.

## 3. Open questions

### 3.1 Why was the audio silent?
The electrical chain is proven (section 1.2): a full-scale tone draws a speaker's worth
of current and the voice coil shows its mechanical resonance at 1.8 kHz. What is left is
the ear: was 13 mW at 440 Hz simply inaudible in the lab from this 23 mm speaker? Listen
to `run.py console tone 1800 3000 1.0`. If that too is silent with the current rising
(`run.py audio`), the cone moves but the sound does not get out: look at how LS1 sits
(its grille up, nothing over it) and at the speaker itself.

### 3.2 Is the token story really coupling?
With a 2-3 mm spacer (or the printed figure) under each token, `run.py sweep 1 90000
500000 200` and `run.py sweep 2 ...`: the owl's bump should move from 214 toward about
161 kHz and the cat's from 452 toward about 343 kHz, and the cat's 150 kHz image toward
114 kHz. Lifting further moves them further toward 142 and 303. If the bumps do not move
with the gap, the coupling story is wrong and stage 6.1 (`run.py tank owl`, `cat`) with
the generator and the pickup loop measures each tank alone.

### 3.3 Are the coils really 3.0 Ω?
Fluke across a pendulum coil's pads with the power off (and across L6/L7 for
`FAM_R1_OHM`). If 3.0 Ω is real, is the inner copper 1 oz as ordered?

### 3.4 Not yet measured
- Board 2 (still sealed, the reference): its TP1-TP6 resistances against board 1's
  800 k / 10 k / 2 M / 280 k / 105 k / 20 k to the USB shell.
- Stage 6.1 tanks: owl, cat and bat frequency and Q (the bare-perch sweeps say the owl
  and cat tanks are near design; 6.1 is the direct check).
- Stage 7: the tree's LP5036 at 0x32 and its LEDs; the perch's DRV5055 and the levitation
  coil's current step (`kcs` vs 2.9 mT/A, the 100 kHz residue).
- Stage 8: IMU axis signs by tilting; the light sensor against the board's own LEDs; the
  LED duty model (12-bit truncation) with a photodiode; the TMAG5273's depth and the
  thread length for the pendulum; the bat's mass and float gap; the coil thermal
  constants with an IR thermometer; `SCENE_MOON_STAR` (which end of the arc is the moon).
- The LED rail's 3.60 V turn-on sample (section 1.5).
- The violet LEDs' UV content, if anything beyond the datasheet is wanted (section 1.7).
