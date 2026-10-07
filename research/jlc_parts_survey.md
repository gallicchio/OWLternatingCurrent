# JLCPCB parts survey for halloween1

Stock, price and library type were queried from JLCPCB's parts API between **2026-10-07T11:17:31-07:00** and **2026-10-07T11:23:57-07:00** (each part's own query time is in `jlc_parts_survey.json`). Regenerate with `python3 research/survey.py` (`--refresh` to re-query).

* **$@100** is JLCPCB's unit price at a quantity of 100, in USD.
* **Basic** parts carry no setup fee; **Preferred** are Extended parts JLCPCB keeps loaded (no setup fee either); each distinct **Ext**ended part costs about $3 to set up.
* ★ marks the recommended pick of each group (in the C0G ladder, of each value); [ds] marks specs read from the datasheet (in `datasheets/`, not committed), the rest are from JLCPCB's description.
* This is a survey of what can be bought and placed, not a design decision.

## a. Orange LEDs (orange 600-615 nm, amber 585-597 nm, red-orange 615-630 nm)

**Recommendation:** Orange: XINGLIGHT XL-1608UOC-06 (C965800, 0603, 600-610 nm) for indicator-size pumpkins and HONGLITRONIC HL-AF-5060S22OC (C516304, 5050 3-die) for a bright glow; if a Basic part is required, KT-0603R (C2286, 615-630 nm) is the closest (red-orange) and KT-0805Y (C2296) the amber.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **Orange 600-615 nm (pumpkin orange)** | | | | | | | |
| C965800 ★ | XL-1608UOC-06 | XINGLIGHT | 0603 | AlGaInP orange, λd 600-610 nm, 80-210 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA (IFP 80) [ds] — API lists 315 mcd; datasheet table says 80-210 mcd | Ext | 398,998 | 0.0071 |
| C51933298 | GL0603UO01 | Gui guang light | 0603 | λd 600-612 nm, 203-358 mcd @20 mA, Vf 1.8-2.4 V, If max 25 mA (IFP 100) [ds] — API lists 100-160 mcd | Ext | 306,360 | 0.0066 |
| C157740 | LTST-C190KFKT | Lite-On | 0603 | λd 605 nm (λp 611), 45-90 mcd @20 mA, Vf 2.0-2.4 V, If max 30 mA (IFP 80), 75 mW [ds] | Ext | 52,705 | 0.0259 |
| C965813 | XL-2012UOC | XINGLIGHT | 0805 | λd 600-610 nm, 80-210 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA [ds] | Ext | 122,281 | 0.0088 |
| C965823 | XL-3216UOC | XINGLIGHT | 1206 | λd 600-606 nm, 80-180 mcd @20 mA, Vf 1.9-2.4 V, If max 20 mA [ds] | Ext | 49,549 | 0.0118 |
| C2837014 | TJ-S3528UG6W9TLC0A-A5 | TOGIALED | SMD3528-2P | PLCC-2/3528; λd 600-610 nm, 100-320 mcd @20 mA, Vf 1.8-2.4 V, If max 30 mA [ds] | Ext | 9,146 | 0.0464 |
| C2843804 | XL-3528UOC | XINGLIGHT | SMD3528-2P | PLCC-2/3528; λd 600-608 nm, 300-400 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA [ds] | Ext | 6,439 | 0.0381 |
| C516304 | HL-AF-5060S22OC-3-S1-THL | HONGLITRONIC | SMD5050-6P | 5050, 3 AlGaInP dice; λd 600-610 nm, 600-800 mcd @3x20 mA, If 60 mA total, Pd 225 mW [ds] — brightest deep-stock orange; no orange 2835/3030 with real stock | Ext | 19,795 | 0.0270 |
| C5440712 | XL-5050UOC | XINGLIGHT | SMD5050-6P | 5050; λd 600-605 nm, 800 mcd @60 mA, Vf 1.8-2.2 V | Ext | 3,954 | 0.0340 |
| **Amber 585-597 nm** | | | | | | | |
| C2296 ★ | KT-0805Y | Hubei KENTO Elec | 0805 | λd 592-594 nm (amber-yellow), 95-113 mcd @20 mA, Vf 2.0-2.2 V, If max 20 mA (IFP 100) [ds] — API lists 584-594 nm, 175 mcd | Basic | 357,470 | 0.0153 |
| C89811 | NCD0603Y2 | Foshan NationStar Optoelectronics | 0603 | λd 583-595 nm (588 typ) @15 mA, 50-180 mcd, Vf 1.5-2.6 V, If max 25 mA (IFP 50) [ds] | Preferred | 30,939 | 0.0196 |
| C965802 | XL-1608UYC-06 | XINGLIGHT | 0603 | λd 585-595 nm, 435 mcd @20 mA, Vf 2.4 V, 50 mW | Ext | 1,360,194 | 0.0071 |
| C7371919 | XL-2835UYC-02FJ | XINGLIGHT | SMD2835-2P | 2835; λd 587-596 nm, 1.75 cd @60 mA, Vf 1.8-2.4 V, 200 mW | Ext | 69,638 | 0.0212 |
| C51933348 | GL5050UY01 | Gui guang light | SMD5050-6P | 5050; λd 585-595 nm, 0.6-2 cd @60 mA, Vf 1.8-2.2 V, 200 mW | Ext | 13,642 | 0.0235 |
| **Red-orange 615-630 nm** | | | | | | | |
| C2286 ★ | KT-0603R | Hubei KENTO Elec | 0603 | λd 615-630 nm, 145-300 mcd @20 mA, Vf 1.8-2.4 V, If max 25 mA (IFP 60) [ds] | Basic | 4,579,800 | 0.0076 |
| C84256 | NCD0805R1 | Foshan NationStar Optoelectronics | 0805 | λd 615-630 nm (620 typ), 50-230 mcd @20 mA, Vf 1.5-2.6 V, If max 25 mA (IFP 50) [ds] | Basic | 4,641,365 | 0.0134 |
| C965798 | XL-1608SURC-04 | XINGLIGHT | 0603 | λd 620-625 nm, 120 mcd @20 mA, Vf 2.4 V, 50 mW | Ext | 319,133 | 0.0057 |
| C2843800 | XL-3528SURC | XINGLIGHT | SMD3528-2P | PLCC-2/3528; λd 620-630 nm, 530 mcd @20 mA, Vf 2.4 V | Ext | 210,675 | 0.0233 |
| C2843869 | XL-2835SURC-02 | XINGLIGHT | SMD2835-2P | 2835; λd 620-630 nm, 900 mcd @60 mA, Vf 2.4 V, 200 mW | Ext | 195,442 | 0.0165 |
| C2843864 | XL-5050SURC | XINGLIGHT | SMD5050-6P | 5050; λd 620-630 nm, 2.2 cd @60 mA, Vf 2.4 V, 200 mW | Ext | 288,220 | 0.0378 |

* No orange (600-615 nm) LED is Basic or Preferred: the only Basic/Preferred LEDs in 'LED Indication - Discrete' are KT-0603R, NCD0805R1 (red 615-630 nm), KT-0805Y (yellow-amber: 584-594 nm per API, 592-594 nm per datasheet), NCD0603Y2 (Preferred, 586-595 nm), KT-0805G (green) and KT-0603W/KT-0805W (white).
* Orange in 2835/3030 is thin: Everlight 67-31EP3-URD1224DBFBZ5 2835 (C5137842, ~1.4k) and an OSRAM 3030 amber (C37155455, 200); for a bright orange glow use 5050 3-die parts or several 3528s.
* Several cheap LED datasheets disagree with the API's mcd figure (e.g. XL-1608UOC-06); [ds] values are the datasheet's.

## b. Purple LEDs (violet 390-420 nm, purple/pink phosphor and red+blue bi-die, UV-A 365-385 nm)

**Recommendation:** Violet: TUOZHAN S2-2835UVTA-0.2W (C2827317, 2835, 390-400 nm, 705k stock) for glow/fluorescence effects; for a visibly purple pixel use GL0603PU01 (C51933300) or a red+blue bi-die XL-1615SURUBC (C965836) mixed by PWM.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)** | | | | | | | |
| C2827317 ★ | S2-2835UVTA-0.2W | TUOZHAN | SMD2835-2P | 2835; λp 390-400 nm, Vf 3.0-3.6 V @60 mA, If max 60 mA (IFP 100), Pd 180 mW; radiant power not stated [ds] — deepest-stock violet by far | Ext | 705,062 | 0.0189 |
| C49652883 | XL-HD2835UVA2-A1 | XINGLIGHT | SMD | 2835 HP; λp 390-400 nm (395 typ), Φe 120-180 mW @120 mA, Vf 3.1-3.7 V, If max 150 mA, Pd 600 mW [ds] — API description is empty; specs from datasheet | Ext | 14,100 | 0.0394 |
| C2843877 | XL-2835UVA-02 | XINGLIGHT | SMD2835-2P | 2835; λp 395 nm, Φe 45-90 mW @60 mA, Vf 3.0-3.6 V, If max 60 mA (IFP 120) [ds] | Ext | 20,020 | 0.0383 |
| C7371898 | XL-1608UVC-04 | XINGLIGHT | 0603 | 0603; λp 390-405 nm, 50-80 mcd @20 mA, Vf 3.0-3.4 V, Pd 100 mW [ds] — datasheet abs-max table prints IF 80 mA / IFP 25 mA (apparently swapped): use <=20 mA | Ext | 20,204 | 0.0133 |
| C7371915 | XL-2012UVA | XINGLIGHT | 0805 | 0805; λd 390-405 nm (405), 52-78 mcd @20 mA, Vf 2.9-3.5 V, 70 mW | Ext | 16,255 | 0.0161 |
| C2827267 | P2-0802UVTA1-1.0T | TUOZHAN | 0805 | 0805; λp 390-395 nm, Vf 2.8-3.4 V @20 mA, If max 30 mA (IFP 100), Pd 90 mW [ds] | Ext | 12,046 | 0.0278 |
| C516136 | HL-A-3528S7VC-S1-13HL | HONGLITRONIC | SMD3528-2P | PLCC-2/3528; λd 400-410 nm, 50 mcd @20 mA, Vf 3.4 V, 102 mW | Ext | 68,094 | 0.0428 |
| **Purple / pink (phosphor) and red+blue bi-die** | | | | | | | |
| C51933300 ★ | GL0603PU01 | Gui guang light | 0603 | 0603 'purple light', 58-145 mcd @5 mA, Vf 2.6-3.1 V, If max 30 mA; no spectrum given [ds] — evidently phosphor-converted: the datasheet warns that sulfides change its 'fluorescent colour' | Ext | 18,511 | 0.0100 |
| C7496841 | F.0805.00034/P2-0805W7YS2-08T-006 | TUOZHAN | 0805 | 0805 purple, 100 mcd @5 mA, Vf 2.6-3.0 V, 90 mW | Ext | 8,611 | 0.0096 |
| C7496831 | F.0603.00106/P2-0603W7YS2-06T-001 | TUOZHAN | 0603 | 0603 purple, 100 mcd @5 mA, Vf 3 V, 90 mW — REVERSE-MOUNT part (shines through a hole in the PCB) | Ext | 22,584 | 0.0107 |
| C965821 | XL-2012UPC | XINGLIGHT | 0805 | 0805 pink (pink lens), 303 mcd @20 mA, Vf 3.3 V, 70 mW | Ext | 60,799 | 0.0140 |
| C51933299 | GL0603UP01 | Gui guang light | 0603 | 0603 pink, 144-249 mcd @5 mA, Vf 2.7-3.2 V | Ext | 83,908 | 0.0063 |
| C965836 | XL-1615SURUBC | XINGLIGHT | SMD-4P,1.6x1.5mm | 1615 4-pin red+blue bi-die, common anode: 465-475 nm + 620-630 nm, 150/160 mcd @20 mA, Vf 3.4/2.4 V — mix the two dies with PWM for a tunable magenta/purple | Ext | 57,782 | 0.0162 |
| C2843811 | XL-3528SURUBC | XINGLIGHT | SMD3528-4P | 3528 4-pin red+blue bi-die, common anode: 465 nm + 620-625 nm, 180/350 mcd @30 mA, Vf 3.2/2.2 V | Ext | 23,857 | 0.0357 |
| **UV-A 365-385 nm (comparison)** | | | | | | | |
| C49652884 ★ | XL-HD2835UVA1-A1 | XINGLIGHT | SMD | 2835 HP; λp 360-375 nm (370 typ), Φe 150-220 mW @120 mA, Vf 3.2-4.0 V, If max 150 mA, Pd 600 mW [ds] — API description is empty; specs from datasheet | Ext | 15,170 | 0.0516 |
| C2837382 | MHP1016UVACT | MEIHUA | SMD,1.6x1.1mm | 1.6x1.1 mm; 370 nm, 20 mA, Vf 3.7 V, 110 mW | Ext | 3,192 | 0.1647 |
| C25170633 | JNJ-L-3535AW120B-36530-SL-G1 | JNJ OPTOELECTRONICS | SMD3535-3P | 3535; 365 nm, 500 mA, Vf 4.8 V, 1.5 W | Ext | 4,069 | 0.6032 |
| C46641552 | P2835P1UVS26G12Q-365 | Silverlight | SMD2835-2P | 2835; 365 nm (from MPN); no description or datasheet at JLCPCB | Ext | 6,211 | 0.0488 |

