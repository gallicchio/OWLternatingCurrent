# Handoff: what the next agent needs to know (written 2026-11-05, evening; updated 2026-11-08)

This is for the agent who runs the bring-up with Jason. It records what the conversations
established that isn't obvious from the code. Read [`BRINGUP.md`](BRINGUP.md) first: it's
the procedure. This file holds the context around it.

**Keep it here, not in an agent's private memory.** Jason wants the bench state, the
machine setup and every decision in the repo, where he and any agent can read it (Jason,
2026-11-08). Update "Where the bench stands" at the end of each session.

## Where the bench stands (2026-11-10, evening)

Board 1 is on the bench PC `bell`, with the tree and the perch; board 2 is still
sealed. Everything up to 2026-11-10 evening is committed (Jason pushes).
**Every number measured on the bench (masses, coil ohms, sense gain, thermal fits, IR
readings, what worked and what failed) is in `bringup/MEASUREMENTS.md`.** Add new ones there.
- **State now (2026-11-10, evening).** Where this block and the 2026-11-09 bullets below
  disagree, this block is right.
  - Board 1 on the BK 9130 by hand (12 V, 3 A), V12 11.74 V. The second owl is on the perch
    (`OWL_LIFT` 12.5, magnet 12.45 mm over the copper); the bat is 4.70 g, cap on, magnet
    flipped. Results: `bringup/results/2026-11-10/`, summed up in MEASUREMENTS.md "The
    second owl" and REVB.md 1.12.
  - **Flashed last** (`firmware/build-bell-next/owlternating.uf2`): the tables for 12.5,
    the eyes breathing at 0.1 by default, the rings' breathing chase (1 s a turn), the
    zero-power walk aiming at 0.2 A (`zp_i`), and `lev tune kcs` that `save` keeps.
  - **Not done yet on that firmware, with the bat away:** the flash still holds the first
    owl's zero (−0.71 mT; this owl's is about 1.37). Run `lev cal zero`, then `lev tune
    kcs 3.64` (`lev cal coil` is wrong on this owl, REVB 1.12 item 4), then `save`. Then
    `lev on`, a `lev_watch.py` logger, and tell Jason in bold to lift the bat. Expect
    about 7.95 mm at about 0.2 A mean. At the last look the bat was stuck up on the perch
    (gap 4.4 mm): ask Jason to take it off first.
  - **Next** (all eleven host test suites pass on this firmware):
    1. Fly the defaults above; check by eye the eyes and rings breathing.
    2. The live presence probe (REVB 1.12 item 5), then the rings fade out under a token.
    3. When Jason prints the third owl (`print/out/owl.stl`, `OWL_LIFT` 11.4): regenerate
       the tables (`~/.local/venvs/owl/bin/python firmware/tools/gen_lev_tables.py`),
       rebuild, run the tests, flash, then zero, kcs and save as above. Expect about 8.4 mm
       with no current.
    4. `lev cal coil`'s "IPROPI disagrees".
  - **Bench scripts added on 2026-11-10** (each records to `results/<date>/`, never sends
    `lev off`, and voids any stretch in which the IMU counted a tap, a bump to the board):
    `lev_setpoint.py` (set-point steps), `lev_eyes.py` (eyes bursts, with the thermometer),
    `lev_eyes_ir.py` (eyes stages for the IR camera), `fam_token.py [sweep]` (tokens on
    and off, with prompts for Jason). Move the set-point only by `g0_mm` in 0.1 mm steps,
    and set `g0_mm` to the walk's `gzp_mm` before any `zp_range_mm` change: the other order
    dropped the bat.
  - **The serial port takes one script at a time.** Stop a logger with SIGINT, so it saves
    its record.
- **Earlier (12:10, 2026-11-09):** board 1 on, from the BK 9130's channel 1 set **by hand**
  (12 V, 3 A; no serial cable yet). It runs `firmware/build-bell-next/owlternating.uf2`
  (12:08), which starts in **`play`**: the demo mode for Friday, where every input lights its
  own LEDs at once (`firmware/src/scenes.h`; `scene auto` gives the old show).
  - The levitation loop is on and waiting. `g0_mm` is 9.5 by default now (`LEV_G0_BENCH_MM`).
    `zp_range_mm` was set to 1.5 by hand so the bat floats at 8 mm or more; a reboot puts it
    back to 2.0. The bat's eyes are on by default (`LEV_EYES_DEFAULT` 0.3): untested by eye.
  - The thermal cutoff is on. The levitation coil's model now uses the bench-fitted
    constants (`LEV_THERMAL_*`, REVB.md 1.11 finding 5).
  - The SPELL button cycles three spells: ghost, wake, chirp. Tap threshold 0.19 g.
  - The perch is still **turned round** (REVB.md 1.9).
