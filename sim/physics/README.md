# Physics feasibility: what PCB coils can do to magnets and figurines

Run on 2026-10-07 to put numbers behind the ideas table in `PLAN.md` before choosing
what to build. Everything here is plain Python (numpy, scipy, matplotlib):

```sh
python3 magnetics.py      # the toolkit's self-tests against closed forms (all pass)
python3 wpt_link.py       # wireless power to a 'familiar' figurine
python3 coil_forces.py    # levitation without iron, pendulum kicks, sliding, rolling (~1 min)
python3 levitation.py     # zero-power suspension of a PCB bat under a perch coil
```

Each script writes a JSON and a PNG into `results/`.

## The toolkit (`magnetics.py`)

- **Conductors** are polylines; each straight segment's field is the closed-form
  Biot-Savart result, so the answer is exact for the polyline.
- **Magnets** are replaced by their equivalent surface currents, K = M × n with
  M = Br/μ0. A disc magnetised along its axis is a stack of loops round its side
  wall; a sphere is loops carrying M·R·sinθ·dθ.
- **Forces and torques** on a magnet are the Lorentz force on those currents in the
  coil's field. The force on the coil is the opposite, which is how a PCB "motor"
  pushes a magnet.
- **Coil inductance** comes from Mohan's current-sheet formula for each layer, plus
  exact (elliptic-integral) mutual inductances between layers. Resistance is counted
  in squares, with a 1-D skin-effect correction and a 1.3× proximity allowance.

The self-tests agree with closed forms to better than 0.02 %:
- on-axis field of a loop;
- on-axis field of a disc magnet;
- the mutual inductance of coaxial loops (Neumann sum against Maxwell's elliptic
  formula);
- the force between loops (Lorentz sum against I1·I2·dM/dz);
- a sphere's external field against a point dipole.

## The canonical coil

A 4-layer spiral on JLC041611-7628: 15 mm outer radius, 3 mm inner, 12 turns per
layer, 0.6 mm track at 1 mm pitch.
- L = 31.5 µH.
- R = 3.35 Ω with JLCPCB's default copper (1 oz outer, 0.5 oz inner), 1.68 Ω with
  2 oz outer and 1 oz inner.
- Self-resonance is roughly 5-6 MHz (layer-to-layer capacitance across the 0.21 mm
  prepreg), so it is a coil up to about 2 MHz, not at 6.78 MHz.

## Results

### 1. Wireless power to a familiar (`wpt_link.py`)

Base coil as above (33 µH, inner radius 6 mm); familiar coil 2 layers, 12 mm radius,
8 turns, 3.8 µH. Gap = top copper of the base to the bottom copper of the familiar
(PLA floor plus air).

| gap | k | best efficiency at 150 kHz | at 400 kHz | at 1 MHz | TX current for 150 mW to LEDs, 150 kHz / 1 MHz |
|---:|---:|---:|---:|---:|---:|
| 2 mm | 0.56 | 48 % | 75 % | 89 % | 0.16 A / 0.05 A |
| 4 mm | 0.42 | 38 % | 68 % | 85 % | 0.20 A / 0.05 A |
| 6 mm | 0.31 | 28 % | 60 % | 81 % | 0.26 A / 0.06 A |
| 10 mm | 0.18 | 14 % | 42 % | 69 % | 0.42 A / 0.09 A |

- **Verdict: easy.** A familiar needs only ~150 mW, so even the low-Q 150 kHz link
  works with a few hundred mA in the base coil.
- **Higher frequencies** raise Q, and with it efficiency, up to the coil's
  self-resonance. They also need faster bridges.
- **Frequency addressing.** Each familiar is a series-resonant tank loaded by its
  LEDs (loaded Q 5-8). Tuned a factor of 2 apart, a familiar off its frequency
  receives 0.7-1.7 % of the power of one on it. So the base can light each familiar
  separately, and find which are present from the reflected impedance (a sweep), with
  **no chip in the familiar**.

### 1b. The familiar in the time domain, with real LEDs (`familiar.py`)

