# OWLternating Current firmware

Version 0.1.0, for rev A. It is C11 on the Pico SDK 2.1.1 and TinyUSB, for the RP2354A
(the RP2350A with 2 MB of flash in the package).

**Status: it builds without warnings and passes ten host-test suites. It has not yet run on
a board.** The boards are not made yet. The core paths are real; the advanced control
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
- **A blank board** starts in the ROM bootloader; `picotool load` or the `RP2350` drive.
- **After that,** `picotool reboot -u -f` reaches BOOTSEL through the reset interface. So do
  the console's `reboot bootsel` and opening the serial port at 1200 baud.
- **Three watchdog timeouts in a row** restart in BOOTSEL, so a bad image can always be
  replaced over USB (GPiBridge's rule).

## Generated files: edit the source, not these

| file | written by | from |
|---|---|---|
| `src/board_pins.h` | `../gen/firmware_pins.py` | `../gen/pins.py`: every GPIO, each bridge's PWM slice (checked: IN1 = channel A), the ADC channels, the multiplexer's channels and the sense dividers' ratios, the I2C addresses, the board's pull resistors |
| `src/led_map.h` | `../gen/firmware_leds.py` | `../gen/leds.py`: all 49 LEDs (driver, channel, name, colour, board, position), each group in order, each driver's channel → LED table. Positions come from `../hardware/checks/led_positions.json` once the placement writes it; until then they are 0 and `LED_UNPLACED` says so |
| `src/lev_table.h`, `test/lev_plant.h` | `tools/gen_lev_tables.py` | `../sim/physics/` (the one-magnet levitation geometry, `../gen/mech.py`'s `OWL_LIFT`): the bias magnet's force, the coil's force per amp, the bat's field at the Hall sensor, all against the gap |

Run `python3 ../gen/firmware_pins.py && python3 ../gen/firmware_leds.py` after any change
to `gen/pins.py` or `gen/leds.py`. The C uses only the generated names, so when the
multiplexer's order changed (2026-10-07) nothing else needed editing.

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

1. **The tick slice's wrap.** PWM slice 6 drives no pin. It runs in phase-locked step with
   the levitation coil's slice: both are started together through the PWM block's EN
   register, and the tick's period is exactly 4 of the coil's 40 kHz periods (9 of its
   90 kHz ones with the carrier on). The wrap's interrupt starts the ADC burst, so every
   burst begins at the same point of the coil's PWM period: the centre of the forward
   pulse.
2. **The burst.** The ADC free-runs in round robin over ADC0 (Hall), ADC1 (the levitation
   IPROPI) and ADC2 (the multiplexer), eight times each: 24 conversions in 48 µs, taken by
   DMA.
3. **The DMA's completion interrupt** does the tick's work:
   - averages the burst;
   - moves the multiplexer to its next channel, which gets at least 30 µs to settle (the
     designer asks for 10 µs);
   - updates the rails and checks the faults;
   - runs the levitation loop;
   - applies the pendulum, film and console requests;
   - writes the coil PWM;
   - every millisecond, updates the thermal models.

### Coil drive (DRV8874, PMODE high = PWM mode)

IN1 is the slice's channel A, as is; IN2 is channel B, inverted; both are phase-correct.
With compare values ccA ≥ ccB, every period runs forward → brake → reverse → brake. The
coil sees a mean of (f_fwd − f_rev) × 12 V. This scheme has three properties:
- **Small ripple near zero current:** the current decays slowly through the brake state.
- **IPROPI keeps working:** the current mirror reads in drive and brake, but not in coast.
- **Linear down to zero:** a little of both directions keeps every output pulse at least
  300 ns long, so the mean stays linear.

The levitation coil's 90 kHz carrier for the bat's eyes is the same scheme with a lot of
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
    0 at 45 °C (the child-safety surface limit).
  - The models are two-node (copper/surface and board), with the board's temperature
    (IMU, else TMAG5273) as ambient.
  - The resistance thermometer: V/I from the current mirror corrects the model
    (copper +0.39 %/°C). In `test_thermal` it holds a coil that cools worse than modelled
    to 43 °C, where the model alone let it reach 50 °C.
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

## The console

USB serial "OWLternating console" (any baud; 1200 baud means BOOTSEL), and the UART at
115200 (J5, GPIO12/13), which mirrors every line. One command a line in, one JSON object a
line out. Replies carry `"ok":true` or `"ok":false,"error":"..."`. Events arrive unasked on
the same lines.

| command | what |
|---|---|
| `status` | version, uptime, rails (V12, V5, VBUS, whether coils are powered, USB-only), I2C devices, faults, coil and board temperatures, coil currents / duties / resistances, the Hall readings (levitation mT, TMAG5273 x/y/z), levitation, pendulum, familiars, scene, theremin, film, light, IMU, core 1's timing, LED frames |
| `scene <asleep\|dusk\|night\|firefly\|quantum\|familiar\|dawn\|theremin\|auto>` | hold a scene, or back to automatic |
| `led <name\|all> <0..1\|off>` | set lightness (still slew-limited), or hand back to the scene. Names as in `led_map.h` (`STAR3`, `PUMPKIN0`, `OWLA_L`, ...), case-insensitive |
| `coil <pend1\|pend2\|pend3\|lev> <duty -1..1> <ms>` | drive a coil at a fraction of 12 V. Refused above 1 A expected, over 2000 ms, without 12 V, when the coil is too warm for that long, or with `lev` while the loop runs |
| `sweep <fam1\|fam2>` | sweep a perch now; the curve comes back as a `sweep` event (frequencies, measured, empty-perch baseline) |
| `lev on\|off\|status` | the levitation loop; `status` gives its full telemetry and every tunable |
| `lev cal [coil\|zero]` | `coil`: measures the coil's field and polarity at the sensor (bat in its cradle or away; it also runs by itself on the first `lev on`). `zero`: the Hall zero (bat removed) |
| `lev tune <param> <value>` | a loop parameter (`bw_hz`, `dfilt_hz`, `ki_div`, `zp_rate`, `g0_mm`, `mass_g`, `i_max`, `catch_mm`, `loss_mm`, `ramp_mm_s`, ...; range-checked) |
| `lev eyes <0..1>` | the 90 kHz carrier that lights the bat's eyes (while it floats) |
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
| `test_lev` | The controller against the plant from `sim/physics` (bias force, coil force/A, Hall field vs gap). Sensor: DRV5055A4 at 7.5 mV/mT, 12-bit ADC with noise, VQ errors; the mirror's offset; a coil 9 % off. Catches, settles, rejects a tap, releases, calibrates | catches from −3, −2, +2, +3 mm: peaks 0.60, 0.49, 0.85, 1.41 A with the soft catch (2.6-2.8 A as a step, as the sim does); settled mean current < 1 mA (limit 10 mA), 34 mA rms, 1 µm jitter; release 2.1 ms after the gap leaves ±5 mm; CAL finds the coil within 0.2 %, either polarity, either sensor orientation |
| `test_pendulum` | The estimator against an independent 3-D pendulum; SUSTAIN, CIRCLE, CHAOS | position error 0.04 mm rms; sustain 24.2 mm (target 25); circle 24.3 ± 0.3 mm; chaos: 14 choices in 4 min over all three coils; peak 0.30 A |
| `test_familiar` | Sweep, identify and drive on a simulated perch | (see the familiar section below) |
| `test_thermal` | Steady state; derating under a hard pulse train; the resistance thermometer against a mis-modelled coil | exact steady state; hottest 42.5 °C; mis-modelled coil 50.0 °C → 43.2 °C with the thermometer |
| `test_film` | Ten minutes of film mode with the thermal model | 136 steps, hottest coil 41.4 °C (42.4 °C if it cools worse than modelled), ≤ 1.000 A, ≤ 1.91 s on |
| `test_console` | Every command, malformed input, the coil limits, the volume cap, JSON well-formedness (quotes escaped) | 61 replies, all well-formed |
| `test_theremin` | Calibration, drift tracking, the exponential pitch map, the volume gate, a dead oscillator; the voice's pitch, ceiling, clickless onset and release | 200 → 1000 Hz; 440 Hz asked, 442 Hz measured with vibrato; peak under the ceiling |
| `test_rt` | Core 1 with the SDK modelled (`test/stubs/`), driven like the hardware: the safe pin state, the PWM's meaning against the DRV8874's truth table, no coil without 12 V, deadlines, owner limits, brown-out, nFAULT (retry, latch, clear), shorted and open coils, ten minutes of 1 A asked for, the levitation CAL through the glue | PWM within 1 count; current 1.4 ms after a request; brown-out off in 0.4 ms; nFAULT off in 1.0 ms; 1 A for 10 min derated to 0.45 A at 42.7 °C (plant 43.3 °C); CAL 3.706 mT/A (plant 3.69) |

## What is untested on hardware

Everything that touches a pin is unexercised on hardware, though `test_rt` covers its logic
with the SDK modelled:
- **Core 1's timing:** the PWM/ADC/DMA sequence, the phase lock and the carrier switch.
- **Bring-up:** the I2C devices' configuration (written from their datasheets' register
  maps) and the SDK's initialisation of everything.
- **Peripherals:** the PIO counter, the audio DMA, USB enumeration, flash settings, and the
  watchdog.

Specific things to check on the bench, in this order (`status` and `adc dump` show them
all):
1. **USB power alone:**
   - `status`: VBUS ≈ 5 V, V12 ≈ 0, `coils_powered` false;
   - `i2c scan` finds 0x30 (and 0x31 with the tree), 0x6A, 0x29, 0x35;
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

Each is a `#define` marked `[ASSUMED]`; the firmware adapts by changing one line.

1. **DRV8874 PMODE tied high (PWM mode).** The drive scheme depends on IN1/IN2 = 1/1 being
   brake. **IMODE:** fixed off-time with automatic retry is assumed (nFAULT only on
   overcurrent); with cycle-by-cycle chopping, nFAULT also pulses during current regulation,
   which the firmware would treat as a fault after 1 ms.
2. **R_IPROPI = 2.2 kΩ and VREF = 3.3 V** (`R_IPROPI_OHM`): 0.99 V/A, ITRIP ≈ 3.3 A, and
   the IPROPI clamp protects the ADC.
3. **The ADC's reference** is the 3.3 V rail, and the DRV5055A4 is powered from the same
   3.3 V (its VQ = VCC/2 is ratiometric). Which way the DRV5055 faces (`HALL_POLARITY`) is
   detected automatically, but say if the marked side does not face the bat.
4. **FAMn_ISENSE**, now the perch bridge's filtered 5 V supply current:
   - its scale (`FAM_ISENSE_V_PER_A`, assumed 1 V/A);
   - its filter's time constant (≤ 1 ms assumed: the sweep waits 4 ms a step);
   - any offset.
5. **LP5036.** EN tied high? Their VCC on USB power alone? `ADDR` as in `pins.py` (0x30,
   0x31).
6. **The LED duty model.** The colour × bank-brightness product, assumed truncated to
   12 bits (C × B / 16); a bench measurement settles it.
7. **The IMU's orientation** on the board (`IMU_AXIS_*`; the wisps roll along board x).
8. **Pendulum geometry.**
   - Assumed values: thread length 15 cm; the TMAG5273's depth under the bat at rest
     12 mm; coil centres 25 mm from the rest point, coil 1 at 90°; the TMAG5273's sensing
     point 0.6 mm over the top copper.
   - The pendulum test found that at 25 mm the coils hold only 0.63 mN/A at the rest point,
     too weak to capture the bat in CHAOS mode. Coils ~15 mm from the rest point, or a
     lower bat, would make "which pumpkin" a real capture.
9. **Levitation.** The bat is 3.6 g. The cradle must hold the bat 2-3 mm below the float
   gap: 10.5-11.5 mm under the perch's bottom copper. The DRV5055 sits on the coil axis,
   0.6 mm below the bottom copper.
10. **The coils:** 2.2 Ω with 1 oz inner copper (`COIL_R20_OHM`; the resistance
    thermometer calibrates it). The thermal constants (0.3 / 2.5 J/K, 3 / 40 K/W) need an
    IR-thermometer check.
11. **A temperature sensor beside the coils** (PLAN.md §7). The firmware uses the IMU's
    die temperature (else the TMAG5273's) as the coils' ambient. Is either near them?
12. **The light sensor's placement.** It must not see the board's own LEDs, or dusk and
    dawn will chase each other. The thresholds are 3 and 30 lux, with 20 s of hysteresis.
13. **Theremin.** The oscillators' frequency (0.5-1 MHz assumed) and the drop with a hand
    at the antenna (3 % assumed: `THEREMIN_*_SPAN`). Which end of the star arc is the moon
    (`SCENE_MOON_STAR` = 11, the right)?
14. **USB VID:PID:** 1209:0001 is a test PID; a public release needs its own.

## Not yet

- The LED positions: `led_map.h` takes them from the placement when it exists; the scenes
  use group order, not positions.
- Back-EMF sensing of the pendulum (the README's bonus measurement) and multi-board
  synchrony.
- A/B images, and a persistent log of faults.
