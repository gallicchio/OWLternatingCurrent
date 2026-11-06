# Handoff: what the next agent needs to know (written 2026-11-05, evening)

This is for the agent who runs the bring-up with Jason on the morning of 2026-11-06.
It records what the conversation established that isn't obvious from the code. Read
[`BRINGUP.md`](BRINGUP.md) first: it's the procedure. This file holds the context
around it.

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

## The laptop (`feynman`)

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
  - **The no-pause version looks fine; use it.** As of 2026-11-06 its stand-ins (the grey
    slab and pedestal) are still on and the magnets aren't in yet. The next steps are
    `print/README.md`'s "After printing", then "Magnets in" (two-part epoxy). After that,
    check the polarity before the epoxy cures.
  - In `out/no_pause/magnets_in.png`, "bat" is the bat **circuit board**. The grey
    pedestal under the printed cap is thrown away.

## Who's who

- **Jason Gallicchio** (jason@hmc.edu) is the designer and owner. This is a Halloween set
  for a six-year-old: child safety around the magnets matters (`print/README.md`,
  `PLAN.md` section 7).
- Git commits end with the Co-Authored-By line the session's system reminder gives.
