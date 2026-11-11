# Rev B: what to change, and what is still open

Started 2026-11-06, the evening of the first bench day on rev A board 1 (`BRINGUP.md`,
results in `bringup/results/2026-11-06/`). This is the one list to add to: anything found
on the bench, in the firmware or in the docs that rev B should change, and every question
that a measurement has not yet answered. Older rev B notes live in `PLAN.md` §10,
`DESIGN_REVIEW.md` §10-11, `HANDOFF.md` and `firmware/README.md` ("Still open"); they
are folded in here so nothing has to be chased. The measured numbers themselves (masses,
coil ohms, sense gain, thermal constants, IR readings) are tabulated in
`bringup/MEASUREMENTS.md`.

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
- **First pass, in firmware on 2026-11-08: constant electrical power** (Jason: "if you
  have a sense for how much power is being used, try to first equalize that"). From
  `results/2026-11-07/131913_speaker.json`, the 12 V current a full-scale tone adds is the
  power into LS1: 26.4 mA at 200 Hz, 25.3 mA at 1 kHz, 21.2 mA at the 1.8 kHz resonance,
  18.7 mA at 4 kHz. `voice.c` scales the amplitude by sqrt(d(1 kHz) / d(f)), in log f,
  capped at `AUDIO_VOLUME_CEILING`: 0.98-1.00 over the theremin's 200-1000 Hz, 1.09 at the
  resonance, 1.16 at 4 kHz. **Over the theremin's range that is under 0.2 dB: the speaker
  takes almost the same power at every pitch there.** What the ear hears changing is the
  cone's acoustic output, which falls steeply below the resonance and which no electrical
  measurement sees. At the resonance this table even boosts slightly, where the ear wants
  a cut. The acoustic table (a sound-level reading at each pitch) replaces it after the
  owl and bat.
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

- **Move the theremin's pad away from the owl's perch** (Jason, 2026-11-09). Holding the owl
  token by its edges, fingers round it, often plays the theremin by accident. Rev B: put
  the nearer pad further from the owl's target, or the target further from the pad.

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
- **The perches' rings drown the tokens** (Jason, 2026-11-09). The three purple LEDs round
  each familiar's perch (owl: D12, D14, D18; cat: D34, D35, D28) are so bright beside a
  token that the token's own LEDs, the interesting part, are hard to see. Fixed in
  firmware (`play`): an empty perch's ring glows softly and goes dark when a token sits on
  it. Rev B: a larger series resistor or a dimmer part for the rings, so even the show
  cannot drown a token.
  - A live perch cannot tell whether its token is there. Its supply current did not move
    when Jason lifted the tokens off and back (owl perch 65 mA, cat perch 31 mA;
    `results/2026-11-09/125924_fam_presence.json`). So the rings cannot dim for a token.
    Rev B: a sense that sees the token's load, such as the perch coil's voltage or its
    current's phase.
- **Three wisps read as legs** (Jason, 2026-11-09). D31 and D30 (WISP4, WISP5) sit under the
  CAT's silkscreen and look like its legs; D10 (WISP0) looks like the OWL's one leg. Rev
  B: move the hill's wisps away from both perches and their silkscreen figures.

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
- **Core 1's work mostly fit its tick; its worst ticks didn't. Fixed 2026-11-08:** the
  image now runs from RAM, and on USB alone its worst tick is 19 µs, with no tick skipped
  in a minute (`results/2026-11-08/210006_tick_budget_ram.json`). So the flash cache was
  the cause. What was measured before the fix, corrected 2026-11-08:
  over 30 h on USB alone, core 1 ran 9 610 ticks a second of 10 000, with 3.3 % skipped
  ("overruns") and `tick_us_max` at 322 µs (`results/2026-11-08/202947_tick_budget.json`).
  The 168-309 µs of 2026-11-07 were that same maximum, not a typical tick. Each tick has
  about 52 µs for the control step: 100 µs minus the 48 µs ADC burst (24 conversions at
  2 µs), during which core 1 waits. The `adc` fault latches at boot because it fires on
  the 11th skipped tick ever. Where the long ticks come from is not measured. The likely
  cause: all of core 1's code (about 10 KB) runs from flash through the 16 KB XIP cache
  shared with core 0, so a tick after core 0 has evicted it refills line by line.
  The options, roughly in order of value for effort. **Done in firmware on 2026-11-08,
  not yet tried on the board: the first three** (the whole image from RAM, the rate-based
  fault, the overlapped burst; firmware/README.md "Core 1's tick"):
  - **Core 1 from RAM** (`__not_in_flash_func` on its handlers, `lev_step`, the thermal
    and coil helpers; or the whole image copied to RAM: 134 KB of the 520 KB SRAM, 52 KB
    already used). Costs about 10 KB of SRAM. The test of the cache theory.
  - **A rate-based `adc` fault** (say, more than 1 % of ticks skipped over a second).
    Needed anyway: a settings save pauses core 1 for up to 200 ms on purpose.
  - **Pipeline the burst:** start the next burst first, then run the control step on the
    previous one. The step gets the whole 100 µs instead of 52. As done, the PWM it
    computes is applied when the overlapped burst ends, so each burst runs under one u,
    and the levitation's current model looks one step further back (`lev_ctrl.u_lag`):
    without that, `test_lev` chatters at 1.4 A rms; with it, 41 mA rms of noise current
    against 38 before. The delay from a burst's middle to its PWM grows from 40-75 µs to
    about 125 µs: 1.2° more phase lag at 40 Hz, 0.3° at the loop's 10 Hz.
  - **Oversample 4, not 8:** a 24 µs burst. The ADC noise rises by √2; levitation_loop.py
    chose 8.
  - **A 5 kHz tick:** about 150 µs for the step, and about 2° more phase lag at 40 Hz.
    But every tick-counted constant moves (lev_ctrl's `TICKS()`, the nFAULT filter,
    `TOP_TICK`'s alignment with the levitation PWM, 20 PWM periods per tick), `test_lev`
    and `test_rt` must be re-run, and it still would not cover a 322 µs tick.
  - **Trimming arithmetic** (one `thermal_r_ohm` per coil per tick, a reciprocal of V12
    instead of several divides): a few µs. Not where the long ticks come from.
  A skipped tick costs nothing yet (levitation off, the pendulum coils read their mirrors
  over eight ticks). For the levitation it would: `lev_ctrl` assumes a fixed step, so a
  skipped tick doubles the motion its derivative sees in one step.
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
- **Every coil was forbidden from 2147.5 s of uptime (found 2026-11-08, fixed).** The first
  hover attempt went to `inhibit` ("the coil may not run (12 V, a bridge fault)") with no
  fault, at exactly 2^31 µs of uptime (`results/2026-11-08/223426_lev_first.json`). Core 1
  kept its deadlines in 32-bit microseconds and compared them by signed difference. The
  nFAULT retry deadline, never armed, stayed 0 and read as 35.8 min in the future from
  then on, repeating. An expired coil request kept its owner and amps, so 2^31 µs after
  its deadline it would have come back to life, its coil on for up to 35.8 min.
  **Fix:** every deadline in `rt.c` is 64-bit (`time_us_64`), the request's under its
  seqlock, and a released request's deadline is 0. `test_rt` now jumps the clock past
  2^31 µs and across 2^32 µs, with a request and an nFAULT retry running across the wrap.

### 1.9 The tree-perch joint is turned round (found 2026-11-08)

**With the perch's coil in front of the tree, as designed, tree header J102's pin N meets
the perch socket J201's pin 17 - N.** The tree-base joint (J101 into J3) is right; the
same calculation shows it pin for pin, and the tree's LEDs and I2C work through it.
- **How it was found.** With the perch on, its two downlights drew nothing, the
  levitation Hall line read 0 V, and the levitation coil read 23.7 ohm, not 2.56
  (`results/2026-11-08/214506_leds.json`, `214402_logic.json`, `214521_coils.json`).
- **The geometry,** from the pad coordinates in `hardware/OWLternatingCurrent.kicad_pcb`
  and the assembled frames of `tools/render_3d.py`:
  - J102's pin 1 sits 8.89 mm to the viewer's right of the tree's centre line; J201's pin
    1 sits 8.89 mm to the left.
  - J102's odd row is the right-angle header's upper level, 3.81 mm behind the tree, so
    it is the rear row; J201's odd row is its front row.
  - Both are reversed, which is a 180° turn of the perch about the vertical.
- **The three readings follow from it.** The base's Hall line reaches the perch's LEV_A
  and goes to ground through the coil, so it reads 0 V. The perch's +3V3 and +5V come
  from the tree's two downlight lines, so the Hall sensor and the downlights have no
  supply. The coil's ends meet the perch's ground pins, which tie the bridge's two
  outputs to ground.
- **Rev A workaround:** the perch turned round, its coil behind the tree. Then every
  pin meets its own. The bat hangs behind the tree, which is good enough for the bench.
- **What the workaround costs** (Jason, 2026-11-09): with the bat behind the tree, the
  tree's owls and LEDs face away from whoever watches the bat. Nobody can see both the
  bat's hover and the owls' eyes (the bat's height indicator in `play`) at once, and the
  three pendulum coils under the perch can do nothing.
- **Rev B:** turn J201 by 180° on the perch (or J102 on the tree), and add the check that
  `gen/connectors.py` says `gen/board.py` makes but no code makes. That check: each
  header pin's position in the assembled set lands on its socket's pin with the same
  number.

### 1.10 Label every board-to-board header and socket (Jason, 2026-11-08)

Soldering J101, J102 and J201 on rev A, the pins could not be told apart, and nothing on
the silkscreen said which face each part goes on. On rev B, beside every header and
socket footprint (J3, J101, J102, J201), on both faces:
- **Pin numbers:** at least 1, 2, 15 and 16 at the ends of both rows, and a pin-1 mark
  that is still visible with the part soldered in.
- **Signal names** for the pins that matter: HALL, +3V3, +5V, LEV_A, LEV_B, SDA, SCL,
  DOWN0, DOWN1, and GND on one ground pin per end.
- **Which face the part goes on and which face its pins solder on:** for example
  "HEADER ON THIS SIDE" on the body's face and "SOLDER THIS SIDE" on the other.
  Near a right-angle header's edge: "PINS OUT HERE: INTO THE PERCH (J201)".
- **A matching label on the socket's board,** with the same pin numbers and names, so a
  look across the bend shows that pin N meets pin N. With the names on both boards, a
  meter can check every signal across each 90° bend before power goes on.
Together with 1.9's check in the generator, this makes a joint turned round, or a part
on the wrong face, visible before anything is powered.

### 1.11 The levitation: first hovers (2026-11-08, night)

Board 1 with the tree and the perch (turned round, 1.9), on the BK 9130's channel 1 by
hand at 12 V with a 3 A limit; the bat brought up by hand from below. Records:
`results/2026-11-08/*_lev_*.json`, video `references/20261108_230944_bat_capture.mp4`.
- **Calibration** (bat away, owl on the perch): the coil's field at the sensor 3.64 mT/A
  (model 2.89); the owl magnet's field at the sensor 7.48 mT with about 1.1 mT of the desk's
  stray field (model 6.36). Saved in flash.
- **What it took to hover,** in order:
  1. the 32-bit clock-wrap fix (1.8): the loop was locked out from 2147.5 s of uptime;
  2. the bridge's 0.5 µs pulse loss compensated (3.3): before it, every catch buzzed, the
     current swung several hundred mA and ran to its 2.6 A limit within half a second;
  3. a levitation-coil thermal limit that is not the copper node at 45 °C: the model's
     copper (0.3 J/K) jumps 20 K in a second at a catch's 2.6 A and stopped the coil
     again and again while Jason found the perch "warm, but not at all hot". Now the
     copper may reach 80 °C and the board node, under the owl's PLA, 50 °C (config.h).
     Measure with an IR thermometer, then fix the model's constants. Rev B: real
     thermometers at every coil (2.2).
- **The bat floats higher than designed.** The zero-power loop walks the set-point to its
  lower bound, so the magnets alone carry the bat nearer than the 8.5 mm design gap
  (estimated 6.6 mm). There the bat's tilted back end touched the perch. With `g0_mm 9.5`
  (bound 7.5 mm) it hovered clear: 163 s at 7.5 ± 0.3 mm, 0.34 A mean, 0.37 A rms, until
  the then 55 °C copper limit tripped; with the two limits, 107 s and then 201 s (at 0.33 A),
  each ended by the board node's 50 °C. `g0_mm 9.0` (bound 7.0 mm) failed: catches began
  near 5 mm and were lost on the way down. A fixed 9.5 mm set-point (`zp_range_mm 0`) needed
  more than the mean-current limit allows. The owl magnet's field matched the model, so
  the bat is probably heavier than the 3.6 g assumed: weigh it. The cure is a stronger
  bias (a second magnet in the owl) or a lighter bat, so that the zero-power gap is 8.5
  mm or more.
- **The levitation coil's thermometer (firmware, 2026-11-09, not yet on the board).** The
  hovers all ended in the thermal model, which had no measurement for this coil: only the
  pendulum coils got the copper-resistance correction. Now the levitation coil has it too,
  from 50 ms means of u·V12 over the mirror's current while it drives one way at 0.3 A or
  more (`rt.c` step 6b), and a cold coil's reference calibrates over a 5 K band instead of
  0.3 K. `status` reports it under `lev_thermo`. The same night: a clear now restarts
  the `adc` fault's one-second window, which had re-latched it from overruns before the
  clear.
- **The thermometer on the board (2026-11-09 morning): nine findings.**
  1. **It tripped a cool coil 0.3 s into the first catch** (`results/2026-11-09/084010_lev_try.json`).
     The catch heated the model's copper past the 5 K calibration band before five 50 ms
     readings were in, so the calibration was dropped. An uncalibrated reading could still
     push the model up, and a catch's window read 4.49 ohm, "213 °C": the board node went
     to 47 °C and the 50 °C limit stopped the loop. Fixed: the levitation coil's
     uncalibrated readings are only reported, and the calibration ends on its five
     readings, with a 30 K band. Readings also start only one second into a hold, but
     that was not the cause. The catch's 4.49 ohm is the same as the steady 4.4 ohm with
     no bat (finding 2). The coil is 30 uH, so a 0.5 A change within a 50 ms window adds
     0.3 mV against about 1.5 V. The bat's motion adds well under a millivolt. No hold is
     still (Jason: the bat turns, sways and bobs, and starts again when stopped by a
     finger), and none needs to be.
  2. **V/I is 4.3-4.6 ohm, steady, with no bat** (`091250_coil_thermo_sweep.json`, the console
     driving 0.2-0.8 A for 1.5 s each: no inductance, no motion), in proportion at every
     current. So it is not the coil's 2.51 ohm (3.3): either the DRV8874's IPROPI reads
     about 0.62 of the current (it mirrors only the high-side FETs: in the brake part of
     each period it reports nothing), or the bridge's mean voltage is not u x V12. The
     two-duty fit of 3.3 cancels such errors; a single ratio does not. A ratio
     thermometer (hot V/I over cold V/I) cancels them as long as they stay constant, so
     the reference is now kept in the reading's own units (`rm_ref_ohm`), apart from the
     R(T) that the model's power and the loop's feedforward use. Before that split, the
     calibration put 4.31 ohm into both. To settle it: a DC ammeter in series with the
     coil, or the BK's current display, at a steady console drive.
  3. **The wiring adds up to 0.32 ohm** (an upper bound, every LEV_A/LEV_B segment in
     series: 0.4 mm, 1 oz, about 200 mm through the tree, no vias), under 13 % of the
     coil. It stays near room temperature, so it dilutes the copper's tempco: a coil
     reading can be up to 13 % low in its rise. It carries the hover's 0.4 A and a catch's
     2.6 A for under a second without trouble.
  4. **Heated with no bat, the model's constants are off by 3×** (`092935_coil_thermo_heat.json`,
     `093544_coil_thermo_cool.json`, plot `coil_thermo_heat_cool.png`). The console held
     the coil at duty 0.158 (0.66 A if the coil is 2.56 ohm; 0.38 A sensed) for 340 s,
     then probed it every 10 s while it cooled. The resistance rose 9.7 %: +24.9 K, about
     44.5 °C. It then fell back to within about 2 K of the start in 10 minutes. The
     firmware's model, free-running from the drive, said 62 °C; from the sensed current,
     47 °C.
     - Fitting the two-node model to both runs gives 1.5 K rms under either current
       hypothesis. The board node's heat capacity is 5.6-8.9 J/K (assumed 2.5), the
       copper node is small and fast, and the copper-to-board resistance is 5-8 K/W
       (assumed 3). The board-to-room resistance is 25 K/W if the coil is 2.56 ohm,
       40 K/W if the sense is right.
     - Which current is true needs a meter: the Fluke's DC volts across the coil during a
       steady `coil lev` drive, and its ohms with the power off.
     - The thermometer's absolute temperature is anchored to the IMU at calibration
       (19.6 °C), while the IR camera saw the perch at 24.5 °C and the TMAG5273 read
       27.5 °C. Its rise is solid; its absolute value may be about 4 K low. Rev B: a real
       thermometer at the coil (2.2) fixes both.
     - The console's `coil` refuses past about 45 °C on the model: `a_coil` uses the
       pendulum coils' limit for every coil, the levitation coil's included.
  5. **The meters settle it: the coil is 3.24 ohm, and the current sense reads 0.79 of
     the current.** Jason measured J201 pin 10 to 14 (and 8 to 16) with the perch off:
     Fluke 3.38 - 0.14 (leads) = 3.24 ohm; Astron DM6000AR 3.5-3.6 - 0.3 ohm. Contact
     resistance varies with probe pressure. That is 25 % over the 2.56 ohm design. Three
     things now agree on the sense's 0.79:
     - the steady V/I: 4.4 x 0.79 = 3.5 ohm, the coil plus its wiring;
     - the two-duty fit of 3.3: 2.51 / 0.79 = 3.18 ohm, which was in the sense's units;
     - the coil's field at the sensor: 3.64 mT/A calibrated against the sense, 2.89
       modelled.
     With the true power (0.82 W at 0.40 A sensed), the heat and cool runs fit with: board
     node 8.0 J/K (assumed 2.5), copper to board 7.5 K/W (assumed 3), board to room 38
     K/W (assumed 40). That is 1.6 K rms; the copper node is too small and fast for
     these readings to pin down.
     - Still to do in the firmware: `LEV_COIL_R20_OHM` about 3.18, the levitation sense's
       gain, and the thermal constants. The loop's own calibration (kcs) is in the
       sense's units and works, so change these together, then recalibrate (`lev cal`).
     - Why the coil is high: check gen/coils.py's copper against JLCPCB's stackup. The
       coil runs on F, In1 and In2, and a 4-layer board's inner copper may be 0.5 oz.
  6. **A 10-minute hover on one catch, thermal cutoff off** (`112012_lev_try.json`, video
     `references/20261109_112109_bat_hover.mp4`). Gap 7.5 ± 0.23 mm (`g0_mm 9.5`), 0.25 A
     mean sensed (about 0.31 A true), peaks at the 2.6 A limit as the bat sways. No
     losses.
     - The thermometer calibrated about 30 s in, once the gap had walked down and the
       sensed current passed 0.3 A. It then tracked the model within about 3 K. In the
       last 150 s: 36.6 °C measured, 37.5 °C model, board node 36.0 °C.
     - Jason's IR camera: 24.5 °C before; 40 °C on the PCB above the bat (the hottest
       spot) at about 320 s; 41-42 °C from another angle; about 44 °C at the end (11:31-11:33),
       when the thermometer read 38.5 °C (+6.4 K: 45 °C). Felt under the perch: warm, fine.
     - The thermometer's reference was taken against the IMU's 18.1 °C; with the IR's
       room temperature it reads about 6.4 K higher, 41-44 °C, which matches. So the
       absolute anchor is the main error left. Calibrate against a sensor at the coil
       (2.2), or let the bench give the room temperature.
  7. **The bat's eyes light** (2026-11-09, 12:10): `lev eyes 0.3`, the 80 kHz carrier during
     a hold, first seen working; now on by default. Two hovers with the eyes on then
     stopped thermally within minutes, the model's copper at 66-71 °C:
     - The thermometer reads only without the carrier, so it never read.
     - The model took the larger of the drive's current and the mirror's, and the
       mirror reads the carrier's swing as current. The model believed about 2.7 W,
       where about 0.6 W is real.
     - Fixed: under the carrier the model uses the drive's current plus the carrier's
       ripple, and the carrier pauses 0.3 s every 4 s (the bat blinks) so the
       thermometer can read.
  8. **The eyes in a hover, and what they cost** (2026-11-09 afternoon; `140553_lev_try.json`,
     `141657_lev_try.json`).
     - With the walk's floor at 8.0 mm (`zp_range_mm 1.5`), the coil carried the bat the
       whole time: 0.41 A mean against 0.25 A at 7.5 mm, about 3× the heat. It stopped
       thermally in 112 s. Floor 7.5 mm again by default.
     - Blinking by switching the carrier off and on jolted the loop at every blink: the
       gap's sd was 0.34 mm, against 0.23 without the eyes. Now the carrier stays on and
       only its strength fades.
     - The thermometer, reading in the blinks, said 61 °C. Jason's IR camera, just after,
       saw 44 °C at the hottest spot under the perch. The fitted model said 44.5 °C copper
       and 40 °C board. So in the blinks the thermometer reads about 17 K high; the
       model is trusted while the eyes are on.
     - Turning the loop off at 7.5-8 mm does not drop the bat: the magnets pull it up to
       the perch. A release would push it down first.
     - The cure for "too close" is mechanical: a lighter bat, or more bias from the owl,
       so the zero-power gap (about 6-6.6 mm now) reaches the 8.5 mm designed.
     - **Weigh magnets on a non-magnetic stand.** A first weighing of the bat said 5.26 g;
       its magnet was pulling toward the scale. On a tall cardboard box, tared: PCB
       3.00 g, one 10 x 2 mm magnet 1.23 g. The printed cap is still to be weighed;
       Jason may drop it and tape the magnet to the PCB, which also lets him balance the
       bat.
     - **Lowering the owl's magnet moves the bat down by the same amount** (two identical
       magnets: in `levitation_onemagnet.json`, gap + lift is 23.1 mm at every lift). For a
       float near 8.5-9 mm the owl's magnet comes down about 2-2.5 mm (`OWL_LIFT` 14 to
       about 11.5-12, gen/mech.py).
     - Weighed properly: the bat 4.70 g with its cap, which with glue and magnet is 1.72 g
       (cap and glue 0.49 g); 4.23 g without the cap. The model at 4.70 g and a 14 mm lift
       gives a 6.7 mm float, matching the bench's 6-6.6, so it is trusted. `OWL_LIFT` is
       now 12.5 mm: a 4.2-4.3 g bat with no cap floats near 8.9 mm. The owl is reprinted
       from `print/out/owl.stl` (the slotted, no-pause owl: the only one since 2026-11-09).
  9. **With the eyes on, the model reads 20 K low** (2026-11-09, about 15:00). After a hover with
     the eyes at 0.3 and 0.49 A mean (cap turned round), Jason's IR camera read **67 °C on the
     owl's underside**, then 52 °C as it cooled. The model's board node had stopped the loop
     at 50 °C and read 45 °C. Without the eyes, the model matched the camera to within 1 K
     (finding 6). The likely cause is the 80 kHz carrier's loss in the coil: the model counts
     only its ripple (about 0.04 A²) at the DC resistance, but the carrier's fundamental is
     about 0.45 A peak, and a three-layer spiral's resistance at 80 kHz (proximity effect) is
     several times its DC value. That could be a watt or more. 67 °C is above PLA's
     softening (55-60 °C).
     - The eyes are off until the carrier's loss is measured.
     - To measure it: the carrier alone with no bat, the thermometer between bursts, and
       the IR camera. Then put the carrier's real loss into the model, or limit the eyes'
       duty and strength to what the owl can stand.
  `lev tune thermal_cut 0` (a bench switch, gone at reboot) turns off every coil's thermal
  derate and fault. Jason asked for it on 2026-11-09 to hover while he watches the perch
  with an IR camera.
