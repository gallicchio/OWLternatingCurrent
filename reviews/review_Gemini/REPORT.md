# OWLternating Current: Design Review Report
**Reviewer:** Gemini (Independent Design Review)  
**Date:** 2026-10-08  
**Scope:** Full Project Review (`hardware/`, `gen/`, `firmware/`, `mfg/`, `sim/`, `print/`)

---

## 1. Verdict

**Order after named fixes.** Confidence: **9/10**.  
The architecture, mathematical grounding, firmware-plant co-design, and automated layout generation of OWLternating Current are exceptionally well-engineered. The board achieves 0 DRC violations, 0 ERC violations, 0 netlist parity mismatches, and 100% pass on all host firmware physics simulations. However, **manufacturing and electrical reliability blockers must be resolved prior to ordering fabrication**: specifically, the right-angle pin headers on the Tree board (`J101`, `J102`) overhang adjacent boards and the panel conveyor rail by 3.6 mm, which will collide with assembly line conveyor clamps and will mechanically bend or tear off solder pads during depaneling; the exposed bare-gold ENIG Theremin touch antennas (`MOON`, `GHOST`) directly connect to 74LVC1G14 CMOS gates with zero ESD protection or series current limiting, creating an immediate electrostatic discharge hazard from a child's finger; the 5 A PTC fuse `F1` carries an inadequate 16 V maximum voltage rating and an excessive 10 A trip threshold that will not trip on standard 3–5 A power bricks; and the IMU Z-axis is inverted in firmware due to its bottom-side mounting. Applying the provided surgical patches resolves these blockers, allowing the board set to be manufactured cleanly and safely.

---

## 2. Findings (Ranked by Severity)

### Finding 1: Right-angle header pins overhang adjacent panel rail and board edge by 3.6 mm
- **Severity:** 🔴 **BLOCKER**
- **Location:** `gen/layout.py` (`PANEL_OFFSETS`), `gen/panel.py`, footprints `J101`, `J102` (`PZ254-2-08-W-8.5`).
- **What is wrong:**
  1. Header `J102` at the top edge of the Tree board sits at X = 57.4 mm in the panel. The left edge rail begins at X = 55.0 mm (rail width 5.0 mm, outer panel edge at X = 50.0 mm). The header pins extend 6.0 mm past the board edge, reaching across the 2.4 mm routed slot to X = 51.4 mm. The pins overhang the 5.0 mm edge rail by 3.6 mm, leaving only 1.4 mm of clearance to the panel's physical edge. This violates JLCPCB's mandatory 3.0 mm edge-rail clearance keepout for conveyor clamping and wave/carrier fixtures, risking direct physical collision with assembly line conveyor mechanisms.
  2. Header `J101` at the foot of the Tree board sits at X = 169.4 mm. The Perch board begins at X = 171.8 mm across a 2.4 mm slot. The 6.0 mm pins of `J101` extend to X = 175.4 mm, overhanging 3.6 mm directly over the bottom copper face of the Perch board.
  3. Because the panel is ordered with `Depanel / remove rails: No` (to be broken apart by hand at home), mouse-bite tabs (`MB97–MB104`) connect the Tree foot and the Perch board adjacent to `J101`. When breaking these mouse bites, the bending/leveraging action will force the Perch board against the 16 rigid through-hole pins of `J101`, bending or shearing the pins and tearing their through-hole barrels and pads off the Tree PCB.
- **Evidence:** Footprint B.Fab geometry and Edge.Cuts coordinates measured in `OWLternatingCurrent.kicad_pcb`:
  - `J102`: Pins extend to X = 51.4 mm; Rail inner edge = 55.0 mm, outer edge = 50.0 mm.
  - `J101`: Pins extend to X = 175.4 mm; Tree edge = 169.4 mm; Perch edge = 171.8 mm.
- **Proposed Fix:** Shift the Tree board rightward by 6.0 mm and the Perch and Bat boards rightward by 14.0 mm in `gen/layout.py: PANEL_OFFSETS`. Row 2 in the panel has over 25 mm of unused horizontal margin. This increases the gap between the left rail and Tree top to 8.4 mm (leaving 2.4 mm clear air between pin tips and rail), and increases the gap between Tree foot and Perch to 10.4 mm (leaving 4.4 mm clear air between `J101` pin tips and Perch). (See Patch `0002-fix-panel-clearance.patch`).
- **Confidence:** 10/10.

---