* No datasheet among the violet/UV/purple parts gives an IEC 62471 risk group; they carry only generic 'do not look into the LED' warnings.  The 2835 parts emitting 45-220 mW at 365-400 nm should be treated as eye hazards at close range (diffuse or shield them, keep them out of direct view of a child).
* The 'purple' parts rated in mcd at 5 mA (Vf ~2.6-3.1 V) behave like phosphor-converted purple/pink emitters (no datasheet gives a spectrum); the violet InGaN parts (Vf ~3.0-3.6 V) look dim and deep-violet because the eye's photopic sensitivity at 400 nm is only ~0.04 % of its 555 nm peak, yet their 45-180 mW of radiant power makes fluorescent inks and glow-in-the-dark pigments light up strongly.
* None of these LEDs is Basic or Preferred.

## c. Constant-current LED driver ICs (high-resolution PWM)

**Recommendation:** LP5036RJVR (C701961, 17k in stock, 36 ch, 12-bit @29 kHz, I2C) for LEDs on a 5 V rail; TLC5971RGER (C543004, 16-bit ES-PWM, 60 mA, runs from 12 V) if 16-bit fades or series strings from 12 V matter. No LED driver is Basic.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **I2C drivers with >=12-bit PWM** | | | | | | | |
| C701961 ★ | LP5036RJVR | Texas Instruments | VQFN-46-EP(5x6) | 36 ch CC sink; 12-bit PWM @29 kHz (21 min); 8-bit colour x 8-bit brightness, log/lin curve; 35 mA/ch (VCC>=3.3 V); OUT<=6 V; I2C; VQFN-46 [ds] — TI LP50xx; deepest stock of any >=12-bit driver. LED anodes must be on a <=5.5 V rail (OUT abs max 6 V). | Ext | 16,987 | 0.8047 |
| C3202873 | IS31FL3205-QFLS4-TR | ISSI | QFN-20-EP(3x3) | 12 ch; selectable PWM 16-bit @244 Hz, 12-bit @3.9 kHz, 8-bit @62 kHz (16 MHz osc); 8-bit DC/ch + global; 38 mA; OUT<=6 V; I2C 1 MHz; QFN-20 3x3 [ds] — Lumissil/ISSI; only stocked ISSI part with 16-bit PWM (16-bit only at 244 Hz). | Ext | 5,000 | 0.4894 |
| C1850306 | LP5030RJVR | Texas Instruments | VQFN-46-EP(5x6) | 30 ch LP503x: 12-bit PWM @29 kHz; 8-bit colour + brightness; 35 mA/ch; OUT<=6 V; I2C; VQFN-46 [ds] | Ext | 8,455 | 0.6812 |
| C427525 | LP5024RSMR | Texas Instruments | VQFN-32-EP(4x4) | 24 ch LP50xx: 12-bit PWM @29 kHz; 25.5 mA/ch (35 mA at VCC>=3.3 V); I2C; VQFN-32 4x4 [ds] | Ext | 6,373 | 0.9381 |
| C2653373 | LP5018RSMR | Texas Instruments | VQFN-32-EP(4x4) | 18 ch LP50xx: 12-bit PWM @29 kHz; 35 mA/ch; I2C; VQFN-32 4x4 (same datasheet as LP5024) [ds] | Ext | 7,814 | 0.7316 |
| C1849481 | LP5012RUKR | Texas Instruments | WQFN-20-EP(3x3) | 12 ch LP50xx: 12-bit PWM @29 kHz; 35 mA/ch (VCC>=3.3 V); I2C; WQFN-20 3x3 [ds] | Ext | 3,499 | 0.7186 |
| **Serial-shift (SPI-style) drivers with 12-16-bit PWM** | | | | | | | |
| C543004 ★ | TLC5971RGER | Texas Instruments | VQFN-24-EP(4x4) | 12 ch; 16-bit ES-PWM (128 segments: ~19.5 kHz with int. 10 MHz osc; 16-bit frame 153 Hz); 7-bit BC/colour; 60 mA/ch; OUT<=17 V; 2-wire 20 MHz; VQFN-24 [ds] — VCC 6-17 V via internal 3.3 V LDO (or 3-5.5 V direct): can sit on the 12 V rail and sink series strings; cascades on 2 wires. | Ext | 3,975 | 1.1591 |
| C116842 | TLC59711PWPR | Texas Instruments | HTSSOP-20-EP | 12 ch; 16-bit ES-PWM; 7-bit BC/colour; 60 mA/ch; LED supply <=17 V; int. LDO 4-17 V or 3-5.5 V direct; 2-wire; HTSSOP-20 [ds] — TLC5971 sibling with clock-fail watchdog; Adafruit breakout exists. | Ext | 3,801 | 2.0126 |
| C110098 | MBI5043GP-A | MBI | SSOP-24 | 16 ch; 16-bit S-PWM (64 x 10-bit sub-periods; ext. GCLK <=33 MHz -> ~32 kHz refresh, 504 Hz frame); 6-bit gain; 45 mA @5 V, 30 mA @3.3 V; OUT<=17 V; SSOP-24 [ds] — Macroblock; cheapest 16-bit option, but the MCU must supply a continuous GCLK (PWM/PIO pin). | Ext | 5,586 | 0.4334 |
| C702083 | TLC5947RHBR | Texas Instruments | VFQFN-32-EP(5x5) | 24 ch; 12-bit PWM from int. 4 MHz osc -> ~977 Hz (586-1370 Hz); 30 mA/ch; OUT<=30 V; SPI-style 30 MHz; VQFN-32 5x5 [ds] — Self-clocked (no GSCLK needed); Adafruit breakout exists. | Ext | 2,722 | 2.0224 |
| C181653 | TLC5940PWPR | Texas Instruments | TSSOP-28-EP | 16 ch; 12-bit PWM from ext. GSCLK <=30 MHz (<=7.3 kHz; MCU drives GSCLK + BLANK); 6-bit dot correction; 120 mA/ch; OUT<=17 V; HTSSOP-28 [ds] — Old but well known; needs continuous MCU clocking. | Ext | 1,922 | 1.8273 |
| C702086 | TLC5955DCAR | Texas Instruments | HTSSOP-56-6.1mm | 48 ch; 16-bit ES-PWM or conventional PWM; dot/brightness/max-current correction; 31.9 mA/ch (VCC>3.6 V); SPI-style; HTSSOP-56 [ds] — Stock under 1000. | Ext | 954 | 2.7604 |
| **8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)** | | | | | | | |
| C5125743 ★ | AW21036QNR | AWINIC | QFN-44-EP(5x5) | 36 ch; 8-bit PWM (122 Hz-62 kHz, 16 MHz osc) x 8-bit DC colour current; <=50 mA/ch; I2C 400 kHz; QFN-44 5x5 [ds] — Awinic; 8-bit PWM, but PWM x DC current spans ~65000:1 for dim fades. Cheap ($0.40). | Ext | 4,716 | 0.3983 |
| C2678558 | PCA9956BTWY | NXP Semicon | TSSOP-38-EP | 24 ch; 8-bit PWM @31.25 kHz + 8-bit IREF DAC (0.225-57 mA); OUT<=20 V; I2C Fm+ 1 MHz; TSSOP-38 [ds] — NXP; OUT<=20 V allows series strings from 12 V. | Ext | 5,070 | 1.5574 |
| C2940546 | IS31FL3218-QFLS2-TR | ISSI | QFN-24-EP(4x4) | 18 ch; 8-bit (256-step) PWM; 38 mA/ch; I2C 400 kHz; QFN-24 4x4 [ds] — Requested; 8-bit only. | Ext | 2,103 | 0.4032 |
| C2940604 | IS31FL3741A-QFLS4-TR | ISSI | QFN-60-EP(7x7) | 39x9 matrix (351 LEDs); 8-bit PWM + 8-bit DC scaling; 29k/3.6k/1.8k/900 Hz; 38 mA; I2C; QFN-60 7x7 [ds] — Requested; matrix-scanned (1/9 duty per LED). | Ext | 2,315 | 2.7214 |
| C92206 | PCA9685PW/Q900,118 | NXP Semicon | TSSOP-28 | 16 ch; 12-bit PWM but only 24-1526 Hz; NOT constant-current (push-pull 25 mA sink/10 mA source, needs resistors); I2C 1 MHz; TSSOP-28 [ds] — Requested. | Ext | 1,131 | 2.4304 |
| C148077 | AW9523BTQR | AWINIC | TQFN-24-EP(4x4) | 16-ch I/O expander with LED mode: 256-step linear constant-current dimming (no PWM, so no flicker); 37 mA/ch; I2C; TQFN-24 4x4 [ds] — Deepest stock of anything here (~77k), but only 8-bit linear current steps. | Ext | 76,798 | 0.2585 |
| **Alternative: RGB LEDs with a built-in 16-bit driver (no driver IC)** | | | | | | | |
| C22371534 ★ | WS2816B | Worldsemi | SMD5050-6P | 5050 RGB LED + 3-ch CC driver; 16-bit PWM/ch (+4-bit gamma), 10 kHz refresh; single-wire 800 kbit/s; 3.3-5.5 V [ds] — Can mix orange/purple from RGB; not a standalone driver. | Ext | 14,402 | 0.0636 |
| C4154877 | WS2816B-2020 | Worldsemi | SMD-6P,2.2x2mm | 2.2x2 mm WS2816B: 16-bit PWM, 10 kHz refresh; 3.7-5.5 V | Ext | 12,368 | 0.0831 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **IS31FL3237** — C2678924 IS31FL3237-QFLS4-TR: stock 12 (36 ch, 16-bit capable) - too few [re-queried: C2678924 IS31FL3237-QFLS4-TR (stock 12)]
* **IS31FL3236** — C5714539 IS31FL3236-TQLS2-TR stock 41, C5555029 stock 1; QFN-44 versions stock 0 (8-bit anyway) [re-queried: C246443 IS31FL3236A-QFLS2-TR (stock 200), C5714539 IS31FL3236-TQLS2-TR (stock 41), C3198350 IS31FL3236A-QFLS4-TR (stock 38), C5555029 IS31FL3236-TQLS2 (stock 1)]
* **IS31FL3236A** — C246443 IS31FL3236A-QFLS2-TR stock 200 (API text oddly says 9 mA, "Digital Tube Drivers"); C3198350 -QFLS4-TR stock 38. Clone HTR3236SQER C46955895: stock 1815, 8-bit [re-queried: C246443 IS31FL3236A-QFLS2-TR (stock 200), C3198350 IS31FL3236A-QFLS4-TR (stock 38), C6280186 IS31FL3236A-TQLS4 (stock 0), C2889039 IS31FL3236A-TQLS4-TR (stock 0)]
* **IS31FL3743** — C2678953 IS31FL3743A, C2962218 and C2678805 IS31FL3743B: stock 0 [re-queried: C2678805 IS31FL3743B-QULS4-TR (stock 0), C2678953 IS31FL3743A-QULS4-TR (stock 0), C2962218 IS31FL3743B-QULS4-TR (stock 0), C4054377 IS31FL3743B-QULS4-TR (stock 0)]
* **IS31FL3746** — C2961656 IS31FL3746A, C1882554 IS31FL3746B: stock 0 [re-queried: C1882554 IS31FL3746B-QFLS4-TR (stock 0), C2961656 IS31FL3746A-QFLS4-TR (stock 0)]
* **AW20036** — C401019 AW20036QNR stock 458; 3x12 matrix, 256-level FADE + 64-level DIM, i.e. 8-bit [ds] [re-queried: C401019 AW20036QNR (stock 458)]
* **AW20054** — C401020 AW20054QNR stock 192 [re-queried: C401020 AW20054QNR (stock 192)]
* **KTD2058** — C19842510 KTD2058EUAC-TR stock 0; the search also returns unrelated NPN transistors named KTD2058 (C2910316, C69775) [re-queried: C2910316 KTD2058 (stock 520), C69775 KTD2058-Y-U/PF (stock 0), C19842510 KTD2058EUAC-TR (stock 0)]
* **KTD2061** — C5224493 KTD2061EUAC-TR and C19842512 KTD2061QGUAC-TR stock 0; C112866 is an unrelated KEC NPN [re-queried: C112866 KTD2061-Y-U/PF (stock 0), C5224493 KTD2061EUAC-TR (stock 0), C19842512 KTD2061QGUAC-TR (stock 0)]

## d. Microcontrollers / FPGA and their crystals