- **The derivative filter:** 25 Hz made it worse (catches lost within a second); 50 Hz,
  the design value, is right.
- **The bat tilts 10-20°, turns, sways and bobs.** Stopped by a finger, the swaying starts again
  (Jason, 2026-11-09): something pumps it, not only light damping. Its centre of mass is off its magnet's axis, and the
  coil controls only the height. Side-to-side swinging and spinning about the vertical
  are only lightly damped. It prefers to face the moon, not the speaker: probably its
  magnet's axis is not quite vertical, and the speaker's magnet pulls on the horizontal
  part. Rev B: centre the bat's mass on its magnet; the pendulum coils could damp the
  swing.
- **The bat's eyes flicker** while the current swings: the 100 kHz levitation PWM excites
  its 82 kHz tank. The eyes' carrier (`lev eyes`) is still untested.

### 1.12 The second owl, the set-points, the eyes and the tokens (2026-11-10)

The numbers are in `MEASUREMENTS.md` ("The second owl"). What they mean:
1. **The 12.45 mm owl works.** The 4.70 g bat (cap on, magnet flipped, flatter) floats at
   7.40-7.44 mm with no steady current and a gap sd of 0.015-0.03 mm, far steadier than
   on the first owl (0.23 mm). Gap + lift is 19.85 mm, 0.9 mm under the model's 20.75. Jason:
   "So much better already!"
