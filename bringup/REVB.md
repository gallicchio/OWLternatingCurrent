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
  4.806 V once reseated.
- **Every test point is an MMCX jack, or U.FL only where there really is no room for
  MMCX.** Each carries its own ground, so a probe or a coax to the scope plugs straight
  in: no little wires soldered on, no ground clip on one wire and probe hooks on the
  others, nothing to fall off while the board sits unattended (TP2's hook did exactly
  that during the evening run). Label each with the net name in silk. For the production
  run leave them unpopulated; the bare footprints then serve as ordinary test pads.
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
- **Confirmed by ear on 2026-11-07** (`131633`, `131705_audio.json`,
  `131913_speaker.json`, SW3 on): the speaker scan from 200 Hz to 4 kHz at full scale was
  clearly audible, quiet at the bottom, loudest around the 1.8 kHz resonance, then
  quieter again toward 4 kHz as the voice coil's inductance takes over (the drive current
  falls from 26 to 19 mA). The repeat of the 440 Hz test at 0.25 is what was not heard on
  day 1: 2 mA, 13 mW, where the speaker is weakest.
- **Equalise the voice to the speaker in firmware** (Jason, 2026-11-07). The theremin's
  pitch range is 200-1000 Hz (`THEREMIN_F_LO_HZ`/`_HI_HZ`, `config.h`), entirely below
  this speaker's 1.8 kHz resonance, where a small cone's output falls steeply with
  frequency; a player sweeping the moon hears the loudness change with the pitch, not
  with the pumpkin. The firmware knows the pitch it is playing, so `voice_set` (or
  `audio_set`) should multiply the requested amplitude by a frequency-dependent gain
  table measured once with a microphone (or a sound-level app) at 1 m: boost the low
  end, suppress the resonance, to make equal-volume notes sound equal. The ceiling
  `AUDIO_VOLUME_CEILING` 0.25 then applies after equalisation, or the low notes never
  get the headroom they need; measure how much boost 200 Hz needs before deciding whether
  the range should start higher (300-400 Hz) instead. The same table serves the familiar
  voices.
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
- **Settled on 2026-11-07 with folded paper under each token** (`131929`, `131933`,
  `132017`, `132052_sweep.json`): the owl's bump moved from 214 to 164 kHz, against the
  161 kHz predicted for the printed floor's gap; the cat's from 452 to 309 kHz, now only
  2 % above its design 303 kHz. Coupling, not capacitors.

  | token on paper | bump | design ft | k² | bump height over the drive's own current |
  |---|---|---|---|---|
  | owl | 164 kHz | 142 kHz | 0.25 (k 0.50) | +107 % at duty 0.03 |
  | cat | 309 kHz | 303 kHz | 0.04 (k 0.19) | +20 % at duty 0.06; invisible at 0.03 |

  The paper towels hid the perches, so the cat's weak showing was placement (off
  centre, or more paper), not the cat: on clear plastic bags, centred and on their own
  perches (`1337xx`-`1339xx_sweep.json`, same morning), both tokens couple alike:

  | token, centred on a bag | bump | design ft | k² | bump height, duty 0.03 / 0.06 |
  |---|---|---|---|---|
  | owl | 178 kHz | 142 kHz | 0.36 (k 0.60) | +140 % / +400 % |
  | cat | 391 kHz, image at 130 kHz | 303 kHz | 0.40 (k 0.63) | +110 % / +230 % |

  Three placements, one story: bare k 0.75, a bag 0.6, a thicker spacer 0.2-0.5, and the
  bump's height falls with k². The familiar's sweep must therefore work from k 0.2
  (a token hovering a few mm up) to 0.75 (lying on the copper), and the detection
  threshold set with the real printed figures. Stage 6.1 (`run.py tank`) still gives each
  tank's own ft and Q, which the fit needs.