The matched-load link budget above assumes a resistive load, but an LED conducts
nothing below about 1.9 V (orange) or 2.9 V (violet), and the EMF induced at 150 kHz
is only 1-2 V. So the familiar coin is a **parallel** resonant tank: the C0G capacitor
across the coil steps the voltage up by Q, and the LEDs clamp it. An orange and a
violet LED sit in anti-parallel across the tank, so each lights on its own half-cycle.

Geometry:
- **coin:** 4 layers (it rides on the base board's panel), 7 turns per layer, 11.5 mm
  outer radius, 11.5 µH;
- **perch:** 10 turns per layer, 28.5 µH;
- **gap:** 3 mm (a 2 mm printed floor and 1 mm of air), M = 8.5 µH, k = 0.47.

Results (`python3 familiar.py`, about 40 s):

| perch current | owl (tuned 150 kHz), driven at 150 kHz: orange / violet | cat (330 kHz) at 330 kHz | cat, while 150 kHz is on | owl, while 330 kHz is on |
|---:|---:|---:|---:|---:|
| 0.05 A | 0 / 0 mA | 14 / 0.2 mA | 0 / 0 | 0 / 0 |
| 0.10 A | 12 / 0 mA | 27 / 6 mA | 0 / 0 | 0 / 0 |
| 0.15 A | 24 / 2.5 mA | 40 / 14 mA | 0 / 0 | 0 / 0 |
| 0.20 A | 35 / 8 mA | 53 / 21 mA | 0.7 / 0 | 0 / 0 |
| 0.30 A | 56 / 20 mA | 79 / 38 mA | 11 / 4.6 | 0 / 0 |

- **Colour follows the drive.** Orange lights first; violet joins as the drive rises,
  because its photons (3.1 eV) need more voltage than orange's (2.0 eV). One coil
  current sets the brightness and the mix: the band gap, visible on the figurine.
- **The LED threshold makes the addressing clean.** Below about 0.2 A, the familiar on
  the other frequency is completely dark, not dim.
  - The asymmetry: a familiar tuned **below** the drive frequency sees its tank voltage
    shrink, so it stays dark at any current.
  - One tuned **above** it sees the EMF almost undivided, so the drive to the
    lower-frequency familiar must stay under about 0.2 A.
- **Limit the LEDs' current with resistors.** At 0.3-0.4 A of drive the orange LED
  would take 56-78 mA. A series resistor in each LED leg, sized for 20 mA at full
  drive, keeps a firmware bug from burning a familiar. The firmware's ramp then runs
  0.1 → 0.2 A for a fade from dark to orange to orange-and-violet.
- **Series resistors alone cannot protect a high-Q familiar** (`familiar_resistors.py`).
  At 150 kHz, 68 Ω per LED gives 12.6/7.5 mA at 0.2 A of drive and 31/24 mA at a 0.4 A
  fault. At 330 kHz even 100 Ω leaves 63/57 mA at 0.4 A: the parallel tank simply rings
  up higher until the current flows.
  - **So the limit comes from physics on the drive side:** the familiar bridge runs from
    **5 V**, not 12 V. Its fundamental is then 4/π × 5 = 6.4 V, and the perch coil's own
    reactance caps the current at 6.4/27 = 0.24 A at 150 kHz and 6.4/59 = 0.11 A at
    330 kHz.
  - With 68 Ω per LED (one value for both familiars), the owl stays near 15/9 mA and the
    cat near 16/11 mA at the most any firmware can ask for.
- **The bridge must switch at up to ~330 kHz.** Driven directly (no tuning capacitor
  on the perch, so any frequency works), the perch coil is 27 Ω at 150 kHz and 59 Ω at
  330 kHz. 0.2 A at 330 kHz needs 11.8 V amplitude, which a 12 V full bridge's 15.3 V
  fundamental covers.

### 2. Levitation with the coil alone (`coil_forces.py`)

Lifting a 10×3 mm N52 disc plus a 3 g bat (4.8 g) under the coil, without iron:

| gap | force per amp | current to hold | coil power 1 oz / 2 oz |
|---:|---:|---:|---:|
| 2 mm | 102 mN/A | 0.46 A | 0.7 W / 0.3 W |
| 5 mm | 56 mN/A | 0.83 A | 2.3 W / 1.2 W |
| 8 mm | 32 mN/A | 1.45 A | 7.1 W / 3.5 W |
| 12 mm | 16 mN/A | 2.89 A | 28 W / 14 W |

**Verdict: carrying the weight with the coil cooks it** beyond about 5 mm. Hence
§3's bias magnet.

### 3. Zero-power suspension of a PCB bat (`levitation.py`)

The bat is a 0.8 mm PCB (with its own receive coil and LED eyes) plus a 10×2 mm N52
disc: 2.7 g. A tiny bias magnet above the perch carries the weight; the coil only
stabilises.

| bias magnet | bat hangs at | negative stiffness | coil grip | lateral stiffness | Hall sees | gap sensitivity | current per 0.5 mm (15 Hz loop) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2×1 mm, 1 mm up | 5.4 mm | 8.7 N/m | 38 mN/A | +4.1 N/m | −95 mT | 24 mT/mm | 0.43 A |
| 3×1 mm, 3 mm up | 6.2 mm | 7.0 N/m | 33 mN/A | +3.5 N/m | −73 mT | 19 mT/mm | 0.47 A |
| **4×1 mm, 3 mm up** | **8.4 mm** | **6.6 N/m** | **22 mN/A** | **+3.2 N/m** | **−49 mT** | **9.1 mT/mm** | **0.70 A** |
| 5×1 mm, 4 mm up | 9.3 mm | 5.7 N/m | 19 mN/A | +2.9 N/m | −41 mT | 6.9 mT/mm | 0.80 A |

(Bigger bias magnets, 6-20 mm, put the bat 17-26 mm down, where the coil has only
1.6-5 mN/A of grip: amperes to stabilise. Small is right.)

- **Laterally stable.** Earnshaw's instability is only vertical, which one coil and
  one Hall sensor control.
- **Zero power.** With an integrator on the coil current, the loop settles at the gap
  where the bias alone holds the bat: the mean current is near zero whatever the bat
  weighs, and only disturbances cost current.
- **Sensing.** The Hall sensor's 9 mT per mm gives micrometre resolution. The coil adds
  3.7 mT/A at the sensor; the firmware subtracts it.
- **The same coil can light the bat.** An H-bridge switching at about 150 kHz leaves a
  triangular ripple of a few hundred mA in the coil, whose fundamental is a ready-made
  wireless-power carrier for the bat's receive tank. Levitation uses the coil's mean
  current, the bat's eyes its ripple.
- **Cost of that:** eddy currents in the bat's own magnet. About 0.1 W for a 10×2 mm
  disc, scaling as radius⁴, so 12 mW for a 6×2 mm one. Choose the smaller magnet or a
  lighter bat.

**Verdict: plausible.** The hardware is simple; the risk is in tuning, and that is
firmware, which can be finished while the boards are in the post.

### 3b. The levitating bat, closed loop (`levitation_loop.py`)

**Superseded (review of 2026-10-09).** This script and the table below are the earlier
two-magnet design: a 2.7 g bat, a 4 x 1 mm bias magnet 3 mm up, the canonical four-layer
coil (31.5 uH, 3.35 ohm), a 25 mV/mT sensor and an ideal +-12 V source. The boards as
drawn are the one-magnet design of 3a (3.6 g, 10 x 2 mm at 14 mm, the three-layer coil,
the DRV5055A4 at 7.5 mV/mT), whose closed loop is validated by the firmware's host test
(`firmware/test/test_lev.c` against `lev_plant.h`, written by
`firmware/tools/gen_lev_tables.py` from the same field computations). Neither models the
DRV8874: its PWM ripple (1 A peak to peak at 100 kHz on 30 uH) and its 3.3 A chopper are
why `LEV_I_MAX_A` is 2.6 A. Porting this script to the one-magnet plant with the driver
in it is on the list (`PLAN.md` section 10).

The vertical axis, simulated in time with nothing linearised:
- **Plant:** the bias attraction and the coil's force per amp, both from the field
  computations as functions of the gap; the coil's L and R; the bridge's ±12 V limit.
- **Sensor:** the Hall sensor sampled at 10 kHz, with 0.08 mT rms of noise and 12-bit
  quantisation. The firmware subtracts the coil's own field (using the measured
  current) and inverts a calibration table.