2. **Lower costs current: 0.36 A per mm.** The mean-current trip (0.6 A) ends any hover
   past about 9.3 mm. Jason wants the bat as low as is stable at a moderate temperature,
   so the walk now aims at 0.2 A (`LEV_ZP_I_A`, a new tunable `zp_i`), about 0.55 mm under
   the natural float. The third owl (`OWL_LIFT` 11.4) moves the natural float to about
   8.4 mm, and 0.2 A to about 8.9. Rev B: the owl's height is the cheapest knob; choose
   it from gap + lift = 19.85 mm for the bat as built.
   **Flown 2026-11-11:** the third owl (11.4) holds the bat at 8.77 mm on 0.16 A, the coil's
   model levelling at 28 °C after 12 minutes; kept for the demo.
3. **Eyes at 0.1 are enough** (Jason: "dim, but visible"), for a few kelvin by IR. At 0.15
   the gap's spread doubles. One eye is slightly brighter than the other: rev B, match
   the two LEDs or their resistors. The eyes now breathe (a 2 s raised cosine) instead of
   switching, which the loop never sees as a step.
4. **`lev cal coil` is wrong on this owl** ("IPROPI disagrees", `kcs` 2.2 against the 3.64
   that flies). `lev tune kcs` now writes the calibration, so `save` keeps a hand value.
   **Fixed 2026-11-11:** at 0 A asked, the PWM's minimum pulses make a zero-mean ripple
   that the |I| mirror reads as about 0.07 A of offset. The cal now coasts the bridge in
   its off windows and measures 3.566 mT/A. Rev B: a signed current sense (or one that
   reads during a known pulse phase) would avoid the trap.