- **Lighting the tokens** (`perch` at duty up to 0.5 in the bring-up image since
  2026-11-07, with an ISENSE trip at 0.2 A; both tokens on bags, k 0.6):

  | drive | duty | ISENSE | power from 4.8 V |
  |---|---|---|---|
  | owl perch at ft 142 kHz | 0.15 / 0.25 / 0.35 / 0.50 | 17 / 39 / 61 / 77 mA | 0.08 / 0.19 / 0.29 / 0.37 W |
  | owl perch at the coupled peak 178 kHz | 0.20 | 103 mA | 0.49 W |
  | cat perch at ft 303 kHz | 0.15 / 0.25 / 0.35 / 0.50 | 7 / 17 / 28 / 37 mA | 0.03 / 0.08 / 0.13 / 0.18 W |
  | cat perch at the coupled peak 391 kHz | 0.20 | 72 mA | 0.35 W |

  **Both tokens light** (seen 2026-11-07 13:52, on bags): orange and purple together on
  the owl at 178 kHz, duty 0.2 (ISENSE 105 mA), and on the cat at 391 kHz, duty 0.2
  (72 mA), the two perches alternated every 0.45 s from the host (the bring-up image
  drives one perch per command). The whole wireless chain works: perch bridge, coil,
  token tank, both LEDs. Whether the ft drive at duty 0.5 also lights them was not
  watched.

  Driving at ft, as `familiar.c` does, the token at its own resonance reflects a large
  resistance into the perch, and the harder the coupling the larger it is: a full square
  wave at ft reaches 0.37 W for the owl but only 0.18 W for the cat, under the 0.25 W
  target (`FAM_P_TARGET_W`), and both numbers fall further as the token is pressed onto
  the copper (k 0.75). At the coupled peak a fifth of the duty delivers more, but there
  the current cap no longer protects an empty perch, which is why the design avoided it.
  Options for the real firmware: drive at ft with the power loop allowed up to duty
  0.5 and accept what the cat gets; or drive between ft and the peak, closed loop on
  ISENSE itself (the cap enforced by measurement, not by the empty-perch model); or, in
  rev B, a 12 V perch bridge (2.5 x the voltage, 6 x the power at the same duty). To
  measure the worst case: tokens bare on the copper, `run.py console perch 1 142000 0.5
  6000` and `perch 2 303000 0.5 6000`.
- **The child's gesture, in firmware.** The coupled-mode frequency rises with k, so the
  owl occupies 142-215 kHz and the cat 303-460 kHz for every placement from hovering to
  lying on the copper, and the two bands never overlap: the fit's job is only to say
  which band the bump is in (the cat's 3rd-harmonic image, 101-153 kHz, lands in the
  owl's band, but on the cat's own perch; a bump above 280 kHz on the same perch
  disambiguates). Today's `familiar.c` cannot follow the gesture: `K2C` stops at 0.40,
  the ft grid starts at 0.78 x peak, and the sweep stops at 400 kHz, so a token set down
  on the copper (k² 0.55, ft at 0.67 x peak, cat at 452 kHz) is "unknown" and dark.
  Extend `K2C` to 0.6, the ft grid to 0.62, `FAM_F_MAX_HZ` to 500 kHz (the PWM clamp
  follows at 1.1 x), or classify by the peak's band directly. "Lights as it arrives" is
  limited by physics: the bump is ~20 % at k 0.2 (a few mm up) and gone at a centimetre,
  so detection starts in the last few millimetres, and the 2.5 s `FAM_RAMP_S` fade is
  what the child sees as the arrival. Staying lit on the copper is then the drive-power
  question above, plus the drive's own frequency clamp.
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
- **Played on 2026-11-07** (the real firmware): it works, but at the assumed 3 % span a
  hand had to be almost touching, and the voice was faint. `THEREMIN_PITCH_SPAN` and
  `_VOL_SPAN` are now 0.01 (a 1 % drop is the full range), `AUDIO_VOLUME_CEILING` 1.0 and
  the default loudness 0.5. The hand-near span is still unmeasured: `status` prints
  `f_pitch`/`f_vol`, so a hand at 1, 2, 5 and 10 cm is a two-minute measurement.