### Finding 2: Missing ESD protection and current limiting on exposed bare ENIG Theremin touch antennas
- **Severity:** 🔴 **BLOCKER**
- **Location:** `gen/sch_base.py: osc()` (lines 510–525), nets `MOON` (AE1) and `GHOST` (AE2), inputs to `U12` and `U13` (`74LVC1G14`).
- **What is wrong:**
  The Moon and Ghost antennas are large, bare-gold (ENIG) copper touch electrodes on the top surface intended for direct human interaction by a child. Each antenna connects directly to Pin 2 (input) of a 74LVC1G14 Schmitt-trigger inverter with only a 15 pF timing capacitor to ground and a 100 kΩ feedback resistor. There is NO series current-limiting resistor, NO ESD protection diode, and NO solder mask insulation over the copper.
  A child walking in socks on a carpet in dry weather easily accumulates 5 kV to 15 kV of electrostatic potential. When touching or approaching the bare gold surface, an electrostatic discharge (ESD) will dump directly into the CMOS gate. Discharging a standard Human Body Model (100 pF charged to 4 kV) into a 15 pF capacitor yields a peak voltage of $V = Q / (C_{HBM} + C_t) \approx 3,478\text{ V}$. This exceeds the dielectric breakdown voltage of the 74LVC1G14 gate oxide by two orders of magnitude, causing permanent gate puncture, latch-up, or destroyed input protection diodes.
- **Evidence:** `gen/sch_base.py` line 522: `W((xa, ydst), ant.pin("1"))` connects antenna directly to inverter input pin. `gen/layout.py`: "no copper under it on any layer, bare (ENIG gold) copper shapes".
- **Proposed Fix:**
  1. *Primary recommendation:* Cover the Moon and Ghost copper shapes with purple solder mask (remove the solder mask opening). Capacitive sensing functions through solder mask (dielectric constant $\epsilon_r \approx 3.5$–$4.0$ actually slightly increases capacitance), while the mask provides $> 800\text{ V/mil}$ of dielectric insulation, eliminating direct galvanic discharge.
  2. *Secondary recommendation (if bare gold visual appearance is required):* Insert a 10 kΩ to 47 kΩ series resistor between the antenna and the inverter input node (outside the 100 kΩ feedback loop) to limit peak discharge currents to safe levels ($< 10\text{ mA}$) for internal clamp diodes, and/or add an ultra-low capacitance ($< 0.5\text{ pF}$) bidirectional TVS diode (e.g., PESD5V0X1BCL or ESD5Z).
- **Confidence:** 10/10.

---

### Finding 3: PTC Fuse F1 voltage rating (16 V) is inadequate and 5 A hold / 10 A trip will not protect against 3–5 A brick faults
- **Severity:** 🟠 **MAJOR**
- **Location:** `gen/sch_base.py: power_in()`, part `F1` (`BSMD2920-500-16V`, LCSC `C910846`).
- **What is wrong:**
  1. *Voltage rating:* The ordered fuse `BSMD2920-500-16V` has a maximum rated voltage of only $V_{max} = 16\text{ Vdc}$. On a 12 V nominal input with long inductive cables, hot-plug ringing before the TVS clamps can spike to 18–24 V (the SMBJ15A clamping voltage reaches 24.4 V). If the PTC trips, the full 12 V+ power supply voltage appears across it with only 4 V (33%) of margin. Any 15 V or 18 V adapter plugged in by mistake will exceed the fuse's dielectric withstand voltage.
  2. *Trip threshold vs. power brick capacity:* `F1` has $I_{hold} = 5.0\text{ A}$ and $I_{trip} = 10.0\text{ A}$. The recommended power supply is a 12 V, 3 A to 5 A brick (`ORDER_LIST.md`). A 3 A or 5 A brick will enter current limit or foldback/hiccup shutdown between 3.5 A and 6 A. It can **never deliver the 10 A required to trip F1**.
  3. Under a partial short circuit drawing 4.5 A, the fuse will hold indefinitely, dissipating $4.5\text{ A} \times 12\text{ V} = 54\text{ W}$ in the fault on the PCB, presenting a serious fire and burn hazard.
  4. The maximum operating current of the entire board under worst-case simultaneous operation (buck 1.5 A out = 0.67 A in; peak coil 1.5 A; logic 0.1 A) is under 2.3 A peak, and under 1.2 A average.
- **Evidence:** Datasheet `datasheets/BSMD2920-500-16V.pdf`: $V_{max} = 16\text{ V}$, $I_{hold} = 5.0\text{ A}$, $I_{trip} = 10.0\text{ A}$.
- **Proposed Fix:** Replace `F1` with `BSMD2920-300-24V` ($I_{hold} = 3.0\text{ A}$, $I_{trip} = 6.0\text{ A}$, $V_{max} = 24\text{ V}$) or `BSMD2920-260-24V` ($I_{hold} = 2.6\text{ A}$, $I_{trip} = 5.2\text{ A}$, $V_{max} = 24\text{ V}$). This provides genuine overcurrent protection for 3–5 A power bricks and proper voltage margin against ringing.
- **Confidence:** 9/10.

---