5. **Live mode cannot see a token** (1.3): the perch current moved 0.2 mA at most at
   63 mA. Sweep mode sees each token at its bump (owl 147.6 kHz, cat 353.8 kHz) but is
   slow to see it go: more than 30 s for the owl, about 10 s for the cat. Planned for rev A:
   live drive, with a short probe at the token's bump every 0.5 s; then the ring round a
   target can fade out when its token is on (Jason's wish). Rev B: a sense that sees the
   load (a series capacitor or a phase measure, 1.3, 1.8).
   **Solved on rev A, 2026-11-11** (MEASUREMENTS "The coil's calibration, the defaults
   flown, the token probe"). At the token's own tuning the reflected load is resistive and
   the supply current doesn't move; at 1.5 × the token's tuning (the coupled mode) it rises
   5-10 times. The live drive breathes over 3 s and probes there, at two duties, in each
   trough; every arrival and departure was seen on the bench, and the rings now fade under
   a token. Limits for rev B: a token 3 mm or more off the copper lights but reads absent;
   a series capacitor (1.8) or a phase sense would give reach and a quieter probe.
6. **The rings round the targets** now breathe round once a second: two neighbouring LEDs
   trade their brightness, then the brighter trades with the next (Jason, 2026-11-10).
   Before, all three glowed at once, and Jason saw them "always on".

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
- **Thermometers on or beside every coil the firmware can cut off for heat** (Jason,
  2026-11-09; PLAN.md §7). Rev A has none: each coil's temperature is a two-node model
  with assumed constants, corrected only by the coil's own resistance (1.11). The ambient
  is the IMU's die, nowhere near the coils. The model cut off the levitation coil again and
  again while the perch felt only warm. Rev B, plenty of them:
  - **The levitation coil:** one on the perch, in contact with the winding or touching
    it, and one on the perch board under the owl's PLA (the model's "board" node, the
    50 °C limit). I2C does not reach the perch: the tree-perch joint carries no SDA/SCL
    (pins 3 and 5 are GND, `gen/connectors.py`). Either route I2C through (two of its
    many GND pins), or put an NTC on a spare pin into an ADC input. The perch's DRV5055
    has no temperature output. A TMAG5273 there would give one, but the 10 kHz loop needs
    the analog Hall, so add a sensor rather than swap it.
  - **Each pendulum coil (three):** an NTC or an I2C sensor beside each winding, not one
    TMAG5273 die between them for all three.
  - **The board under each coil driver** (the DRV8874s), and the familiar perches' coils.
    Those are capped at 0.25 A by the rail and resistors, but have no time limit (below).
  - **Check that the coils' fields don't blind them** (Jason, 2026-11-09). A sensor next
    to a coil sits in its 100 kHz PWM ripple and its kHz-rate current swings: an NTC's
    traces pick up the coil's dV/dt and dI/dt, an I2C sensor's lines can glitch, and an
    IC's own sense path can rectify the AC into an offset. Before rev B is fixed: on a
    rev A coil, put a candidate sensor (and its traces, as routed) where it would go, run
    the coil at its worst (a catch at 2.6 A, the pendulum's kicks, the 82 kHz eyes'
    carrier), and compare its reading against the same sensor with the coil off at the
    same temperature, and against the coil's resistance. Keep ADC lines away from the
    winding's ends, filter each NTC at the ADC, sample it between PWM edges like the Hall,
    and route I2C as a pair over ground with the sensor's bypass at its pins.
  - **Firmware:** limit on the measured temperatures, and keep the model and the
    resistance thermometer as a cross-check. A sensor that disagrees with the model by
    more than a few kelvin is a fault, not a reading to trust.
  - **Bench:** with these in, the model's constants (0.3 J/K, 2.5 J/K, 3 and 40 K/W) can
    be fitted rather than assumed; until then, an IR thermometer (1.11).
- **LP5036:** EN tied high, VCC on USB alone? (firmware README question 2.)
- **Put the bat's magnet at its centre of mass, and centre the notches on it** (Jason,
  2026-11-09). Rev A puts the magnet's axis (the receive coil's centre, `gen/mech.py` origin)
  1.66 mm behind the bare outline's centroid (toward the tail; the eyes are forward). The
  eye LEDs at the head put the real centre of mass further forward still. The bat tipped
  10-20° and hovered flatter with its cap turned round, which moved the magnet toward
  the eyes. The head and tail notch bottoms (`BAT_HEAD_Y` -12.5, `BAT_TAIL_Y` 11.5) are
  centred 0.5 mm forward of the magnet too, so the cap's arms differ by 1 mm.
  - Rev B: compute the centre of mass from the outline, the copper and the parts.
  - Put the magnet axis and the receive coil there.
  - Make the notches symmetric about it, so the cap is symmetric but for its ears.
  - Rev A, without the cap: tape the magnet at the bare PCB's balance point.
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

