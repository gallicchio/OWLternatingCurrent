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
- **The speaker made no sound** at `run.py tone` (440 Hz, amplitude 0.25 of full scale,
  the image's maximum) in either position of SW3. The amplifier's enable path works: the
  12 V current steps 1.35 ↔ 3.12 mA as SW3 toggles, which is the NS4150B's quiescent
  current. What is wrong is still open (section 3.1). Whatever it turns out to be, rev B
  wants the path probeable without flipping the board: test points at GPIO8's PWM, after
  the two RC filters, at IN+, and a way to reach the speaker pads with a probe tip.
- Consider driving the amplifier's CTRL from a GPIO and reading SW3 on a GPIO, so the
  firmware knows the switch and can mute by itself.

### 1.3 The tokens
- **Both tokens resonate far from their design frequency** on their own perches (stage
  6.2, `172647_perch.json`), while the perch numbering is verified right from the
  netlist (U9 → L6 at the left, the owl; U10 → L7 at the right, the cat):

  | token, on its own coil | bump | design | off by |
  |---|---|---|---|
  | owl (C401 100 nF, L401) | 208 kHz | 142 kHz | +46 % |
  | cat (C501 22 nF, L501) | 145 kHz | 303 kHz | −52 % |

  145 kHz is what 100 nF gives on 12.5 µH; 208 kHz is 47 nF on 12.5 µH. The BOM has the
  right values (C97946 100 nF, C77069 22 nF), so either the capacitors were swapped or
  mis-placed at assembly, or the coils are not 12.5 µH. Settle it with stage 6.1 (`run.py
  tank owl`, then `cat`: each token alone with the generator and the pickup loop) and a
  look at C401/C501.
- Rev B: measure the coil's inductance on rev A before choosing the tank capacitors;
  give each token two capacitor footprints so it can be tuned; and keep the owl and cat
  frequencies far enough apart that a 30 % error cannot swap them (the firmware's
  windows, 116-168 and 248-358 kHz, are ±18 %).

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

### 3.1 Why is the audio silent?
Amp enable is fine (section 1.2). Next, non-invasively: with SW3 on, play a 4 s tone
while logging the 12 V current. A rise of about 1 mA means the amplifier is driving a
load, so the fault is the speaker or its joints (LS1 is through-hole; JLCPCB asked about
its orientation and it was right). No rise means no signal reaches the amplifier: GPIO8's
PWM (146 kHz, 10-bit), the two 1k/10n RC stages, the 22n/220k coupling, or the NS4150B's
input. Then the probe tip, never a ground clip, on each speaker pad against ground.

### 3.2 Which token part is wrong?
Swap the tokens (cat on the left coil, owl on the right) and `run.py perch`: if the bumps
follow the tokens, the tokens are off; if they stay with the perches, the perches are.
Then stage 6.1 for each token's own frequency and Q, and a look at C401 and C501.

### 3.3 Are the coils really 3.0 Ω?
Fluke across a pendulum coil's pads with the power off (and across L6/L7 for
`FAM_R1_OHM`). If 3.0 Ω is real, is the inner copper 1 oz as ordered?

### 3.4 Not yet measured
- Board 2 (still sealed, the reference): its TP1-TP6 resistances against board 1's
  800 k / 10 k / 2 M / 280 k / 105 k / 20 k to the USB shell.
- Stage 6.1 tanks: owl, cat and bat frequency and Q.
- Stage 7: the tree's LP5036 at 0x32 and its LEDs; the perch's DRV5055 and the levitation
  coil's current step (`kcs` vs 2.9 mT/A, the 100 kHz residue).
- Stage 8: IMU axis signs by tilting; the light sensor against the board's own LEDs; the
  LED duty model (12-bit truncation) with a photodiode; the TMAG5273's depth and the
  thread length for the pendulum; the bat's mass and float gap; the coil thermal
  constants with an IR thermometer; `SCENE_MOON_STAR` (which end of the arc is the moon).
- The LED rail's 3.60 V turn-on sample (section 1.5).
- The violet LEDs' UV content, if anything beyond the datasheet is wanted (section 1.7).
