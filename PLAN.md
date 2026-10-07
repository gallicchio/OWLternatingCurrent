# The Halloween board: the plan

A cute (not scary) Halloween board for Jason's six-year-old witch, which is also a
genuinely interesting piece of engineering and physics: owls, bats, a little witch on
her broom across a gold moon, orange and purple light that never blinks, and magnets
and coils doing things that look like magic.

This file is the plan and the state of the work. It is kept current so that a new
session can pick it up. The lessons it follows are in `CLAUDE_PCB.md` in Jason's private OpticsPCBs
repository (a public snapshot goes into this repository when it is published). The conversation is
in `CLAUDE_CODE_CHAT.md`.

**Status (2026-10-07):** ideas surveyed and the physics checked (`sim/physics/`); a
recommendation is waiting for Jason's choice. Nothing is drawn in KiCad yet.

## 0. The calendar is the hardest constraint

Halloween is **Saturday 2026-10-31**, 24 days away (`research/web_research.md` §1c
has the sources):
- Build: a 4-layer board takes 2-5 days (24 h is free with assembly, if offered for
  4 layers), Standard PCBA at least 4 more, and JLCPCB is just back from its October
  holiday.
- Post: UPS Express Saver (DDP) takes 4-5 business days to California; DHL and FedEx
  Express now go only to corporate accounts.
- **Order by Monday 10-12 to Wednesday 10-14**, with only in-stock parts (globally
  sourced parts add 9-15 days). Ordering on 10-19 or 10-20 is a gamble that needs
  paid expediting and no engineering holds.

That leaves **about five to seven days of design**: schematic, layout, art, release,
and the first firmware.

Purple solder mask on a 4-layer assembled board means JLCPCB's Standard PCBA, whose
smallest board is 70 × 70 mm. So the small boards (perch, bat, familiar coins) ride on
the base board's panel as break-away tabs: one design, one order.

So rev A must be built from things that are nearly certain to work. Anything risky
goes on the board as an *option* (a port, a DNP footprint, a firmware feature) so
that failing costs nothing but time after Halloween. Firmware beyond bring-up is
written while the boards are in the post.

## 1. The ideas

Scales:
- **Difficulty:** 1 (an evening) to 5 (research).
- **Cost:** the added parts per board, beyond the base board's MCU, power and LEDs.
- **Works first time:** the chance that it works on rev A without a respin, given
  reasonable care (firmware may still need tuning on the bench).
- **Cute** and **physics:** 1-5.

### 1A. Light and colour

| # | idea | the physics | diff. | cost | works first time | cute | physics |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| A1 | **The light show:** ~40-70 orange and purple LEDs on constant-current drivers with 12-16-bit PWM far above 100 Hz; perceptual (CIE L*) fades; scenes from dusk to dawn | vision (why linear fades look wrong); band gaps: orange 2.0 eV, violet 3.1 eV | 2 | $3-6 | 95 % | 5 | 2 |
| A2 | **The quantum ghost:** a wave packet evolved by the Schrödinger equation along a row of LEDs (brightness = \|ψ\|²) walks into a wall and partly tunnels through it | quantum tunnelling: ghosts walk through walls, and so do electrons | 2 | $0 | 95 % | 4 | 5 |
| A3 | **Glow-in-the-dark familiars:** violet LEDs charge figurines printed in glow PLA; they glow on after the lights fade | phosphorescence (trapped electrons in SrAl₂O₄:Eu,Dy); power-law, not exponential, decay | 1 | $0.5 + filament | 95 % | 5 | 4 |
| A4 | Secret messages in invisible (UV-marker) ink, or tonic water, revealed by violet light | fluorescence; Stokes shift | 1 | $0 | 95 % | 4 | 3 |
| A5 | **LEDs that see:** a reverse-biased LED is a photodiode for photons above its band gap. An orange LED sees violet light; a violet LED is blind to orange | photoelectric effect, band gaps | 2 | $0 | 80 % | 3 | 5 |
| A6 | Back-lit board art: light through copper-free windows in the FR4 itself; ENIG-gold moon | optics of FR4 | 2 | $0 | 90 % | 4 | 2 |
| A7 | Edge-lit engraved acrylic witch or owl standing in a slot | total internal reflection | 2 | $3-5 | 90 % | 4 | 3 |
| A8 | Pepper's ghost: a 45° clear sheet in a printed haunted house makes an LED ghost float inside | partial reflection (the Haunted Mansion's trick) | 2 | $2 | 90 % | 4 | 3 |
| A9 | A diffraction-grating window to see each LED's spectrum | diffraction; line widths | 1 | $1 | 95 % | 3 | 4 |
| A10 | Neon (orange) and argon (violet) glow lamps | atomic line spectra | 3 | $3 | 70 % | 3 | 5 |

