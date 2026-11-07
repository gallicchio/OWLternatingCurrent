# Bringing up OWLternating Current, rev A

*(An agent picking this up: read [`HANDOFF.md`](HANDOFF.md) too: the laptop, the
network, what's been tested and what hasn't.)*

The boards came from JLCPCB on 2026-11-05: two assembled panels, three bare ones. This is
how to take the first assembled panel from the bag to a board that runs its real
firmware. Each step either passes or stops with a reason, before anything has had the
chance to get hot.

**Who does what.** Jason is at the bench and does everything physical: unwrapping,
looking, probing, soldering, plugging in, and putting a finger on parts to feel for heat.
Claude runs the steps from the laptop (`python3 bringup/run.py <step>`), reads the
results against what the design says, and decides what comes next. The scripts never
wait for keyboard input, so they can be run from the chat. Between two steps the person
at the bench does whatever the next step needs.

**The rules:**
- **Power always comes from the current-limited supply first.** The 12 V brick comes in
  only for the levitation, at the end.
- **Any step that sees something wrong turns the supply off.** That includes a current
  limit, a current above what's expected, a sagging input or a rail out of its window.
  An error in the script, Ctrl-C or a kill turns it off too. `python3 bringup/run.py off`
  turns it off by hand.
- **Change wiring only with the power off,** except for moving a probe tip.
- **Board 2 stays in its panel, untouched.** It's the reference for anything the design
  can't predict, such as resistances to ground.
- Every step writes its record to `bringup/results/<date>/`: a JSON file, plus plots
  where they help. These records are the bring-up's log; commit them.

What's in `bringup/`:

| file | what |
|---|---|
| `run.py` | the command line: one step per call; `--sim` runs any step against a simulated bench |
| `steps.py` | the steps |
| `expect.py` | every expected number, with where it comes from. Many are estimates: after board 1, replace them with what it read |
| `bench.py` | the instruments, through lab-instrument-control's drivers; the "supply off on any error" rule |
| `owlboard.py` | the board's console: one JSON line per reply (bring-up image or main firmware) |
| `sim.py`, `test_bringup.py` | the simulated bench (board, supply, scope, generator, DMM, with faults to inject) and the tests that run every step against it |

The firmware side is in `firmware/`:
- **The bring-up image** (`owl_bringup.uf2`) is a small separate image. It runs a console
  and direct hardware tests: rails, I2C, sensors, single LEDs, short coil pulses, perch
  sweeps, a tone and the theremin oscillators. It has no watchdog and no second core, and
  nothing in it drives a coil unless asked. See "The bring-up image" in
  [`firmware/README.md`](firmware/README.md).
- **The real firmware** is `owlternating.uf2`. Its bench checks are the last stage here.

---

## 0. Before the morning (done on 2026-11-05 unless marked)

- [x] Both images build on `feynman`, and all the host tests pass: `python3
      bringup/run.py build`. That builds into `firmware/build-<hostname>/` with
      `CXXFLAGS="-include cstdint"`, the workaround for Pico SDK 2.1.1's `pioasm` on
      GCC 15. (`firmware/build/` was configured on another machine, at another path.)
- [x] `pytest bringup/` passes: every step against the simulated bench, and every injected
      fault stops the ramp.
- [ ] **Optional:** `sudo apt install libusb-1.0-0-dev` (type `! sudo apt install
      libusb-1.0-0-dev` in the chat), then rebuild. The SDK then builds a `picotool`
      with USB support (`picotool load`, `reboot`, `info`). Without it, images go onto
      the board by copying the UF2 to its RP2350 drive, which is what `run.py flash`
      does.
- [ ] **Optional, only if USB fails:** an OpenOCD that knows the RP2350, so SWD
      through the Debug Probe works. Neither the system's OpenOCD 0.12.0 nor
      oss-cad-suite's has an `rp2350.cfg`. Raspberry Pi's fork, `raspberrypi/openocd`,
      or `probe-rs` would do. The Debug Probe's UART on J5 needs nothing: it's a plain
      serial port (`run.py --port /dev/ttyACM1 ...`).