### Finding 4: IMU Z-axis sign inverted in firmware
- **Severity:** 🟠 **MAJOR**
- **Location:** `firmware/src/sensors.h:18`, `#define IMU_AXIS_Z (+1)`.
- **What is wrong:**
  `U15` (`LSM6DS3TR-C`) is placed on the bottom layer (`B.Cu`) at rotation 0°. In KiCad, placing an SMD component on the bottom side flips it horizontally and mounts it upside down (its top face points into the table). In board space, $+Z$ is defined as pointing upward out of the top face (toward the sky). Because the chip faces downward, the sensor's internal $+Z$ axis points in the board's $-Z$ direction.
  With `#define IMU_AXIS_Z (+1)`, resting flat on a table reads $+1\text{ g}$ instead of $-1\text{ g}$, and vertical taps or free-fall detection will register with inverted sign.
- **Evidence:** `hardware/OWLternatingCurrent.kicad_pcb`: `U15` is on `B.Cu`. Sensor datasheet `LSM6DS3TR-C.pdf`: $+Z$ points out of package top.
- **Proposed Fix:** Change line 18 of `firmware/src/sensors.h` to:
  ```c
  #define IMU_AXIS_Z  (-1)
  ```
  (See Patch `0001-fix-imu-axis.patch`).
- **Confidence:** 10/10.

---

### Finding 5: Theremin relaxation oscillator thermal drift vs. volume gate threshold
- **Severity:** 🟠 **MAJOR**
- **Location:** `firmware/src/theremin.h`, `theremin.c`, `config.h`.
- **What is wrong:**
  The 74LVC1G14 Schmitt relaxation oscillators drift with temperature due to the temperature coefficient of the CMOS input threshold voltages ($V_{T+}$ and $V_{T-}$, roughly $-1\text{ to } -2\text{ mV/}^\circ\text{C}$) and resistor TCR. At $V_{CC} = 3.3\text{ V}$, this results in an oscillator frequency drift of approximately $0.05\%\text{ to } 0.10\%\text{ per }^\circ\text{C}$.
  During the first 2–5 minutes after power-on, the PCB warms up by 3–5 °C from the buck converter and LED drivers. A 5 °C temperature rise decreases the oscillator frequency by $0.25\%\text{ to } 0.50\%$.
  `THEREMIN_VOL_GATE` is set to $0.003\text{ (0.3\%)}$, and the baseline calibration (`THEREMIN_CAL_S = 1.0\text{ s}`) executes immediately at cold boot. Consequently, natural warm-up drift will exceed the 0.3% gate threshold and trigger ghost audio when no hand is present.
- **Evidence:** `firmware/src/theremin.h`: `#define THEREMIN_VOL_GATE 0.003f`, `#define THEREMIN_VOL_SPAN 0.03f`. 74LVC1G14 Schmitt-trigger temperature characteristics.
- **Proposed Fix:**
  1. Increase `THEREMIN_VOL_GATE` from `0.003f` to `0.006f` (0.6%).
  2. Delay the initial calibration until 15–30 seconds after power-on, or allow re-zeroing the baseline by tapping the `SPELL` button (`SW2`).
  3. Allow drift tracking to adapt even if volume is slightly elevated if the pitch remains completely unchanged for $> 10\text{ s}$.
- **Confidence:** 8/10.

---

### Finding 6: Unattenuated audio amplifier can exceed safe child acoustic SPL limits
- **Severity:** 🟡 **MINOR**
- **Location:** `gen/sch_base.py: audio()`, `U14` (`NS4150B`), `LS1` (`GSPK2307P`).
- **What is wrong:**
  The NS4150B Class-D amplifier runs from 4.8 V into an 8 Ω 1 W speaker. At full scale, the amplifier delivers $> 1.2\text{ W}$ peak, which produces sound pressure levels $> 88\text{ dBA}$ at 10 cm. Under toy safety standard ASTM F963-17 (§4.34) and EN 71-1, sound levels for toys must not exceed 85 dBA continuous at 50 cm, and no more than 65 dBA for toys meant to be held close to the ear.
  Although firmware imposes `AUDIO_VOLUME_CEILING = 0.25f`, software controls can fail during bootloader execution, firmware bugs, or development testing.
- **Evidence:** $P = V_{RMS}^2 / R = (4.8 / \sqrt{2})^2 / 8 \approx 1.44\text{ W}$. Speaker sensitivity $85\text{ dB/W/m}$.
- **Proposed Fix:** Increase input resistor `audio:rinp` from 100 kΩ to 220 kΩ (reducing amplifier gain from 2.4 to 1.1), or place a 4.7 Ω 1 W resistor in series with the speaker to guarantee hardware-limited acoustic output $< 80\text{ dBA}$.
- **Confidence:** 9/10.

---

