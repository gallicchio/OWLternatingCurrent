# OWLternating Current: design review package

For another reviewer (human or LLM) to check the design before it is ordered. It says
what the boards are, what every subsystem does and why, which numbers it rests on, what
has been checked and how, and what is still uncertain. Section 10 lists the questions we
most want a second opinion on. Paths are relative to the repository's root.

The repository is generated: nearly every file under `hardware/`, `mfg/release/`,
`firmware/src/board_pins.h` and `firmware/src/led_map.h` is written by a script in `gen/`,
`tools/` or `mfg/` (`build.py` runs them in order and stops at the first failing check).
A reviewer should read the generators, not only their output.

## 1. What it is

A Halloween display for a six-year-old who wants to be an owl: a purple, ENIG, 4-layer
board set that shows physics as magic.

| feature | what she sees | the physics |
|---|---|---|
| **Light show** | violet stars, orange pumpkins that flicker like candles, purple will-o'-wisps, owls whose eyes open at dusk | 49 LEDs on two LP5036s, every change a fade through CIE L*; dusk and dawn from a light sensor |
| **Wireless familiars** (C1) | put the owl token or the cat token on its perch and its eyes light; each perch lights only its own animal | resonant inductive power: each perch drives its coil at the token's tank frequency (owl 142 kHz, cat 303 kHz) and finds it by the drop in its own supply current |
| **The pendulum bat** (C2) | a bat on a thread that never stops swinging, or circles the moon | three coils under the swing give it timed kicks; a 3-axis Hall sensor under the rest point times them |
| **The levitating bat** (C3) | the bat floats in the air under the owl's perch | a magnet in the printed owl holds the bat's magnet up; a 10 kHz loop on a Hall sensor and the perch's coil keeps it from falling or jumping up (Earnshaw's theorem says it cannot float on magnets alone) |
| **Theremin** (B5) | move a hand toward the gold moon and a note rises; toward the gold ghost and it gets louder | two relaxation oscillators whose capacitance includes the hand; a speaker that a slide switch turns off |
| **The spell book** | the back of the base: the equations behind each trick, and her name | silkscreen |

Rev A is to be ordered from JLCPCB fully assembled (both sides, through-hole parts too):
Jason's own work is to print one plate of PLA (the owl, the bat's cap, four feet), drop
in two magnets at a pause, snap the boards apart, plug them together, and flash firmware
over USB-C. `ORDER_LIST.md` lists everything to buy.

## 2. The boards and how they connect

One 4-layer panel, 245.2 x 223.2 mm (inside JLCPCB's 250 x 250 mm for an assembled
panel), six boards joined by mouse-bite tabs (`gen/panel.py`):

| board | size | carries |
|---|---|---|
| **Base** | 190 x 130 mm | everything electronic: 12 V input, 4.8 V buck, the RP2354A, LED driver 1, the sensors, four DRV8874 coil bridges, two UCC27524 perch bridges, the theremin, the audio; on top the scene (moon, ghost, stars, pumpkins, wisps, the two familiar perches, three pendulum coils, the tree's socket) |
| **Tree** | 76 x 112 mm, tree-shaped | stands vertically in the base's 2x8 socket (J3) on a right-angle header (J101); LED driver 2 (U101) and the owls' eyes and stars; carries the levitation coil's current, the Hall signal, I2C and power up to the perch (J102) |
| **Perch** | 34 x 56 mm | horizontal, plugs onto the tree's top header with a socket underneath (J201); the levitation coil (3 layers), the DRV5055 Hall sensor in its hole, two downlights; the printed owl snaps over it |
| **Bat** | 47.8 x 25 mm | a 4-layer receive coil round its magnet, a C0G tank, two side-view LED eyes; no battery; the printed cap holds its magnet |
| **Owl token, cat token** | ~33 x 36 mm | a coil, a C0G tank capacitor, an orange and a purple LED with 150 ohm each |

Mechanically: the tree's bottom edge sits on the 8.5 mm socket, so its top edge is 120.5
mm above the base, and the perch's underside 129 mm (another 8.5 mm socket). The bat
floats about 8.5 mm under the perch's coil, 32 mm in front of the tree. As a pendulum it
hangs from a 1.2 mm hole at the perch's front on a thread, its magnet about 10 mm above
the base and 12 mm above the TMAG5273 under the base (pendulum length about 119 mm).

Connectors (`gen/connectors.py`): base J3 (socket) to tree J101 (header) carries HALL,
+3V3, SDA, +5V, SCL, ground (seven pins), and LEV_A and LEV_B on two pins each; tree J102
(header) to perch J201 (socket) the same, with the perch's two downlight channels in
place of I2C. Each board's supplies have their own net names (GND_T, +5V_T...): boards
meet only through mated connectors, and each sheet's PWR_FLAGs say so.

## 3. Power

- **Input:** 12 V, 3-5 A brick on a 5.5 x 2.1 mm barrel jack (J1, centre positive) ->
  F1 (5 A PTC, 2920) -> Q1 (AO4407A P-MOSFET, reverse-polarity protection; D1 a 10 V
  zener gate clamp, R1 100 k pull-down) -> **+12V**. D2 (SMBJ15A TVS) and C1 (470 uF 35 V
  polymer) on +12V. The jack's line runs straight down through F1 and Q1 into a 12 V pour
  under them (`gen/routes.py power_entry`).
- **4.8 V** (net +5V): TPS54302 buck (U1, 400 kHz) with a 10 uH FXL0630 inductor; feedback
  36 k / 5.1 k gives 0.596 V x 8.06 = 4.80 V; EN 100 k / 22 k from +12V turns it on above
  about 6.8 V. 4.8 V, not 5 V: the NS4150B audio amplifier's absolute maximum is 5.25 V.
  Loads: every LED anode, the UCC27524 perch bridges, the audio, the tree and perch.
- **VSYS -> 3.3 V:** VBUS (USB-C) and +5V meet at VSYS through two Schottky diodes (D4,
  D3, B5819W); an XC6206 LDO (U2, ceramic-stable) makes **+3V3** for the RP2354A, the LED
  drivers' logic, the sensors and the op-amp. The RP2354A's own switching regulator
  makes +1V1 (Raspberry Pi's minimal-design layout, copied from GPiBridge).
- **On USB alone** the RP2354A, the LED drivers' logic and the sensors run (it can be
  programmed with no adapter), but the LED anodes (+5V) are dark and the coils (+12V) off.
  The firmware reads VBUS, V5 and V12 through the mux and knows which.
- **Stack-up and planes** (JLC04161H-7628, 1.6 mm, 1 oz on all four layers): F.Cu the
  scene and its LEDs; In1 the 4.8 V plane (ground under the RP2354A's corner, where a few
  lines may run); In2 solid ground; B.Cu the electronics. Ground and 4.8 V reach their
  planes through a via at every pad; +12V and +3V3 are routed (+12V at 1.0 mm, 0.6 where
  pads are small, from a pour at the input); the planes are cleared under the coils and
  the antennas.

## 4. The RP2354A and its pins

- RP2354A (RP2350A with 2 MB flash in the package), 12 MHz crystal, USB-C, SWD and UART
  on JST-SH connectors (J4, J5), BOOT and SPELL buttons. The whole corner (decoupling,
  regulator, crystal, USB) is GPiBridge's layout, which is Raspberry Pi's, turned 90
  degrees (`gen/placement.py`, `gen/routes.py rpi_core`/`rpi_local`).
- **Which GPIO does what is chosen from the board** (`gen/assign.py`, `gen/assignment.json`):
  each line's destination is traced back to a ring round the chip, and the pins are
  bound in the order the lines arrive, within the function classes the firmware needs:
  a bridge's two inputs on one PWM slice (A even, B odd, GPIO0-15), the audio on a free
  slice's A output, HALL, LEV_IPROPI and MUX_OUT on ADC pins (GPIO26-29), I2C0 and UART0
  on the pins those instances allow, the mux's three selects consecutive. The same
  binding is applied to the LP5036 outputs (any LED on any channel; the firmware's bank
  split takes any mix) and the 74HC4051 inputs. `gen/pins.py` and `gen/leds.py` keep the
  hand-written tables as defaults; the schematic, `firmware/src/board_pins.h`,
  `led_map.h` and the SDK board header are generated from the result.
- Crossings at the ring: LED drivers 115 -> 0 and 42 -> 0, mux 6 -> 0, RP2354A 132 -> 84.
  Most of the RP2354A's are forced: its GPIO19-29 face the back edge (the chip is turned
  so its USB side faces the USB-C) and the ADC pins are among them, while everything they
  serve is in front.