- The theremin scene's arc is now a stepped meter from the moon's end (off is off; one
  star per step; the top one fractional) and the pumpkins follow the volume from nearly
  dark. The ambient twinkle used to sit under the meter and read as random dim stars.

### 1.7 LEDs
- All 31 LEDs light, in the right order, 4.8-4.9 mA each on 12 V at duty 0.5 (the
  estimate was 5.2 mA). No board change needed.
- **The firmware's LED groups were in channel order, not position order** (found by eye
  on 2026-11-07: the theremin's arc meter lit "the four nearest the witch first,
  backwards"). `gen/leds.py` numbers the stars left to right, but the LP5036 channels were
  reassigned for the routing, and `gen/firmware_leds.py` listed each group in table
  (channel) order: the arc ran STAR3, 2, 1, 0, 8, 7, 9, 10, 11, 6, 5, 4, the owl eyes were
  paired across owls. Fixed in the generator (groups sorted by the number in the name;
  eyes by owl then L, R); `led_map.h` regenerated; `test_leds` passes. Not a board change,
  but any future reassignment of channels is now harmless.
- The violet stars are 400-410 nm (HL-A-3528S7VC). A rough IEC 62471 estimate puts them
  in the exempt group at these currents and distances, but it is an estimate; measure
  before a child sleeps under it, or move to ≥420 nm parts, or diffuse them.