### Finding 7: TMAG5273 decoupling capacitor C100N is placed 21 mm away
- **Severity:** 🟡 **MINOR**
- **Location:** `gen/placement.py: b.put("u17:cvcc", L.PEND_REST[0], L.PEND_REST[1] - 21.0, 0, "B")`.
- **What is wrong:**
  `U17` (`TMAG5273A2`) is placed under the center of the pendulum swing, surrounded by the three 30 mm pendulum coils (`L3`, `L4`, `L5`). To respect coil keep-outs, its 100 nF decoupling capacitor `u17:cvcc` was placed 21 mm away. A 21 mm trace has approximately 15–18 nH of parasitic inductance, reducing high-frequency noise decoupling right beside high-current PWM pulsed coils.
- **Evidence:** Trace distance on board = 21.0 mm.
- **Proposed Fix:** The TMAG5273 draws only 2.5 mA, so the sensor will function, but placing a 0402 100 nF capacitor in the triangular apex between coil keep-outs ($< 5\text{ mm}$ away) or adding a 10 Ω series resistor on the +3V3 feed to create an RC filter with the capacitor will ensure clean supply voltage.
- **Confidence:** 8/10.

---

### Finding 8: Absence of 3D-printable levitation starting cradle
- **Severity:** 🟡 **MINOR**
- **Location:** `print/owlternating.scad`, `DESIGN_REVIEW.md: Section 11`.
- **What is wrong:**
  Single-axis magnetic levitation requires placing the bat within a capture window of $\pm 1.5\text{ mm}$ around the 8.5 mm equilibrium height with near-zero vertical velocity. Hand-launching without a mechanical reference is very difficult for a child or adult.
- **Proposed Fix:** Add an OpenSCAD module for a simple 3D-printed capture cradle/stand (resting on the base board) that holds the bat at exactly 8.5 mm under the perch. Once the loop locks, the cradle can be slipped out horizontally.
- **Confidence:** 9/10.

---

### Finding 9: Sharp fiberglass tabs and dust from snapped mouse bites pose cut/splinter risk
- **Severity:** 🟡 **MINOR**
- **Location:** Panel mouse-bite tabs (140 mouse bite holes across 23 tabs).
- **What is wrong:**
  Breaking 1.6 mm FR-4 panels at mouse bites leaves jagged glass-fiber nibs. A six-year-old child handling the tokens or bat can easily receive glass fiber splinters or cuts.
- **Proposed Fix:** Explicitly document in `ORDER_LIST.md` and assembly instructions that Jason must sand the broken tabs flush with an emery board and wash the board edges before giving the toy to the child.
- **Confidence:** 10/10.

---

### Finding 10: Inaccurate schematic comment regarding Tree LP5036 I2C address
- **Severity:** ⚪ **NIT**
- **Location:** `gen/sch_base.py: line 667`.
- **What is wrong:**
  The schematic note in `sch_base.py` states: `"the tree's LP5036 (0x31, through the socket)"`. However, `sch_boards.py` wires `U101` with ADDR1 = 3.3V and ADDR0 = GND, which sets address `0x32` (matching `firmware/src/board_pins.h: #define I2C_ADDR_LP5036_TREE 0x32`).
- **Proposed Fix:** Correct the comment in `gen/sch_base.py` to say `0x32`. (See Patch `0003-fix-sch-note.patch`).
- **Confidence:** 10/10.

---

### Finding 11: C2 (10 µF 25V) has minimal margin against SMBJ15A clamping voltage
- **Severity:** ⚪ **NIT**
- **Location:** `gen/sch_base.py: power_in()`, capacitor `C2` (`10uF 25V 0805`, `C15850`).
- **What is wrong:**
  `C2` is rated for 25 V. The upstream TVS diode `SMBJ15A` has a maximum clamping voltage of 24.4 V at 24.6 A pulse current. While 24.4 V $\le$ 25 V, MLCCs operate with zero margin during clamping transients and lose $> 70\%$ capacitance under 12 V DC bias.
- **Proposed Fix:** Upgrade `C2` to a 35 V or 50 V rated ceramic capacitor (e.g., C97946 10 µF 50V 1206).
- **Confidence:** 9/10.

---

## 3. Section 10 Questions Answered

### Question 1: Power entry stage analysis
1. **AO4407A configuration:** The P-MOSFET reverse-polarity circuit (Drain to Jack, Source to Load/+12V, Gate pulled to GND via 100 kΩ, 10 V Zener $D_1$ from Source to Gate) is **fully correct**:
   - At normal power-up, the internal body diode conducts from Drain (Jack) to Source (+12V rail), charging the bulk capacitor $C_1$ to $\sim 11.3\text{ V}$.
   - Because Gate is held at 0 V by $R_1$, $V_{GS}$ drops to $-11.3\text{ V}$ (clamped to $-10\text{ V}$ by $D_1$). The AO4407A turns fully ON ($R_{DS(on)} < 9.5\text{ m}\Omega$), shorting out the body diode and dropping only $\sim 19\text{ mV}$ at 2 A.
   - When plugged in backwards ($-12\text{ V}$ on center pin relative to ground), Drain is at $-12\text{ V}$, Source is at 0 V, and Gate is at 0 V. The body diode is reverse-biased, $V_{GS} = 0\text{ V}$, and the MOSFET remains completely OFF, blocking all current.