## 5. Each subsystem

### 5.1 LEDs
Two LP5036 (U3 on the base at 0x30, U101 on the tree at 0x32), VCC and EN on +3V3, IREF
3.3 k (22 mA a channel at most). 31 LEDs on U3 (12 stars on an arc, 4 scattered stars, 6
wisps, 3 + 3 perch-ring LEDs, 3 pumpkins whose three dice share one channel), 18 on U101
(6 owl eyes, 6 stars, 4 wisps, the perch's 2 downlights). Colours: violet 405 nm 3528,
purple 0603 phosphor, orange 0603, orange three-die 5050. The firmware (`led_engine.c`)
sets each bank's brightness for its brightest LED and dithers the colour registers.

### 5.2 Coil bridges and coils
- Four DRV8874 (PWM mode, PMODE high; IMODE ground: fixed off-time, nFAULT on
  overcurrent only), VM from +12V, R_IPROPI 2.2 k with VREF 3.3 V: ITRIP 3.3 A and 0.99 V/A
  sensed. Three drive the pendulum coils (L3-L5, 4-layer spirals on the base, r 3-15 mm,
  49 turns, 33.2 uH, 2.29 ohm), one the levitation coil on the perch (L201, 3 layers, 43
  turns, 30.1 uH, 2.56 ohm) through the tree.
- Two UCC27524 (dual low-side drivers used as a full bridge from 4.8 V) drive the
  familiar perches (L6, L7: 30.3 uH, 2.13 ohm) through a 10 uF blocking capacitor; a 0.5
  ohm shunt in each bridge's ground return, x20.6 (OPA2333) and filtered, gives the
  supply current (10.3 V/A) that tells the firmware a token is there.
- Every coil is a generated footprint whose own copper is the spiral, a KiCad net tie
  (`gen/coils.py`, its checks; L and R from `sim/physics/magnetics.py`).

### 5.3 Sensors
LSM6DS3TR-C IMU (U15, bottom, 0x6A: taps, tilt), LTR-303ALS-01 light sensor (U16, top,
behind the tree), TMAG5273A2 3-axis Hall (U17, bottom, under the pendulum's rest point,
in the middle of the three pendulum coils), DRV5055A4 linear Hall (U201, perch, in the
levitation coil's hole). A 74HC4051 (U11) puts the three pendulum IPROPI lines, the two
perch currents and the three rail dividers on one ADC pin.

### 5.4 Theremin and audio
Two 74LVC1G14 Schmitt relaxation oscillators (U12 pitch, U13 volume), each with its
antenna (the gold moon and ghost: F.Cu on its net under an ENIG mask opening, no plane
under it on any layer, a 3 mm keep-out round it), counted by PIO. Audio: one PWM output,
two RC stages, an NS4150B class-D amplifier, an 8 ohm 1 W speaker (GSPK2307P, soldered
by JLCPCB). The SOUND slide switch holds the amplifier's CTRL low (shutdown) whatever the
firmware does.

## 6. Mechanics and the 3D prints
`print/`: one PLA plate (owl, bat cap, four feet), one pause for both magnets
(10 x 2 mm N52), no supports, no glue; numbers from `gen/mech.py` so prints and boards
agree by construction. The owl snaps over the perch into side notches and holds its
magnet 14.05 mm above the perch's top copper; the cap hooks under the bat's head and
tail notches. `print/README.md` has the printing and assembly steps.

## 7. The PCB as built

`gen/board.py` builds the whole panel from the netlist: placement (`gen/placement.py`, by
part role), art (`gen/art.py`), planned copper and routing (`gen/routes.py`,
`gen/routing.py`, `gen/router.py`), pours, silkscreen (`gen/silk.py`) and the panel
(`gen/panel.py`). Nothing on the board is drawn by hand in KiCad, and a build takes about
15 minutes.

**Stack** (JLC04161H-7628, 1.6 mm, 1 oz on every layer):

| layer | base | tree | perch | bat, tokens |
|---|---|---|---|---|
| F.Cu | the scene (art, LEDs, the theremin's gold); the RP2354A's corner, hidden behind the tree; routing | LEDs, routing | the levitation coil | coil |
| In1 | 4.8 V plane, with a ground island under the RP2354A that is a routing layer | 4.8 V plane | the levitation coil | coil |
| In2 | ground, unbroken | ground | coil inside its disc, ground outside | coil |
| B.Cu | electronics, routing, ground pour | the LP5036, routing | the sensor, downlights, routing | coil, parts |

The coils are copper spirals inside their footprints (`gen/coils.py`): four layers each,
except the levitation coil's three, which leaves its bottom layer free for the Hall
sensor in its middle.

**Rules:** track and space at least 0.15 mm on every net (`gen/project.py`). The 12 V,
coil and 4.8 V classes once asked 0.2-0.25 mm. That bought nothing at these voltages:
IPC-2221 asks 0.1 mm between outer-layer copper up to 15 V. So every class now keeps
0.15 mm, and width is set by current. Signals are 0.2 mm, 0.15 mm into fine-pitch pins.
Vias are 0.45/0.25 mm (JLCPCB's standard 4-layer via). Power lines are routed at a width
every pin they reach can take, then widened where the copper round them leaves room:
12 V toward 1 mm, coil lines toward 1.5 mm, 3.3 V toward 0.4 mm. Pours stay 0.5 mm
inside each board's edge.

**How it was routed**, in order:

1. **Late pin assignment** (`gen/assign.py`): the RP2354A's GPIOs, both LP5036s'
   channels and the mux's inputs were bound after placement. They follow the order in
   which coarse paths from their destinations arrive round each chip, within each pin's
   function class (PWM slices, ADC, I2C0, UART0). Crossings: LP5036 on the base 115 to
   0, on the tree 42 to 0, mux 6 to 0, RP2354A 132 to 84 (its PWM-slice pairs and fixed
   I2C/UART pins leave less freedom).
2. **Planned copper**, written as coordinates from the pads:
   - the RP2354A's core (decoupling and 1.1 V regulator, after GPiBridge);
   - the 12 V entry and the buck's power loop;
   - each coil's terminal stubs, each QFN's exposed-pad vias and ground ties;
   - ground and 4.8 V vias beside their pads, a via beside each 3.3 V pad;
   - the crystal's XIN and XOUT lines.
3. **Planned fan-outs** (`routes.fan`) for the RP2354A (33 signals, 0.4 mm pitch), both
   LP5036s and the IMU. Each signal pin gets a short stub and a straight line to a via of
   its own. The vias of a side are evenly spaced in one row or two staggered rows, so the
   lines spread like a fan and none crosses another. Clearances are checked with exact
   geometry, because a grid cannot judge a line at an arbitrary angle. The fan prints
   what blocks each pin it cannot serve. That report drove the placement changes below.
4. **A maze router** (A* on a 0.1 mm grid, three routing layers) routes the rest in a
   fixed order:
   - short local nets first;
   - the RP2354A's lines and the LED channels in "travel order" (those heading straight
     out first, those that travel round the chip last);
   - power, then the coil pairs (the farther first), then everything else.
5. **Rip-up and reroute** (`routes.repair`). For a net still in pieces, the router-laid
   nets that bound the pocket it was walled into come out. The walled-in net goes first,
   then they do. The result is kept only when fewer nets end in pieces; otherwise the old
   copper goes back exactly. It finishes the last 5-8 nets of the base.
6. **Widening**, ground stitching vias, pours. Then `board.prune` removes what the
   routing did not need: vias that join copper on one layer only, and track stubs with a
   free end. In this build that was 82 items, mostly planned vias beside 3.3 V pads that
   the router reached another way.

**Placement changes the fan-out asked for** (each one's reason is in `gen/placement.py`):

- The RP2354A's north decoupling capacitors sit midway between their signal neighbours.
- Pin 30's capacitor moved 0.6 mm along, with its line rising at 45 degrees.
- The 1.1 V via and its test point moved past the south fan.
- Pin 23's capacitor moved 1 mm along.
- The LED drivers' VCC capacitors and their VCAP and IREF parts moved to the two ends of
  the pin row, in front of ground pins (which join the exposed pad inward).
- Decoupling now sits 1.5-3 mm from the pins it serves rather than 1 mm. That's a few
  nanohenries more, which we judge harmless at these speeds (12 MHz crystal, 1 MHz I2C,
  PWM).

**Result:**

| board | tracks | vias | nets left in pieces |
|---|--:|--:|--:|
| base | 3471 | 1028 | 0 |
| tree | 296 | 159 | 0 |
| perch | 94 | 22 | 0 |
| bat | 39 | 5 | 0 |
| owl token, cat token | 23, 19 | 4, 4 | 0 |

KiCad's DRC at every severity, with schematic parity (`tools/pcb_check.py`, written to
`hardware/checks/drc.json`): 0 violations, 0 unconnected items, 0 parity errors.

**The panel** (`gen/panel.py`): 245.2 x 223.2 mm, 23 tabs (base 15, tree 8, perch 3,
owl token 4, cat token 3, bat 2), 140 mouse-bite holes. A tab is placed only where its
holes miss every part's courtyard (the tree's headers reach past its edges) and the
edges that must stay clean (the USB and barrel-jack mouths, the switch's lever, the
perch's and the bat's notches). Three fiducials and four tooling holes sit on 5 mm rails.

To look at the copper: `python3 tools/render_pcb.py` writes `build/view/pcb_*.png`;
`--crop` takes board millimetres.

## 8. Manufacturing

`mfg/make_release.py` writes `mfg/release/`: gerbers, BOM and CPL in JLCPCB's format
(bottom side 180 - angle, X not negated, checked against JLCPCB's own drawing of every
chip part on both sides), placement and footprint checks, order settings and a cost
estimate (about $343 for 5 panels with 2 assembled, before about $120 duty and
shipping). It refuses to write a release if an LCSC code's description lacks the part,
a part is short of stock, the zones are not filled, DRC is unclean, or a footprint's
holes miss JLCPCB's drawing.

## 9. Firmware
`firmware/`: C on the Pico SDK, both cores (core 1 runs a 10 kHz control tick: ADC
burst, levitation loop, coil safety; core 0 the scenes, LEDs at 200 frames a second,
familiars, pendulum, theremin, USB console). Every subsystem is host-tested against a
simulated plant (`make -C firmware/test`: all pass); the target builds.

## 10. What we would most like checked

Each question names where to look. Disagreement is welcome; a numbered list of findings
with the file and line is the most useful form.

1. **Power entry** (`gen/sch_base.py` power_in, `gen/placement.py`, `gen/routes.py`
   power_entry): is the AO4407A reverse-polarity stage right (drain to the jack side,
   source to the load, gate pulled down through 100 k, a 10 V zener gate to source)? Is
   a 5 A PTC plus an SMBJ15A after the MOSFET enough for a hot-plugged 12 V brick with a
   long cord? The 12 V reaches the four DRV8874s through routed copper widened to 1 mm
   where it fits and 0.4 mm into the pins: is that enough for 3.3 A trip currents in
   short pulses?
2. **The 4.8 V buck** (TPS54302, 400 kHz, 10 uH FXL0630, two 10 uF outputs): stable
   with ceramic outputs and the rail's load (49 LEDs to 1 A, an NS4150B, two UCC27524
   bridges at 142 and 303 kHz)? Its power loop is planned copper (VIN to the input
   capacitors beside the pins, SW straight to the inductor): look at the layout render.
3. **The levitation** (`sim/physics/levitation_onemagnet.py`, `levitation_loop.py`,
   `firmware/src/lev_ctrl.c`): one N52 10 x 2 mm magnet in the owl 14.05 mm above the
   perch's top copper holds a 3.7 g bat about 8.5 mm under it; a DRV5055 in the coil's
   hole and a 10 kHz loop stabilise it vertically. Is the loop's margin real with the
   DRV8874's PWM (40 kHz) and its current regulation in the loop? Does the Hall sensor
   see enough of the bat and little enough of its own coil?
4. **The familiars** (`sim/physics/familiar.py`, `firmware/src/familiar.c`): finding a
   token by the bridge's supply current through a 0.5 ohm shunt, x20.6 and a 1 ms
   filter. Robust against a phone or keys put on a perch? Safe for the tokens' LEDs at
   the 4.8 V drive's limit (150 ohm each)?
5. **The theremin's antennas** are large ENIG shapes on the scene side with no plane
   under them. Is 74LVC1G14 relaxation-oscillator drift with temperature and humidity
   small next to a hand's capacitance change (about 3 % assumed)?
6. **The RP2354A's GPIO binding** (`gen/assign.py`, `gen/assignment.json`): within the
   constraints the firmware has (PWM slices, ADC pins, I2C0, UART0), is there a binding
   with fewer crossings than 84? Are the constraints themselves right for the RP2350's
   GPIO function table?
7. **The panel** (`gen/panel.py`): 23 tabs with mouse bites, three fiducials and four
   tooling holes on 5 mm rails; the tree turned 90 degrees. The tree's two right-angle
   headers' pins reach 6 mm past its top and bottom edges, below the panel's plane: one
   over the left rail, one over the perch's edge. Will JLCPCB's assembly accept that?
8. **The CPL rotations on the bottom side** (`mfg/jlc_rotation.py`): 180 - angle, X not
   negated, checked against JLCPCB's drawings of the chip parts. The LEDs' and diodes'
   polarity marks are predicted from JLCPCB's drawings, not yet seen in their preview.
9. **Child safety** (`CLAUDE_PCB.md` section 16): two 10 x 2 mm magnets sealed inside
   PLA prints, 12 V, a 1 W speaker, PCB edges after snapping the tabs.

## 11. Known risks and open items

- **Her name** for the spell book (`gen/board_info.py FOR_NAME`) is not set yet; until
  it is, the release says DRAFT and the back reads "for ______".
- **The levitation** is the riskiest feature (about 65 % to work first time, by our own
  estimate): the firmware's tuning tables come from simulations, and there is no
  printed cradle to hold the bat at the float height while the loop starts (the
  firmware's README asks for one; by hand, or hanging on its thread, are the fallbacks).
  If it does not float, the same bat swings as the pendulum.
- **USB alone lights nothing**: the LEDs' anodes are on the 4.8 V rail, which only the
  12 V adapter feeds. The firmware's "USB only: dim" ceiling never applies.
- **The IMU's axes**: U15 (LSM6DS3TR-C) is on the bottom at 0 degrees: the chip faces
  down, and KiCad mirrors a bottom footprint front-to-back (its local +y becomes the
  board's -y), so of its axes only X keeps the board's sense. `firmware/src/sensors.h
  IMU_AXIS_*` still assume a chip on top; the signs are to be set by tilting the first
  board (the wisps roll the wrong way if X is wrong, which is harmless).
- **The light sensor** (U16, top, right of the tree's foot) looks up; the nearest LEDs
  are a star 11 mm away and the tree's own. It may see them; the firmware's 20 s
  hysteresis and the thresholds (3 and 30 lux) are the guard, a printed hood the cure.
- **No temperature sensor beside the coils**: the TMAG5273 sits in the middle of the
  three pendulum coils (its die temperature is their ambient); the coils' own
  resistance is their thermometer (calibrated at power-up).
- **USB VID:PID** 1209:0001 is pid.codes' test ID; fine for one board at home.
- **The pendulum's thread** is tied by hand (`ORDER_LIST.md`): its length sets the
  swing's period (about 0.69 s for 119 mm) and the magnet's height over the sensor.