**Recommendation:** RP2354A (C41378174, 16k, 2 MB flash on chip) + ABM8-272-T3 (C20625731) + AOTA-B201610S3R3-101-T (C42411119, only 677 in stock: enough for a prototype run). No MCU is Basic; STM32G474 is shallow (<=620), so use STM32G431CBT6 (C529355, 4k) if an STM32 is wanted; ESP32-C3FH4 (C2858491, 5.7k) + 40 MHz XL2EL89COI-111YLC-40M (C18214314) for Wi-Fi.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **RP2350 / RP2354 (Raspberry Pi)** | | | | | | | |
| C41378174 ★ | RP2354A | Raspberry Pi | QFN-60(7x7) | 2x Cortex-M33 or Hazard3 RISC-V @150 MHz; 520 KB SRAM; 2 MB stacked flash; 30 GPIO, 4 ADC; 12 PIO SMs; 24 PWM; QFN-60 7x7 [ds] — No external QSPI flash needed. | Ext | 16,231 | 1.2030 |
| C39843328 | RP2354B | Raspberry Pi | QFN-80-EP(10x10) | As RP2354A but 48 GPIO, 8 ADC; 2 MB stacked flash; QFN-80 10x10 [ds] — Stock under 2000. | Ext | 1,682 | 1.3835 |
| C42411118 | RP2350A | Raspberry Pi | QFN-60-EP(7x7) | As RP2354A without flash (needs external QSPI flash); 30 GPIO; QFN-60 7x7 [ds] | Ext | 6,951 | 1.1234 |
| C42415655 | RP2350B | Raspberry Pi | QFN-80-EP(10x10) | No flash; 48 GPIO, 8 ADC; QFN-80 10x10 [ds] | Ext | 3,255 | 1.1266 |
| C2040 | RP2040 | Raspberry Pi | LQFN-56(7x7) | 2x Cortex-M0+ @133 MHz; 264 KB SRAM; external flash; 30 GPIO; LQFN-56 7x7 — Not requested: deep-stock fallback (64k). | Ext | 64,405 | 0.7576 |
| **RP2350 12 MHz crystal** | | | | | | | |
| C20625731 ★ | ABM8-272-T3 | Abracon LLC | SMD3225-4P | 12 MHz, CL 10 pF, +/-30 ppm, ESR 50 ohm, 3.2x2.5 mm — The crystal the RP2350 datasheet (sec 8.2.1.1) recommends and Pico 2 is tuned for [ds]. | Ext | 10,462 | 0.4048 |
| C9002 | X322512MSB4SI | YXC Crystal Oscillators | SMD3225-4P | 12 MHz, CL 20 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 80 ohm, 3.2x2.5 mm — BASIC part, but higher CL/ESR than RPi specifies: needs bigger load caps and a start-up check. | Basic | 133,361 | 0.0760 |
| **RP2350 regulator inductor (3.3 uH)** | | | | | | | |
| C42411119 ★ | AOTA-B201610S3R3-101-T | Abracon LLC | 0806 | 3.3 uH, 2016 (0806), Isat 2.4 A, Irms 2.1 A, DCR 115 mohm, polarity-marked — RP2350 ds sec 6.3.8.2 requires a shielded, polarity-marked 3.3 uH (Isat>=1.5 A, DCR<=250 mohm) and names this part [ds]. Only 677 in stock. | Ext | 667 | 0.2239 |
| C5832345 | FTC201610S3R3MBCA | cjiang | 0806 | 3.3 uH, 2016 (0806), Isat 2.3 A, Irms 1.7 A, DCR 140 mohm, molded — Fallback only: NOT polarity-marked, which the RP2350 ds requires. | Ext | 3,357 | 0.0389 |
| C18724415 | FTC201612S3R3MBCA | cjiang | 0806 | 3.3 uH, 2016 (0806), 1.2 mm tall, Isat 2.7 A, Irms 2.4 A, DCR 165 mohm, molded — Fallback only: NOT polarity-marked. | Ext | 3,422 | 0.0383 |
| **STM32** | | | | | | | |
| C529355 ★ | STM32G431CBT6 | STMicroelectronics | LQFP-48(7x7) | Cortex-M4F @170 MHz; 128 KB flash, 32 KB RAM; 38 GPIO; LQFP-48 7x7 — Best-stocked STM32G4; the G4 family has motor-control timers, CORDIC, comparators and op-amps. | Ext | 4,137 | 4.3422 |
| C529356 | STM32G431CBU6 | STMicroelectronics | UFQFPN-48(7x7) | Cortex-M4F @170 MHz; 128 KB flash, 32 KB RAM; 42 GPIO; UFQFPN-48 7x7 | Ext | 4,203 | 5.8524 |
| C730123 | STM32G474CBT6 | STMicroelectronics | LQFP-48_7x7 | Cortex-M4F @170 MHz; 128 KB flash, 128 KB RAM; 38 GPIO; LQFP-48 — G474 adds the HRTIM. All G474 packages are shallow (<=620). | Ext | 620 | 3.5066 |
| C521608 | STM32G474RET6 | STMicroelectronics | LQFP-64(10x10) | Cortex-M4F @170 MHz; 512 KB flash, 128 KB RAM; 52 GPIO; LQFP-64 — 381 in stock, ~$10. | Ext | 432 | 10.1441 |
| C529341 | STM32G071C8T6 | STMicroelectronics | LQFP-48(7x7) | Cortex-M0+ @64 MHz; 64 KB flash, 36 KB RAM; 44 GPIO; LQFP-48 | Ext | 5,566 | 1.4225 |
| C3446137 | STM32G0B1VCT6 | STMicroelectronics | LQFP-100(14x14) | Cortex-M0+ @64 MHz; 256 KB flash, 144 KB RAM; 94 GPIO; LQFP-100 — Smaller G0B1 packages are <450 in stock. | Ext | 1,179 | 3.1083 |
| **ESP32 bare chips** | | | | | | | |
| C2858491 ★ | ESP32-C3FH4 | Espressif Systems | QFN-32-EP(5x5) | RISC-V @160 MHz; 400 KB SRAM; 4 MB in-package flash; 22 GPIO; Wi-Fi 4 + BLE 5; QFN-32 5x5 [ds] — No external flash needed; needs a 40 MHz crystal + RF matching network. | Ext | 5,735 | 1.4908 |
| C2838500 | ESP32-C3 | Espressif Systems | QFN-32-EP(5x5) | RISC-V @160 MHz; 400 KB SRAM; no flash (external SPI flash required); 22 GPIO; QFN-32 5x5 [ds] | Ext | 7,429 | 1.2746 |
| C3013940 | ESP32-S3FH4R2 | Espressif Systems | QFN-56(7x7) | Dual Xtensa LX7 @240 MHz; 4 MB flash + 2 MB PSRAM in package; Wi-Fi 4 + BLE 5; QFN-56 7x7 — Best-stocked S3 chip. | Ext | 2,056 | 2.5101 |
| C2913196 | ESP32-S3FN8 | Espressif Systems | QFN-56-EP(7x7) | Dual Xtensa LX7 @240 MHz; 512 KB SRAM; 8 MB in-package flash; 45 GPIO; QFN-56 7x7 — 605 in stock. | Ext | 605 | 2.5995 |
| C2913192 | ESP32-S3 | Espressif Systems | QFN-56-EP(7x7) | Dual Xtensa LX7 @240 MHz; no flash; QFN-56 7x7 — 762 in stock. | Ext | 762 | 2.0549 |
| C5364646 | ESP32-C6 | Espressif Systems | QFN-40-EP(5x5) | RISC-V @160 MHz; 512 KB SRAM; Wi-Fi 6 + BLE 5 + 802.15.4; no flash; 30 GPIO; QFN-40 5x5 — Only 287 in stock; ESP32-C6FH4/FH8 stock 0. | Ext | 287 | 1.8305 |
| **ESP32 40 MHz crystal** | | | | | | | |
| C18214314 ★ | XL2EL89COI-111YLC-40M | YXC Crystal Oscillators | SMD3225-4P | 40 MHz, CL 12 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 40 ohm, 3.2x2.5 mm | Ext | 41,840 | 0.0649 |
| C3003278 | 5YMA40000151SF40E1 | Interquip | SMD3225-4P | 40 MHz, CL 15 pF, +/-10 ppm tol, +/-10 ppm stab, ESR 40 ohm, 3.2x2.5 mm, -20..+85 C — Tightest stability. | Ext | 32,550 | 0.0621 |
| C7420757 | SX32Y040000BF1T001 | TKD | SMD3225-4P | 40 MHz, CL 15 pF, +/-10 ppm tol, +/-30 ppm stab, ESR 20 ohm, 3.2x2.5 mm — Deepest stock (59k). | Ext | 59,352 | 0.0545 |
| C18213370 | K3A400001210 | KYX | SMD3225-4P | 40 MHz, CL 12 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 30 ohm, 3.2x2.5 mm — Cheapest. | Ext | 23,248 | 0.0470 |
| **FPGA** | | | | | | | |
| C2678152 ★ | ICE40UP5K-SG48I | Lattice | QFN-48-EP(7x7) | iCE40 UltraPlus: 5280 LUTs, 1 Mbit SPRAM + BRAM, 39 I/O, 1.2 V core; QFN-48 7x7 — Only 182 in stock, ~$8; no other iCE40 or Gowin part above 50. | Ext | 182 | 8.1039 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **STM32G474** — usable but shallow in every package: CBT6 C730123 620, QET6 611, CCT6 460, RET6 C521608 381 (~$10), VET6 43, CEU6 35 [re-queried: C730129 STM32G474QET6 (stock 621), C730123 STM32G474CBT6 (stock 620), C730124 STM32G474CCT6 (stock 460), C521608 STM32G474RET6 (stock 381)]
* **ESP32-C6F** — ESP32-C6FH4 C6908287 and ESP32-C6FH8 C41459370 stock 0; bare ESP32-C6 C5364646 only 287 (modules: ESP32-C6-WROOM-1-N8 C5366877 3177) [re-queried: C6908287 ESP32-C6FH4 (stock 0), C41459370 ESP32-C6FH8 (stock 0)]
* **ICE40UP5K** — only ICE40UP5K-SG48I C2678152 (182); -UWG30ITR C2678192 and -SG48ITR50 C2889329 stock 0; no Gowin GW1N in stock [re-queried: C2678152 ICE40UP5K-SG48I (stock 182), C22335778 ICE40UP5K-B-EVN (stock 0), C2678192 ICE40UP5K-UWG30ITR (stock 0), C2889329 ICE40UP5K-SG48ITR50 (stock 0)]

* No microcontroller or FPGA is Basic.  The Basic crystals are 32.768 kHz, 8, 12, 16 and 25 MHz parts (e.g. X322512MSB4SI C9002 at 12 MHz); there is no Basic 40 MHz crystal for the ESP32s.

## e. Coil power stage (12 V, 1-3 A per phase)