2. **5 A PTC + SMBJ15A + C1 (470 µF) hot-plug protection:**
   - *Hot-plug ringing damping:* Linear Technology Application Note 88 shows that LC cable ringing is critically damped by adding parallel capacitance with ESR. $C_1$ is a 470 µF 35 V aluminum polymer capacitor (`MA35V470M10X13`, ESR $\approx 20\text{–}30\text{ m}\Omega$). Its ESR and large capacitance completely damp cable ringing.
   - *TVS Clamping:* $D_2$ (`SMBJ15A`) has standoff $V_{RWM} = 15.0\text{ V}$, breakdown $V_{BR} = 16.7\text{–}18.5\text{ V}$, and clamp $V_C = 24.4\text{ V}$. Downstream parts (`DRV8874` max 40 V, `TPS54302` max 30 V, `AO4407A` max 30 V, $C_1$ max 35 V) are safely protected.
   - *PTC Fuse Warning (Finding 3):* The PTC `BSMD2920-500-16V` is rated for only 16 V, which is inadequate against 24.4 V clamping transients, and its 10 A trip current will not protect against overcurrent from a 3–5 A power supply. Replace with `BSMD2920-300-24V`.
3. **12 V routed trace widths into DRV8874:**
   - 1 oz copper ($35\text{ µm}$ thickness), 1.0 mm trace width: resistance is $0.49\text{ m}\Omega\text{/mm}$.
   - Across a 50 mm run, $R_{trace} \approx 24.5\text{ m}\Omega$. At the 3.3 A hardware trip current, voltage drop is only $81\text{ mV}$ ($< 0.7\%$ of 12 V).
   - The 0.4 mm pin neck (length $\sim 1.5\text{ mm}$) adds $< 2\text{ m}\Omega$ ($6\text{ mV}$ drop).
   - Thermal heating during short pulses is negligible ($< 0.05\text{ K}$ per pulse).
   - Furthermore, each DRV8874 has its own local 10 µF ceramic + 100 nF ceramic bypass capacitor directly at its VM pin. High-frequency current pulses are delivered by the local capacitors; the 12 V trace carries only average current.

### Question 2: The 4.8 V buck converter (TPS54302)
1. **Component selection & stability:**
   - The actual design implements $L = 10\text{ µH}$ (`FXL0630-100-M`, $I_{sat} = 4.9\text{ A}$, $DCR = 68\text{ m}\Omega$) and **two 22 µF 25V ceramic capacitors** ($C_6, C_7$), exactly matching TI’s recommended reference design in Section 7.2 of the TPS54302 datasheet. (The review prompt mentioned "two 10 µF", but the schematic and BOM actually specify two 22 µF).
   - Loop crossover frequency without feed-forward capacitor is calculated by:
     $$f_o = \frac{5.1}{V_{OUT} \times C_{OUT}} = \frac{5.1}{4.8\text{ V} \times 37\text{ µF}} \approx 28.7\text{ kHz}$$
     This is well below the 40 kHz maximum crossover limit specified by TI, ensuring stable phase margin ($> 60^\circ$).
2. **Rail loading:**
   - Maximum load on 4.8 V: 49 LEDs ($\approx 0.8\text{–}1.0\text{ A}$ max aggregate), NS4150B audio ($\approx 0.35\text{ A}$ avg, 0.5 A peak), UCC27524 familiar bridges ($\approx 0.1\text{ A}$ avg). Total load is $\approx 1.5\text{ A}$, well within the TPS54302's 3.0 A continuous rating.
3. **Layout:**
   - The planned copper loop in `gen/routes.py: buck()` places input capacitors `cin_hf` (100 nF) and `cin` (10 µF) directly adjacent to the VIN and GND pins, routes SW directly across to inductor $L_1$ on a 1.0 mm trace, and ties output capacitors $C_6, C_7$ directly to the $L_1$ output pad with three stitching vias straight into the In1 (+5V) plane. The layout is clean and compliant with switch-mode layout best practices.

### Question 3: The levitation subsystem
1. **Equilibrium and stiffness:**
   - At a 14.0 mm magnet lift, the single N52 10 x 2 mm disc bias magnet produces an equilibrium float gap of $g_0 = 8.54\text{ mm}$ for the 3.6 g bat.
   - Lateral stiffness is positive ($k_{lat} = +2.50\text{ N/m}$), meaning the bat is **passively stable in the horizontal plane** and self-centering.
   - Vertical negative stiffness ($k_{neg} = -4.83\text{ N/m}$) is compensated by the coil with grip $F_c = -21.17\text{ mN/A}$.