A10 needs about 90 V: no, on a child's board.

### 1B. Sensing and motion

| # | idea | the physics | diff. | cost | works first time | cute | physics |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| B1 | **Accelerometer:** tap to wake; tilt the board and glowing will-o'-wisps roll downhill; footsteps in the room wake the owls | gravity, a particle simulation; floor vibration | 2 | $1 | 95 % | 5 | 3 |
| B2 | **Owls wake at dusk** (ambient-light sensor) and sleep when the lights come on | nocturnal owls; photometry | 1 | $0.5 | 95 % | 5 | 2 |
| B3 | Owl eyes that follow you: multi-zone laser time-of-flight (8×8 zones) | photon time of flight: 1 ns = 15 cm | 3 | $5-8 | 80 % | 5 | 4 |
| B4 | An echolocating bat: 40 kHz chirps, two "ears" find direction from the arrival-time difference | sonar, speed of sound, interaural time difference (≤ 90 µs) | 3 | $2-3 | 80 % | 5 | 5 |
| B5 | Theremin ghost: your hand's capacitance detunes an oscillator; the ghost's "woo-oo" and its light follow your hand | capacitance; heterodyning | 2-3 | $2 + speaker | 85 % | 4 | 4 |
| B6 | The witch's wand: a magnet-tipped printed wand, located by 3-axis magnetometers; gestures cast spells | dipole fields, an inverse problem | 3 | $3-6 | 80 % (tracking quality 60 %) | 5 | 4 |
| B7 | **Firefly synchrony:** the jack-o'-lanterns pulse out of step, then pull into step (and between boards, by light) | coupled oscillators (Kuramoto; Mirollo-Strogatz) | 2 | $0.5 | 90 % | 4 | 5 |
| B8 | Hoot back: the owl hears "hoo-hoo" and answers | pitch detection | 3 | $2 + speaker | 75 % | 5 | 3 |
| B9 | Ghost detector: the 60 Hz electric field of the house wiring, and the microwave oven's 2.45 GHz | capacitive pickup; RF | 2 | $1 | 85 % | 5 | 4 |
| B10 | The owl oracle: yes/no answers from the avalanche noise of a reverse-biased junction | true (quantum) randomness | 2 | $0.5 | 85 % | 4 | 4 |
| B11 | The real moon: the gold moon shows tonight's phase (on Halloween 2026 a waning gibbous, about 65 % lit, six days after the full moon of the evening of 10-25 in California) | orbital mechanics (Meeus) | 2 | $0.5 | 95 % | 3 | 3 |

### 1C. Coils and magnets (PCB "motors")

The numbers behind these are in `sim/physics/README.md`.