### 3.3 Are the coils really 3.0 Ω? Probably not (2026-11-08)
The bridge loses about 0.50 µs of every PWM pulse: its switching and dead time. Two
pulses on the levitation coil, at duty 0.08 and 0.15 of 100 kHz, solve for the coil and
that loss separately. They give 2.51 Ω, against 2.56 designed
(`results/2026-11-08/215828_coils.json`, `215851_coils.json`). The single-duty step
reported 7.05 Ω and 3.87 Ω. The pendulum coils' 3.0 Ω on 2026-11-06 came from the same
single-duty step at 30 kHz, where a 0.5-0.6 µs loss accounts for the difference from
2.29 Ω. To confirm: the same two-duty pulse on a pendulum coil, or the Fluke across its
pads with the power off. The levitation coil's PWM pulses are 0.8 µs at duty 0.08, so the
loss matters to the loop's gain at small drive.

**Compensated since 2026-11-08** (`DRV_PULSE_LOSS_S`, 500 ns, in `config.h`): `coils.c` adds
it to every output pulse asked for, at each coil's own PWM frequency. Without it the
levitation coil's 0.3 µs alternation pulses vanished and the forward pulse lost 0.5 µs:
a dead zone of ±0.02 in u (about ±85 mA) round zero at 100 kHz, and 0.02 short beyond it. That plausibly
drove the limit cycle of the first hovers (`results/2026-11-08/223951_lev_first.json`:
five catches, each lost within half a second with "the current stayed at its limit",
600-900 mA rms round a small mean). `test_rt`'s simulated bridge now loses the same
0.5 µs a pulse. The bring-up image's `coil` command uses the same code, so its
single-duty resistance now reads the coil itself.

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