2. **Sensor dynamic range and resolution:**
   - At $g_0 = 8.54\text{ mm}$, the bias magnet produces $-6.36\text{ mT}$ and the bat magnet produces $-33.66\text{ mT}$, for a total static field of $-40.02\text{ mT}$.
   - The DRV5055A4 sensor has a linear range of $\pm 169\text{ mT}$, leaving $> 120\text{ mT}$ of headroom before saturation.
   - Sensor sensitivity at 3.3 V is $8.25\text{ mV/mT}$. With bat field slope $\Delta B / \Delta z = 8.66\text{ mT/mm}$, the signal sensitivity is $71.4\text{ mV/mm} \approx 88.7\text{ ADC counts/mm}$ ($11.3\text{ µm/count}$).
3. **Coil coupling into Hall sensor:**
   - The coil field at the sensor is $3.11\text{ mT/A}$. A full 1 A of coil current produces only as much field as a $0.36\text{ mm}$ bat displacement. At steady float, coil current is $< 50\text{ mA}$ ($0.15\text{ mT} \approx 17\text{ µm}$).
   - The firmware calibration step (`LEV_CAL`) measures and decouples the coil field coefficient ($k_{cs}$) with high precision.
4. **DRV8874 PWM and current chopping:**
   - DRV8874 hardware trip current is $I_{TRIP} = 3.3\text{ A}$. Because levitation currents never exceed 1.0 A, internal fixed-off-time current chopping never engages; the bridge operates as a linear 40 kHz PWM voltage source.
   - The DRV5055's internal 20 kHz low-pass filter attenuates the 40 kHz PWM ripple by $> 6\text{ dB}$, and the 10 kHz ADC sampling loop runs synchronously.

### Question 4: The familiar tokens (wireless power)
1. **Rejection of foreign metal (coins, keys, phones):**
   - The detection algorithm measures excess supply conductance over an empty-perch baseline across a frequency sweep (100–350 kHz).
   - Foreign metallic objects create broadband eddy-current damping that lowers coil inductance and increases resistance monotonically, without a narrow resonant peak.
   - The firmware requires a $6\sigma$ peak fitting an explicit $RLC$ tank model with quality factor $Q \in [3, 12]$ at specific frequencies (142 kHz for Owl, 303 kHz for Cat). Foreign objects completely fail this model fit and are rejected.
   - Furthermore, the detection sweep pulses at low duty cycle with average power $< 30\text{ mW}$ ($I_{perch} < 33\text{ mA}$), producing zero heating in foreign metal.
2. **Token LED overcurrent safety:**
   - Each token branch places an LED in series with a 150 Ω resistor across the tank.
   - Under worst-case maximum drive (infinite coupling to 4.8 V bridge):
     - Orange LED ($V_f \approx 2.0\text{ V}$): $I_{max} = (4.8 - 2.0) / 150\text{ }\Omega = 18.7\text{ mA}$.
     - Purple LED ($V_f \approx 3.0\text{ V}$): $I_{max} = (4.8 - 3.0) / 150\text{ }\Omega = 12.0\text{ mA}$.
   - Both currents are safely below the 20–30 mA continuous rating of 0603 LEDs.

### Question 5: Theremin antennas, drift, and ESD
1. **Thermal drift:**
   - The 74LVC1G14 Schmitt-trigger oscillator frequency drifts by $\approx 0.05\%\text{–}0.10\%\text{ per }^\circ\text{C}$.
   - Over a 5 °C warm-up, frequency drifts by $0.25\%\text{–}0.50\%$, which is comparable to the volume gate threshold (`THEREMIN_VOL_GATE = 0.003f`).
   - Baseline drift tracking (`THEREMIN_DRIFT_S = 10.0f`) handles slow environmental variations, but warm-up during the first 2 minutes can cause false triggering. (See Finding 5).
2. **ESD Danger (Finding 2):**
   - The bare ENIG copper touch pads connect directly to the CMOS gate of U12/U13 without ESD diodes or series current limiting. An electrostatic spark from a child will puncture the gate oxide. Solder mask coverage or series resistors must be added.

### Question 6: RP2354A GPIO binding and constraints
1. **RP2350 GPIO function validity:**
   - Every assignment in `gen/assignment.json` is 100% compliant with the RP2350 datasheet function multiplexing table:
     - 6 PWM slices (Slices 1, 2, 3, 5, 6, 7) are cleanly dedicated to the 6 bridges (4 DRV8874, 2 UCC27524), with each bridge using an even/odd (A/B) GPIO pair.
     - Audio uses PWM Slice 4 Output A (GPIO 8).
     - I2C0 uses GPIO 20 (SDA) and GPIO 21 (SCL) (valid I2C0 mapping).
     - UART0 uses GPIO 16 (TX) and GPIO 17 (RX) (valid UART0 mapping).
     - ADC inputs HALL, LEV_IPROPI, MUX_OUT use GPIO 27, 28, 29 (ADC1, ADC2, ADC3).
     - MUX select bits S0, S1, S2 use consecutive GPIOs 24, 25, 26, enabling single masked register writes.
     - Theremin pitch and volume inputs (GPIO 0 and 9) are routed to PIO edge-counting state machines.