## What goes on the bench

| thing | what for | notes |
|---|---|---|
| Agilent **E3646A**, RS-232 null-modem cable, FTDI USB adapter | the board's 12 V | **output 2**, on the 20 V range: 1.5 A at most. One of the two units has a dead output 1 (lab-instrument-control `hp/hp.md`), and output 2 works on both. One OUTPut switch serves both outputs, so leave output 1 unwired. |
| A **5.5 x 2.1 mm barrel plug** on two leads, **centre positive** | into J1 | check its polarity with a meter before it goes near the board |
| **Siglent SDS2104X Plus** and four x10 probes | the rails; the ripple; the tanks | the nicer scope (192.168.8.203 on the bench LAN; `--scope usb` over USB) |
| **Siglent SDG1032X**, or the Agilent 33220A or an HP 33120A | the tanks' resonances | `--gen sdg:IP`, `33220a:IP`, `33120a:gpib:10` |
| a 100 ohm resistor and about 5 turns of thin wire, ~3 cm across | the pickup loop for the tanks | |
| **Fluke 45** (RS-232), or any meter | resistances; rails to 0.1 % | `--dmm PORT` puts readings in the record; a hand-held meter's readings go into the chat |
| a **USB-C data cable** | programming and the console | a charge-only cable shows nothing at all |
| Raspberry Pi **Debug Probe** | UART console on J5; SWD on J4 | only if USB misbehaves |
| magnifier or microscope, tweezers, flux, iron, solder wick | inspection; the hand-soldered headers | |
| the **12 V 5 A brick**, or the **E3632A** (15 V, 7 A, with OCP) | levitation (current peaks near 3 A) | stage 8 only |
| an ESD mat and strap | | |

A ground point for the scope: the barrel plug's negative lead is the easiest. The foot
holes are not plated. J4/J5 pin 2 and the USB-C shell are ground too.

---

## 1. Unpowered

**1.1 Unwrap one assembled panel, on the mat.** Leave the second assembled panel in its
bag: it's board 2, the reference.

**1.2 Look at the base, all over, under magnification.** Compare it with JLCPCB's own
placement snapshots (`mfg/jlcpcb_order/*SMT_Snapshot*`) and the assembly drawings
(`mfg/release/OWLternatingCurrent_assembly_{top,bottom}.pdf`). In order of what would do
the most harm:
- **The power entry**, at the top right of the base, by J1:
  - **C1**, the 470 uF polymer can: its + is the left pad (`mfg/jlcpcb_order/README.md`);
  - **D2**, the SMBJ15A TVS: its cathode band toward +12V. Backwards, it shorts the input
    at 0.7 V;
  - **Q1**, the AO4407A, and **F1**;
  - **U1** (the TPS54302) and **L1**;
  - **D3, D4** (B5819W): their bands toward VSYS.
- **The RP2354A's corner**:
  - **L2** has a polarity dot. It must sit as in Raspberry Pi's layout (`gen/rpi_minimal`);
  - **U2** (the XC6206), the crystal Y1, and J2 (the USB-C): its pins and shell tabs
    soldered.
- **Every chip's pin 1**: U3 and U101 (the LP5036s), U5-U8 (DRV8874), U9 and U10
  (UCC27524), U11 (74HC4051), U14 (NS4150B), U15-U17 (the sensors).
- Solder bridges on the QFNs and TSSOPs, tombstoned 0402s, missing parts. JLCPCB's X-ray
  of the QFN area (`mfg/jlcpcb_order/SMT026100964723-*`) shows clean joints.
- **LS1**, the speaker, is through-hole: soldered from below.
- Cracked parts near the mouse bites.

A photo of anything doubtful goes into the chat.

**1.3 Snap the base out of the panel.** Use pliers on the tabs, one tab at a time, and
don't bend the board itself: MLCCs near a tab crack when the board flexes. The tree, the
perch, the bat and the tokens stay in the panel until stage 7.