### 1.8 The real firmware on rev A (2026-11-07, evening)
- **It crashed within 25 ms of boot, three times, and parked in BOOTSEL** exactly as the
  watchdog rule intends. No USB enumeration was ever seen, so the console could not say
  why; the Debug Probe's UART on J5 is not wired (nothing came out), nor is SWD. Found with
  a diagnostic build (`cmake -DOWL_DIAG=1`: the watchdog fed unconditionally, a `diag`
  event every second with core 1's tick count and stage, and a hard-fault handler that
  records the fault instead of the SDK's silent breakpoint): core 1 had done 209 ticks
  and was spinning in the SDK's `adc_fifo_drain()`, waiting for an ADC that never became
  READY. **The cause:** the tick's PWM-wrap interrupt (IRQ 9) and the ADC burst's DMA-done
  interrupt (IRQ 11) share the highest priority, so when both are pending the PWM wins;
  the tick handler then saw the DMA idle, assumed `adc_done_isr` had already stopped the
  ADC, and drained a FIFO that the still free-running ADC kept filling, at a priority the
  DMA handler could never preempt. A race of a few hundred nanoseconds per 100 µs tick:
  about once in 200 ticks. **Fixed in `rt.c`:** the tick handler yields when the DMA-done
  interrupt is still pending. Core 1 then ran 48 000 ticks per 5 s, indefinitely.
- **Core 1's work does not fit its tick.** `tick_us_max` reads 168-309 µs against a 100 µs
  tick (`CTRL_TICK_HZ` 10 kHz), so about one tick in 30 is skipped ("overruns") and the
  `adc` fault latches at boot. Everything still runs, at an effective 3-9 kHz; the
  levitation loop was designed at 10 kHz. Either trim `control()` (the thermal models and
  the lev step are the heavy parts; profile with `tick_us_max`) or lower the tick to 5 kHz
  and re-check `test_lev`. A design decision, not taken tonight.
- **The watchdog rule works** (three resets to BOOTSEL), `picotool load -x` from BOOTSEL
  works, the console's `reboot bootsel` works, and the reset interface is there but
  picotool cannot open it without a udev rule for 1209:0001 (it says "unable to connect,
  try sudo"). The bench scripts: `run.py flash owlternating` (positional) now works and
  `run.py console reboot bootsel` no longer waits for a reply.
- **Familiars, as designed (sweep and fit): the fit is degenerate on a bare token.** One
  bump fixes only the coupled mode ft/sqrt(1 − k²), so with k² free the owl's 214 kHz
  bump reads equally well as an owl at 142 kHz (k² 0.56) or as the 3rd-harmonic image of
  a stranger at 441 kHz (k² 0.53); the fit picked the stranger, called it "unknown" and
  drove 441 kHz into the owl, dark. Changes: `K2C` to 0.6 and the ft grid to 0.62 (bare
  tokens), the fit restricted to the two known tokens with the perch's own preferred
  (`FAM_OTHER_PERCH_PENALTY`), `FAM_SWEEP_N` 32, the sweep every 0.2 s, fades 0.8/0.5 s.
  With that both tokens were named and lit on the copper. A stranger at 240 kHz is now
  taken for the cat (`test_familiar` updated); the tuning the fit reports is only good to
  about 12 %. The ADC-side detection threshold and `FAM_BASE_SLACK` were not touched.
- **Live mode is the default now** (`fam live`; `fam sweep` for the fit): each perch drives
  its own token's tuning at the empty-perch current cap all the time; the token's glow
  follows the hand that brings it in, instantly; "present" (the ring swirl, the events) is
  the power drawn beyond an empty perch's, read every millisecond with a 20 ms / 100 ms
  debounce (`FAM_LIVE_*`). Jason's reaction with the child present: the sweep's seconds of
  lag on a put-down token were "annoyingly long"; live mode "seems better". Costs: the
  empty perches run all the time (~15 mA each from 4.8 V, the coil warm, no sleep), a coin
  on a perch reads as present, and the other perch's token on a perch stays dark but
  also unannounced. `FAM_I_MAX_A` is 0.25 now (the owl perch's square wave is 0.22 A
  anyway).
- **Reach.** The child had to bring a token within a millimetre or two; Jason wants
  centimetres ("spookier, more physics"). The 4.8 V bridge is the limit: the owl perch is
  already a square wave (0.22 A into 27 Ω of coil reactance), the cat's 58 Ω allows
  0.105 A, and the token's power falls as k². Rev B options, in order of effect: a series
  capacitor in each perch coil, tuned to its token (42 nF at 142 kHz, 9.2 nF at 303 kHz),
  cancels the reactance and lets the 4.8 V bridge push up to 1.4 A (then the firmware must
  cap the current by ISENSE, not by duty); a 12 V perch bridge (2.5 x the current); larger
  or more turns on the perch coils; lower-Vf LEDs or a step-up tank in the tokens. The
  series capacitor could be tried on rev A as a bodge (cut the track to L6, 42 nF C0G
  across the cut) before rev B.
- **In daylight the show sleeps** (the light sensor's `asleep` scene). For a demo in a lit
  room, `scene night` or `scene auto` after covering the sensor.

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

**Answered 2026-11-07: yes.** Jason heard the full-scale speaker scan plainly (section
1.2). The open question is now the equalisation and the pitch range, not the hardware.

### 3.2 Is the token story really coupling?
With a 2-3 mm spacer (or the printed figure) under each token, `run.py sweep 1 90000
500000 200` and `run.py sweep 2 ...`: the owl's bump should move from 214 toward about
161 kHz and the cat's from 452 toward about 343 kHz, and the cat's 150 kHz image toward
114 kHz. Lifting further moves them further toward 142 and 303. If the bumps do not move
with the gap, the coupling story is wrong and stage 6.1 (`run.py tank owl`, `cat`) with
the generator and the pickup loop measures each tank alone.

**Answered 2026-11-07: coupling.** Folded paper under the tokens moved the owl to 164 kHz
and the cat to 309 kHz (section 1.3). Open: how faint the cat is at the printed floor's
gap, and the sweep duty and threshold the familiar needs to see it.

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
  constants with an IR thermometer. (`SCENE_MOON_STAR` is settled: the moon is at STAR0's
  end; the meter's odd order was the LED-group bug of 1.7.)
- The LED rail's 3.60 V turn-on sample (section 1.5).
- The violet LEDs' UV content, if anything beyond the datasheet is wanted (section 1.7).