- **The eyes are OFF by default** (`LEV_EYES_DEFAULT` 0, flashed at 15:05). An IR reading
  of 67 °C under the owl came while the model said under 50 (REVB.md 1.11 finding 9).
  `lev eyes 0.3` turns them on by hand, only while someone watches with the IR camera.
  The loop was left off.
- **The new owl (2026-11-09, 14:40):** `gen/mech.py` `OWL_LIFT` is now 12.5 mm (was 14). The
  bat weighs 4.70 g with its cap, 4.23 g without; 3.6 g was assumed. `print/out/owl.stl`
  is rebuilt (`check.py` all OK). Built with the venv's Python and `--no-render`; this PC
  has no display for OpenSCAD's renders, so `parts.png`, `foot.png` and `assembly.png` are
  older renders (the two matplotlib cut-throughs were redrawn). When Jason has printed it,
  glued its magnet and dropped the bat's cap (magnet taped to the PCB):
  1. Regenerate the levitation tables: `python3 firmware/tools/gen_lev_tables.py`, then
     rebuild and run the tests.
  2. With the bat away: `lev cal zero`, then `save`.
  3. `lev tune mass_g` to the bat's weight on a non-magnetic stand, then hover. The
     model says it should float near 8.9 mm with no current.
  4. Build's README line "bat floats 10.1 mm" assumes 3.6 g: ignore it.
- **Only the no-pause prints exist now (2026-11-09, 16:30).** Jason printed `out/owl.stl`,
  which was then the pause version (a sealed pocket, no slot), by mistake. The sealed
  version is gone from the OpenSCAD source, `build.py` and `check.py`; `out/owl.stl`,
  `out/bat_cap.stl` and `out/plate.stl` are now the slotted owl and the floorless cap
  (byte-identical to the old `out/no_pause/` files), and `out/no_pause/` is deleted. Every
  owl STL in the repo has the slot in its back.
- **Next, with Jason at the bench:**
  1. The Fluke settles the current question (REVB.md 1.11, findings 2 and 4): its ohms
     across the levitation coil with the power and USB off, then its DC volts across
     the coil during `run.py console coil lev 0.158 2000`.
     - **Where:** the perch's socket J201, measured on its solder joints on the top.
       Look down on the perch with PERCH upright, so the socket's two rows run across
       below the word.
     - As seen from above, PERCH upright:
       ```
       upper row:  15     13     11   9    7    5    3    1 (square)
                   DOWN1  DOWN0  GND  GND  GND  GND  GND  HALL
       lower row:  16     14     12   10    8     6    4    2
                   LEV_A  LEV_A  GND  LEV_B LEV_B GND  5V   3.3V
       ```
     - Measured on 2026-11-09, pin 10 to 14: 3.24 Ω, against 2.56 designed (REVB.md 1.11, finding 5).
  2. The 5-minute hover with the IR camera on the perch: `run.py console lev tune g0_mm
     9.5`, `run.py console lev tune thermal_cut 0` (Jason asked for the cutoff off; it is
     back on at reboot), then `python3 bringup/lev_watch.py 600 "..."`, which logs
     `lev_thermo` once a second.
  3. Then fix the model's constants from the fits (REVB.md 1.11 finding 4), and decide
     what the levitation coil's limit should act on: the thermometer's reading, once its
     absolute anchor is settled.
- **Tools added today:**
  - `bringup/coil_thermo.py sweep|heat|cool` drives the levitation coil from the console
    and records the thermometer against the model.
  - `lev tune thermal_cut 0|1`.
  - `status` → `lev_thermo` gains `copper_C`, `ref_ohm`, `ref_C` and `cut`.