- **Controller:** a PID, with the derivative low-passed, plus a slow loop that moves the
  set-point until the mean coil current is zero.
- **Test:** the bat is released 1 mm low, then tapped (5 mN for 20 ms) at 1.5 s.

```sh
python3 levitation_loop.py --sweep      # tuning
python3 levitation_loop.py --catch      # how far from the float point it can be let go
```

| loop bandwidth / derivative filter / ADC averaging | holds | peak current | steady rms current | coil heat | jitter |
|---|---|---:|---:|---:|---:|
| 25 Hz / 400 Hz / 1 | yes | 3.6 A | 640 mA | 1.4 W | 1.1 µm |
| 12 Hz / 100 Hz / 4 | yes | 1.0 A | 40 mA | 5 mW | 0.5 µm |
| **10 Hz / 80 Hz / 8** | **yes** | **0.8 A** | **20 mA** | **1 mW** | **0.4 µm** |
| 8 Hz / 60 Hz / 8 | yes | 0.6 A | 12 mA | ~0 | 0.4 µm |

With the 10 Hz loop, released 2 mm off the float point it is caught with a 1.6 A peak,
3 mm off with 2.4 A, and 4 mm low with 3.2 A (the bridge's 12 V / 3.35 Ω limit is
3.6 A).

- **The first tuning is too hot.** Sensor noise through a wide derivative makes 0.6 A
  of chatter. Averaging eight ADC samples and a 10 Hz loop cut it to 20 mA.
