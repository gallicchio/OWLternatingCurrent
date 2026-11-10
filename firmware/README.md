# OWLternating Current firmware

Version 0.1.0, for rev A. It is C11 on the Pico SDK 2.1.1 and TinyUSB, for the RP2354A
(the RP2350A with 2 MB of flash in the package).

**Status: it builds without warnings and passes eleven host-test suites. It has not yet run
on a board.** The boards are not made yet. The core paths are real; the advanced control
loops (levitation, pendulum, familiars, film, theremin) are implemented and tested against
simulated plants, and await bench tuning. Every number that depends on the schematic and
is not yet decided is marked `[ASSUMED]` in the source and listed under [Open
questions](#open-questions-for-the-board-designer).

## Build, test, flash

```sh
./fetch_sdk.sh                       # once: Pico SDK 2.1.1 (and TinyUSB) into external/
cmake -S . -B build && cmake --build build -j8
make -C test                         # the host tests, no hardware needed (about 30 s)
picotool load -x build/owlternating.uf2 -f   # or copy the .uf2 onto the RP2350 drive
```

- **Needs:** CMake and `arm-none-eabi-gcc` (tested with 10.3).
- **GCC 15 on the host** (Ubuntu 25.10 and later): the Pico SDK 2.1.1's `pioasm`, built for
  the host during the build, is missing `#include <cstdint>` and fails to compile. Configure
  and build with `CXXFLAGS="-include cstdint" cmake -S . -B build && CXXFLAGS="-include cstdint"
  cmake --build build -j8`; the flag reaches only the host tools, not the RP2354A's code.
- **Two images:** `owlternating.uf2` (the firmware) and `owl_bringup.uf2` ([the bring-up
  image](#the-bring-up-image), for a board's first power-up).
- **A blank board** starts in the ROM bootloader; `picotool load` or the `RP2350` drive.
- **After that,** `picotool reboot -u -f` reaches BOOTSEL through the reset interface. So do
  the console's `reboot bootsel` and opening the serial port at 1200 baud.
- **Three watchdog timeouts in a row** restart in BOOTSEL, so a bad image can always be
  replaced over USB (GPiBridge's rule). Seen working on rev A, 2026-11-07.
- **The diagnostic build**, `cmake -S . -B build-diag -DOWL_DIAG=1`: the same firmware with
  the watchdog fed whatever core 1 does, a `diag` event every second (core 1's ticks,
  overruns, faults, stage, rails) and a hard-fault handler that records the fault (PC, LR,
  CFSR, HFSR, BFAR) instead of the SDK's silent breakpoint. For a board that resets before
  USB enumerates; it found the ADC/DMA interrupt race of 2026-11-07 (rt.c, `tick_isr`).

## The bring-up image

`owl_bringup.uf2` is for the first power-up of an untested board, before the real firmware:
whatever goes wrong then points at the hardware, not at the firmware. It is core 0 only:
`board_safe_init()` first, then the console on USB (CDC "OWL bring-up", the same 1209:0001
and reset interface, so `picotool reboot -u -f`, `bootsel` and 1200 baud reach BOOTSEL) and
on the UART (J5, 115200). **No watchdog, no core 1, no DMA, nothing automatic.** A coil, a
perch or a sound runs only inside a command, for a bounded time, and every command ends
with every bridge low, the DRV8874s asleep and FAM_EN low.

Flash it like the firmware: hold BOOT while plugging in USB (a blank board starts there
anyway) and copy `build/owl_bringup.uf2` onto the `RP2350` drive, or `picotool load -x
build/owl_bringup.uf2 -f`. Go back to the firmware the same way with `owlternating.uf2`.

On boot it sends four lines (the UART has them all; USB gets the first again when a terminal
opens the port): `boot` (image, version, chip ID), `i2c` (SDA/SCL found stuck low, freed),
`rails`, and `i2c_scan`. Then one command a line in, one JSON object a line out, with
`"ok":true`, or `"ok":false` and an `"error"`. The code is `src/bringup_cmd.c` (portable:
parser, limits, sequences) behind `src/bringup_main.c` (the board).

| command | what it does | reply (beyond `ok`, `cmd`) |
|---|---|---|
| `help` | the list | `commands` |
| `id` | who is running | `image` ("bringup"), `version`, `board`, `uptime_ms`, `chip_id` |
| `rails` | V12, V5, VBUS through the 74HC4051 (16 conversions each, 50 µs settle) | `v12`, `v5`, `vbus` (V), `usb_only`, `raw` (counts) |
| `adc` | every ADC input and mux channel | `hall_V`, `hall_mT`, `lev_ipropi_A`, and `mux.<name>`: `ch`, `raw`, `V`, `value`, `unit` |
| `gpio` | the inputs worth seeing | `nfault`, `button`, `imu_int`, `nsleep`, `fam_en` |
| `i2c scan` | probes 0x08-0x77 | `found`, `names`, `missing` (of 0x30 0x32 0x6A 0x29 0x35) |
| `i2c rd <addr> <reg> <n>` | reads 1-32 bytes (`0x..` for hex) | `bytes` |
| `i2c wr <addr> <reg> <b0> [..b15]` | writes | `n` |
| `sensors` | configures and reads the IMU, light sensor, 3-axis Hall; the perch's Hall | `imu` (`whoami`, `accel_g` in the chip's axes, `accel_board_g` with `sensors.h`'s assumed signs, `temp_C`), `als` (`lux`, `ch0`, `ch1`), `tmag` (`mT`, `temp_C`), `hall_lev_mT`; each `present`, or an `error` |
| `led <name\|all> <0..1>` | one LED's (or every LED's) LP5036 colour register, linear, no fades; the driver configured on first use (reset, enabled, independent, banks at full) | `driver`, `out`, `name`, `duty` (`all`: `lit`, `drivers`) |
| `led <drv 0\|1> <out 0..35> <0..1>` | one output by number | as above (`name` "unconnected" if no LED) |
| `led off`, `led cap <0\|1>` | every output to 0; allow duty above 0.5 (`cap 1`) or not | |
| `ledwalk [ms]` | each LED alone at 0.2 for ms (400), in `led_map.h` order; any input stops it | events `ledwalk` (`i`, `name`, `driver`, `out`), then `count`, `skipped`, `aborted` |
| `coil <pend1\|pend2\|pend3\|lev> <duty> <ms>` | wakes the bridges, drives one coil at a fraction of 12 V (-0.5..0.5) for 1-500 ms, reads its current mirror throughout, then everything off. Refused below 10.8 V or if \|duty\| x V12 / R20 > 1 A; stopped at once by nFAULT or a mirror reading 1.5x what was expected (a short) | `v12`, `i_expected_A`, `i_mean_A`, `i_peak_A`, `i_before_A`, `i_off_A` (the mirror's offset), `i_net_A`, `r_loop_ohm`, `r_est_ohm` (less the bridge's 0.2 Ω), `nfault`, `ran_ms`, `pwm` |
| `perch <1\|2> <freq_hz> <duty> <ms>` | one perch bridge at 50-500 kHz (clamped to 90-500 kHz by `coils.c` in this build; 90-440 in the real one), duty 0-0.5 (0.5 is a square wave: enough to light a token), 1-10000 ms; ISENSE before (bridge off) and over the second half; the pulse stops at once if ISENSE passes 0.2 A | `freq_hz` (as set), `held_ms`, `tripped`, `isense_base_A`, `isense_on_A`, `isense_net_A`, `v5`. Refused below 4.5 V |
| `sweep <1\|2> [f0 f1 steps duty]` | 100-400 kHz, 48 steps, duty 0.03, 20 ms a step (any range in 50-500 kHz, up to 200 steps); any input stops it | events `sweep_pt` (`f`, `i_A`), then `points`, `base_A`, `peak_f`, `peak_i_A`, `aborted` |
| `tone <hz> <ms> [amp]` | a sine on the audio PWM (no DMA), 100-4000 Hz, 1-20000 ms, amplitude 0-1 of full scale (0.1; 1.0 is 0.2 W in the speaker, the real firmware stops at 0.25), with slow ramps at each end; the SOUND switch mutes it | `hz`, `ms`, `amp` |
| `audio <level>`, `audio off` | holds the audio PWM at a steady duty 0-1 (3.3 V x level after the RC filter, for a meter at C30; DC, so the amplifier stays silent) until `audio off` or a `tone` | `level`, `filter_V` |
| `osc [ms]` | counts both theremin oscillators' edges (PIO) over ms (100) | `pitch_hz`, `volume_hz` (0 and a `note` if no edges) |
| `reboot`, `bootsel` (or `reboot bootsel`) | LEDs and bridges off first | |

The coil drive is the main firmware's (`coils.c`): phase-correct PWM, forward for |duty| of
each period and brake for the rest (so the DRV8874's current mirror reads throughout), 30 kHz
for the pendulum coils and 100 kHz for the levitation coil.

**Without a board:** `make -C test bringup_sim` builds `test/bringup_sim`, the same console
on a simulated board (`test/bringup_board_sim.c`): command lines on stdin, JSON lines on
stdout, flushed, the boot lines first. Environment variables make faults: `OWL_SIM_NO12V=1`,
`OWL_SIM_USB_OFF=1`, `OWL_SIM_MISSING=0x32,0x29`, `OWL_SIM_TOKEN=owl|cat` (a resonance in the
perch current), `OWL_SIM_NFAULT=1`, `OWL_SIM_SHORT=pend2`, `OWL_SIM_OSC_DEAD=1`,
`OWL_SIM_SDA_STUCK=1`, `OWL_SIM_BUTTON=1`, `OWL_SIM_REALTIME=1` (waits take real time, so a
walk or a sweep can be interrupted). `test_bringup` runs every command and limit against it.

## Generated files: edit the source, not these

| file | written by | from |
|---|---|---|
| `src/board_pins.h` | `../gen/firmware_pins.py` | `../gen/pins.py`: every GPIO, each bridge's PWM slice (checked: IN1 = channel A), the ADC channels, the multiplexer's channels and the sense dividers' ratios, the I2C addresses, the board's pull resistors |
| `src/led_map.h` | `../gen/firmware_leds.py` | `../gen/leds.py`: all 49 LEDs (driver, channel, name, colour, board, position), each group in order, each driver's channel → LED table. Positions come from `../hardware/checks/led_positions.json` once the placement writes it; until then they are 0 and `LED_UNPLACED` says so |
| `src/lev_table.h`, `test/lev_plant.h` | `tools/gen_lev_tables.py` | `../sim/physics/` (the one-magnet levitation geometry, `../gen/mech.py`'s `OWL_LIFT`) with the levitation coil as built (`../gen/parts.py` `COILS["COIL_LEV"]`: 11 turns a layer, r 4-15 mm): the bias magnet's force, the coil's force per amp, the bat's field at the Hall sensor, all against the gap. Half a minute; it cross-checks the magnets against the simulation's result |

Run `python3 ../gen/firmware_pins.py && python3 ../gen/firmware_leds.py` after any change
to `gen/pins.py` or `gen/leds.py`. The C uses only the generated names. When the
multiplexer's order, the tree driver's address (now 0x32) and the downlights' channels
changed on 2026-10-07, nothing else needed editing.

## Architecture

```
core 0 (main.c)                                    core 1 (rt.c)
  USB: CDC console + picotool reset interface         10 kHz tick, phase-locked to the levitation PWM
  JSON console (console.c), UART mirror               ADC burst by DMA: Hall, LEV IPROPI, mux x 8 each
  I2C slots, 2.5 ms each:                             mux -> next channel (every channel at 1.25 kHz)
    TMAG5273 @400 Hz -> pendulum.c                    rails, nFAULT, brown-out, mirrors -> faults
    LP5036 base / tree frames @200/s                  levitation loop (lev_ctrl.c)
    IMU @100 Hz, light sensor @5 Hz                   coil requests (with deadlines) -> PWM
  scenes.c -> led_engine.c @200 frames/s              thermal models @1 kHz (thermal.c)
  familiar.c @1 kHz -> perch PWM                    shared: rt_shared rt (rt.h)
  film.c, theremin @100 Hz; voice -> audio DMA
  watchdog: fed only while core 1's tick advances
```

**Start-up order.** `board_safe_init()` runs first, before anything else. It makes every
bridge input a plain output driven low, puts the DRV8874s to sleep (`nSLEEP` low) and
disables the perch drivers (`FAM_EN` low). The board's pull-downs on `nSLEEP` and `FAM_EN`
already hold these states during reset.

The rest follow in order:
1. The UART log and USB.
2. The I2C bus: freed with nine clocks if stuck, then scanned, with the result reported.
3. The two LP5036s. The tree's driver may be absent; it is looked for again every 5 s and
   fades in when found.
4. The IMU, the light sensor and the TMAG5273.
5. Core 1.
6. The audio (silent), the theremin's counters, and the watchdog (250 ms).

### The files

| file | what | host test |
|---|---|---|
| `main.c` | core 0: start-up, the slot scheduler, events, the console's actions, USB callbacks | |
| `rt.c`, `rt.h` | core 1: the tick, the ADC sequencing, the safety checks, coil requests, the levitation loop's glue, the thermal models' updates | `test_rt` (SDK modelled in `test/stubs/`) |
| `coils.c` | the PWM behind the four DRV8874 bridges and the two perch bridges | `test_rt` |
| `board.c` | the safe pin state, nSLEEP, nFAULT, FAM_EN, the button, the multiplexer | `test_rt` |
| `led_engine.c` | targets → slew limit → CIE L* → 12-bit duty → LP5036 bank split and dither | `test_leds` |
| `scenes.c`, `noise.c` | the light show and its noise | `test_leds` |
| `quantum.c` | the quantum ghost (Crank-Nicolson) | `test_quantum` |
| `lev_ctrl.c` | the levitating bat's controller | `test_lev` |
| `pendulum.c` | the pendulum's estimator and drive | `test_pendulum` |
| `familiar.c` | the familiar perches: sweep, identify, drive, track | `test_familiar` |
| `thermal.c` | each coil's two-node thermal model; the coil as its own thermometer | `test_thermal` |
| `film.c` | film mode | `test_film` |
| `theremin.c`, `voice.c` | the theremin's mapping; the "woo" voice | `test_theremin` |
| `console.c` | the JSON console's parser and limits | `test_console` |
| `lp5036.c`, `sensors.c`, `i2c_bus.c` | the I2C devices (LP5036, LSM6DS3TR-C, LTR-303ALS, TMAG5273) | |
| `audio.c`, `theremin_hw.c`, `edge_count.pio` | PWM + DMA audio; PIO edge counting | |
| `settings.c` | flash settings (the last sector) | |
| `usb_descriptors.c` | one CDC port and the reset interface (as GPiBridge's) | |
| `config.h` | every board number not in `gen/`, marked `[DS]`, `[SIM]`, `[ASSUMED]` or `[CHOICE]` | |

Every module that holds logic is portable C with no SDK and no dynamic allocation. The
realtime loops run on core 1; the scenes and the console run on core 0.

### Core 1's tick (100 µs)

1. **The tick slice's wrap.** PWM slice 0 (`PWM_SLICE_TICK`) drives no pin. It runs in phase-locked step with
   the levitation coil's slice: both are started together through the PWM block's EN
   register, and the tick's period is exactly 10 of the coil's 100 kHz periods (8 of its
   80 kHz ones with the carrier on). The wrap's interrupt starts the ADC burst, so every
   burst begins at the same point of the coil's PWM period: the centre of the forward
   pulse.
2. **The burst.** The ADC free-runs in round robin over ADC0 (Hall), ADC1 (the levitation
   IPROPI) and ADC2 (the multiplexer), eight times each: 24 conversions in 48 µs, taken by
   DMA into one of two buffers.
3. **The same interrupt, while the burst converts, does the tick's work on the previous
   burst** (the other buffer; since 2026-11-08, so the work has the whole 100 µs, not the
   52 µs the burst leaves):
   - averages the burst;
   - updates the rails and checks the faults;
   - runs the levitation loop;
   - applies the pendulum, film and console requests;
   - computes the coil PWM;
   - every millisecond, updates the thermal models.
4. **The DMA's completion interrupt** (a higher priority, and short) stops the ADC, moves
   the multiplexer to its next channel (it then settles for the rest of the period: the
   designer asks for 10 µs), and applies the PWM the work computed, once the burst is
   over. So every burst runs under one u, the one from the tick before the work that
   reads it: the levitation's current model allows for that step (`lev_ctrl.u_lag`;
   without it, `test_lev` chatters at 1.4 A rms). From a burst's middle to its PWM the
   delay grows from 40-75 µs to about 125 µs: 1.2° more phase lag at 40 Hz, 0.3° at the
   loop's 10 Hz.
5. **Skipped ticks** (`overruns`: the work ran so late that PWM wraps went by) are
   counted, and `skipped_last_s` gives the last second's. The `adc` fault is a rate: more
   than 1 % of a second's ticks skipped, or of its conversions failing. A gap over 5 ms is
   core 1 parked by a flash write (`pauses`), not an overrun.
6. **The whole image runs from RAM** (`copy_to_ram`, 182 kB of the 512 kB), so no tick
   waits on the 16 kB flash cache that core 0 shares. From flash, the worst tick was
   322 µs (2026-11-08).

### Coil drive (DRV8874, PMODE high = PWM mode)

IN1 is the slice's channel A, as is; IN2 is channel B, inverted; both are phase-correct.
With compare values ccA ≥ ccB, every period runs forward → brake → reverse → brake. The
coil sees a mean of (f_fwd − f_rev) × 12 V. This scheme has three properties:
- **Small ripple near zero current:** the current decays slowly through the brake state.
- **IPROPI keeps working:** the current mirror reads in drive and brake, but not in coast.
- **Linear down to zero:** a little of both directions keeps every output pulse at least
  300 ns long, so the mean stays linear.
- **The bridge's loss is put back:** on rev A the DRV8874 took about 0.5 µs off every
  output pulse (`bringup/REVB.md` 3.3), so `coil_set_fractions()` lengthens every pulse
  asked for by `DRV_PULSE_LOSS_S` (500 ns) at that coil's PWM frequency. That is 0.05 of
  the period at 100 kHz and 0.015 at 30 kHz. A fraction of zero stays zero.

The levitation coil's 80 kHz carrier for the bat's eyes is the same scheme with a lot of
both directions (`lev eyes`). It only runs while the bat floats, and it always gives way
to the loop when the loop needs the voltage.

### Safety: the rules the code keeps

- **Nothing drives a coil until it is safe.**
  - Pins are plain and low at start.
  - Bridges sleep unless needed, and wake (1.2 ms) only when allowed.
  - A second with nothing to do puts them back to sleep.
- **No coil runs without 12 V.**
  - Coils start only after V12 > 10.8 V for half a second.
  - V12 < 10 V turns every coil off at once (0.4 ms in `test_rt`).
  - On USB power alone, coil requests are refused, and the LEDs are capped at 15 % of
    their luminance.
- **nFAULT** (wired-OR, all four DRV8874s), if held for 1 ms:
  - every coil goes off and the bridges sleep;
  - a retry follows 100 ms later;
  - three faults in a minute latch the coils off until `clear`.
- **Every coil request carries a deadline**, enforced on core 1, so a core 0 that stops
  talking leaves no coil on. Pendulum pulses are renewed every 2.5 ms and lapse after
  10 ms; film steps after 50 ms.
- **Current limits per owner:**

  | owner | limit |
  |---|---|
  | pendulum | 0.5 A |
  | film | 1 A |
  | console | 1 A for at most 2 s |
  | levitation | 3 A (below the DRV8874's 3.3 A chopping) |

- **Thermal limits.**
  - Every limit is multiplied by the coil's thermal derating: 1 below 40 °C, falling to
    0 at 45 °C (the child-safety surface limit). The levitation coil, in the perch under
    the printed owl, has two limits instead (since 2026-11-08): its copper 80 °C and its
    board node, under the owl's PLA, 50 °C (`config.h`, `LEV_COIL_*`).
  - The models are two-node (copper/surface and board), with the board's temperature
    (IMU, else TMAG5273) as ambient.
  - The resistance thermometer: V/I from the current mirror corrects the model
    (copper +0.39 %/°C). In `test_thermal` it holds a coil that cools worse than modelled
    to 43 °C, where the model alone let it reach 50 °C.
    - The pendulum coils read it from steady pulses; the levitation coil (since
      2026-11-08) from 50 ms means, mean(u V12) / mean(I), while it holds the bat
      (`rt.c` step 6b; `status` → `lev_thermo`), from one second into a steady hold (not
      during a catch). In `test_rt` a levitation coil that cools three times better than
      modelled ends within 2 K of the truth, where the model alone read 17 K high and
      derated it.
    - The thermometer's reference calibrates on its first five readings once the coil has
      been cold a minute (within a 30 K band, `THERMAL_CAL_BAND_K`, each reading corrected
      by the model's rise). It is kept in the reading's own units (`rm_ref_ohm`): only
      the ratio hot/cold is a temperature, and the coil's R(T) for power and drive stays
      nominal. On the bench the levitation coil's V/I reads 4.4 Ω for its 2.5 Ω
      (bringup/REVB.md 1.11).
    - Uncalibrated, a pendulum coil's reading may only push its model up; the levitation
      coil's is only reported (a catch's window once read "213 °C").
    - `lev tune thermal_cut 0` turns every coil's thermal derate and fault off until
      reboot. It is a bench switch, for hovering under an IR camera.
- **Mirror checks.**
  - A mirror reading 1.5× more than asked (a short) stops that coil.
  - No current when 0.25 A was asked (an open coil) stops it too.
  - The levitation loop checks its own coil the same way.
- **The levitation loop releases the bat** (current to zero):
  - within 2 ms of the gap leaving ±5 mm;
  - if the Hall sensor sees no bat;
  - if the current is pinned at its limit, or its 1 s mean is too high (a hand holding the
    bat).
- **Watchdogs.**
  - The watchdog (250 ms) is fed only while core 1's tick advances, so either core
    stalling resets the chip, and a reset leaves every bridge asleep.
  - After a watchdog reset the thermal models do not assume the coils are cold.
- **Flash writes** (`save`) are refused unless every coil is off, because a write pauses
  core 1 for ~45 ms.

## The light show

**The engine (`led_engine.c`)**, 200 frames a second, for each of the 49 LEDs:
1. The target lightness L (CIE L*/100, so equal steps look equal).
2. Ceilings on luminance:
   - the colour's own: the 0603 orange LEDs' 20 mA of the LP5036's 25.5 mA, and violet at
     60 % for eye safety;
   - the power state's: 15 % on USB alone;
   - a master dimmer.
3. **The slew limit.** No LED's L moves more than 1/60 in a frame: nothing changes faster
   than a fade from 0 to full in 300 ms (Jason's rule: no blinking, only smooth
   transitions). Every input passes through it, including the ceilings and the console's
   `led` command.
4. L → luminance → the LP5036's 12-bit duty.
5. The bank split. Three outputs share a bank brightness register B, and each has its own
   colour register C; the duty is C × B / 16 (`[ASSUMED]` truncation: see the questions).
   B is the smallest that reaches the bank's brightest output (but at least 16), so dim
   LEDs keep the finest steps.
6. **Temporal dithering** in the chip's own duty units. A fraction within 0.15 of a step
   is rounded instead, so no dither pattern is slower than ~30 Hz; a slow one would be a
   visible twinkle.

Each frame is one I2C burst per driver: registers 0x08-0x37, only the span that changed.
The LP5036s run in independent mode, with linear dimming and their own 3-bit PWM dither.

**The scenes (`scenes.c`, PLAN.md §3):**

| scene | what it does |
|---|---|
| asleep | pumpkins breathe very slowly and dimly |
| dusk | stars fade in one at a time over 30 s; pumpkins warm up; owls open their eyes; wisps come out |
| night | pumpkins flicker like candles (smooth 1/f noise); stars scintillate; owls look left and right; wisps drift and roll downhill along the IMU's gravity |
| firefly | Kuramoto-coupled pumpkins and wisps pull into step over a minute, hold, then drift apart |
| quantum | the ghost on the 12-star arc |
| familiar | the rings swirl, as when a familiar arrives (a demo) |
| dawn | the reverse of dusk |
| theremin | the moon-side stars climb with the pitch; the pumpkins follow the volume; the owls look toward the moon |

Overlays apply on every scene:
- a familiar's ring swirls for 8 s when it arrives, then glows;
- the pendulum's chosen pumpkin lights;
- the perch's downlights come on while the bat floats.

**The automatic sequence.** The light sensor drives asleep ↔ dusk → night → dawn → asleep,
with hysteresis: below 3 lux or above 30 lux, for 20 s. Its first reading counts at once.
Every 3-5 minutes the night becomes a firefly synchrony. A tap or the SPELL button moves
to the next scene; a double tap calls the quantum ghost. `scene <name>` holds a scene until
`scene auto`. Changes of scene cross-fade over 1.5 s.

**The quantum ghost (`quantum.c`)** solves the Schrödinger equation on 120 points, 10 per
star, with hard walls at both ends and a wall between stars 7 and 8. It uses
Crank-Nicolson, which is unitary and unconditionally stable, factorised once (Thomas) and
O(N) per step. One step a frame; |ψ|² in each star's cell is its brightness. The packet's
mean energy (0.46) is below the wall's top (0.50), and about a third of it tunnels.

## The coils' features

- **Levitation (`lev_ctrl.c`, core 1, 10 kHz).**
  - A port of `sim/physics/levitation_loop.py` to the one-magnet design.
  - PID on the gap, with gains scheduled from the tables: a 10 Hz loop, the derivative
    low-passed at 50 Hz.
  - The Hall reading (8× oversampled, taken in step with the PWM) minus the coil's own
    field, from the current mirror above 0.4 A and the command below.
  - The slow zero-power loop walks the set-point to where the mean current is zero.
  - **States:** off, CAL, wait, hold, lost, inhibit and fault.
    - CAL: ±0.3 A pulses measure the coil's field at the sensor and its polarity, on the
      first `lev on`; `lev cal zero` measures the Hall zero.
    - Wait: the catch engages when the bat is within ±5 mm of the float gap and steady.
      The set-point starts where the bat is and walks to the float gap.
    - Hold: the bat floats. It is released within 2 ms if the gap leaves ±5 mm, if the
      Hall sees no bat, if the current is pinned, or if the 1 s mean current is too high.
    - Fault: an open coil, thermal, or repeated trips.
  - The 80 kHz carrier for the bat's eyes runs only while it floats: `lev eyes 0.3` makes
    about 0.45 A of carrier.
- **The pendulum (`pendulum.c`, core 0, 400 Hz).**
  - The TMAG5273's three axes are inverted through the bat's dipole field: position,
    then a Kalman filter per axis that learns the swing's frequency.
  - **SUSTAIN** pumps one axis and damps the other.
  - **CIRCLE** makes a force rotating through the three coils, 120° apart, along the
    bat's motion.
  - **CHAOS** pumps a swing, then lets the three coils attract it: "which pumpkin will it
    choose".
  - Pulses of up to 0.3 A, renewed every 2.5 ms; the coils sit 18 mm from the rest point.
    There a coil at 0.5 A holds the bat 11 mm out, a real capture; at 25 mm it would not.
- **The familiars (`familiar.c`, core 0, 1 kHz).** Two modes, `fam live` (the default
  since 2026-11-07) and `fam sweep`.
  - **Live:** each perch drives its own token's tuning (perch 1 the owl's 142 kHz, perch 2
    the cat's 303 kHz) at the empty-perch current cap, all the time. The token's glow
    follows the coupling, so it brightens as a hand brings it in; "present" is the power
    the perch delivers beyond an empty perch's (`FAM_LIVE_ON_W` 50 mW on, 25 mW off, 20 /
    100 ms debounce), and it raises the same arrived / left events as the fit does. Safe
    at any coupling: at its tuning a token only raises the perch's impedance. A coin reads
    as present; the other token stays dark and silent.
  - **Sweep (the original design):** every 0.2 s an idle perch sweeps 100-400 kHz in 32 steps.
  - Each step is read at two duties so small that a token stays dark (0.010 and 0.030).
    Their difference cancels the drivers' own draw, giving the perch's conductance:
    FAMn_ISENSE is the bridge's 4.8 V supply current, at 10.3 V/A.
  - A token shows a resonance peak (the coupled mode, 15 % above its tuning at the printed
    floor's gap, 50 % lying on the copper). A fit of the coupled-tank model, third harmonic
    included, names the token: owl (116-168 kHz) or cat (248-358 kHz), each 18 % round its
    own (FAM_ID_TOL), the perch's own preferred. Only those two: one bump fixes only
    f_t / sqrt(1 − k²), so a free fit read a bare owl as the image of a 441 kHz stranger
    (rev A, 2026-11-07); a stranger now fits as the nearer token or, with no resonance, not
    at all. The tuning reported is good to about 12 %.
  - The perch is driven at f_t, never at the peak: there a token only raises the perch's
    impedance, so the empty-perch duty cap (0.92 × 0.2 A into an empty perch) bounds the
    current with or without a token.
  - The delivered power ramps to 0.25 W.
  - A ±1 % dither at 100 Hz, compensated so the light stays steady, notices the token
    leaving within 0.5 s.
- **Film mode (`film.c`).** For magnetic viewing film laid over the pendulum coils: steps of
  DC current, alone and in pairs, sometimes opposed (1 → 1+2 → 2 → 2+3 → 3 ...).
  - Each step is at most 1 A, on for at most 1.9 s with 0.4 s ramps, then 2.5 s of rest.
  - Each step is planned against the thermal model, which shortens or skips it rather than
    pass 44 °C.
- **The theremin (`theremin.c`, `voice.c`, `theremin_hw.c`).**
  - PIO counts each oscillator's edges; core 0 reads the counts every 10 ms.
  - Calibrated at start with hands away, it then follows slow drift while nobody plays.
  - The hand's nearness is the fractional frequency drop over its span (3 % assumed).
    Pitch maps exponentially to 200-1000 Hz; volume is gated above the noise.
  - The voice is a sine with a little 2nd and 3rd harmonic, a slow vibrato that deepens
    after the onset, a glide, and a soft attack and release. It runs at 36.6 kHz into a
    146 kHz PWM by DMA, at 0.12 of full scale by default, never above 0.25.

## The console

USB serial "OWLternating console" (any baud; 1200 baud means BOOTSEL), and the UART at
115200 (J5, GPIO16/17), which mirrors every line. One command a line in, one JSON object a
line out. Replies carry `"ok":true` or `"ok":false,"error":"..."`. Events arrive unasked on
the same lines.

| command | what |
|---|---|
| `status` | version, uptime, rails (V12, V5, VBUS, whether coils are powered, USB-only), I2C devices, faults, coil and board temperatures, coil currents / duties / resistances, the Hall readings (levitation mT, TMAG5273 x/y/z), levitation, pendulum, familiars, scene, theremin, film, light, IMU, core 1's timing, LED frames |
| `scene <asleep\|dusk\|night\|firefly\|quantum\|familiar\|dawn\|theremin\|auto>` | hold a scene, or back to automatic |
| `led <name\|all> <0..1\|off>` | set lightness (still slew-limited), or hand back to the scene. Names as in `led_map.h` (`STAR3`, `PUMPKIN0`, `OWLA_L`, ...), case-insensitive |
| `coil <pend1\|pend2\|pend3\|lev> <duty -1..1> <ms>` | drive a coil at a fraction of 12 V. Refused above 1 A expected, over 2000 ms, without 12 V, when the coil is too warm for that long, or with `lev` while the loop runs |
| `sweep <fam1\|fam2>` | sweep a perch now; the curve comes back as a `sweep` event (frequencies, measured, empty-perch baseline) |
| `fam <live\|sweep>` | the familiars' mode: drive each token's tuning all the time (live, the default), or sweep and fit |
| `lev on\|off\|status` | the levitation loop; `status` gives its full telemetry and every tunable |
| `lev cal [coil\|zero]` | `coil`: measures the coil's field and polarity at the sensor (bat in its cradle or away; it also runs by itself on the first `lev on`). `zero`: the Hall zero (bat removed) |
| `lev tune <param> <value>` | a loop parameter (`bw_hz`, `dfilt_hz`, `ki_div`, `zp_rate`, `g0_mm`, `mass_g`, `i_max`, `catch_mm`, `loss_mm`, `ramp_mm_s`, ...; range-checked) |
| `lev eyes <0..1>` | the 80 kHz carrier that lights the bat's eyes (while it floats); 0.3 makes about 0.45 A |
| `pend <off\|sustain\|circle\|chaos>` | the pendulum's mode |
| `pend cal` | the TMAG5273's zero (bat away) |
| `theremin <on\|off\|cal>` | the theremin (`cal`: hands away for a second) |
| `film <on\|off>` | film mode: DC fields under magnetic viewing film |
| `volume <0..1>` | the theremin's loudness, capped at 0.25 (quiet by default: 0.12) |
| `i2c scan` | who answers on the bus |
| `adc dump` | every ADC input and multiplexer channel, raw and scaled |
| `clear` | clear latched faults |
| `save` | keep the levitation and pendulum calibrations, volume and switches in flash (every coil off first) |
| `reboot`, `reboot bootsel`, `bootsel` | with every coil off first |
| `help` | the list |

Events:
- `boot`, `i2c_scan`, `led_driver`, `sensors`;
- `faults` (now and new);
- `lev` (each state change, with the reason);
- `familiar` (arrived: owl / cat / unknown at f; left), `sweep`;
- `pendulum` (`chose`: the coil);
- `pend_cal`, `scene`.

**USB:** one device, 1209:0001 (pid.codes' test PID until it has its own). It has a CDC
port and Raspberry Pi's reset interface, with Microsoft OS 2.0 descriptors so Windows
binds WinUSB for picotool.

## The host tests (`make -C test`)

All run under AddressSanitizer and UBSan. The portable modules are built for the host
exactly as for the board.

| test | what it proves | numbers |
|---|---|---|
| `test_leds` | Every scene alone, and every scene under a storm of random events (taps, tilts, familiars on and off, theremin jumps, the room lights, 12 V unplugged and back, console overrides). Plus 30 minutes of the automatic sequence. Every LED, every frame: the lightness shown moves at most 1/60 a frame. The registers' real duty moves at most that plus two of its own steps. No LED passes its ceiling. Banks valid | largest per-frame change in any scene 0.0167 = the limit; the scenes alone need the limiter on <0.01 % of LED-frames; dither average within 0.15 of a step, slowest pattern 40 Hz |
| `test_quantum` | Crank-Nicolson keeps the norm (no renormalisation); stable at 20× the step; the group velocity; tunnelling vs the textbook barrier | norm drift 9×10⁻⁵ over the 14 s show (3×10⁻⁸ a step, float rounding); v 0.837 vs sin k₀ 0.841; 34 % tunnels (E 0.46 < V 0.50) |
| `test_lev` | The controller against the plant from `sim/physics` with the as-built coil (bias force, coil force/A, Hall field vs gap). Sensor: DRV5055A4 at 7.5 mV/mT, 12-bit ADC with noise, VQ errors; the mirror's offset; a coil 9 % off. Catches, settles, rejects a tap, releases, calibrates | catches from −3, −2, +2, +3 mm: peaks 0.64, 0.51, 0.88, 1.42 A with the soft catch (2.1-2.8 A as a step, as the sim does); settled mean current < 0.6 mA (limit 10 mA), 35 mA rms, 1 µm jitter; release 2.0-2.1 ms after the gap leaves ±5 mm; CAL finds the coil within 0.3 %, either polarity, either sensor orientation |
| `test_pendulum` | The estimator against an independent 3-D pendulum; SUSTAIN, CIRCLE, CHAOS, with the coils at 18 mm | position error 0.04 mm rms; sustain 24.5 mm (target 25); circle 17.7 ± 0.9 mm (target 18); chaos: 20 choices in 4 min over all three coils; peak 0.30 A |
| `test_familiar` | Sweep, identify and drive on a simulated perch. The plant reports the bridge's supply current: four harmonics, the drivers' draw, gain error, noise, the 1 ms filter. The last cases go through the 12-bit ADC at 2, 10 and the board's 10.3 V/A | owl named at 150.5 kHz, cat at 331.7 kHz (within ±5 % across gap, gain, R1 ±15 % and noise variations); empty perch and a coin: nothing; a 240 kHz token "unknown"; perch current ≤ 185 mA; the sweep keeps tanks ≤ 1.6 V (dark); lift-off noticed in 0.45 s. At the schematic's first 0.5 V/A (no amplifier) nothing was found, which led to the ×20.6 amplifier |
| `test_thermal` | Steady state; derating under a hard pulse train; the resistance thermometer against a mis-modelled coil | exact steady state; hottest 42.5 °C; mis-modelled coil 50.0 °C → 43.2 °C with the thermometer |
| `test_film` | Ten minutes of film mode with the thermal model | 136 steps, hottest coil 41.4 °C (42.4 °C if it cools worse than modelled), ≤ 1.000 A, ≤ 1.91 s on |
| `test_console` | Every command, malformed input, the coil limits, the volume cap, JSON well-formedness (quotes escaped) | 61 replies, all well-formed |
| `test_theremin` | Calibration, drift tracking, the exponential pitch map, the volume gate, a dead oscillator; the voice's pitch, ceiling, clickless onset and release | 200 → 1000 Hz; 440 Hz asked, 442 Hz measured with vibrato; peak under the ceiling |
| `test_bringup` | The bring-up image's console (`bringup_cmd.c`) on a simulated board: every command and its reply's values, every refusal and limit (no 12 V, over 1 A, the LED cap, ranges, malformed and over-long lines), a short and nFAULT stopping a pulse, walks and sweeps interrupted, the boot lines, and after every command every bridge off and asleep | 469 checks; one reply per command; every line well-formed JSON with no NaN |
| `test_rt` | Core 1 with the SDK modelled (`test/stubs/`), driven like the hardware: the safe pin state, the PWM's meaning against the DRV8874's truth table, no coil without 12 V, deadlines (64-bit: the clock run across 2^31 and 2^32 µs), the bridge's 0.5 µs loss a pulse, owner limits, brown-out, nFAULT (retry, latch, clear), shorted and open coils, ten minutes of 1 A asked for, the levitation CAL through the glue | PWM within 1 count; current 1.4 ms after a request; brown-out off in 0.6 ms (0.4 before the overlapped burst); nFAULT off in 1.0 ms; 1 A for 10 min derated to 0.45 A at 42.7 °C (plant 43.3 °C); CAL 3.18 mT/A (plant 3.11) |

## What is untested on hardware

Exercised on rev A board 1 on 2026-11-07: boot, USB enumeration and the console, the
watchdog rule (three resets to BOOTSEL, which is how the ADC/DMA interrupt race in
`tick_isr` was found and fixed), core 1's PWM/ADC/DMA sequence (running from flash, 3.3 %
of ticks were skipped and the worst tick's work took 322 µs, so the `adc` fault latched at
every boot; the RAM image, the overlapped burst and the rate-based fault of 2026-11-08 are
not yet tried on the board), the I2C devices
(all present), the scenes, the theremin (PIO counting, the voice, the audio DMA) and the
familiars in both modes. Still unexercised:
- **Core 1's phase lock and the carrier switch** (needs the levitation).
- **Flash settings** (`save`).
- **The levitation and the pendulum** (need the bigger supply, the bat and its magnet).

Specific things to check on the bench, in this order (`status` and `adc dump` show them
all):
1. **USB power alone:**
   - `status`: VBUS ≈ 5 V, V12 ≈ 0, `coils_powered` false;
   - `i2c scan` finds 0x30 (and 0x32 with the tree), 0x6A, 0x29, 0x35;
   - the LEDs are dim.
2. **12 V:** V12 reads 12 V (the divider). `led all 0.3`, then `led all off`. Check
   `scene night`.
3. **Coils, one at a time**, e.g. `coil pend1 0.05 200`. `adc dump` shows `pend1_ipropi`
   (R_IPROPI, the mux order). Check the bridges wake and sleep (`status` → `coils.awake`).
4. **The LP5036's duty model.** With a photodiode or a scope on one LED, check
   duty = C × B / 16 (`led_engine.h`).
5. **Levitation:** bat removed, `lev cal zero`; bat in its cradle, `lev on` (it calibrates
   the coil first, then catches); watch the `lev` events. Then `save`.
6. **Pendulum:** bat away, `pend cal`; hang the bat; `pend sustain`. Set `PEND_POLARITY`
   if it damps instead of pumping.
7. **Familiars:** `sweep fam1` with and without the owl; compare the event's curves.
   Check ISENSE's scale and filter time.
8. **Theremin:** `theremin cal` with hands away, then play; `volume 0.1`.
9. **Film:** `film on` with the film over the coils; watch `temps_C` and the coils with an
   IR thermometer to calibrate the thermal constants.

## Open questions for the board designer

**Settled with the designer on 2026-10-07:**
- PMODE tied high (PWM mode).
- IMODE grounded: fixed off-time chopping, nFAULT on overcurrent only.
- R_IPROPI 2.2 kΩ with VREF 3.3 V: 0.99 V/A, ITRIP 3.3 A.
- FAMn_ISENSE at 10.3 V/A (0.5 Ω, 10 k / 100 n, ×20.6 OPA2333): asked for after
  `test_familiar` showed that 0.5 V/A could not see a token.
- The "+5 V" rail is 4.8 V.
- The tree driver at 0x32; the downlights on OUT33/34.
- The pendulum coils 18 mm from the rest point.
- The bat's carrier at 80 kHz (tank 84 kHz, Q 2.5: 97 %).
- The LED positions JSON format.

**Still open.** Each is a `#define` marked `[ASSUMED]`; changing one line adapts the firmware.

1. **The ADC's reference** is the 3.3 V rail, and the DRV5055A4 is powered from the same
   3.3 V (its VQ = VCC/2 is ratiometric). Which way it faces (`HALL_POLARITY`) is detected
   automatically.
2. **LP5036.** EN tied high? Their VCC on USB power alone?
3. **The LED duty model.** The colour × bank-brightness product, assumed truncated to
   12 bits (C × B / 16); a photodiode on the bench settles it.
4. **The IMU's orientation** on the board (`IMU_AXIS_*`; the wisps roll along board x).
5. **Pendulum.** The thread's length (15 cm); the TMAG5273's depth under the bat at rest
   (12 mm); its sensing point 0.6 mm over the top copper; coil 1's direction (90°).
6. **Levitation.** The bat's mass (3.6 g). The cradle must hold the bat 2-3 mm below the
   float gap, 10.5-11.5 mm under the perch's bottom copper. The DRV5055 sits on the coil
   axis, 0.6 mm below the bottom copper.
7. **The coils.** 2.2 Ω with 1 oz inner copper (`COIL_R20_OHM`; the resistance
   thermometer calibrates it). The thermal constants (0.3 / 2.5 J/K, 3 / 40 K/W) want an
   IR-thermometer check on the bench. The perch coil's resistance (`FAM_R1_OHM`, 4.2 Ω with
   the drivers) must be right to ±15 % for the familiars' reported tuning to stay within
   ±5 %; the owl/cat names are robust either way.
8. **A temperature sensor beside the coils** (PLAN.md §7). The firmware uses the IMU's die
   temperature (else the TMAG5273's) as the coils' ambient. Is either near them?
9. **The light sensor's placement.** It must not see the board's own LEDs, or dusk and
   dawn will chase each other. The thresholds are 3 and 30 lux, with 20 s of hysteresis.
10. **Theremin.** The oscillators' frequency (0.5-1 MHz assumed) and the drop with a hand
    at the antenna (3 % assumed: `THEREMIN_*_SPAN`). Which end of the star arc is the moon
    (`SCENE_MOON_STAR` = 11, the right)?
11. **USB VID:PID:** 1209:0001 is a test PID; a public release needs its own.

## Not yet

- The LED positions: `led_map.h` takes them from the placement when it exists; the scenes
  use group order, not positions.
- Back-EMF sensing of the pendulum (the README's bonus measurement) and multi-board
  synchrony.
- A/B images, and a persistent log of faults.