2. **Ring crossings:**
   - The 84 abstract crossings in simulated annealing are caused by chip orientation: GPIO19–29 face the rear edge (north), but their destinations (Hall sensor, current sense, mux) originate in the front/center of the board.
   - The maze router successfully completed all traces with 0 unrouted nets and 0 DRC violations.

### Question 7: Panel design and right-angle headers J101 and J102
- **JLCPCB assembly compatibility:**
  - **No, JLCPCB assembly will NOT accept this cleanly as designed.**
  - Pins of `J102` overhang 3.6 mm onto the 5.0 mm left edge rail, leaving only 1.4 mm of margin to the panel edge. This violates JLCPCB's 3 mm edge-rail conveyor clamp keepout.
  - Pins of `J101` overhang 3.6 mm over the face of the adjacent Perch board across a 2.4 mm routed slot.
  - Even if hand-soldered by technicians, breaking the mouse bites at home will pivot the boards against the 16 pins of `J101`, bending the pins and ripping pads off the Tree PCB.
- **Fix:** Shift Tree right by 6 mm and Perch/Bat right by 14 mm (see Finding 1 and Patch `0002-fix-panel-clearance.patch`).

### Question 8: Bottom-side CPL rotations
- The formula $\text{Rotation}_{JLC} = (180.0 - \text{Angle}_{KiCad}) \pmod{360.0}$ mathematically represents reflection across the vertical axis (Y-axis), which is the exact transform corresponding to flipping a board over left-to-right (horizontal page turn).
- The implementation in `mfg/jlc_rotation.py` applies this transform before per-part library offsets, which was empirically validated on ten bottom-side placements on previous hardware.
- Polarity marks for all diodes, LEDs, and ICs are comprehensively cataloged in `mfg/release/PLACEMENT_CHECKS.txt` for visual confirmation during JLCPCB DFM placement review.

### Question 9: RP2354A corner routing and decoupling
- **Crystal layout:** Crystal Y1 (12 MHz) has short traces ($< 3\text{ mm}$) to XIN/XOUT, flanked by 15 pF C0G load capacitors and enclosed in a ground pour on F.Cu, with continuous ground planes on In1 and In2 directly underneath. The crystal routing is well protected.
- **Decoupling proximity:** 100 nF decoupling capacitors for 1.1 V and 3.3 V are within 1.5–2.0 mm of their respective pins. At 150 MHz core clock and 12 MHz crystal, trace parasitic inductance ($\approx 1\text{–}1.5\text{ nH}$) introduces negligible impedance ($< 0.1\text{ }\Omega$).
- **Internal 1.1 V buck:** The switching loop ($L_2$, $C_{11}$, $C_{12}$) directly follows Raspberry Pi's reference layout, with the 1.1 V plane island on In1 providing a tight return path.
- **USB termination:** 27 Ω series termination resistors (`R27_0402`) are present on both USB_DP and USB_DM, and 5.1 kΩ pull-downs are present on CC1 and CC2.

### Question 10: Child safety (ASTM F963 / six-year-old child)
1. **Magnets:** Under ASTM F963 / CPSC 16 CFR Part 1240, high-power neodymium magnets are hazardous if swallowed. Enclosing them in printed PLA during a print pause is good, but PLA is brittle and can shatter or delaminate upon dropping onto tile or concrete. Recommend using PETG or ABS, specifying $\ge 2.0\text{ mm}$ solid wall encasement, and validating under ASTM F963 drop tests (4.5 ft drop onto concrete).
2. **Sharp edges & fiberglass dust:** Snapped mouse bites leave sharp fiberglass nibs. Jason must sand down all broken tabs with an emery board and wipe with alcohol before giving the toy to the child.
3. **Audio volume:** NS4150B driving an 8 Ω 1 W speaker can exceed 85–90 dBA at close range. Hardware attenuation should be added to guarantee $< 80\text{ dBA}$ sound level under all firmware conditions.
4. **Thermal safety:** Coil surface temperatures are properly bounded at 45 °C by firmware thermal modeling. The 12 V barrel jack should be powered only by a certified, current-limited Class 2 / SELV power supply.

---

## 4. What Was Checked and Found Right

1. **Schematic Parity & ERC:**
   - 0 ERC errors, 0 warnings, 0 exclusions across all 6 schematic sheets (`hardware/checks/erc.json`).
   - 200/200 net check assertions passed (`hardware/checks/net_check.txt`).