- **Zero power is real.** The mean coil current settles at about 1 mA, and the bat
  hangs where the bias magnet alone holds it.
- **Design consequences:**
  - the perch's bridge must allow about 3.5 A peaks;
  - a printed cradle under the perch should guide the bat into the ±3 mm catch zone;
  - the ADC should oversample the Hall sensor.
- **Not simulated:** the lateral and tilt modes. Their stiffness is positive, but
  lightly damped: about a 5 Hz sway that only air damps.

### 4. Pendulum kicks (`coil_forces.py`)

A 15 cm thread, an 8 g bat with a 10×3 mm disc, 35 mm amplitude: 320 µJ of swing
energy, losing 20-200 µJ per cycle to air (Q 100 to 10).

| bat's height over the coil | peak sideways force | best work per pass at 1 A |
|---:|---:|---:|
| 5 mm | 29 mN/A | 734 µJ |
| 10 mm | 11 mN/A | 329 µJ |
| 15 mm | 4.9 mN/A | 166 µJ |
| 20 mm | 2.4 mN/A | 90 µJ |

**Verdict: easy.** Pulses of 0.1-0.3 A keep it flying.

**Sensing it: use a Hall sensor, not the coil.** By reciprocity, the EMF a moving magnet
induces in a coil is the coil's force per amp times the speed. At 10 mm that is
11.4 mN/A × 0.28 m/s ≈ **3 mV**: about four counts of the RP2350's ADC. Classic
pendulum kickers get away with it because their coils have ~1500 turns; ours has 48.
So a 3-axis Hall sensor under the swing (several mT from the bat's magnet) times the
kicks, and the coils' back-EMF is a bonus measurement through an amplifier, a nice
demonstration of Faraday's law.

### 5. Sliding and rolling (`coil_forces.py`)

- **A 10×3 mm disc lying on a 1 mm cover:** up to 68 mN/A sideways, against 10 mN of
  sliding friction for a 4 g puck (μ 0.25). The coil also tips it, with 0.28 mN·m/A
  against 0.39 mN·m of righting moment, so keep it under about 0.5 A, or put the puck
  in a groove.
- **A 10 mm magnet sphere** (in a 3D-printed ball), axis horizontal: 160-650 µN·m/A of
  torque against 8-18 µN·m of rolling resistance. **Tens of milliamps roll it.**