- **Works:** the rails, all 47 LEDs (base, tree, the perch's downlights: 4.8-4.9 mA each
  at duty 0.5), every I2C device, the speaker, the theremin, both tokens lighting
  live, the levitation Hall sensor, the levitation coil (2.51 Ω), and **the bat hovers**
  (201 s at most, at 7.5 mm and 0.33 A; each hover ends in the levitation coil's thermal
  model, never in the loop; REVB.md 1.11). All eleven host test suites pass.
- **Firmware changed tonight** (REVB.md 1.8, 1.11, 3.3): both cores from RAM (worst tick
  322 µs to 20 µs), the `adc` fault as a rate, the ADC burst overlapping the control step,
  64-bit coil deadlines (the loop was locked out from 2147.5 s of uptime), the bridge's
  0.5 µs pulse loss compensated, the levitation coil's thermal limits (copper 80 °C,
  board 50 °C), a constant-power speaker table (under 0.2 dB: the speaker's loudness
  change is acoustic).
- **Demo notes:** in a lit room the show sleeps (`scene night` forces it on). `fam live`
  is the default. For the bat: `lev tune g0_mm 9.5`, `lev on`, bring it up from below
  under the coil and let it go when it pulls.

What's next, in order:
1. **The bat floats too near the perch.** The zero-power gap is about 6.6 mm against the
   8.5 mm designed: weigh the bat (3.6 g assumed); a second magnet in the owl, or a
   lighter bat. Then make `g0_mm` the default, or let the firmware find the zero-power
   gap itself.
2. **The thermal model of the levitation coil ended every hover after 2-3 minutes,**
   while Jason found the perch "warm, but not at all hot". The levitation coil now has
   the copper-resistance thermometer (REVB.md 1.11; in the build above, not yet on the
   board). Check on the board that `lev_thermo.calibrated` turns true early in a hover
   and that `t_meas_C` agrees with an IR thermometer on the perch. Rev B: a temperature
   sensor on the perch (a TMAG5273 instead of the DRV5055 gives one).
3. **The bat's tilt and spin:** its centre of mass off its magnet (rev B); the pendulum
   coils might damp the swing. Then the eyes (`lev eyes 0.3`) and the pendulum.
4. **The BK 9130s' serial cables** (IT-E131, ordered by Jason), then `bk/test_bk.py`
   against the 1.5 Ω resistors on channels 1 and 3.
5. **Token reach** (after Friday): a series capacitor in each perch coil (REVB.md 1.8).
6. **Theremin hand distance** and **the speaker's acoustic table**, after the owl and
   bat, with Jason's free-text feedback.
7. **A coin reads as a token in live mode;** **`main.c`'s float clock** loses resolution
   over hours (8 ms at 18 h; the familiars' dither is 5 ms).

## The plan for the morning

- **The boards arrived on 2026-11-05 and are still wrapped:** two assembled panels and
  three bare ones (JLCPCB order SMT026100964723, 13544840A_Y19).
- **Where and who:** the bring-up happens in **Jason's office**.
  - Jason is at the bench and does everything physical: probing, soldering, plugging in.
    He checks the chat now and then.
  - Claude runs `python3 bringup/run.py <step>` through the Bash tool. Every step is one
    non-interactive command, because the Bash tool can't answer keyboard prompts. Between
    steps, say in the chat exactly what Jason should do next.
- **Power:** the base gets 12 V from the Agilent **E3646A's output 2** through a
  centre-positive barrel plug into J1, at the current limits the scripts set. The
  levitation (peaks near 3 A) comes last, on the E3632A (OCP on) or the 12 V brick.
- **Board 2** (the second assembled panel) stays sealed as the reference for
  resistances to ground.
- **Records:** every step writes to `bringup/results/<date>/`. Commit them with the
  findings. Jason pushes himself; commit only when he asks.

## The laptop (`feynman`), the original plan

- **Network:** on 2026-11-05 it was on WiFi, 192.168.4.x. The instruments' addresses in
  lab-instrument-control's `AGENTS.md` are the *teaching bench's* (bench PC `bell`, LAN
  192.168.8.x), and none of them answered from here. **Run `run.py find` first.** If the
  scope or the generator doesn't answer, ask Jason how they're connected: `--scope usb`
  works for the SDS2104X Plus. Or put the addresses in `bringup/bench.json` (the keys
  are in `bench.DEFAULTS`).
- **The supply** is RS-232 through an FTDI adapter and a null-modem cable with DTR and
  DSR wired (lab-instrument-control `hp/hp.md`).
  - `run.py find` locates the E3646A with scpi_link's identify, which only asks `*IDN?`.
  - **One of the two E3646As has a dead output 1,** so everything uses output 2.
  - One OUTPut switch serves both outputs; the scripts park the unused one at 0 V, 20 mA.
- **Firmware build:** use `python3 bringup/run.py build`.
  - It builds into `firmware/build-feynman/` with `CXXFLAGS="-include cstdint"`, the
    workaround for Pico SDK 2.1.1's `pioasm` on GCC 15.
  - `firmware/build/` was configured on another machine (`frank`, another path): don't use
    it.
  - `make -C firmware/test` runs the eleven host-test suites; they all passed on
    2026-11-05.
- **Flashing:** there's no `picotool` with USB support unless Jason ran `sudo apt install
  libusb-1.0-0-dev` and the firmware was rebuilt. `run.py flash` copies the UF2 onto the
  RP2350 drive (`/media/jason/RP2350*`), which must be mounted: ask Jason to open it in
  the file manager.
- **SWD:** no OpenOCD here supports the RP2350 (the system's 0.12.0 and oss-cad-suite's
  both lack `rp2350.cfg`), so SWD needs Raspberry Pi's fork or `probe-rs`. The Debug
  Probe's **UART** on J5 works as a plain serial port: `run.py --port /dev/ttyACMx ...`.
- **Python:** pyserial, numpy and matplotlib are installed. **pytest and shapely are
  not**: last night's virtual environment was in the session's scratchpad and won't
  survive the reboot.
  - To get them back: `python3 -m venv --system-site-packages <dir> && <dir>/bin/pip
    install pytest shapely`.
  - pytest runs `bringup/test_bringup.py`; shapely is for `print/build.py`.
- **lab-instrument-control** is at `~/mudd/lab-instrument-control` (or `$OWL_LAB`). Its
  rules apply: shared instruments, put back what you change, leave outputs off.

## The bench PC (`bell`), where the bring-up actually runs

Set up on 2026-11-06; the instruments' default addresses in `bench.py` are right here
(LAN 192.168.8.x).
- **Build:** `PATH=/usr/bin:$PATH python3 bringup/run.py build`, into
  `firmware/build-bell/`. Xilinx Vitis's old cmake 3.3 and gcc 11 come first in the
  login PATH and break `cmake --install`; apt's cmake 4.2 and gcc-arm-none-eabi 14.2 are
  in `/usr/bin`.
- **The diagnostic build:** `firmware/build-bell-diag/`, with `-DOWL_DIAG=1`
  (firmware/README.md).
- **Tools, called by full path** (`~/.local/bin` may not be on an agent shell's PATH):
  - `~/.local/bin/picotool` v2.3.2 with libusb (`load`, `info`, `reboot` work), built in
    `~/.local/build/picotool` from `firmware/build-bell/_deps/picotool-src`. It can't
    open the running app's reset interface (no udev rule for 1209:0001): reach BOOTSEL
    with the console's `reboot bootsel` instead.
  - `~/.local/bin/probe-rs` 0.32.0, for SWD through the Debug Probe (serial
    E66548545752B026, flashed to debugprobe v2.3.1 on 2026-11-06; probe-rs refuses the
    1.0.x it shipped with). SWD and the UART aren't wired to the board yet.
- **Python:** the venv `~/.local/venvs/owl` (system site packages plus pytest and
  shapely).
- **Ports:** the board's USB is `/dev/ttyACM1`; `/dev/ttyACM0` is the Debug Probe.
- **Git:** an agent's shell here has no SSH agent, so it can commit but not push. Jason
  pushes.
- **Supplies:** `run.py --psu E3632A` drives an E3632A (15 V range, OCP at `--ocp`, default
  3.5 A) for the levitation; the default is the E3646A's output 2. The BK 9130 is by hand
  until its IT-E131 cables come.
- **Levitation runs:** `python3 bringup/lev_watch.py SECONDS "what"` turns the loop on and
  records it (`results/<date>/*_lev_try.json`).

## What has been tested, and what hasn't

- **Simulation only.** No script or firmware here has run against real instruments or a
  real board.
  - `bringup/sim.py` imitates the drivers method by method.
  - The board's console in simulation is the bring-up image's own command code, built for
    the PC (`firmware/test/bringup_sim`).
  - **The first real run of each step may turn up driver or timing problems.** If a step
    fails for reasons of its own, fix the script; don't push on.
- **Numbers that are estimates, not measurements** (`bringup/expect.py`; replace them with
  what board 1 reads):
  - the idle current at 12 V: 15-40 mA estimated, the blank chip in its ROM bootloader;
  - each LED's extra 12 V current at duty 0.5: ~5 mA;
  - resistances to ground: unknown, so compare with board 2;
  - the theremin oscillators: 0.5-1 MHz was assumed;
  - the tanks' Q.
- **Checked against the datasheets on 2026-11-05:**
  - The DRV8874's IPROPI reads in drive and in brake (slow decay), not in coast, so the
    bring-up image's coil currents are the coil's real current.
  - The LP5036 answers its broadcast address 0x1C, which is why 0x1C is in the expected
    I2C list.
- **Still open on the board** (`firmware/README.md`, "Still open"): the LP5036's EN tied
  high? The IMU's axis signs (U15 is on the bottom, so KiCad mirrors it). The LED duty
  model. The light sensor seeing the board's own LEDs.

## Safety decisions already made (don't undo them without a reason)

- **Never above 13.5 V on J1.** The supply's OVP is 13.5 V; D2, the SMBJ15A, stands off
  15 V.
- **The ramp has a step at 7.0 V,** just above the buck's 6.7 V turn-on. In the simulator,
  a broken feedback divider put 7.2 V on the "4.8 V" rail by the old first step at
  7.5 V, beyond the NS4150B's 5.25 V absolute maximum.
- **The bring-up image refuses any coil pulse expected to draw over 1.0 A.** It stops a
  pulse on nFAULT or on a mirror reading over 1.5 x the expected current.
- **Don't clip a scope ground to either speaker terminal:** the NS4150B drives both ends
  of the speaker.

## Things found that aren't fixed (not bring-up blockers)

- `gen/pins.py`'s comments say the perch current sense is "0.5 R, x20.6, 10.3 V/A". As
  built it's **0.1 ohm x 101 = 10.1 V/A**, and `firmware/src/config.h` already uses
  10.1. Those comments flow into the generated `firmware/src/board_pins.h`, so fix them
  in `gen/pins.py` and regenerate (`python3 gen/firmware_pins.py`).
- DESIGN_REVIEW.md section 10 says "a 5 A PTC"; F1 holds 3 A and trips by 6 A
  (`gen/sch_base.py`).
- The levitation still has no printed cradle to hold the bat at the float height while
  the loop catches it (PLAN.md section 10). By hand, or on its thread, are the fallbacks.

## The 3D prints (from the same conversation)

- **Jason's 3DPrinterOS account (cloud.3dprinteros.com, the X1 Carbon) refuses `.3mf`
  uploads,** so the repo now has STLs only.
  - Its X1C profile once failed with `wall_filament: 0 not in range` (a profile fault,
    not the file's).
  - Its defaults include tree supports and a brim: both must be off for these parts.
- **Jason has printed both plates** through 3DPrinterOS.
  - The pause version printed with no pause, so its owl's and cap's pockets are sealed
    with nothing inside: those two parts can't take magnets.
  - (Since 2026-11-09 the pause version is gone from the repo: only the no-pause parts
    are built, at `print/out/*.stl`.)
  - **The no-pause version looks fine; use it.** As of 2026-11-06 its stand-ins (the grey
    slab and pedestal) are still on and the magnets aren't in yet. The next steps are
    `print/README.md`'s "After printing", then "Magnets in" (two-part epoxy). After that,
    check the polarity before the epoxy cures.
  - In `print/out/magnets_in.png`, "bat" is the bat **circuit board**. The grey
    pedestal under the printed cap is thrown away.

## Who's who

- **Jason Gallicchio** (jason@hmc.edu) is the designer and owner. This is a Halloween set
  for a six-year-old: child safety around the magnets matters (`print/README.md`,
  `PLAN.md` section 7).
- Git commits end with the Co-Authored-By line the session's system reminder gives.