| # | idea | the physics | diff. | cost | works first time | cute | physics |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| C1 | **Wireless familiars:** an owl and a cat (printed) light up when set on their "magic circle" perches: no battery and no chip inside, just a coil, a capacitor and LEDs. Each is tuned to its own frequency, so the board lights each one separately and can tell which one is sitting where | Faraday induction, resonance, coupling; frequency-division addressing; reflected impedance | 3 | $1.5 per familiar + print | 90 % | 5 | 5 |
| C2 | **The bat that never stops flying:** a magnet bat on a thread, kept swinging by pulses from coils under it, timed by a 3-axis Hall sensor under the swing (the coils' own back-EMF, only ~3 mV with 48 turns, is a bonus measurement through an amplifier). It circles the moon (a rotating field), or wanders chaotically between three pumpkins | driven pendulum; Faraday's law (reciprocity: EMF = force per amp × velocity); chaos with fractal basins | 3 | $2 + printed arch | 90 % | 5 | 5 |
| C3 | **The levitating bat:** a small PCB bat floats 8 mm under a "perch" board with no visible support, eyes lit by induction. A tiny bias magnet carries its weight; a PCB coil and a Hall sensor hold it there; the coil's mean current is about zero; the H-bridge's PWM ripple lights its eyes | Earnshaw's theorem and feedback; zero-power suspension; induction. Closed-loop simulation: holds with 20 mA rms and ~1 mW in the coil, catches the bat from ±3 mm (`sim/physics/` §3b) | 4-5 | $5 + perch PCB + prints | 65 % | 5 | 5 |
| C4 | A rolling pumpkin: a magnet sphere in a printed pumpkin rolls round a coil track | torque on a dipole; rolling | 3 | $3 | 75 % | 5 | 4 |
| C5 | A sliding bat puck: a 3-phase PCB linear motor ring round the moon | Lorentz force; synchronous motors | 3-4 | $3-5 | 65 % | 4 | 4 |
| C6 | A carousel: a PCB axial-flux motor spins a printed rotor of bats round a tower | BLDC commutation, back-EMF | 3 | $3 + bearing | 85 % | 4 | 4 |
| C7 | An everlasting spinning top, kicked by a coil | gyroscopes; induction | 3 | $1 | 80 % | 4 | 4 |
| C8 | A ferrofluid potion that dances (needs tens of mT: a magnet moved by C6, not PCB coils) | magnetic fluids, the Rosensweig instability | 4 | $15 | 50 % | 4 | 5 |
| C9 | A floating graphite ghost: pyrolytic graphite levitates, unpowered, about 1 mm over a magnet checkerboard (pushing it with light needs 0.3-2 W lasers; a 2012 result was mostly the laser's fan) | diamagnetism, the loophole in Earnshaw | 2 / 5 | $20-30 | 95 % / 5 % | 3 | 5 |
| C10 | Magnetic viewing film over the coils | field lines | 1 | $10 | 95 % | 2 | 3 |
| C11 | A shake-to-charge wand: a magnet sliding through a coil charges a supercapacitor that lights the tip | Faraday's law; energy storage | 3 | $3 | 75 % | 4 | 4 |
| C12 | Lenz's slow ghost: a magnet ghost drifts down a copper tube; pickup coils time its fall | eddy currents, terminal velocity | 2 | $5-10 | 90 % | 4 | 5 |

Not worth it: carrying a bat's whole weight with a PCB coil and no iron. At a 5 mm
gap that takes 0.8 A and 2.3 W; at 8 mm, 1.5 A and 7 W.

### 1D. Radio

| # | idea | the physics | diff. | cost | works first time | cute | physics |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| D1 | **A bat-wing 2.4 GHz antenna** on an ESP32, simulated in openEMS (`sim/antenna/`): the wings are a dipole; a 46 mm span has S11 below −17 dB across the whole band (preliminary; it needs a balun). A phone "spell book" page; the time for the moon phase | antennas, resonance, radiation | 4 | $3-4 | 75 % | 3 | 5 |
| D2 | "Entangled pumpkins": two boards linked (ESP-NOW, or by light); touch one and the other answers | (networking) | 2-3 | $0-2 | 85 % | 4 | 2 |
| D3 | Data over the familiar link: amplitude modulation down, load modulation back, like Qi and NFC (needs a tiny MCU in each familiar) | near-field communication | 4 | $0.5 + programming | 70 % | 3 | 4 |
| D4 | A bat detector: an ultrasonic microphone heterodyned down to audible | heterodyning; real bats' calls | 3 | $2 + speaker | 75 % | 4 | 5 |

### 1E. Heat and other

| # | idea | the physics | diff. | cost | works first time | cute | physics |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| E1 | A secret ghost: a heater trace under 31 °C thermochromic paint makes a hidden ghost appear | Joule heating, thermal diffusion | 2 | $5 | 85 % | 4 | 4 |
| E2 | A cloud chamber showing cosmic-ray "ghost trails" | muons, supersaturation | 5 | $40+ | 30 % | 3 | 5 |
| E3 | A persistence-of-vision wand that draws a ghost in the air | vision | 3 | $3 + motor | 75 % | 4 | 3 |
| E4 | A strobed "time fountain" of water drops | stroboscopy | 4 | pump | 60 % | 4 | 4 |

E2 is not for a child's room; E4 strobes, which this board does not do.

## 2. Rev A: what is being built (Jason's choices, Prompt 2, 2026-10-07)

**Name: OWLternating Current.** Jason's daughter wants to be an owl for Halloween. The
capital OWL reads at a glance, and keeps the pun whole where a hyphen would break it.
Repository: `github.com/gallicchio/OWLternatingCurrent`.

**Features:**
- **C1, wireless familiars:** an owl and a cat, as flat PCB tokens that light on their
  perches.
- **C2, the pendulum bat.**
- **C3, the levitating bat.**
- **B5, the theremin,** with a physical sound switch.
- **Film mode** for her magnetic viewing film: firmware only.
- **The light show:** A1, A2, B7, with B1 and B2.

**Guiding rule (Prompt 2):** minimise what Jason must do beyond uploading the JLCPCB
order.
- Everything electronic is made and assembled by JLCPCB, as one panel with break-away
  boards.
- The tree and perch **plug together**; there is no wiring and no soldering.
- **One kind of magnet**, one print plate, no glue.

### What Jason does after the JLCPCB order (the whole list)

1. Buy two things: a 12 V, 5 A barrel-jack adapter, and one pack of 10 × 2 mm N52
   disc magnets (`ORDER_LIST.md`).
2. Print one plate in PLA, with two pauses: the bat's cap and the perch owl, each of
   which takes one magnet at its pause, plus four feet. "Take the top two magnets off
   the stack without turning them over, one into each pocket" sets the polarity.
3. When the boards arrive, snap off the break-away boards.
4. Assemble:
   - snap the four feet into the base;
   - plug the tree into the base, and the perch onto the tree;
   - snap the owl onto the perch, and the cap onto the bat.
5. Plug in the 12 V adapter.

Steps 1 and 2 can happen while the boards are in the post. Step 4 needs both 2 and 3.

### The boards (one 4-layer panel: purple mask, ENIG, 1 oz outer and inner copper)

| board | size | what is on it |
|---|---|---|
| **Base** | ~170 × 120 mm | MCU, power, LED driver #1, sensors, 4 DRV8874 coil bridges, 4 UCC27524 perch drivers, theremin oscillators, audio, the art (gold moon with the witch, pumpkins, stars), two familiar perches, three pendulum coils, the tree socket |
| **Tree** | ~75 × 110 mm, tree-shaped | stands in the base's 2 × 8 socket (right-angle header and two tabs); LED driver #2; owls with orange LED eyes; carries the perch coil's current and the Hall signal to the perch |
| **Perch** | ~28 × 55 mm | plugs onto the tree's top header (socket on its underside); the levitation coil; a DRV5055 Hall sensor at the coil's centre on the underside; two violet LEDs shining down on the bat; holes for the owl (bias magnet) |
| **Bat** | ~48 × 26 mm, bat-shaped | its 4-layer receive coil round the magnet; a C0G tuning capacitor; two orange side-view LED eyes looking forward; three holes for the cap that holds its magnet |
| **Owl token, cat token** | ~38 mm | coil, C0G tank capacitor, an orange and a violet LED, 150 Ω each; the owl tuned to 150 kHz, the cat to 330 kHz |

### The physics, as designed (`sim/physics/`)

- **Levitation with one magnet size** (`levitation_onemagnet.py`):
  - the bias magnet (10 × 2 mm, in the owl, 14 mm above the perch's top copper) holds
    the 3.6 g bat 8.5 mm below the perch;
  - vertically it needs control (k_neg 4.8 N/m against the coil's 21 mN/A); sideways it
    is stable (+2.5 N/m);
  - the Hall sensor sees ~40 mT, 8.7 mT per mm of gap.
- **The bat's eyes** (`bat_power.py`): the perch's DRV8874 adds a 90 kHz carrier
  (0.43 A from 12 V); the bat's 44-turn coil and a 70 nF C0G tank light two side-view
  orange LEDs at ~9 mA each. Eddy heating of the bat's magnet is 4-10 mW.
- **The familiar tokens:** lying flat on the perch (k 0.74), at the 5 V drive's hard
  cap, they reach 15-23 mA through 150 Ω. Below 0.2 A the other token stays dark.
- **The pendulum:** 0.1-0.3 A pulses; a TMAG5273 under the swing times them.

### Coil drivers (from the datasheets, 2026-10-07)

| coils | job | driver | why |
|---|---|---|---|
| 3 pendulum coils, the levitation perch | pulses to ~2 A; levitation catches to 3.5 A; mean ~0 | **DRV8874** (one per coil) | 4.5-37 V, 6 A peak, built-in current sense (IPROPI) so no shunt, PWM to 100 kHz, 150 ns edges |
| 2 familiar perches | 0.1-0.24 A of AC at 150 and 330 kHz into 27-59 Ω | **a dual low-side gate driver (UCC27524 class) used as a full bridge, from 5 V**, so the coil's own reactance caps the current where no firmware can overdrive a familiar's LEDs (`sim/physics/familiar_resistors.py`) | integrated H-bridges stop at 100-200 kHz (DRV8874 100 kHz, DRV8316 200 kHz), and a cheap bridge has been seen delivering 56 mA at 260 kHz against 360 mA at 5 kHz; a gate driver has ~15 ns edges and 5 A peaks, and is happy at hundreds of kHz into a coil |

### Key parts (JLCPCB stock queried 2026-10-07, 11:17-11:24; `research/jlc_parts_survey.md`)

None of these is a Basic part; each distinct Extended part costs about $3 to set up.

| job | part | LCSC | stock | $ each | why |
|---|---|---|--:|--:|---|
| MCU | RP2354A | C41378174 | 16,231 | 1.20 | 2 MB flash inside; GPiBridge's layout |
| its crystal and inductor | ABM8-272-T3, AOTA-B201610S3R3-101-T | C20625731, C42411119 | 10,462, **667** | 0.40, 0.22 | Raspberry Pi's own parts; watch the inductor's stock |
| LED drivers | **LP5036** ×2 | C701961 | 16,987 | 0.80 | 36 channels each, 12-bit PWM at 29 kHz, log dimming curve, 35 mA |
| pumpkin orange (eyes, small glows) | XL-1608UOC-06, 0603, 600-610 nm | C965800 | 398,998 | 0.007 | |
| bright orange (pumpkin faces) | HL-AF-5060S22OC, 5050, three dice | C516304 | 19,781 | 0.03 | |
| violet (stars; charges glow PLA) | HL-A-3528S7VC-S1-13HL, 400-410 nm | C516136 | 68,094 | 0.04 | 405 nm rather than 395 for the eyes' sake |
| visible purple | GL0603PU01, 0603 phosphor purple | C51933300 | 18,511 | 0.01 | |
| pendulum and levitation bridges | DRV8874 ×4 | C1855818 | 28,928 | 0.66 | |
| familiar perch bridges | **UCC27524DR** ×2 (second source SLM27524, C2921387) | C465729 | 61,758 | | dual 5 A, 7-9 ns |
| magnet tracking | TMAG5273A2 (3-axis Hall, ±266 mT) | C3715882 | 18,024 | 0.35 | under the pendulum's swing |
| levitation sensor | DRV5055A4 (linear Hall) | C266123 | | | analog, for the 10 kHz loop |
| motion, light | LSM6DS3TR-C (or LIS2DW12); LTR-303ALS-01 | C967633; C364577 | 29,432; | | |
| 12 V input | DC-005-5A-2.0 jack; TPS259474L eFuse; SMBJ15A (Preferred: no setup fee); 470 µF/35 V polymer | C381116; C2864845; C19077569; C46550472 | 30.5k; 3,772; 7,969; 74.8k | | |
| 12 → 5 V, 5 → 3.3 V | TPS54302 (3 A); TLV62569 | C311983; C141836 | 78,316; 243,695 | 0.23; | |
| familiar tanks | C0G 100 nF 1206 (Murata GRM31C5C1H104JA01L) | C97946 | | | |

## 3. The light show (sequencing)

No LED ever switches abruptly. Every change is a fade of at least 300 ms, computed at
about 200 frames/s and shown through PWM at tens of kHz, so neither eyes nor phone
cameras see flicker. Brightness is mapped through CIE L*, so a fade looks even to the
eye.

| scene | when | what happens |
|---|---|---|
| asleep | room lights on (light sensor) | pumpkins breathe very slowly and dimly; everything else is dark |
| dusk | the room goes dark, or a tap | violet stars fade in one by one over 30 s; the pumpkins warm up; the owls' eyes open slowly |
| night | then | pumpkins glow like candles (smooth 1/f "flame" noise, never a blink); stars scintillate gently (slow turbulence noise); owls look left and right (light moving between eyes); purple will-o'-wisps drift, and roll downhill when the board is tilted |
| firefly synchrony | every few minutes | the jack-o'-lanterns pulse out of step, then pull into step over a minute (Kuramoto coupling), hold, and drift apart |
| quantum ghost | a double tap | a purple wave packet runs along the stars, meets the "wall" and partly tunnels through, partly reflects |
| a familiar arrives | a figurine set on a perch | the perch finds its resonance, then its eyes fade up in the board's colours |
| dawn | the room lights come on | the reverse of dusk; the owls close their eyes and go to sleep |

## 4. Power and copper

**Budget:**
- LEDs: about 2-3 W at full brightness.
- Coils: pulses of up to 1-2 A each, with a low average:
  - the pendulum needs 0.1-0.3 A in pulses;
  - a familiar 0.1-0.24 A at 150-330 kHz, from 5 V;
  - the levitation about 20 mA rms steady (1 mW), with 1.6-2.4 A peaks while it
    catches the bat.
- Logic: about 0.5 W.
- **Total:** typically 5 W; the worst case about 15 W.

**Supply:** a common **12 V, 3-5 A** barrel-jack brick (5.5 × 2.1 mm, centre
positive, UL-listed). 15 V or more would not help: nothing on the board wants a higher
voltage, and every converter would only waste more.

**Input protection:** reverse polarity, a fuse, a TVS, and a bulk electrolytic that
damps hot-plug ringing (CLAUDE_PCB.md §15).

**Copper:**
- **1 oz outer is enough** for the power paths: at 3 A a 1.4 mm track rises 10 °C,
  and the 12 V and ground run in pours.
- **Ask for 1 oz inner** (JLCPCB's default is 0.5 oz) if it costs little. It halves
  the resistance of the coils' inner layers, taking the canonical coil from 3.35 Ω to
  2.2 Ω: a third less heat for the same current.
- 2 oz outer would halve it again. It is not required at these currents, and it
  costs extra and coarsens the fab's minimum track and gap.

## 5. The work, in order

Status: `[ ]` to do, `[~]` under way, `[x]` done.

1. [x] Repository, `.gitignore` (references, datasheets, caches), this plan, the chat.
2. [x] Hans Rosenberg's checklist and fast-digital, RF, power and child-safety
   sections folded into OpticsPCBs' `CLAUDE_PCB.md`.
3. [x] Physics feasibility (`sim/physics/`): coils, wireless power, pendulum,
   levitation, sliding and rolling.
4. [x] Parts survey with JLCPCB stock (`research/jlc_parts_survey.md`); 81 datasheets
   in `datasheets/` (ignored by git), every chosen part's among them.
5. [~] Antenna feasibility (`sim/antenna/`, running). [x] Prior art, names, fab facts,
   safety (`research/web_research.md`).
6. [ ] **Jason chooses** the features and the name.
7. [ ] Tooling from GPiBridge, copied in so the project stands alone: the schematic
   writer, JLCPCB API, footprint and rotation checks, release.
8. [ ] Art: the characters (`art/shapes.py`) to KiCad silkscreen, mask and gold;
   coils as generated footprints.
9. [ ] Schematics, ERC; pins checked against datasheet figures.
10. [ ] Base board: floorplan, placement, routing, zones, DRC; perch, bat and familiar
    boards.
11. [ ] 3D prints: tree, perch cap, bat body, owl and cat figurines (FreeCAD or
    OpenSCAD).
12. [ ] Firmware v0.1: power-up, LEDs, sensors, coil drive, USB console; host tests.
13. [ ] JLCPCB release, cost estimate, `PLACEMENT_CHECKS.txt`; order by 10-14 or
    10-16.
14. [ ] Firmware while the boards are in the post: scenes, familiars, pendulum,
    levitation.
15. [ ] Bring-up (`HANDBOOK.md`).

## 6. The name

Checked on 2026-10-07 (GitHub, the web, Trademarkia; `research/web_research.md` §3). A
quick look, not a legal clearance.

| name | the joke | verdict |
|---|---|---|
| **Hocus Flux** (my pick) | hocus-pocus + magnetic flux (Φ in Faraday's law, which powers everything here) + solder flux | no project, product or mark found; "Flux" is also an AI PCB-design company (flux.ai), which an AI-designed board can wear as a wink |
| **Owlternating Current** | owls + the AC that lights the familiars | zero hits anywhere: the most unique, if the longest |
| **Faraday's Familiars** | a witch's familiars, powered by Faraday's law | free as a phrase; bare "Familiar" is a pending robot-pet trademark (Familiar Machines & Magic, 2026), so keep the "Faraday's" |
| Maxwell's Witch | Maxwell's demon, made cute | free |
| Hoot Induction, Jack-o'-Lenz, Lenz Lantern | puns on induction and Lenz's law | free |
| Spooky Action (at a Distance) | Einstein's phrase; everything here acts at a distance | crowded: 21 repositories, nearby marks (ACTION AT A DISTANCE, SPOOKY2) |

The repository would be `github.com/gallicchio/hocus-flux` (or the chosen name); none of
`halloween1`, `halloween2026` or `halloween` exists there yet.

## 7. Safety, for a six-year-old (`CLAUDE_PCB.md` §16)

- **Magnets:**
  - Under ASTM F963, every neodymium magnet here is a "hazardous magnet", even a 2 × 1
    mm disc (flux index about 81 against a limit of 50).
  - Each must be captive in a part too big to swallow. It must stay in after soaking,
    drops, 4 in·lbf of torque, a 15 lbf pull and a 30 lbf squeeze (the tests for ages
    3-8).
  - So every magnet is printed in (pause the print, drop the magnet in, print over it),
    never glued into an open pocket. That includes the bat's, the bias magnet in the
    perch cap, and any pendulum or rolling magnet.
- **Violet light:** 405 nm, not 395 nm. 395 nm looks dim, so the blink reflex does not
  protect the eye. Use low current and diffuse the LEDs. IEC 62471's limits are measured
  at 200 mm; a child at 2 cm gets about 100 times the exposure.
- **Heat:** every coil's duty is limited in firmware, with a temperature sensor beside
  the coils, so nothing a hand can reach passes about 45 °C.
- **Power:** a UL-listed 12 V adapter, a fuse on the board, rounded corners, and ENIG
  (lead-free).

## 8. Precedents (`research/web_research.md` §2)

- **North Pole Circuit** (Janky Jingle Crew, 2024): a Christmas card that drives a
  magnet sleigh along PCB traces. It is the nearest "holiday PCB with real physics",
  and the one to beat. It used 4 layers, 1 oz inner copper, 2 × 1 mm magnets, about
  500 mA at 5 V and DRV8833 drivers, and was assembled by JLCPCB.
- **Gauss Speedway** (Jeff McBride, 2022): its ancestor; phases about 5 Ω.
- **Carl Bugeja's PCB motors**, and **Kevin Lynagh's** PCB stepper notes. Lynagh's
  cheap bridge delivered 56 mA at 260 kHz against 360 mA at 5 kHz. Our familiar
  drive at 150-330 kHz therefore needs a bridge built for it.
- **Hall-sensor hanging levitation** kits: 1-3 cm gaps at about 80 mA from 12 V,
  with a narrow range of workable payloads; we avoid that problem with zero-power
  control. One DIY 80 kHz wireless-power add-on managed 1.3 % overall efficiency.
- **The "laser-pushed levitating graphite" of 2012** turned out, on replication,
  mostly to be the laser's cooling fan blowing on it: C9's light-driven version is
  out.

## 9. Open questions for Jason

- Which features (§2 is the recommendation)?
- The name (§6; my pick is Hocus Flux).
- Her name on the board? A line like "made for ___, Halloween 2026" on the back.
- Do you have a 3D printer here (a Bambu?), or should the prints go to JLC3DP with
  the boards?