**1.4 Resistance to ground at the test points**, board 1 and then board 2 (in its panel).
The black lead goes on ground: the USB-C shell, or J4/J5 pin 2. Read each rail with the
leads both ways round, since the reading depends on polarity through the chips' diodes.
With the Fluke on RS-232, `run.py ohms TP1 1` records each reading (`... ohms TP1 2` for
board 2). Otherwise the readings go into the chat.

| TP | rail | what it says |
|---|---|---|
| TP1 | +12V | tens of kohm or more, rising as C1 charges. **Under 100 ohm: stop** (D2 backwards, a bridge) |
| TP2 | +4.8V | kohms (the LEDs, two dividers, the UCC27524s) |
| TP4 | VSYS | kohms |
| TP3 | +3V3 | hundreds of ohms to kohms |
| TP5 | +1V1 | the lowest of all (the RP2354A's core); compare the two boards |
| TP6 | VBUS | high (the 10 k/10 k divider and the D4 diode) |

**What passes:** no rail under about 100 ohm (+1V1 excepted), and the two boards within
about 20 % of each other on every rail. A rail that differs between the boards is where
to look first.

**1.5 The bench check, with no board powered.** `run.py find` lists what answers.
`run.py tank owl` is a first job for the generator and the scope, with no risk to
anything (stage 6 explains it). It checks the instruments' wiring and the scripts, and
is useful in itself.

## 2. First power: the base alone, from the current-limited supply, without USB

**2.1 Wire it.**
- Leave USB unplugged, and nothing on J3.
- Supply output 2 to the barrel plug, and the plug into J1.
- The scope probes:
  - CH1 on **TP1** (+12V)
  - CH2 on **TP2** (+4.8V)
  - CH3 on **TP3** (+3V3)
  - CH4 on **TP5** (+1V1)

  The probes' ground clips go to the plug's negative lead. TP3 and TP5 are 1 mm pads: a
  short stub of bare wire soldered to each, and to TP1 and TP2, gives the probe hooks
  something to hold.

**2.2 `python3 bringup/run.py ramp`.** The input climbs slowly to 12 V:

| step | limit | what's expected |
|---|---|---|
| 1, 2, 3, 4.5, 6, 6.5 V | 20 mA | ~0.1 mA (only two 122 k dividers). +4.8V stays at 0 |
| 7.0 V | 150 mA | the buck starts (its EN threshold is 6.7 V): +4.8V, +3V3 and +1V1 appear. Tens of mA |
| 7.5, 9, 10.5, 12 V | 150 mA | the same power from a higher voltage, so the current falls. At 12 V: an estimated 15-40 mA for the blank board |

- Before each reading, the script takes a "zero": the supply's current reading at 0 V
  with the board connected. That cancels the supply's offset, which can be several mA.
- It stops the ramp and turns the output off if:
  - the supply sits at its current limit for more than 0.8 s;
  - the current is above the table's band;
  - the input sags;
  - +4.8V shows before 6.7 V;
  - a rail goes over its top: 5.25 V, 3.6 V, 1.3 V. The step at 7.0 V is there so a
    broken feedback divider can't put much more than 7 V on the "4.8 V" rail before the
    script sees it;
  - a rail is under its bottom once the buck has had 0.5 V more than its EN threshold.
- At 12 V it holds for 30 s, watching the current drift. **During the hold, Jason
  touches U1, L1, U2, Q1 and the RP2354A**: warm is fine, too hot to keep a finger on is
  not. Then it leaves the output on at 12 V with a 150 mA limit.

`ramp --to 6` stops below the buck: use it if the first ramp stops somewhere and the
input side needs looking at alone.

**2.3 `run.py rails`.** It zooms the scope in on each rail to read its level, then
measures the 4.8 V ripple (AC coupled, 20 MHz bandwidth). The expected levels:

| rail | expected | window |
|---|---|---|
| +12V | 12.0 V | 11.8-12.1 V |
| +4.8V | 4.80 V | 4.68-4.92 V |
| +3V3 | 3.30 V | 3.23-3.37 V |
| +1V1 | 1.10 V | 1.05-1.16 V |
| ripple on +4.8V | | under 50 mVpp; about 400 kHz, or bursts (pulse skipping at light load is normal) |

The scope's DC accuracy is a percent or two. For the record, read each rail with the
Fluke: move its leads, then `run.py rails +4.8V`, then the same for `+3V3`, `+1V1` and
`VSYS` (TP4, expected 4.3-4.6 V).

**2.4 `run.py capture`.** It turns the output off and waits for the rails to decay, then
switches 0 -> 12 V in one step. It captures all four rails, triggered on +4.8V rising
through 2.4 V, and saves a plot and a screenshot. It shows the order the rails come up
in and any overshoot (the script warns above 108 % of nominal). This leaves the output
on.

## 3. USB and the bring-up image

**3.1 Plug the USB-C cable from the laptop in**, with 12 V still on. Then `run.py usb`.
A blank RP2354A shows up as `2e8a:000f`, "RP2350 Boot", and an **RP2350** drive
appears. The 12 V current falls: VBUS is now the higher source for VSYS, so the logic
runs from USB.

If nothing appears:
- the cable: a charge-only one shows nothing;
- J2's joints;
- +1V1;
- the crystal: scope Y1's XOUT side with a x10 probe, expecting a 12 MHz sine. The ROM
  starts it for USB;
- hold **BOOT** while plugging in.

Then the Debug Probe's UART on J5. Its SWD on J4 needs the OpenOCD from section 0.

**3.2 `run.py flash`.** It copies `owl_bringup.uf2` to the RP2350 drive, and the board
reboots into it. The drive must be mounted: open it in the file manager if it isn't.
Then `run.py console id` should answer `{"ok":true,"image":"bringup",...}`.

**3.3 `run.py logic`.** It checks, all against `expect.py`:
- the rails as the ADC reads them, through the 74HC4051: within 5 % of the scope;
- the I2C scan: 0x30 (the base's LP5036), 0x6A (the IMU), 0x29 (the light sensor), 0x35
  (the TMAG5273), and 0x1C (the LP5036s' broadcast address);
- the sensors: the IMU reads |a| = 1 g at rest, the light sensor some lux, the TMAG5273
  a few mT (the board's own parts);
- the inputs: nFAULT not asserted with every bridge asleep; the SPELL button.

Press SPELL and run it again: `button` should change. Tilt the board for the IMU, and
cover the light sensor (U16, right of the tree's foot) for the lux.

## 4. The base's 31 LEDs

**4.1 `run.py leds`.** It lights each LED alone at duty 0.5. The supply's extra current
says the LED really conducts: about 5 mA at 12 V each, more for the pumpkins' three-die
5050s. An LED that adds less than 40 % of the median is flagged as open, reversed or not
soldered.

**4.2 `run.py ledwalk`.** Each LED alone, in `led_map.h`'s order, with its name printed.
Jason watches each one light in the right place, in the right colour:
- violet stars;
- purple wisps and rings;
- orange pumpkins.

A wrong place means `gen/leds.py`'s map is wrong, which is a firmware fix, not a
hardware one.

## 5. The base's bridges, audio and theremin

**5.1 The pendulum coils.**
1. `run.py limit 0.8`, so the supply can give the coils their pulses.
2. `run.py coils` gives each of pend1, pend2 and pend3 a 200 ms pulse at duty 0.08,
   about 0.35 A.

The bring-up image reads the current mirror, IPROPI. It reads in drive and in brake, so
its mean is the coil's current. From that, the image reports:
- the loop's resistance, and the coil's alone: the loop less the DRV8874's 0.2 ohm, to
  match 2.29 ohm within 30 %;
- the mirror's offset after the pulse;
- nFAULT.

A coil whose current is near 0 is open. The image stops a pulse early on nFAULT, or when
the mirror reads over 1.5 x the expected current: a short. The reply then says why and
still carries what it measured. It refuses any pulse that would draw over 1.0 A.

**5.2 The familiar perches.** `run.py perch` sweeps each perch's bridge from 100 to 400
kHz at a tiny duty (0.03), with no token on it. The driver clamps the frequency to
90-440 kHz: the reply's `freq_hz` is what ran. It saves the supply-current curve as a plot.
That curve is the empty-perch baseline. With a token on the perch, the curve shows a
bump near the token's frequency (stage 6).

**5.3 The audio.** Turn the SOUND switch on, then `run.py tone` plays 440 Hz for a
second at a tenth of full scale. That is quiet, and 440 Hz is two octaves under the
23 mm speaker's resonance (1.8 kHz, measured 2026-11-06), so listen with
`run.py console tone 1800 3000 1.0` (full scale, 0.2 W) before deciding anything.

`run.py audio` tells whether the amplifier drives the speaker without an ear: the 12 V
current the amplifier draws awake (SOUND on, ~1.8 mA), then what each tone adds (full
scale ~22 mA, a speaker's worth; nothing means no signal reaches it). The speaker's
impedance against frequency, from the same current, shows its mechanical resonance as a
dip. `run.py console audio 0.5` holds the PWM at a steady level for a meter on C30
(1.65 V) and `audio off` ends it.

**Don't clip a scope ground to either speaker terminal.** The NS4150B drives both ends
of the speaker. Probe each end against ground with the probe tip only.

**5.4 The theremin.** `run.py osc` counts both oscillators: some hundreds of kHz to a
couple of MHz, steady. Run it again with a hand near the gold moon, then near the ghost.
Each frequency should fall by a few per cent.

## 6. The tanks: tokens and bat, unpowered, then on the perches

**6.1 `run.py tank owl` (then `cat`, then `bat`).**

The wiring:
- The generator drives the pickup loop through 100 ohm.
- The token lies on the loop.
- Scope CH1, with a x10 probe, goes across the token's tank capacitor (C401, C501,
  C301).

The script sweeps the frequency from 0.6 to 1.6 times the design value, then finely
round the peak, and reports the peak and the Q:

| tank | design | window |
|---|---|---|
| owl | 142 kHz | ±12 % |
| cat | 303 kHz | ±12 % |
| bat | 82 kHz | ±12 % |

Keep the tank's amplitude under about 1.5 Vpp, or its LEDs clamp it and flatten the
peak. The script warns at 3 Vpp, and `--vpp 0.3` drives it more gently.

**6.2 The tokens on their perches.** Put the owl token on perch 1, then `run.py perch
1`. Then the cat token on perch 2, then `run.py perch 2`. Each curve should show a bump
inside its perch's window: 116-168 kHz for the owl, 248-358 kHz for the cat
(`familiar.c`).

**The bump is the coupled mode, not the tank's own frequency:** it sits at
ft / sqrt(1 - k^2), and a bare token flat on the perch couples hard (k about 0.74,
measured 2026-11-06: the owl's bump at 214 kHz, the cat's at 452 kHz, with a second
image of the cat at 150 kHz from the drive's 3rd harmonic). The firmware expects the
printed figure's 2 mm floor between them (k about 0.47: bumps near 161 and 343 kHz).
So test the tokens inside their printed figures, or on a 2-3 mm spacer, and use
`run.py sweep <perch> 90000 500000 200` to see the whole range: `perch` stops at 400 kHz,
below the bare cat's bump.

## 7. The tree and the perch

**7.1 Power off** (`run.py off`). Snap out the tree and the perch. **Jason solders J101
and J102** (the right-angle headers, top and bottom of the tree) **and J201** (the socket
under the perch): 48 joints. Then check for bridges, and check the even pins (+3V3,
+5V, grounds) against the base's J3 table in `gen/connectors.py`.

**7.2 Resistance check again**, with the tree plugged into J3 (and the perch on the
tree): TP1-TP5 against the values from 1.4.

**7.3 `run.py ramp`, again.** The ramp's windows are for the base alone, so expect
a few mA more. Then:
- `run.py logic --tree`: 0x32 must answer (the tree's LP5036);
- `run.py leds --tree` and `run.py ledwalk`: the tree's 18 LEDs, including the perch's
  two downlights.

**7.4 The levitation Hall sensor** (U201, in the perch's coil). `run.py logic` reports
`hall_lev_mT`. It should read near 0. A magnet brought under the perch moves it by tens
of mT, and the sign depends on the magnet's face.

**7.5 The levitation coil.** `run.py limit 0.8`, then `run.py coils lev`: 2.56 ohm,
through the tree's connectors.

## 8. The real firmware

**8.1** `run.py flash owlternating`, then `run.py console status`.

Done on 2026-11-07 (evening). The image as committed that morning crashed three times in
75 ms and parked in BOOTSEL (the ADC/DMA interrupt race, fixed in `rt.c`; `bringup/REVB.md`
1.8). If a new image does that again: it is back in BOOTSEL by itself, so `run.py flash
owl_bringup` restores the bench image, and a build with `-DOWL_DIAG=1` (firmware/README.md,
"The diagnostic build") says what core 1 was doing. The familiars are in live mode by
default (`fam sweep` for the sweep-and-fit design); in a lit room the show sleeps
(`scene night`). The supply's limit for the real firmware: 0.5 A (`run.py limit 0.5`);
the base draws 55-80 mA at 12 V with both tokens lit.

**8.2** Then firmware/README.md's "Specific things to check on the bench", in its order:
- USB alone;
- 12 V;
- each coil;
- the LP5036's duty model;
- the levitation, the pendulum, the familiars, the theremin and the film.

Each of those is a `run.py console <command>` (`status`, `adc dump`, `coil pend1 0.05
200`, `sweep fam1`, `lev cal zero`, ...). Each answer goes into the chat and the record.

**8.3 Levitation needs more current than the E3646A gives.** Its catches peak near 3 A
(`test_lev`). Switch to the E3632A (15 V, 7 A range, OCP set to 3.5 A) or the 12 V
brick, and do this last.

Also on the list: PLAN.md section 10's bench items.
- the perch loop's resistance into `FAM_R1_OHM`;
- the IMU's axis signs, by tilting;
- the 4.8 V rail at the amplifier through an LED step;
- a current step into the levitation coil with the Hall sensor recorded: does `kcs`
  match 2.9 mT/A?

---

## When something is wrong

| what you see | look at first |
|---|---|
| the ramp stops at 1 V at its 20 mA limit | a short on +12V: D2 backwards, C1, a bridge at Q1/F1/U1 |
| the current climbs below 6.7 V | the same, softly: D2's leakage, a DRV8874 awake (nSLEEP should be pulled low) |
| the limit is hit at 7.0 V, with the rails low | a short on +4.8V (an LED's anode? U9/U10? U14?) or +3V3 (U2, a sensor) |
| +4.8V over 5.25 V | the buck's feedback divider (36 k / 5.1 k); stop and look before anything else |
| +3V3 fine, no +1V1 | L2's orientation, the RP2354A's VREG pins |
| no USB at all | the cable, J2, the 27 ohm resistors on D+/D-, the crystal, +1V1 |
| USB works, no console after flashing | `run.py --port /dev/ttyACMx console id` on the Debug Probe's UART (J5): the image runs but USB doesn't |
| an I2C device missing | its supply, its pull-ups, and the `i2c` boot event's `sda_stuck` and `scl_stuck` |
| an LED flagged dim | that LED's orientation and joints; the LP5036 channel (`led <drv> <out> 0.5`) |
| a coil reads high resistance or no current | its vias (the coils are four-layer spirals); its bridge's nSLEEP; IPROPI's 2.2 k |

## The simulated bench

`--sim` runs any step against `sim.py`. That's how the steps were debugged:

```sh
python3 bringup/run.py --sim ramp
python3 bringup/run.py --sim --fault short5 ramp     # stops at 7.0 V at the current limit, output off
python3 bringup/run.py --sim --fault fb_open ramp    # stops at 7.0 V: "+4.8V reads 6.7 V"
python3 bringup/run.py --sim --fault led_open:STAR3 leds
pytest bringup/                                      # all of it
```

The simulated board's console is the bring-up image's own command code, compiled for the
PC (`firmware/test/bringup_sim`). So the protocol the scripts use is the one the board
will speak. The rest of the simulated board is a model of the 12 V input and the rails
from the same numbers as `expect.py`. It agrees with the design by construction, not
with the hardware: its job is to exercise the scripts, not to predict the board.