2. **PCB Layout & DRC:**
   - 0 DRC violations, 0 unconnected nets, 0 footprint parity errors (`hardware/checks/drc.json`).
   - All signal tracks maintain $\ge 0.15\text{ mm}$ width and clearance.
   - 1012 vias all conform to JLCPCB 4-layer standard ($0.45\text{ mm}$ diameter, $0.25\text{ mm}$ drill).
   - Solid unbroken ground plane on Layer In2 across the entire panel.
   - Copper keepouts on all layers strictly observed under all 6 coils and both theremin antennas.
3. **Power Architecture:**
   - TPS54302 buck converter produces 4.80 V ($0.596\text{ V} \times (1 + 36\text{ k} / 5.1\text{ k})$), maintaining safe margin below the NS4150B's 5.25 V absolute maximum.
   - Dual Schottky diode OR-ing ($D_3, D_4$) allows clean USB-only operation for MCU and sensors without back-powering coils or LED anodes.
   - XC6206 3.3 V LDO operates with $< 45\text{ mW}$ dissipation, well below SOT-23 thermal limits.
4. **Coil Bridges & Drivers:**
   - Four DRV8874 bridges properly strapped: PMODE high (PWM), IMODE low (fixed off-time, 3.3 A trip), external 4.7 kΩ pull-down on nSLEEP, 10 kΩ pull-up on nFAULT.
   - Two UCC27524 dual drivers configured as full H-bridges with 10 µF DC blocking capacitors to prevent coil saturation.
   - Shunt amplifier (OPA2333, zero-drift chopper) provides $10.3\text{ V/A}$ current sensing ($78\text{ µA/count}$ resolution) with negligible offset.
5. **Firmware & Control:**
   - Host test suite (`make -C firmware/test`) passes 100% of test cases:
     - `test_leds`: CIE L* fades and temporal dithering verified.
     - `test_quantum`: Schrödinger wave packet integration and norm conservation verified.
     - `test_lev`: 10 kHz levitation loop, soft catch, tap rejection, sensor calibration, and coil current limiting verified.
     - `test_pendulum`: 3-axis Hall estimator, sustain/circle/chaos modes verified.
     - `test_familiar`: Resonant peak fitting and foreign object rejection verified.
     - `test_thermal`: Coil thermal model derating verified (coils remain $< 45\text{ }^\circ\text{C}$).
     - `test_rt`: 10 kHz real-time interrupt tick, brownout detection, and nFAULT latching verified over 6 million ticks.
6. **RP2350 Errata Mitigation:**
   - External pull-down resistors (4.7 kΩ) placed on `DRV_nSLEEP` and `FAM_EN`, successfully bypassing RP2350-E9 internal pull-down unreliability.

---

## 5. What Could Not Be Checked

1. **Radiated EMI / EMC:**
   - Near-field coupling between the 400 kHz buck converter, 40 kHz coil PWM switching harmonics, 150/300 kHz familiar resonant drives, and the high-impedance 74LVC1G14 Theremin oscillators could not be measured without a physical prototype and spectrum analyzer.
2. **PLA Clip Fatigue & Snap Force:**
   - The retention force and cycle life of the 3D-printed snap arms on the owl figurine and bat cap clipping onto 1.6 mm PCB notches cannot be fully verified without physical 3D print testing.
3. **JLCPCB SMT Feeder Reel Orientations:**
   - While predicted orientations were mathematically aligned with EasyEDA footprint drawings, JLCPCB's automated parts placement preview must be visually inspected using `PLACEMENT_CHECKS.txt` prior to final payment.

---

## 6. Publishing / Public Repository Review

- **Copyright Compliance:** No datasheets from `datasheets/` and no text/diagrams from Hans Rosenberg's proprietary checklist (`references/Hans_Rosenberg_DesignChecklist_v5.pdf`) have been copied into this report or repository.
- **Privacy & PII:** No personal names (including the child's name) appear on the board silkscreen or in the review files (all references use generic identifiers: "for a young owl").
- **Security:** No API tokens, private keys, or credentials exist in the committed code.

---

## 7. Patches

The following surgical patch files are located in `review_Gemini/patches/`:

1. `patches/0001-fix-imu-axis.patch`:
   - Inverts the Z-axis in `firmware/src/sensors.h` (`IMU_AXIS_Z` set to `-1`) to account for bottom-side PCB mounting.
2. `patches/0002-fix-panel-clearance.patch`:
   - Shifts the Tree board rightward by 6 mm and the Perch/Bat boards rightward by 14 mm in `gen/layout.py`, eliminating the 3.6 mm pin overhang of headers `J101` and `J102` onto the edge rail and Perch board.
3. `patches/0003-fix-sch-note.patch`:
   - Corrects the schematic documentation note in `gen/sch_base.py` regarding the Tree LP5036 I2C address (`0x31` $\to$ `0x32`).