**Recommendation:** Coil phases: DRV8316RRGFR (35 V, 8 A peak, 3 half-bridges) or, for 4 independent half-bridges with deep stock, DRV8844PWPR; DRV8874PWPR for single H-bridges; AO3400A (Basic) for simple low-side switching.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **3-phase drivers (integrated FETs)** | | | | | | | |
| C5218861 ★ | DRV8316RRGFR | Texas Instruments | VQFN-40(5x7) | 3 half-bridges, 4.5-35 V (40 V abs), 8 A peak, 95 mOhm HS+LS, 6x/3x PWM up to 200 kHz, SPI, integrated current sense, 3.3/5 V buck, VQFN-40 7x5 [ds] — Most margin for 1-3 A/phase at 12 V; DRV8316CRRGFR (C5447274, ~2.7k) is a second stocked variant | Ext | 2,773 | 3.3717 |
| C92482 | DRV8313PWPR | Texas Instruments | HTSSOP-28 | 3 independent half-bridges (EN+IN each), 8-60 V, 2.5 A peak, 0.24+0.24 Ohm, 3.3 V/10 mA LDO, spare comparator, HTSSOP-28 [ds] — SimpleFOC classic; 2.5 A is peak, plan on ~1.5 A continuous | Ext | 6,751 | 3.0855 |
| C5218862 | DRV8311HRRWR | Texas Instruments | WQFN-24(3x3) | 3 half-bridges, 3-20 V (24 V abs max), 5 A peak, 210 mOhm HS+LS, 6x/3x PWM (H = hardware variant), integrated current sense, WQFN-24 3x3 [ds] — Cheap with deep stock, but 24 V abs max is tight on a 12 V rail clamped by a 15 V TVS | Ext | 18,097 | 0.9933 |
| C3655732 | MP6536DU-LF-Z | Monolithic Power Systems | QFN-40(5x5) | 3 half-bridges, 5-26 V, 5.5 A peak, 140 mOhm, QFN-40 5x5 (API) — Requested; only ~1.2k in stock | Ext | 1,160 | 2.3114 |
| C5296869 | AT8313QNR | ZHONGKEWEI | QFN-36 | DRV8313-style triple half-bridge, 8-35 V, 2.5 A, 450 mOhm, QFN-36 (API) | Ext | 4,448 | 0.7641 |
| **Single H-bridge drivers (integrated FETs)** | | | | | | | |
| C1855818 ★ | DRV8874PWPR | Texas Instruments | HTSSOP-16-EP | 4.5-37 V, 6 A peak, 100+100 mOhm, PMODE: PH/EN, PWM or independent half-bridge, PWM <=100 kHz, IPROPI current sense/regulation, HTSSOP-16 [ds] — Two of these = dual H-bridge (or 4 independent half-bridges) | Ext | 28,928 | 0.6552 |
| C2827823 | AT8236 | ZHONGKEWEI | ESOP-8 | 5.5-36 V, 6 A peak / 4 A continuous, 200 mOhm HS+LS, IN1/IN2 PWM <=100 kHz, VREF current limit, ESOP-8 [ds] — ZHONGKEWEI, Chinese-only datasheet; very deep stock and cheap | Ext | 86,188 | 0.3040 |
| C86590 | DRV8870DDAR | Texas Instruments | HSOP-8-EP | 6.5-45 V, 3.6 A peak, 565 mOhm HS+LS, IN1/IN2 PWM, current regulation with external sense resistor, SO-8 PowerPAD [ds] — Deepest stock of any H-bridge | Ext | 114,243 | 0.2694 |
| C545417 | TB67H450FNG,EL | TOSHIBA | HSOP-8-EP | 4.5-44 V (50 V abs), 3.5 A max, 0.6 Ohm HS+LS, IN1/IN2 direct PWM or constant-current chopper, HSOP-8 [ds] | Ext | 32,578 | 0.3544 |
| C75864 | DRV8871DDAR | Texas Instruments | SO-8-EP | 6.5-45 V, 3.6 A peak, 565 mOhm HS+LS, IN1/IN2 PWM, internal current regulation (no sense resistor), SO-8 PowerPAD [ds] — Requested; ~4x the DRV8870 price | Ext | 9,454 | 1.0957 |
| **Dual H-bridge / multi half-bridge drivers (integrated FETs)** | | | | | | | |
| C177807 ★ | DRV8844PWPR | Texas Instruments | HTSSOP-28 | 4 independent half-bridges (EN+IN each), 8-60 V, 2.5 A peak / 1.75 A rms per ch (24 V, 25 C), 0.24+0.24 Ohm, HTSSOP-28 [ds] — 3 coil phases + 1 spare (or 2 H-bridges) from one chip | Ext | 31,019 | 0.7722 |
| C36542 | DRV8841PWPR | Texas Instruments | HTSSOP-28 | Dual H-bridge, 8.2-45 V, 2.5 A peak at 24 V, 400 mOhm HS+LS, IN/IN PWM, 2-bit current control, HTSSOP-28 [ds] | Ext | 6,964 | 0.9007 |
| C2150710 | TMC2209-LA-T | TRINAMIC Motion Control GmbH | QFN-28-EP(5x5) | 2-coil stepper driver, 4.75-29 V, 2 A, 340 mOhm, 256 microsteps, STEP/DIR + UART, QFN-28 5x5 (API) — Current-regulated sinusoidal drive of 2 coils without firmware PWM | Ext | 15,932 | 1.7964 |
| C112630 | BTN8962TAAUMA1 | Infineon Technologies | TO-263-7 | Single high-current half-bridge (Infineon NovalithIC), 8-18 V, IN/INH inputs, over-current/short/over-temp protection, TO-263-7 (API) — Only stocked BTN/BTS part (BTS7960 out of stock); oversized for 1-3 A | Ext | 10,571 | 1.7314 |
| **Gate drivers (for discrete MOSFETs)** | | | | | | | |
| C3655801 ★ | DRV8300DRGER | Texas Instruments | VQFN-24(4x4) | 3-phase 100 V gate driver, GVDD 5-20 V, 750 mA source / 1.5 A sink, integrated bootstrap diodes (D variant), cross-conduction prevention, VQFN-24 4x4 [ds] — Pair with 3x AON7934 | Ext | 25,737 | 0.3853 |
| C91879 | LM5106MMX/NOPB | Texas Instruments | VSSOP-10-0.5mm | 100 V half-bridge, 1.2 A source / 1.8 A sink, single PWM input + EN, programmable dead time, VDD 8-14 V, VSSOP-10 [ds] | Ext | 35,671 | 0.3366 |
| C2960 | IR2104STRPBF | Infineon Technologies | SOIC-8 | 600 V half-bridge, IN + /SD, internal dead time, VCC 10-20 V, 130/270 mA, SOIC-8 (API) | Ext | 39,436 | 0.8438 |
| C480653 | EG2104M | EG Micro | SOIC-8 | IR2104-style half-bridge, 600 V bootstrap, VCC 10-20 V, 3.3/5 V logic inputs, built-in dead time, 0.3/0.6 A, SOIC-8 [ds] — Cheap Chinese IR2104 equivalent | Ext | 28,804 | 0.2530 |
| C913823 | UCC27201ADR | Texas Instruments | SOIC-8 | 120 V half-bridge, 3 A source/sink, independent HI/LI inputs (no dead time), VDD 8-17 V, SOIC-8 (API) | Ext | 11,564 | 0.5121 |
| **N-MOSFETs (single/dual)** | | | | | | | |
| C20917 ★ | AO3400A | Alpha & Omega Semicon | SOT-23 | N, 30 V, 5.7 A, 48 mOhm @2.5 V Vgs, SOT-23 (API) — Basic; low-side coil/LED switch straight from 3.3 V logic, ~2-3 A | Basic | 908,636 | 0.0716 |
| C22469448 | HL3400 | hongjiacheng | SOT-23 | N, 30 V, 5.6 A, 21/25/33 mOhm @10/4.5/2.5 V, SOT-23 (API) — AO3400A equivalent | Preferred | 1,392,989 | 0.0420 |
| C485677 | AON7934 | Alpha & Omega Semicon | DFN-8(3x3) | Dual asymmetric N half-bridge (S1/D2 tied), 30 V, Q1 <10.2 / Q2 <7.7 mOhm @10 V (<15.8/<11.6 @4.5 V), 16/18 A, DFN3x3 [ds] — One per phase with DRV8300/LM5106 | Ext | 128,893 | 0.1769 |
| C477943 | AO4882 | Alpha & Omega Semicon | SOIC-8 | Dual N (independent), 40 V, 27 mOhm @4.5 V, SOIC-8 (API) | Ext | 51,159 | 0.2476 |
| C2944312 | AO4406A | UMW | SOP-8 | N, 30 V, 12 A, 10 mOhm @10 V, SOP-8 (API) — UMW second source of the AOS part; for ~5 A low-side | Ext | 34,466 | 0.0945 |
| C53550 | IRLML6344TRPBF | Infineon Technologies | SOT-23 | N, 30 V, 5 A, 29 mOhm @4.5 V, SOT-23 (API) | Ext | 21,539 | 0.1511 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **DRV8317** — only C6022114 DRV8317HREER, stock 4 [re-queried: C6022114 DRV8317HREER (stock 4)]
* **TMC6300** — C5274455 TMC6300-LA-T stock 7 (and 2-11 V only) [re-queried: C5274455 TMC6300-LA-T (stock 7), C5196961 TMC6300-LA (stock 0), C17205301 TMC6300-BOB (stock 0)]
* **L6234** — C1523896 L6234PD stock 3; others 0 [re-queried: C1523896 L6234PD (stock 3), C19842 L6234d (stock 0), C77581 L6234PD013TR (stock 0)]
* **DRV8412** — C79852 DRV8412DDWR stock 264 only [re-queried: C79852 DRV8412DDWR (stock 264), C1523831 DRV8412DDW (stock 0)]
* **DRV8432** — C79853 DRV8432DKDR stock 13 [re-queried: C79853 DRV8432DKDR (stock 13), C2861841 DRV8432DKD (stock 0)]
* **BTS7960** — C5122776 BTS7960B stock 0 (BTN7960 also 0) [re-queried: C5122776 BTS7960B (stock 0)]
* **DRV8833** — stocked (C50506, ~7.5k) but VM max 10.8 V: unusable on 12 V [re-queried: C50506 DRV8833PWPR (stock 7,474), C55566425 DRV8833RTYR-JSM (stock 4,990), C53055901 DRV8833PWPR-HX (stock 2,659), C191171 DRV8833CPWPR (stock 619)]
* **AT8833** — stocked (C575404 ~8.4k, C5120769 ~10.8k) but 2.7-15 V, 1.2 A: marginal at 12 V [re-queried: C5120769 AT8833CQ (stock 10,846), C575404 AT8833CT (stock 8,401)]
* **TB6612FNG** — stocked (C141517 ~5.7k) but VM 15 V max, ~1.2 A avg: marginal at 12 V [re-queried: C141517 TB6612FNG(O,C,8,EL (stock 5,748), C88224 TB6612FNG(O,C,8,EL (stock 5,417), C911133 TB6612FNG,C,8,EL (stock 0)]

* Only four MOSFETs are Basic and in stock: 2N7002 (C8545), AO3400A (C20917), AO3401A (C15127) and SI2301CDS-T1-GE3 (C10487); HL3400 (C22469448) is a Preferred AO3400A equivalent.
* No motor driver or gate driver (BLDC, brushed-DC, stepper or gate-driver categories) is Basic.

## f. 12 V input: jack, protection, bulk capacitance

**Recommendation:** DC-005-5A-2.0 jack (C381116) -> TPS259474LRPWR eFuse (or AO4407A P-FET + 2920L500 PTC) -> SMBJ15A (Preferred) TVS -> MA35V470M10X13 polymer bulk cap.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **Barrel jacks (5.5 mm, >=5 A)** | | | | | | | |
| C381116 ★ | DC-005-5A-2.0 | XKB Connection | Plugin | THT right-angle, 2.0 mm pin (5.5x2.1 plugs), 5 A, 24 V (API) | Ext | 30,504 | 0.2073 |
| C17701683 | DC007B-2.0 | SHOU HAN | Plugin | THT right-angle, 2.0 mm pin, 7 A, 20 V (API) | Ext | 24,649 | 0.2602 |
| C720558 | DC-005-A250 | XUNPU | Plugin | THT right-angle, 2.5 mm pin (5.5x2.5 plugs), 5 A, 24 V (API) | Ext | 23,595 | 0.1343 |
| C129006 | DC-044A-20A | Korean Hroparts Elec | Plugin | THT right-angle, 2.0 mm pin, 5 A, 30 V, low profile (7.2 mm) (API) | Ext | 13,177 | 0.2070 |
| C17701686 | DC007B-2.5-J | SHOU HAN | Plugin | THT right-angle, 2.5 mm pin, 7 A, 20 V (API) | Ext | 26,301 | 0.2959 |
| C22434687 | PJ-002AH-SMT-TR | CUI | SMD | SMD right-angle, 2.0 mm pin, 5 A, 24 V (API) — Only SMD >=5 A jack with stock >1k | Ext | 1,145 | 1.2713 |
| **TVS (~15 V)** | | | | | | | |
| C19077569 ★ | SMBJ15A | hongjiacheng | DO-214AA(SMB) | Unidirectional 600 W, VRWM 15 V, VBR 16.7 V min, VC 24.4 V @24.6 A, SMB (API) | Preferred | 7,969 | 0.0402 |
| C19077571 | SMBJ16A | hongjiacheng | DO-214AA(SMB) | Unidirectional 600 W, VRWM 16 V, VC 26 V @23 A, SMB (API) — much deeper stock than SMBJ15A | Preferred | 125,452 | 0.0290 |
| C19077535 | SMAJ15A | hongjiacheng | DO-214AC(SMA) | Unidirectional 400 W, VRWM 15 V, VC 24.4 V @16.4 A, SMA (API) | Preferred | 108,709 | 0.0371 |
| C113988 | SMBJ15A | MDD | DO-214AA(SMB) | Unidirectional 600 W, VRWM 15 V, VC 24.4 V @24.6 A, SMB (API) | Ext | 134,497 | 0.0485 |
| **Reverse-polarity P-MOSFETs** | | | | | | | |
| C2841482 ★ | AO4407A | UMW | SOP-8 | P, -30 V, 14 A, 9.5 mOhm @10 V, SOP-8 (API) — UMW; ~0.24 W at 5 A. Add a zener gate clamp if Vin can exceed the Vgs rating | Ext | 106,457 | 0.1010 |
| C15127 | AO3401A | Alpha & Omega Semicon | SOT-23 | P, -30 V, 4 A, 47 mOhm @10 V, SOT-23 (API) — Basic; only for <=2 A | Basic | 792,424 | 0.0821 |
| C2944310 | AO4435 | UMW | SOP-8 | P, -30 V, 12 A, 15 mOhm @10 V, SOP-8 (API) | Ext | 112,012 | 0.0846 |
| C431196 | AONR21357 | Alpha & Omega Semicon | DFN-8(3x3) | P, -30 V, 34 A, 12.3 mOhm @4.5 V, DFN3x3 (API) — Genuine AOS | Ext | 61,207 | 0.2803 |
| C400894 | AOD4185 | Alpha & Omega Semicon | TO-252(DPAK) | P, -40 V, 40 A, 15 mOhm @10 V, TO-252 (API) — Genuine AOS; 40 V margin | Ext | 42,545 | 0.2910 |
| **Fuses / PTC** | | | | | | | |
| C19078763 ★ | 2920L500/30GR | LUTE | 2920 | PTC, 5 A hold / 10 A trip, 30 V, 40 A max, 2920 (API) | Ext | 98,654 | 0.1342 |
| C20539728 | BSMD2920-500-30V | BHFUSE | 2920 | PTC, 5 A hold / 10 A trip, 30 V, 2920 (API) | Ext | 46,180 | 0.1740 |
| C41367230 | BSMD1206C-1700T | BHFUSE | 1206 | One-time fuse, 7 A, 32 V, 150 A breaking, 1206 (API) — 7 A rating for a 5 A load (derating) | Ext | 36,910 | 0.0568 |
| C48467 | 0451005.MRL | Littelfuse | 2410 | One-time fuse (Littelfuse NANO2), 5 A, 125 V, 50 A breaking, 2410 (API) | Ext | 33,333 | 0.1956 |
| C41367229 | BSMD1206C-1500T | BHFUSE | 1206 | One-time fuse, 5 A, 32 V, 150 A breaking, 1206 (API) | Ext | 63,732 | 0.0501 |
| **eFuse ICs** | | | | | | | |
| C2864845 ★ | TPS259474LRPWR | Texas Instruments | VQFN-10-HR(2x2) | TPS25947: 2.7-23 V, 28 mOhm, 0.5-6 A adj. ILIM (circuit breaker), adj. OVLO, true reverse blocking, -15 V reverse-polarity tolerant, latch-off, VQFN-10 2x2 [ds] — Replaces the P-FET + PTC; A (auto-retry) variant C3662807 has only ~400 stock | Ext | 3,772 | 0.7885 |
| C165131 | TPS259241DRCR | Texas Instruments | VSON-10-EP(3x3) | TPS25924: 12 V eFuse, 4.5-13.8 V (20 V abs), fixed 15 V OV clamp, 1-5 A adj. ILIM, 28 mOhm, VSON-10 3x3 [ds] | Ext | 4,021 | 0.5349 |
| C471038 | TPS259571DSGR | Texas Instruments | WSON-8-EP(2x2) | TPS2595: 2.7-18 V, 34 mOhm, up to 4 A, no OV clamp, auto-retry, WSON-8 2x2 [ds] — Requested family; 4 A max | Ext | 11,914 | 0.4211 |
| C3662793 | TPS259470LRPWR | Texas Instruments | VQFN-10-HR(2x2) | TPS25947: 2.7-23 V, 28 mOhm, 0.5-6 A active current limit, adj. OVLO, reverse blocking, latch-off, VQFN-10 2x2 [ds] | Ext | 2,668 | 0.8990 |
| C544399 | TPS26600PWPR | Texas Instruments | HTSSOP-16-EP | TPS26600: 4.2-60 V, 150 mOhm, 0.1-2.23 A, HTSSOP-16 (API) — Requested; current too low for a 5 A input | Ext | 4,990 | 0.9771 |
| **Bulk capacitors (25 V+, 100-470 uF)** | | | | | | | |
| C46550472 ★ | MA35V470M10X13 | jieerrui | SMD,D10xL13mm | Polymer Al, 470 uF 35 V, 16 mOhm, 3.8 A ripple @100 kHz, 2000 h @105 C, D10x12.5 SMD (API) | Ext | 74,832 | 0.2618 |
| C46550466 | MA25V470M8x10 | jieerrui | SMD,D8xL10mm | Polymer Al, 470 uF 25 V, 25 mOhm, 4.1 A ripple, D8x10 SMD (API) — 25 V is marginal against a TVS clamp | Ext | 128,656 | 0.2223 |
| C46550469 | MA35V220M8X9 | jieerrui | SMD,D8xL9mm | Polymer Al, 220 uF 35 V, 28 mOhm, 2.9 A ripple, D8x9 SMD (API) | Ext | 56,429 | 0.2176 |
| C46550413 | JVJ35V470M10x10 | jieerrui | SMD,D10xL10.5mm | Al electrolytic, 470 uF 35 V, 320 mA ripple @120 Hz, 2000 h @105 C, D10x10.5 SMD (API) — Cheap but low ripple rating | Ext | 174,233 | 0.1314 |
| C48935389 | RV35V470M8X10 | jieerrui | SMD,D8xL10.5mm | Al electrolytic, 470 uF 35 V, 190 mA ripple @120 Hz, 5000 h @105 C, D8x10.5 SMD (API) | Ext | 154,529 | 0.1275 |
| C125977 | UWT1H221MNL1GS | Nichicon | SMD,D10xL10mm | Al electrolytic (Nichicon), 220 uF 50 V, 220 mA ripple @120 Hz, 1000 h @105 C, D10x10 SMD (API) | Ext | 262,473 | 0.1734 |

* No DC jack, resettable or one-time fuse, eFuse/power-distribution switch, aluminium electrolytic or polymer capacitor is Basic (each category searched with the Basic filter).
* The only Basic SMBJ/SMAJ TVS is SMBJ6.5CA (C7420377, 6.5 V bidirectional: unusable on 12 V); the hongjiacheng SMBJ15A/SMBJ16A/SMAJ15A are Preferred (no setup fee).

## g. Buck converters and power inductors

**Recommendation:** TPS54302DDCR (28 V, 3 A) + FXL0630 10/6.8 uH for 12->5/3.3 V (TPS5430DDAR + SS34 if Basic parts matter), TLV62569DBVR + 2.2 uH for 5->3.3 V.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **12V->5V/3.3V bucks 2-3 A** | | | | | | | |
| C311983 ★ | TPS54302DDCR | Texas Instruments | TSOT-23-6 | Sync, 4.5-28 V in (30 V abs), 3 A, fixed 400 kHz, Eco-mode, SOT-23-6; L = 10 uH (5 V) / 6.8 uH (3.3 V) [ds] — Best balance of input margin, size and stock | Ext | 78,316 | 0.2306 |
| C9864 | TPS5430DDAR | Texas Instruments | SOIC-8-EP | Non-sync, 5.5-36 V in (40 V abs), 3 A cont. (4 A peak), fixed 500 kHz, SOIC-8 PowerPAD; needs Schottky catch diode; datasheet example L = 15 uH [ds] — Basic part: no setup fee | Basic | 326,559 | 0.4113 |
| C116592 | TPS563201DDCR | Texas Instruments | SOT-23-THIN-6 | Sync, 4.5-17 V in (19 V abs), 3 A, 580 kHz, SOT-23-6; L = 3.3 uH (5 V) / 2.2 uH (3.3 V) [ds] — Cheapest and deepest, but little margin above a 12 V rail | Ext | 123,278 | 0.0560 |
| C3200405 | TPS62933DRLR | Texas Instruments | SOT-583 | Sync, 3.8-30 V in, 3 A, 200 kHz-2.2 MHz adj., SOT-583 (API) | Ext | 33,731 | 0.3707 |
| C9865 | TPS54331DR | Texas Instruments | SOIC-8 | Non-sync, 3.5-28 V in, 3 A, 570 kHz, SOIC-8; needs Schottky catch diode (API) — requested | Preferred | 287,627 | 0.2613 |
| C111875 | SY8205FCC | Silergy Corp | SOIC-8-EP | Sync, 4.5-30 V in, 5 A, 500 kHz, SOIC-8-EP (API) — Requested | Ext | 20,847 | 0.2537 |
| C61063 | XL1509-5.0E1 | XLSEMI | SOIC-8 | Non-sync, 4.5-40 V in (45 V abs), fixed 5.0 V out, 2 A, 150 kHz, SOIC-8; app circuit 12 V->5 V/2 A uses 68 uH + Schottky [ds] — the only other Basic buck besides TPS5430DDAR; 5 V only (the ADJ version is not Basic); big inductor | Basic | 481,419 | 0.1894 |
| **Other requested 12 V bucks (stocked)** | | | | | | | |
| C2071106 ★ | TPS56339DDCR | Texas Instruments | TSOT-23-6 | Sync, 4.5-24 V in, 3 A, 500 kHz, SOT-23-6 (API) | Ext | 10,158 | 0.1767 |
| C479075 | SY8113IADC | Silergy Corp | TSOT-23-6 | Sync, 4.2-18 V in, 3 A, 500 kHz, TSOT-23-6 (API) | Ext | 48,210 | 0.1181 |
| C5383002 | LMR51420YDDCR | Texas Instruments | SOT-23-6 | Sync, 4.5-36 V in, 2 A, 1.1 MHz, SOT-23-6 (API) | Ext | 12,563 | 0.5853 |
| C45889 | MP2315GJ-Z | Monolithic Power Systems | TSOT-23-8 | Sync, 4.5-24 V in, 3 A, 500 kHz, TSOT-23-8 (API) — Expensive here | Ext | 1,670 | 1.8513 |
| **5V->3.3V buck** | | | | | | | |
| C141836 ★ | TLV62569DBVR | Texas Instruments | SOT-23-5 | Sync, 2.5-5.5 V in, 2 A, 1.5 MHz, SOT-23-5; L = 2.2 uH [ds] | Ext | 243,695 | 0.0613 |
| C398365 | TLV62569PDDCR | Texas Instruments | SOT-23-THIN-6 | As TLV62569 plus power-good output, SOT-23-6 (API) | Ext | 14,360 | 0.1850 |
| C479074 | SY8089A1AAC | Silergy Corp | SOT-23-5 | Sync, 2.5-5.5 V in, 2 A, 1.5 MHz, SOT-23-5 (API) | Ext | 96,449 | 0.0685 |
| C5350187 | TPS62A02DRLR | Texas Instruments | SOT-563 | Sync, 2.5-5.5 V in, 2 A, 2.4 MHz, SOT-563 (API) | Ext | 32,325 | 0.0581 |
| **Power inductors** | | | | | | | |
| C167223 ★ | FXL0630-100-M | cjiang | SMD,7x6.6mm | 10 uH, 4.5 A rated / 5.5 A sat, 68 mOhm, molded 7x6.6 mm (API) — TPS54302 at 5 V out | Ext | 221,953 | 0.0724 |
| C167221 | FXL0630-6R8-M | cjiang | SMD,7x6.6mm | 6.8 uH, 5 A rated / 6 A sat, 48 mOhm, molded 7x6.6 mm (API) — TPS54302 at 3.3 V out | Ext | 50,850 | 0.0839 |
| C177243 | FXL0630-150-M | cjiang | SMD,7x6.6mm | 15 uH, 3 A rated / 4 A sat, 115 mOhm, molded 7x6.6 mm (API) — TPS5430 at 5 V out | Ext | 138,239 | 0.0807 |
| C167219 | FXL0630-3R3-M | cjiang | SMD,7x6.6mm | 3.3 uH, 8.5 A rated / 9.5 A sat, 22 mOhm, molded 7x6.6 mm (API) — TPS563201 at 5 V out | Ext | 37,740 | 0.0872 |
| C5832372 | FTC252012S2R2MBCA | cjiang | 1008 | 2.2 uH, 3 A rated / 3.8 A sat, 55 mOhm, 1008 (2.5x2.0 mm) (API) — TLV62569 at 3.3 V out | Ext | 298,265 | 0.0352 |
| C132141 | MWSA0603S-100MT | Sunlord | SMD,7x6.6mm | 10 uH, 4.5 A rated / 5.5 A sat, 67 mOhm, molded 7x6.6 mm (API) — Sunlord second source for the 10 uH | Ext | 44,000 | 0.0690 |
| **Catch diode (non-sync TPS5430/TPS54331)** | | | | | | | |
| C8678 ★ | SS34 | MDD | SMA(DO-214AC) | Schottky, 40 V, 3 A, 0.55 V @3 A, SMA (API) | Basic | 4,379,804 | 0.0348 |
| C22452 | SS54 | MDD | SMA(DO-214AC) | Schottky, 40 V, 5 A, 0.55 V @5 A, SMA (API) | Basic | 2,353,666 | 0.0361 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **MP1584** — MP1584EN-LF-Z C15051 has only ~560; MP1584EN C454188 and the other codes stock 0 [re-queried: C15051 MP1584EN-LF-Z (stock 556), C454188 MP1584EN (stock 0), C2916141 MP1584WN (stock 0), C55109561 MP1584EN-Z (stock 0)]
* **JW5026** — C185109 / C19712093 stock 0 (and 1 A only) [re-queried: C185109 JW5026SOTB#TRPBF (stock 0), C19712093 JW5026SOTB#TRPBF (stock 0)]

* Only two in-stock DC-DC converters are Basic: TPS5430DDAR (C9864) and XL1509-5.0E1 (C61063); both are non-synchronous and need a Schottky catch diode (SS34 C8678 / SS54 C22452 are Basic).
* No power inductor is Basic (neither the 'Power Inductors' nor the 'Molding Power Inductors' category).

## h. Sensors

**Recommendation:** No sensor is Basic. Motion: LSM6DS3TR-C (6-axis, deepest IMU stock) or LIS2DW12TR for accel-only; magnets: TMAG5273A2 (±266 mT 3D Hall, $0.35) to track NdFeB magnets (MMC5603NJ only as a compass) and DRV5055A4 for analog coil/magnet sensing; ToF: VL53L1X (VL53L1CXV0FY/1, 4 m) or VL53L5CX for 8x8 gestures; light: LTR-303ALS-01; mic: T3902 PDM (bottom port) or ZTS6216 analog top port; 40 kHz ultrasonic only as shallow-stock through-hole HY40A16T12-1/R12-1 pair.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **Accelerometers / IMUs** | | | | | | | |
| C967633 ★ | LSM6DS3TR-C | STMicroelectronics | LGA-14(2.5x3) | 6-axis IMU: ±2/4/8/16 g + ±125..2000 dps, ODR to 6.66 kHz, 0.9 mA combo HP, 4 KB FIFO, I2C/SPI, 1.71-3.6 V, LGA-14L 2.5x3x0.83 mm [ds] — Deepest-stock IMU; no Basic accelerometer exists (only Preferred one: MPU-6050 C24112, ~$15.6, EOL) | Ext | 29,432 | 1.0470 |
| C189624 | LIS2DW12TR | STMicroelectronics | LGA-12(2x2) | 3-axis accel ±2/4/8/16 g, 14-bit HP / 12-bit LP, ODR 1.6-1600 Hz, 50 nA PD, 90 µA HP, tap/free-fall/wake/6D engine, 32-level FIFO, I2C/SPI, 1.62-3.6 V, LGA-12 2x2 [ds] — Accel-only, lowest power; ST original (MSKSEMI/HXY clones also listed, not recommended) | Ext | 19,984 | 0.7966 |
| C19274408 | SC7A20HTR | Hangzhou Silan Microelectronics | LGA-12(2x2) | 3-axis accel ±2/4/8/16 g, 12-bit, ODR 1.56 Hz-4.27 kHz, tap/free-fall/6D/wake, FIFO, I2C/SPI, 1.71-3.6 V, LGA-12 2x2x1.0 mm [ds] — Silan; cheapest and deepest stock; datasheet in Chinese only | Ext | 104,058 | 0.1891 |
| C2836813 | BMI270 | Bosch Sensortec | LGA-14(2.5x3) | 6-axis IMU ±2..16 g + ±125..2000 dps, 16-bit, 2 KB FIFO, I2C/SPI, 1.71-3.6 V, 3.5 µA, LGA-14 2.5x3 mm (API) | Ext | 7,773 | 1.3721 |
| C2655100 | LSM6DSOTR | STMicroelectronics | LGA-14(2.5x3) | 6-axis IMU ±2..16 g + ±125..2000 dps, 9 KB FIFO, I2C/SPI/I3C, 1.71-3.6 V, LGA-14 2.5x3 mm (API) — Newer ST IMU, shallower stock and ~2x the price of LSM6DS3TR-C | Ext | 3,917 | 2.4905 |
| C2887190 | QMA6100P | QST | LGA-12(2x2) | 3-axis accel ±2..32 g, 14-bit, motion-event detection, I2C/SPI, 1.71-3.6 V, 500 nA, LGA-12 2x2 mm (API) — QST; cheap, deep stock, ±32 g for hard shakes | Ext | 29,418 | 0.3805 |
| **Magnetometers / 3D Hall** | | | | | | | |
| C3715882 ★ | TMAG5273A2QDBVR | Texas Instruments | SOT-23-6 | 3D linear Hall ±133/±266 mT, 12-bit, 20 kSPS (1 axis), angle CORDIC, temp sensor, I2C ≤1 MHz + INT, 1.7-3.6 V, 2.3 mA active, SOT-23-6 [ds] — Right range for tracking NdFeB magnets near the coils; A1 (±40/80 mT) variants have <50 in stock | Ext | 18,024 | 0.3512 |
| C404328 | MMC5603NJ | MEMSIC | WLP-4(0.8x0.8) | 3-axis AMR magnetometer ±30 G (±3 mT), 20-bit 0.0625 mG/LSB, 2 mG rms noise, BW to 1 kHz, SET/RESET, I2C 400 kHz/I3C, 1.62-3.6 V, WLP-4 0.8x0.8x0.4 mm [ds] — Earth-field/compass grade: saturates near magnets; tiny 4-ball WLP | Ext | 21,508 | 0.2285 |
| C404329 | MMC5983MA | MEMSIC | LGA-16(3x3) | 3-axis AMR magnetometer ±8 G, 18-bit, I2C/SPI, 2.8-3.6 V, 450 µA, LGA-16 3x3 mm (API) — MEMSIC, -40..+105 °C | Ext | 15,712 | 1.5428 |
| C3716101 | TMAG5170A2QDGKR | Texas Instruments | VSSOP-8 | 3D linear Hall up to ±300 mT, SPI, 2.3-5.5 V, 3.4 mA, -40..+150 °C, VSSOP-8 (API) — SPI alternative to TMAG5273; A1 (±100 mT) C5220642 also stocked | Ext | 5,568 | 1.7785 |
| C919695 | LIS2MDLTR | STMicroelectronics | LGA-12(2x2) | 3-axis magnetometer ±50 G (±5 mT), 16-bit, I2C/SPI, 1.71-3.6 V, 200 µA, LGA-12 2x2 mm (API) — ST; pricey | Ext | 7,767 | 3.3018 |
| C2847467 | QMC5883P | QST | LGA-16(3x3) | 3-axis magnetometer ±30 G (±3 mT), 16-bit, I2C, 2.5-3.6 V, 35 µA, LGA-16 3x3 mm (API) — QMC5883L itself is out of stock (see ABSENT); P version is a different part | Ext | 2,373 | 1.1136 |
| **Linear Hall sensors** | | | | | | | |
| C266123 ★ | DRV5055A4QDBZR | Texas Instruments | SOT-23 | Ratiometric analog Hall, 12.5 mV/mT @5 V (±169 mT), 7.5 mV/mT @3.3 V (±176 mT), 20 kHz BW, 3.3 or 5 V supply, SOT-23 [ds] — Range suited to NdFeB magnets close to the sensor | Ext | 9,334 | 0.4211 |
| C962987 | DRV5055A1QDBZR | Texas Instruments | SOT-23 | Ratiometric analog Hall, 100 mV/mT @5 V (±21 mT), 60 mV/mT @3.3 V (±22 mT), 20 kHz BW, SOT-23 [ds] — Most sensitive DRV5055, deepest stock; saturates near magnets | Ext | 20,464 | 0.4308 |
| C266128 | DRV5055A3QDBZR | Texas Instruments | SOT-23 | Ratiometric analog Hall, 25 mV/mT @5 V (±85 mT), 15 mV/mT @3.3 V (±88 mT), 20 kHz BW, SOT-23 [ds] | Ext | 5,243 | 0.2683 |
| C126669 | SS39ET | Honeywell | SOT-23 | Honeywell linear Hall (SMD sibling of SS49E), 1.4 mV/G, ±100 mT, 2.7-6.5 V, 6 mA, SOT-23 (API) | Ext | 7,421 | 0.3162 |
| C85697 | SS49E | Honeywell | TO-92S | Honeywell linear Hall, 1.4 mV/G, ±100 mT, 2.7-6.5 V, 6 mA, TO-92S through-hole (API) — Through-hole; SS39ET is the SMD equivalent | Ext | 5,267 | 0.3561 |
| C5447698 | MT9102ET | NOVOSENSE | SOT-23 | NOVOSENSE linear Hall, 1.6-2.5 mV/G, ±88 mT, rail-to-rail output, 3-5.5 V, SOT-23 (API) | Ext | 5,908 | 0.2732 |
| **Time-of-flight** | | | | | | | |
| C190004 ★ | VL53L1CXV0FY/1 | STMicroelectronics | LGA-12(2.5x4.9) | VL53L1X: 940 nm Class 1 laser ToF, up to 4 m, 50 Hz, 27° FoV, programmable ROI, I2C ≤1 MHz, 2.6-3.5 V, LGA-12 4.9x2.5x1.56 mm [ds] — VL53L1CXV0FY/1 is the ordering code of the VL53L1X | Ext | 12,639 | 3.3521 |
| C3178303 | VL53L5CXV0GC/1 | STMicroelectronics | SMD,6.4x3mm | 4x4/8x8 multizone ToF, 2-400 cm per zone, up to 60 Hz, 63° diag FoV, 940 nm VCSEL Class 1, I2C ≤1 MHz, 2.8/3.3 V, 6.4x3.0x1.5 mm [ds] — Depth image for gestures; driven through ST C driver/API | Ext | 3,407 | 4.7892 |
| C91199 | VL53L0CXV0DH/1 | STMicroelectronics | SMD-12P,4.4x2.4mm | VL53L0X: 940 nm ToF up to 2 m, I2C, 2.6-3.5 V, 19 mA, 4.4x2.4x1.0 mm (API) — Listed under ordering code VL53L0CXV0DH/1 (keyword "VL53L0X" finds only stock-0 placeholders) | Ext | 20,412 | 1.8956 |
| C3178291 | VL53L4CDV0DH/1 | STMicroelectronics | SMD-12P | ToF 1-1300 mm, temperature compensated, I2C, 2.6-3.5 V, 4.4x2.4x1.0 mm (API) | Ext | 11,552 | 2.1963 |
| C7386355 | VL53L8CXV0GC/1 | STMicroelectronics | LGA-16 | 8x8 multizone ToF, low-power mode, interrupt output, LGA-16 (API) — Pricier successor of VL53L5CX | Ext | 2,426 | 7.4618 |
| C2655167 | VL6180V1NR/1 | STMicroelectronics | SMD-12P | Short-range ToF proximity 0-62 cm, 1.7 mA, I2C, 2.6-3.0 V, 4.8x2.8x1.0 mm (API) | Ext | 5,313 | 1.0031 |
| **Ambient light sensors** | | | | | | | |
| C364577 ★ | LTR-303ALS-01 | Lite-On | DFN-6(2x2) | 0.01-64k lux, 16-bit, gains 1-96x, INT pin, 50/60 Hz flicker rejection, I2C 400 kHz, 2.4-3.6 V, 2.0x2.0x0.7 mm 6-pin ChipLED [ds] | Ext | 15,880 | 0.3252 |
| C78960 | BH1750FVI-TR | ROHM Semicon | WSOF-6 | 1-65535 lx, 16-bit, I2C, 2.4-3.6 V, WSOF-6 (API) — Deepest stock | Ext | 48,943 | 0.5918 |
| C1850416 | VEML7700-TT | Vishay Intertech | SMD-4P | 0-120 klx, 16-bit, I2C, 2.5-3.6 V, 4-pin SMD 6.8x3.0x2.35 mm (API) | Ext | 7,670 | 0.7413 |
| C90462 | OPT3001DNPR | Texas Instruments | USON-6-EP(2.1x2.1) | 0.01-83 klx, eye-matched, I2C, 1.8-3.6 V, 1.8 µA, USON-6 2.1x2.1 mm (API) | Ext | 5,852 | 1.0583 |
| C132182 | VEML6030 | Vishay Intertech | SMD-6P,2x2mm | 0-120 klx, 16-bit, I2C, 2.5-3.6 V, SMD-6P 2x2x0.87 mm (API) | Ext | 8,713 | 0.4487 |
| C492382 | LTR-308ALS-01 | Lite-On | SMD | Up to 157 klx, I2C, 1.7-3.6 V (API) | Ext | 3,408 | 0.2862 |
| **MEMS microphones** | | | | | | | |
| C3171752 ★ | MMICT390200012 | TDK InvenSense | LGA-5(3.5x2.7) | TDK T3902 PDM, bottom port, −26 dBFS, SNR 64.5 dBA, AOP 120 dB SPL (126 HP mode), 185 µA LP / 12 µA sleep, 1.65-3.63 V, 3.5x2.65x0.98 mm [ds] — Bottom port needs a PCB hole; PDM needs a PIO/PDM-capable peripheral | Ext | 7,547 | 0.9803 |
| C481302 | ZTS6216 | ZILLTEK | SMD-4P,2.8x1.9mm | Analog, top port, −38 dBV/Pa, SNR 65 dBA, AOP 125 dB SPL, 120 µA, 1.5-3.6 V, 2.75x1.85x1.0 mm [ds] — Top port (no PCB hole); needs AC coupling + gain stage into an ADC | Ext | 28,469 | 0.4634 |
| C2895290 | SD18OB261-060 | Goertek | SMD-5P,3.5x2.7mm | Goertek PDM, −26 dBFS, SNR 65 dB, AOP 120 dB SPL, 1.6-3.6 V, 3.5x2.65 mm [ds] | Ext | 6,226 | 0.5853 |
| C481300 | ZTS6117 | ZILLTEK | SMD-4P,2.8x1.9mm | Analog, −42 dBV, SNR 59 dB, 120 µA, 1.5-3.6 V, 2.75x1.85x0.9 mm (API) — Cheapest analog option | Ext | 14,061 | 0.1334 |
| C503097 | MP34DT06JTR | STMicroelectronics | HCLGA-4LD(3x4) | ST PDM, −26 dBFS, SNR 64 dB, 650 µA, HCLGA-4LD 3x4x1 mm (API) | Ext | 3,439 | 1.3770 |
| C5656610 | ICS-43434 | TDK InvenSense | LGA-6(3.5x2.7) | TDK I2S digital output, −26 dBFS, SNR 64 dB, 550 µA, 1.65-3.63 V, LGA-6 3.5x2.65x0.98 mm (API) — Only I2S-output mic with >1k stock | Ext | 1,372 | 3.2839 |
| **Ultrasonic 40 kHz transducers** | | | | | | | |
| C17701106 ★ | HY40A16T12-1 | HYDZ | Plugin,16x12mm | 40±0.5 kHz open-type transmitter, SPL ≥116 dB, 2200 pF, 70° (−6 dB), ≤140 Vpp, Al can Ø16x12 mm, through-hole [ds] — Through-hole only; pair with HY40A16R12-1 | Ext | 1,351 | 0.2553 |
| C17701107 | HY40A16R12-1 | HYDZ | Plugin,16x12mm | 40 kHz open-type receiver, −62 dB (0 dB = 1 V/µbar), Ø16x12 mm, through-hole (API) — Shallow stock | Ext | 483 | 0.2553 |
| C242189 | GU1610B-40TR | INGHAi | Plugin | INGHAi 40 kHz transceiver, through-hole (API) — Shallow stock | Ext | 952 | 0.9267 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **LIS3DH** — LIS3DHTR C15134 listed but only 245 in stock [re-queried: C15134 LIS3DHTR (stock 245), C2655077 LIS3DHHTR (stock 2)]
* **LIS2DH12** — LIS2DH12TR C110926 listed but only 869 in stock [re-queried: C110926 LIS2DH12TR (stock 869)]
* **MC3479** — MC3479 C3248221 listed but only 860 in stock [re-queried: C3248221 MC3479 (stock 860)]
* **QMC5883** — QMC5883L C976032 stock 0 (QMC5883P C2847467 is stocked instead) [re-queried: C2847467 QMC5883P (stock 2,373), C976032 QMC5883L (stock 0), C46468678 QMC5883P (stock 0), C192585 QMC5883L-TR (stock 0)]
* **ALS31313** — ALS31313KLEATR-500 C2654988 stock 30; other variants <=21 [re-queried: C2654988 ALS31313KLEATR-500 (stock 30), C2654983 ALS31313KLEATR-JOY (stock 21), C2654977 ALS31313KLEATR-1000 (stock 1), C2654975 ALS31313KLEATR-2000 (stock 0)]
* **DRV5053** — DRV5053RAQDBZR C2654960 only 1402 (filed under Hall Switches); DRV5053VAQDBZR C962159 only 88 [re-queried: C2654960 DRV5053RAQDBZR (stock 1,402), C107633 DRV5053VAQLPG (stock 1,165), C1526533 DRV5053CAQLPG (stock 950), C2860511 DRV5053EAQLPG (stock 242)]
* **A1308** — A1308KUA-5-T C1559904 368 (SIP-3), A1308LLHLX-05-T C2152984 271; 5 V-only parts [re-queried: C1559904 A1308KUA-5-T (stock 368), C2152984 A1308LLHLX-05-T (stock 271), C1526515 A1308KUA-2-T (stock 98), C3716297 A1308LLHLT-1-T (stock 58)]
* **VL53L7CX** — VL53L7CXV0GC/1 C5270520 only 42 in stock [re-queried: C5270520 VL53L7CXV0GC/1 (stock 42)]
* **LTR-329** — LTR-329ALS-01 C284894 only 108 in stock [re-queried: C284894 LTR-329ALS-01 (stock 108)]
* **MSM261S4030H0** — MSM261S4030H0R C2840615 stock 0 [re-queried: C2840615 MSM261S4030H0R (stock 0)]
* **SPH0645** — SPH0645LM4H-B (C45337831 and others) all stock 0 [re-queried: C255205 SPH0645LM4H-B (stock 0), C2686054 SPH0645LM4H-B (stock 0), C45337831 SPH0645LM4H-B (stock 0), C19190864 SPH0645LM4H-B-8 (stock 0)]
* **SPH0641** — SPH0641LU4H-1 C2879853 only 1055 in stock [re-queried: C2879853 SPH0641LU4H-1 (stock 502), C497724 SPH0641LM4H-1 (stock 377), C5454543 SPH0641LM4H-1-8 (stock 0)]
* **ICS-41350** — ICS-41350 C3171856 only 87 in stock [re-queried: C3171856 ICS-41350 (stock 87)]
* **IM69D130** — IM69D130V01 C536262 only 442 in stock [re-queried: C536262 IM69D130V01 (stock 442), C54305019 IM69D130A (stock 0), C20191539 IM69D130V11XTSA2 (stock 0), C42464166 IM69D130V01XTSA1 (stock 0)]
* **GMA4030** — no hits (also none for GMA35/GMA40)
* **MA40S4** — Murata MA40S4S C1519281 and MA40S4R C2912274 stock 0 [re-queried: C1519281 MA40S4S (stock 0), C2912274 MA40S4R (stock 0)]
* **SY-US-18** — only SMD 40 kHz transducer, SY-US-18BRTD C5380075, has 91 in stock [re-queried: C5380075 SY-US-18BRTD (stock 91), C5380076 SY-US-18BT (stock 25), C5380074 SY-US-18BD (stock 6)]

## i. USB-C receptacle and USB-C PD sink controllers

**Recommendation:** TYPE-C-31-M-12 (C165948) is deeply stocked (Extended). CH224A (C42459160, Extended, 17.6k stock, $0.27): WCH says it is pin-compatible with the out-of-stock CH224K; a single 24 kOhm CFG1 resistor requests 12 V (also 9/15/20/28 V). HUSB238 (C7471904) is the second source.

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **USB-C receptacle** | | | | | | | |
| C165948 ★ | TYPE-C-31-M-12 | Korean Hroparts Elec | SMD | HRO 16-pin USB-C receptacle, SMD right angle, 20 V 5 A, 10,000 cycles | Ext | 417,782 | 0.1467 |
| **USB-C PD sink controllers** | | | | | | | |
| C42459160 ★ | CH224A | WCH | ESSOP-10 | PD3.2 sink (EPR/AVS/PPS/SPR) + BC1.2; asks 5/9/12/15/20/28 V; 4-30 V; 1-resistor, I/O-level or I2C config; built-in HV LDO + OVP; ESSOP-10 [ds] — WCH datasheet: "CH224A is pin-compatible with CH224K" (CH224K is out of stock); only peripherals change (VHV pin takes VBUS + cap, no series resistor); CFG1 24 kOhm = 12 V [ds] | Ext | 17,619 | 0.2699 |
| C7471904 | HUSB238_002DD | Hynetek | DFN-10L(3x3) | PD3.0 sink up to 100 W (5-20 V), Type-C 1.4, BC1.2/Apple; VSET/ISET resistors or I2C; GATE pin drives ext. PMOS; 3-25 V (30 V abs); DFN-10 3x3 [ds] — USB-IF certified (TID 3666); good second source to CH224A | Ext | 7,784 | 0.3479 |
| C3975094 | CH224D | WCH | QFN-20 | PD3.0 sink up to 100 W (5/9/12/15/20 V); 1-resistor or I/O-level config; 4-30 V; QFN-20 3x3 [ds: CH224 family sheet] | Ext | 4,541 | 0.2678 |
| C132291 | FUSB302BMPX | onsemi | WFQFN-14(2.5x2.5) | Type-C CC logic + USB-PD BMC PHY, I2C to an MCU; 2.8-5.5 V supply; WQFN-14 2.5x2.5 (API) — needs a PD stack in MCU firmware; most flexible (any PDO/PPS) but most work | Ext | 9,084 | 0.5804 |
| C24833806 | HUSB238A-BB001-QN16R | Hynetek | QFN-16L-EP(3x3) | PD3.1 sink incl. EPR: 5/9/12/15/20/28/48 V, QC2.0/BC1.2; 3.15-29.4 V; QFN-16 3x3 (API) | Ext | 3,295 | 0.4130 |
| C2678061 | STUSB4500QTR | STMicroelectronics | QFN-24-EP(4x4) | standalone PD2.0/3.0 sink controller, PDOs stored in NVM, I2C; QFN-24 4x4 (API) — the most expensive option | Ext | 4,797 | 1.7850 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **CH224K** — C970725 CH224K listed, stock 0 (CH224Q C46061833 also 0); use pin-compatible CH224A C42459160 [re-queried: C970725 CH224K (stock 0)]
* **AP33772** — C5244513 AP33772DKZ-13 stock 65; C24374260 AP33772SDKZ-13-FA01 stock 15; C50341643 -FA02 stock 0 [re-queried: C5244513 AP33772DKZ-13 (stock 65), C24374260 AP33772SDKZ-13-FA01 (stock 15), C50341643 AP33772SDKZ-13-FA02 (stock 0)]
* **IP2721** — C603176 IP2721 stock 0; C7426784 IP2721-MAX12 stock 0 [re-queried: C603176 IP2721 (stock 0), C7426784 IP2721-MAX12 (stock 0)]

## j. Wireless power: Qi ICs, rectifiers, resonant capacitors, ferrite

**Recommendation:** Qi silicon is optional: a custom resonant link needs only the coil-driver half-bridges, 4x Basic Schottkys (1N5819WS C191023 / SS34 C8678) and C0G tank caps (only 2.2 nF C28260 is Basic; e.g. Murata GRM31C5C1H104JA01L C97946 for 100 nF). For Qi interoperability IP6808 (C515682) + BQ51013B (C55663) are the stocked TX/RX pair. Ferrite sheets are effectively unstocked (hand-apply).

| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |
|---|---|---|---|---|---|--:|--:|
| **Qi / wireless-power TX ICs** | | | | | | | |
| C515682 ★ | IP6808_NF | INJOINIC | QFN-32-EP(5x5) | Qi (WPC 1.2.4) TX SoC, 5-10 W, A11 coil; integrated NMOS full-bridge gate driver + V/I ASK demod, FOD; 4.5-22 V in (25 V abs); QFN-32 5x5 [ds] — external full-bridge N-FETs needed; pairs with the A11 TX coil below | Ext | 3,424 | 0.9055 |
| C2927864 | IP6809 | INJOINIC | VFQFN-40-EP(6x6) | Qi (WPC 1.2.4) TX SoC, 5-15 W, 2-3 coils (A28/MP-A8); integrated NMOS full-bridge driver, FOD, PD3.0 input request; 4.5-22 V; QFN-40 6x6 [ds] | Ext | 2,066 | 1.0356 |
| C134094 | BQ500101DPCR | Texas Instruments | VSON-CLIP-8(3.5x4.5) | NexFET half-bridge power stage (driver + FETs) for Qi TX: VIN <=24 V, 10 A cont./15 A peak, <=600 kHz, 3.3/5 V PWM input; SON 3.5x4.5 [ds] — power stage only (two = full bridge); suits an MCU-PWM-driven custom resonant link; low stock | Ext | 196 | 0.9706 |
| C2921390 | IP6826 | INJOINIC | QFN-32-EP(5x5) | Qi (WPC 1.2) TX, 15 W, FOD, 4.5-12 V in; QFN-32 5x5 (API) — LCSC description says "Need to burn firmware" | Ext | 322 | 0.8145 |
| C5896696 | RT3181CGQW | Richtek Tech | WQFN-48(6x6) | Qi TX controller, 15 W, FOD, watchdog, 5-19 V; WQFN-48 6x6 (API) — low stock | Ext | 200 | 1.5607 |
| **Qi / wireless-power RX ICs** | | | | | | | |
| C55663 ★ | BQ51013BRHLR | Texas Instruments | VQFN-20(4.5x3.5) | Qi (WPC 1.1) RX: full sync rectifier + LDO, 5.0 V out (4.95-5.04 V @1 A), <=1.5 A, VRECT 4-10 V (20 V abs), 93% peak eff.; VQFN-20 4.5x3.5 [ds] — closed loop needs a Qi-type TX (ASK back-modulation; WPC 110-205 kHz) | Ext | 1,007 | 2.0695 |
| C42411074 | IP6831 | INJOINIC | QFN-16-EP(3x3) | Qi BPP 2 W RX: integrated sync rectifier, 5.0-5.1 V out, <=400 mA, RECT OVP 18 V; QFN-16 3x3 [ds] — cheapest RX; tuned for small/irregular coils (earbud/wearable class) | Ext | 787 | 0.3268 |
| C133307 | BQ51050BRHLR | Texas Instruments | QFN-20-EP(3.7x4.7) | Qi RX with integrated Li-ion charger: 4.2 V, <=1.5 A, 4-10 V in, NTC input; QFN-20 (API) — only if a satellite carries a Li-ion cell | Ext | 3,822 | 1.0957 |
| **Schottky rectifiers** | | | | | | | |
| C191023 ★ | 1N5819WS | Guangdong Hottech | SOD-323 | Schottky 40 V 1 A, Vf 0.6 V @1 A, 25 A surge; SOD-323 (API) — Basic; four make a full bridge on a small satellite PCB | Basic | 4,930,284 | 0.0137 |
| C8678 | SS34 | MDD | SMA(DO-214AC) | Schottky 40 V 3 A, Vf 0.55 V @3 A; SMA (API) — Basic; for 1-3 A bridges (SS54 C22452 is a Basic 5 A option) | Basic | 4,379,804 | 0.0348 |
| C2480 | SS14 | MDD | SMA(DO-214AC) | Schottky 40 V 1 A, Vf 0.55 V @1 A, 25 A surge; SMA (API) | Basic | 1,127,552 | 0.0191 |
| C8598 | B5819W SL | Jiangsu Changjing Electronics Technology Co., Ltd. | SOD-123 | Schottky 40 V 1 A, Vf 0.6 V @1 A; SOD-123 (API) — Basic; MDD B5819W C64885 is Preferred with 925k stock | Basic | 453,537 | 0.0280 |
| C19726 | BAT54SLT1G | onsemi | SOT-23 | dual Schottky, series pair, 30 V 200 mA, Vf 0.8 V @100 mA; SOT-23 (API) — two = a full bridge for <=200 mA; BAT54C,215 C37704 (common cathode) is Preferred | Ext | 240,216 | 0.0137 |
| C880909 | KMB14F | FUXINSEMI | MBS | Schottky bridge rectifier 40 V 1 A, Vf 0.55 V @1 A, 30 A surge; MBS (API) — one-part full bridge; AB24S C882375 (MDD, 2 A, ABS) for more current | Ext | 22,503 | 0.0592 |
| **C0G/NP0 resonant capacitors (50 V+)** | | | | | | | |
| C62774 ★ | CC0805JRNPO9BN102 | YAGEO | 0805 | 1 nF ±5% 50 V NP0, 0805 (API) — ladder 1 nF | Ext | 1,078,513 | 0.0096 |
| C28260 ★ | CL21C222JBFNNNE | Samsung Electro-Mechanics | 0805 | 2.2 nF ±5% 50 V C0G, 0805 (API) — ladder 2.2 nF; the only Basic (or Preferred) C0G between 1 and 100 nF | Basic | 118,332 | 0.0233 |
| C77063 ★ | GRM2165C1H472JA01D | Murata Electronics | 0805 | 4.7 nF ±5% 50 V C0G, 0805 (API) — ladder 4.7 nF | Ext | 15,742 | 0.0319 |
| C2971995 ★ | 0805CG103J500NT | FH | 0805 | 10 nF ±5% 50 V C0G, 0805 (API) — ladder 10 nF | Ext | 207,038 | 0.0418 |
| C97929 ★ | GRM3195C1H223JA01D | Murata Electronics | 1206 | 22 nF ±5% 50 V C0G, 1206 (API) — ladder 22 nF (0805: GRM21B5C1H223JA01L C77069) | Ext | 101,655 | 0.1122 |
| C21812 ★ | GRM31M5C1H473JA01L | Murata Electronics | 1206 | 47 nF ±5% 50 V C0G, 1206 (API) — ladder 47 nF; no 0805 C0G >=50 V in stock at 47 nF or 100 nF | Ext | 77,126 | 0.1288 |
| C97946 ★ | GRM31C5C1H104JA01L | Murata Electronics | 1206 | 100 nF ±5% 50 V C0G, 1206 (API) — ladder 100 nF | Ext | 84,312 | 0.1612 |
| C405303 | GRM31C5C2A104JA01L | Murata Electronics | 1206 | 100 nF ±5% 100 V C0G, 1206 (API) — higher-voltage 100 nF, for series-resonant tanks | Ext | 22,337 | 0.3309 |
| C41370618 | FP31N103J631EEG | PSA | 1206 | 10 nF ±5% 630 V C0G, 1206 (API) — higher-voltage 10 nF | Ext | 6,061 | 0.1291 |
| **High-voltage C0G (1-2 kV)** | | | | | | | |
| C113872 ★ | CC1206JKNPOCBN102 | YAGEO | 1206 | 1 nF ±5% 1 kV NP0, 1206 (API) | Ext | 11,180 | 0.0274 |
| C4355181 | C1206N222J102TDF | IHHEC | 1206 | 2.2 nF ±5% 1 kV NP0, 1206 (API) | Ext | 20,704 | 0.1023 |
| C5156739 | FV32N103J102EGG | PSA | 1210 | 10 nF ±5% 1 kV C0G, 1210 (API) | Ext | 5,396 | 0.3195 |
| C7503858 | MT32N223J102EGE | PSA | 1210 | 22 nF ±5% 1 kV C0G, 1210 (API) | Ext | 4,382 | 0.3512 |
| C692314 | FV32N102J202EFG | PSA | 1210 | 1 nF ±5% 2 kV C0G, 1210 (API) | Ext | 4,954 | 0.1509 |
| C22370026 | FV43N152J202EFG | PSA | 1812 | 1.5 nF ±5% 2 kV C0G, 1812 (API) — for HF tanks, 220 pF 2 kV 1206 Yageo CC1206JKNPODBN221 C469629 has 63k stock | Ext | 7,957 | 0.2502 |
| **Ferrite sheets** | | | | | | | |
| C17556940 ★ | IFL04-050NB300X200 | TDK | - | flexible ferrite noise-suppression sheet 300x200 mm, 0.06 mm thick; mu' 45, mu'' 1.3 @13.56 MHz (API) — the only ferrite sheet JLCPCB has in stock (4 pcs); NFC-grade; hand-applied, so buy elsewhere if needed | Ext | 4 | 14.3643 |
| **Qi coils with ferrite backing (hand-placed)** | | | | | | | |
| C424425 ★ | YX-A11-R500800-R0845 | CND-tek | - | Qi A11 TX coil: 6.3 uH ±5% @100 kHz, DCR <=75 mOhm, Litz 105x0.08 mm on a 50 mm x 0.8 mm ferrite disc [ds] — pairs with IP6808; handy reference coil next to PCB-trace coils | Ext | 441 | 0.3398 |
| C22381709 | YX-A11-R431231-G3232 | CND-tek | - | Qi RX coil: 11.5 uH, 175 mOhm (API), on a 43 x 31.5 x 0.3 mm magnetic sheet with adhesive [ds] | Ext | 497 | 0.2553 |
| C3606555 | WR222230-26M8-G | TDK | - | Qi RX coil, 22 mm dia., 0.87 mm thick, 27 uH @100 kHz, 1.1 Ohm, flexible ferrite sheet [ds] — small enough for a satellite PCB; low stock | Ext | 132 | 3.0010 |

Requested but not usable (searched by MPN; the note was written during the survey, the bracket is the re-query made when this file was generated):

* **BQ500212** — C2876641 BQ500212ARGZT stock 0 [re-queried: C2876641 BQ500212ARGZT (stock 0)]
* **BQ500511** — C3189479 BQ500511RHAT stock 4 [re-queried: C3189479 BQ500511RHAT (stock 4), C3036452 BQ500511RHAT (stock 0), C7220648 BQ500511ARHAR (stock 0)]
* **P9235** — P9235A-RNDGI/-RBNDGI/-RNDGI8/-RBNDGI8 (C1575185, C1012920, C2156195, C1858382) all stock 0 [re-queried: C1575185 P9235A-RNDGI (stock 0), C1012920 P9235A-RBNDGI (stock 0), C2156195 P9235A-RNDGI8 (stock 0), C1858382 P9235A-RBNDGI8 (stock 0)]
* **P9242** — C2156160 P9242-RNDGI8 stock 5; other P9242 codes stock 0 [re-queried: C2156160 P9242-RNDGI8 (stock 5), C1575065 P9242-RNDGI (stock 0), C3189582 P9242-RBNDGI (stock 0), C1511769 P9242-RBNDGI8 (stock 0)]
* **P9222** — C1511994 P9222-RAZGI8 stock 9 (P9221/P9025/P9415 codes: stock 0) [re-queried: C1511994 P9222-RAZGI8 (stock 9)]
* **BQ51003** — C134093 BQ51003YFPR stock 97 (2.5 W RX, DSBGA) [re-queried: C134093 BQ51003YFPR (stock 97), C2650142 BQ51003YFPT (stock 2)]
* **CPS4019** — only consigned "JLCPCB Assembly" placeholders (C9900047042, C9900189128), no stock; CPS4035/CPS4041: no hits
* **NU1680** — NuVolta NU1020/NU1680/NU1708: only consigned placeholders, no stock [re-queried: C2874932 NU1680-QFN16 (stock 0)]
* **XKT-510** — XKT-510/XKT-412/T3168/T5336: only consigned placeholders (e.g. C9900041368, C9900003802, C2887878), no stock
* **IFL10M** — ferrite sheets (Noise Suppressors category, 998 listed): TDK IFL10M/IFL12, KEMET EFX all stock 0; only IFL04-050NB300X200 has 4 [re-queried: C694563 IFL10M-100NB300X200 (stock 0), C3274071 IFL10M-050NB300X200 (stock 0), C3274271 IFL10M-200NB300X200 (stock 0), C17290395 IFL10M-025NB300X200 (stock 0)]

* The C0G ladder lists one pick per value, so it carries several ★.
* The resonant-capacitor ladder from 1 nF to 100 nF has exactly one Basic part (2.2 nF CL21C222JBFNNNE, C28260).

## Datasheets

Saved as `datasheets/<MPN>.pdf` (characters other than letters, digits and `._+-` written as `_`), with a `pdftotext` copy in `datasheets/txt/`. The directory is gitignored. Only the files listed here were fetched for (or checked by) this survey; other PDFs in `datasheets/` were placed by other agents.

| MPN | fetched from | file present | note |
|---|---|---|---|
| XL-1608UOC-06 | C965800 | yes |  |
| XL-2012UOC | C965813 | yes |  |
| XL-3216UOC | C965823 | yes |  |
| XL-3528UOC | C2843804 | yes |  |
| TJ-S3528UG6W9TLC0A-A5 | C2837014 | yes |  |
| HL-AF-5060S22OC-3-S1-THL | C516304 | yes |  |
| KT-0603R | C2286 | yes |  |
| S2-2835UVTA-0.2W | C2827317 | yes |  |
| XL-HD2835UVA2-A1 | C49652883 | yes |  |
| XL-2835UVA-02 | C2843877 | yes |  |
| XL-1608UVC-04 | C7371898 | yes |  |
| P2-0802UVTA1-1.0T | C2827267 | yes |  |
| GL0603PU01 | C51933300 | yes |  |
| XL-HD2835UVA1-A1 | C49652884 | yes |  |
| KT-0805Y | C2296 | yes |  |
| NCD0805R1 | C84256 | yes |  |
| GL0603UO01 | C51933298 | yes |  |
| LTST-C190KFKT | C157740 | yes |  |
| NCD0603Y2 | C89811 | yes |  |
| P2835P1UVS26G12Q-365 | C46641552 | — | **FAILED:** JLCPCB lists no datasheet for this part |
| LP5036RJVR | C701961 | yes |  |
| LP5024RSMR | C427525 | yes |  |
| LP5012RUKR | C1849481 | yes |  |
| IS31FL3205-QFLS4-TR | C3202873 | yes |  |
| TLC5971RGER | C543004 | yes |  |
| TLC59711PWPR | C116842 | yes |  |
| MBI5043GP-A | C110098 | yes |  |
| TLC5947RHBR | C702083 | yes |  |
| TLC5940PWPR | C181653 | yes |  |
| TLC5955DCAR | C702086 | yes |  |
| AW21036QNR | C5125743 | yes |  |
| PCA9956BTWY | https://www.nxp.com/docs/en/data-sheet/PCA9956B.pdf | yes | LCSC PDF for C2678558 was not a PDF; fetched from NXP |
| IS31FL3218-QFLS2-TR | C2940546 | yes |  |
| IS31FL3741A-QFLS4-TR | C2940604 | yes |  |
| PCA9685PW/Q900,118 | https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf | yes | saved as PCA9685PW_Q900_118.pdf (LCSC PDF for C92206 was not a PDF; fetched from NXP) |
| AW9523BTQR | C148077 | yes |  |
| AW20036QNR | C401019 | yes |  |
| TLC59116IPWR | C131194 | yes |  |
| WS2816B | C22371534 | yes |  |
| RP2354A | C41378174 | yes | LCSC serves the full 11 MB RP2350 datasheet |
| RP2354B | C39843328 | yes | LCSC serves the RP2350 product brief only; the full datasheet is RP2354A.pdf |
| ESP32-C3 | C2838500 | yes | ESP32-C3 Series datasheet v1.5, covers ESP32-C3FH4 |
| DRV8316RRGFR | https://www.ti.com/lit/ds/symlink/drv8316.pdf | yes | LCSC copy was the Chinese edition; replaced with TI English |
| DRV8874PWPR | C1855818 | yes |  |
| DRV8844PWPR | C177807 | yes |  |
| AON7934 | C485677 | yes |  |
| TPS54302DDCR | https://www.ti.com/lit/ds/symlink/tps54302.pdf | yes | LCSC copy was the Chinese edition; replaced with TI English |
| TPS563201DDCR | C116592 | yes |  |
| TLV62569DBVR | C141836 | yes |  |
| TPS5430DDAR | C9864 | yes |  |
| LSM6DS3TR-C | C967633 | yes |  |
| LIS2DW12TR | C189624 | yes |  |
| SC7A20HTR | C19274408 | yes | Chinese only |
| TMAG5273A2QDBVR | https://www.ti.com/lit/ds/symlink/tmag5273.pdf | yes | JLC copy was the Chinese translation; replaced by TI English rev C |
| MMC5603NJ | C404328 | yes |  |
| DRV5055A4QDBZR | https://www.ti.com/lit/ds/symlink/drv5055.pdf | yes | TI rev C, Jun 2026; covers A1-A4 |
| VL53L1CXV0FY/1 | C190004 | yes |  |
| VL53L5CXV0GC/1 | C3178303 | yes |  |
| LTR-303ALS-01 | C364577 | yes |  |
| MMICT390200012 | C3171752 | yes | T3902 |
| ZTS6216 | C481302 | yes |  |
| SD18OB261-060 | C2895290 | yes |  |
| HY40A16T12-1 | C17701106 | yes |  |
| MSM261DDB020 | C27636198 | — | **FAILED:** no datasheet link in the JLC/LCSC listing (dropped as a candidate) |
| IP6808_NF | C515682 | yes |  |
| IP6809 | C2927864 | yes |  |
| IP6831 | C42411074 | yes |  |
| BQ51013BRHLR | C55663 | yes |  |
| BQ500101DPCR | C134094 | yes |  |
| CH224A | C42459160 | yes |  |
| HUSB238_002DD | C7471904 | yes |  |
| XL1509-5.0E1 | C61063 | yes |  |
| ABM8-272-T3 | C20625731 | yes | already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey |
| AOTA-B201610S3R3-101-T | C42411119 | yes | already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey |
| TYPE-C-31-M-12 | C165948 | yes | already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey |
