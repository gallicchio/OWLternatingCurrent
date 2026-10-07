#!/usr/bin/env python3
"""JLCPCB parts survey for the halloween1 board (a survey, not a design).

Every candidate below is looked up again BY ITS LCSC CODE through tools/jlc_api.py,
and the MPN that JLCPCB returns must contain the `expect` string, so that a code
that names the wrong part stops the script instead of reaching the report.  Stock,
price and Basic/Extended come from those answers, with the time each was fetched
(answers younger than 24 h are reused from tools/jlc_cache.json; --refresh re-asks).

The `specs` strings were written from the API description and, where marked [ds],
from the datasheet in datasheets/ (gitignored).  The candidate codes themselves were
all found by searching the API (search / search_ex / sweep), never typed from memory.

    python3 research/survey.py             write research/jlc_parts_survey.{md,json}
    python3 research/survey.py --refresh   re-query everything first
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import jlc_api  # noqa: E402

QTY = 100

CATS = [
    ("a", "Orange LEDs (orange 600-615 nm, amber 585-597 nm, red-orange 615-630 nm)"),
    ("b", "Purple LEDs (violet 390-420 nm, purple/pink phosphor and red+blue bi-die, UV-A 365-385 nm)"),
    ("c", "Constant-current LED driver ICs (high-resolution PWM)"),
    ("d", "Microcontrollers / FPGA and their crystals"),
    ("e", "Coil power stage (12 V, 1-3 A per phase)"),
    ("f", "12 V input: jack, protection, bulk capacitance"),
    ("g", "Buck converters and power inductors"),
    ("h", "Sensors"),
    ("i", "USB-C receptacle and USB-C PD sink controllers"),
    ("j", "Wireless power: Qi ICs, rectifiers, resonant capacitors, ferrite"),
]

# ---------------------------------------------------------------------------
# Candidates.  rank 1 = recommended pick of its group; 2.. = alternates in order.
CANDIDATES = [
    # ---- a. orange -------------------------------------------------------
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C965800", expect="XL-1608UOC-06", rank=1,
         specs="AlGaInP orange, λd 600-610 nm, 80-210 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA (IFP 80) [ds]",
         note="API lists 315 mcd; datasheet table says 80-210 mcd"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C51933298", expect="GL0603UO01", rank=2,
         specs="λd 600-612 nm, 203-358 mcd @20 mA, Vf 1.8-2.4 V, If max 25 mA (IFP 100) [ds]",
         note="API lists 100-160 mcd"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C157740", expect="LTST-C190KFKT", rank=3,
         specs="λd 605 nm (λp 611), 45-90 mcd @20 mA, Vf 2.0-2.4 V, If max 30 mA (IFP 80), 75 mW [ds]"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C965813", expect="XL-2012UOC", rank=4,
         specs="λd 600-610 nm, 80-210 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA [ds]"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C965823", expect="XL-3216UOC", rank=5,
         specs="λd 600-606 nm, 80-180 mcd @20 mA, Vf 1.9-2.4 V, If max 20 mA [ds]"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C2837014", expect="TJ-S3528UG6W9TLC0A-A5", rank=6,
         specs="PLCC-2/3528; λd 600-610 nm, 100-320 mcd @20 mA, Vf 1.8-2.4 V, If max 30 mA [ds]"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C2843804", expect="XL-3528UOC", rank=7,
         specs="PLCC-2/3528; λd 600-608 nm, 300-400 mcd @20 mA, Vf 1.8-2.4 V, If max 20 mA [ds]"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C516304", expect="HL-AF-5060S22OC", rank=8,
         specs="5050, 3 AlGaInP dice; λd 600-610 nm, 600-800 mcd @3x20 mA, If 60 mA total, Pd 225 mW [ds]",
         note="brightest deep-stock orange; no orange 2835/3030 with real stock"),
    dict(cat="a", group="Orange 600-615 nm (pumpkin orange)", code="C5440712", expect="XL-5050UOC", rank=9,
         specs="5050; λd 600-605 nm, 800 mcd @60 mA, Vf 1.8-2.2 V"),
    dict(cat="a", group="Amber 585-597 nm", code="C2296", expect="KT-0805Y", rank=1,
         specs="λd 592-594 nm (amber-yellow), 95-113 mcd @20 mA, Vf 2.0-2.2 V, If max 20 mA (IFP 100) [ds]",
         note="API lists 584-594 nm, 175 mcd"),
    dict(cat="a", group="Amber 585-597 nm", code="C89811", expect="NCD0603Y2", rank=2,
         specs="λd 583-595 nm (588 typ) @15 mA, 50-180 mcd, Vf 1.5-2.6 V, If max 25 mA (IFP 50) [ds]"),
    dict(cat="a", group="Amber 585-597 nm", code="C965802", expect="XL-1608UYC-06", rank=3,
         specs="λd 585-595 nm, 435 mcd @20 mA, Vf 2.4 V, 50 mW"),
    dict(cat="a", group="Amber 585-597 nm", code="C7371919", expect="XL-2835UYC-02FJ", rank=4,
         specs="2835; λd 587-596 nm, 1.75 cd @60 mA, Vf 1.8-2.4 V, 200 mW"),
    dict(cat="a", group="Amber 585-597 nm", code="C51933348", expect="GL5050UY01", rank=5,
         specs="5050; λd 585-595 nm, 0.6-2 cd @60 mA, Vf 1.8-2.2 V, 200 mW"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C2286", expect="KT-0603R", rank=1,
         specs="λd 615-630 nm, 145-300 mcd @20 mA, Vf 1.8-2.4 V, If max 25 mA (IFP 60) [ds]"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C84256", expect="NCD0805R1", rank=2,
         specs="λd 615-630 nm (620 typ), 50-230 mcd @20 mA, Vf 1.5-2.6 V, If max 25 mA (IFP 50) [ds]"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C965798", expect="XL-1608SURC-04", rank=3,
         specs="λd 620-625 nm, 120 mcd @20 mA, Vf 2.4 V, 50 mW"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C2843800", expect="XL-3528SURC", rank=4,
         specs="PLCC-2/3528; λd 620-630 nm, 530 mcd @20 mA, Vf 2.4 V"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C2843869", expect="XL-2835SURC-02", rank=5,
         specs="2835; λd 620-630 nm, 900 mcd @60 mA, Vf 2.4 V, 200 mW"),
    dict(cat="a", group="Red-orange 615-630 nm", code="C2843864", expect="XL-5050SURC", rank=6,
         specs="5050; λd 620-630 nm, 2.2 cd @60 mA, Vf 2.4 V, 200 mW"),
    # ---- b. purple ---------------------------------------------------------
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C2827317",
         expect="S2-2835UVTA-0.2W", rank=1,
         specs="2835; λp 390-400 nm, Vf 3.0-3.6 V @60 mA, If max 60 mA (IFP 100), Pd 180 mW; radiant power not stated [ds]",
         note="deepest-stock violet by far"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C49652883",
         expect="XL-HD2835UVA2-A1", rank=2,
         specs="2835 HP; λp 390-400 nm (395 typ), Φe 120-180 mW @120 mA, Vf 3.1-3.7 V, If max 150 mA, Pd 600 mW [ds]",
         note="API description is empty; specs from datasheet"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C2843877",
         expect="XL-2835UVA-02", rank=3,
         specs="2835; λp 395 nm, Φe 45-90 mW @60 mA, Vf 3.0-3.6 V, If max 60 mA (IFP 120) [ds]"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C7371898",
         expect="XL-1608UVC-04", rank=4,
         specs="0603; λp 390-405 nm, 50-80 mcd @20 mA, Vf 3.0-3.4 V, Pd 100 mW [ds]",
         note="datasheet abs-max table prints IF 80 mA / IFP 25 mA (apparently swapped): use <=20 mA"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C7371915",
         expect="XL-2012UVA", rank=5,
         specs="0805; λd 390-405 nm (405), 52-78 mcd @20 mA, Vf 2.9-3.5 V, 70 mW"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C2827267",
         expect="P2-0802UVTA1-1.0T", rank=6,
         specs="0805; λp 390-395 nm, Vf 2.8-3.4 V @20 mA, If max 30 mA (IFP 100), Pd 90 mW [ds]"),
    dict(cat="b", group="Violet 390-420 nm InGaN (also excites glow / fluorescent pigments)", code="C516136",
         expect="HL-A-3528S7VC", rank=7,
         specs="PLCC-2/3528; λd 400-410 nm, 50 mcd @20 mA, Vf 3.4 V, 102 mW"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C51933300", expect="GL0603PU01", rank=1,
         specs="0603 'purple light', 58-145 mcd @5 mA, Vf 2.6-3.1 V, If max 30 mA; no spectrum given [ds]",
         note="evidently phosphor-converted: the datasheet warns that sulfides change its 'fluorescent colour'"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C7496841", expect="P2-0805W7YS2", rank=2,
         specs="0805 purple, 100 mcd @5 mA, Vf 2.6-3.0 V, 90 mW"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C7496831", expect="P2-0603W7YS2", rank=3,
         specs="0603 purple, 100 mcd @5 mA, Vf 3 V, 90 mW",
         note="REVERSE-MOUNT part (shines through a hole in the PCB)"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C965821", expect="XL-2012UPC", rank=4,
         specs="0805 pink (pink lens), 303 mcd @20 mA, Vf 3.3 V, 70 mW"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C51933299", expect="GL0603UP01", rank=5,
         specs="0603 pink, 144-249 mcd @5 mA, Vf 2.7-3.2 V"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C965836", expect="XL-1615SURUBC", rank=6,
         specs="1615 4-pin red+blue bi-die, common anode: 465-475 nm + 620-630 nm, 150/160 mcd @20 mA, Vf 3.4/2.4 V",
         note="mix the two dies with PWM for a tunable magenta/purple"),
    dict(cat="b", group="Purple / pink (phosphor) and red+blue bi-die", code="C2843811", expect="XL-3528SURUBC", rank=7,
         specs="3528 4-pin red+blue bi-die, common anode: 465 nm + 620-625 nm, 180/350 mcd @30 mA, Vf 3.2/2.2 V"),
    dict(cat="b", group="UV-A 365-385 nm (comparison)", code="C49652884", expect="XL-HD2835UVA1-A1", rank=1,
         specs="2835 HP; λp 360-375 nm (370 typ), Φe 150-220 mW @120 mA, Vf 3.2-4.0 V, If max 150 mA, Pd 600 mW [ds]",
         note="API description is empty; specs from datasheet"),
    dict(cat="b", group="UV-A 365-385 nm (comparison)", code="C2837382", expect="MHP1016UVACT", rank=2,
         specs="1.6x1.1 mm; 370 nm, 20 mA, Vf 3.7 V, 110 mW"),
    dict(cat="b", group="UV-A 365-385 nm (comparison)", code="C25170633", expect="JNJ-L-3535AW120B-36530", rank=3,
         specs="3535; 365 nm, 500 mA, Vf 4.8 V, 1.5 W"),
    dict(cat="b", group="UV-A 365-385 nm (comparison)", code="C46641552", expect="P2835P1UVS26G12Q-365", rank=4,
         specs="2835; 365 nm (from MPN); no description or datasheet at JLCPCB"),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C701961', expect='LP5036', rank=1,
         specs='36 ch CC sink; 12-bit PWM @29 kHz (21 min); 8-bit colour x 8-bit brightness, log/lin curve; 35 mA/ch (VCC>=3.3 V); OUT<=6 V; I2C; VQFN-46 [ds]',
         note='TI LP50xx; deepest stock of any >=12-bit driver. LED anodes must be on a <=5.5 V rail (OUT abs max 6 V).'),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C3202873', expect='IS31FL3205', rank=2,
         specs='12 ch; selectable PWM 16-bit @244 Hz, 12-bit @3.9 kHz, 8-bit @62 kHz (16 MHz osc); 8-bit DC/ch + global; 38 mA; OUT<=6 V; I2C 1 MHz; QFN-20 3x3 [ds]',
         note='Lumissil/ISSI; only stocked ISSI part with 16-bit PWM (16-bit only at 244 Hz).'),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C1850306', expect='LP5030', rank=3,
         specs='30 ch LP503x: 12-bit PWM @29 kHz; 8-bit colour + brightness; 35 mA/ch; OUT<=6 V; I2C; VQFN-46 [ds]'),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C427525', expect='LP5024', rank=4,
         specs='24 ch LP50xx: 12-bit PWM @29 kHz; 25.5 mA/ch (35 mA at VCC>=3.3 V); I2C; VQFN-32 4x4 [ds]'),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C2653373', expect='LP5018', rank=5,
         specs='18 ch LP50xx: 12-bit PWM @29 kHz; 35 mA/ch; I2C; VQFN-32 4x4 (same datasheet as LP5024) [ds]'),
    dict(cat='c', group='I2C drivers with >=12-bit PWM', code='C1849481', expect='LP5012', rank=6,
         specs='12 ch LP50xx: 12-bit PWM @29 kHz; 35 mA/ch (VCC>=3.3 V); I2C; WQFN-20 3x3 [ds]'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C543004', expect='TLC5971', rank=1,
         specs='12 ch; 16-bit ES-PWM (128 segments: ~19.5 kHz with int. 10 MHz osc; 16-bit frame 153 Hz); 7-bit BC/colour; 60 mA/ch; OUT<=17 V; 2-wire 20 MHz; VQFN-24 [ds]',
         note='VCC 6-17 V via internal 3.3 V LDO (or 3-5.5 V direct): can sit on the 12 V rail and sink series strings; cascades on 2 wires.'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C116842', expect='TLC59711', rank=2,
         specs='12 ch; 16-bit ES-PWM; 7-bit BC/colour; 60 mA/ch; LED supply <=17 V; int. LDO 4-17 V or 3-5.5 V direct; 2-wire; HTSSOP-20 [ds]',
         note='TLC5971 sibling with clock-fail watchdog; Adafruit breakout exists.'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C110098', expect='MBI5043', rank=3,
         specs='16 ch; 16-bit S-PWM (64 x 10-bit sub-periods; ext. GCLK <=33 MHz -> ~32 kHz refresh, 504 Hz frame); 6-bit gain; 45 mA @5 V, 30 mA @3.3 V; OUT<=17 V; SSOP-24 [ds]',
         note='Macroblock; cheapest 16-bit option, but the MCU must supply a continuous GCLK (PWM/PIO pin).'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C702083', expect='TLC5947', rank=4,
         specs='24 ch; 12-bit PWM from int. 4 MHz osc -> ~977 Hz (586-1370 Hz); 30 mA/ch; OUT<=30 V; SPI-style 30 MHz; VQFN-32 5x5 [ds]',
         note='Self-clocked (no GSCLK needed); Adafruit breakout exists.'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C181653', expect='TLC5940', rank=5,
         specs='16 ch; 12-bit PWM from ext. GSCLK <=30 MHz (<=7.3 kHz; MCU drives GSCLK + BLANK); 6-bit dot correction; 120 mA/ch; OUT<=17 V; HTSSOP-28 [ds]',
         note='Old but well known; needs continuous MCU clocking.'),
    dict(cat='c', group='Serial-shift (SPI-style) drivers with 12-16-bit PWM', code='C702086', expect='TLC5955', rank=6,
         specs='48 ch; 16-bit ES-PWM or conventional PWM; dot/brightness/max-current correction; 31.9 mA/ch (VCC>3.6 V); SPI-style; HTSSOP-56 [ds]',
         note='Stock under 1000.'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C5125743', expect='AW21036', rank=1,
         specs='36 ch; 8-bit PWM (122 Hz-62 kHz, 16 MHz osc) x 8-bit DC colour current; <=50 mA/ch; I2C 400 kHz; QFN-44 5x5 [ds]',
         note='Awinic; 8-bit PWM, but PWM x DC current spans ~65000:1 for dim fades. Cheap ($0.40).'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C2678558', expect='PCA9956B', rank=2,
         specs='24 ch; 8-bit PWM @31.25 kHz + 8-bit IREF DAC (0.225-57 mA); OUT<=20 V; I2C Fm+ 1 MHz; TSSOP-38 [ds]',
         note='NXP; OUT<=20 V allows series strings from 12 V.'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C2940546', expect='IS31FL3218', rank=3,
         specs='18 ch; 8-bit (256-step) PWM; 38 mA/ch; I2C 400 kHz; QFN-24 4x4 [ds]',
         note='Requested; 8-bit only.'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C2940604', expect='IS31FL3741A', rank=4,
         specs='39x9 matrix (351 LEDs); 8-bit PWM + 8-bit DC scaling; 29k/3.6k/1.8k/900 Hz; 38 mA; I2C; QFN-60 7x7 [ds]',
         note='Requested; matrix-scanned (1/9 duty per LED).'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C92206', expect='PCA9685', rank=5,
         specs='16 ch; 12-bit PWM but only 24-1526 Hz; NOT constant-current (push-pull 25 mA sink/10 mA source, needs resistors); I2C 1 MHz; TSSOP-28 [ds]',
         note='Requested.'),
    dict(cat='c', group='8-bit or non-constant-current drivers (fail the >=12-bit wish; for comparison)', code='C148077', expect='AW9523B', rank=6,
         specs='16-ch I/O expander with LED mode: 256-step linear constant-current dimming (no PWM, so no flicker); 37 mA/ch; I2C; TQFN-24 4x4 [ds]',
         note='Deepest stock of anything here (~77k), but only 8-bit linear current steps.'),
    dict(cat='c', group='Alternative: RGB LEDs with a built-in 16-bit driver (no driver IC)', code='C22371534', expect='WS2816B', rank=1,
         specs='5050 RGB LED + 3-ch CC driver; 16-bit PWM/ch (+4-bit gamma), 10 kHz refresh; single-wire 800 kbit/s; 3.3-5.5 V [ds]',
         note='Can mix orange/purple from RGB; not a standalone driver.'),
    dict(cat='c', group='Alternative: RGB LEDs with a built-in 16-bit driver (no driver IC)', code='C4154877', expect='WS2816B-2020', rank=2,
         specs='2.2x2 mm WS2816B: 16-bit PWM, 10 kHz refresh; 3.7-5.5 V'),
    dict(cat='d', group='RP2350 / RP2354 (Raspberry Pi)', code='C41378174', expect='RP2354A', rank=1,
         specs='2x Cortex-M33 or Hazard3 RISC-V @150 MHz; 520 KB SRAM; 2 MB stacked flash; 30 GPIO, 4 ADC; 12 PIO SMs; 24 PWM; QFN-60 7x7 [ds]',
         note='No external QSPI flash needed.'),
    dict(cat='d', group='RP2350 / RP2354 (Raspberry Pi)', code='C39843328', expect='RP2354B', rank=2,
         specs='As RP2354A but 48 GPIO, 8 ADC; 2 MB stacked flash; QFN-80 10x10 [ds]',
         note='Stock under 2000.'),
    dict(cat='d', group='RP2350 / RP2354 (Raspberry Pi)', code='C42411118', expect='RP2350A', rank=3,
         specs='As RP2354A without flash (needs external QSPI flash); 30 GPIO; QFN-60 7x7 [ds]'),
    dict(cat='d', group='RP2350 / RP2354 (Raspberry Pi)', code='C42415655', expect='RP2350B', rank=4,
         specs='No flash; 48 GPIO, 8 ADC; QFN-80 10x10 [ds]'),
    dict(cat='d', group='RP2350 / RP2354 (Raspberry Pi)', code='C2040', expect='RP2040', rank=5,
         specs='2x Cortex-M0+ @133 MHz; 264 KB SRAM; external flash; 30 GPIO; LQFN-56 7x7',
         note='Not requested: deep-stock fallback (64k).'),
    dict(cat='d', group='RP2350 12 MHz crystal', code='C20625731', expect='ABM8-272-T3', rank=1,
         specs='12 MHz, CL 10 pF, +/-30 ppm, ESR 50 ohm, 3.2x2.5 mm',
         note='The crystal the RP2350 datasheet (sec 8.2.1.1) recommends and Pico 2 is tuned for [ds].'),
    dict(cat='d', group='RP2350 12 MHz crystal', code='C9002', expect='X322512MSB4SI', rank=2,
         specs='12 MHz, CL 20 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 80 ohm, 3.2x2.5 mm',
         note='BASIC part, but higher CL/ESR than RPi specifies: needs bigger load caps and a start-up check.'),
    dict(cat='d', group='RP2350 regulator inductor (3.3 uH)', code='C42411119', expect='AOTA-B201610S3R3-101-T', rank=1,
         specs='3.3 uH, 2016 (0806), Isat 2.4 A, Irms 2.1 A, DCR 115 mohm, polarity-marked',
         note='RP2350 ds sec 6.3.8.2 requires a shielded, polarity-marked 3.3 uH (Isat>=1.5 A, DCR<=250 mohm) and names this part [ds]. Only 677 in stock.'),
    dict(cat='d', group='RP2350 regulator inductor (3.3 uH)', code='C5832345', expect='FTC201610S3R3MBCA', rank=2,
         specs='3.3 uH, 2016 (0806), Isat 2.3 A, Irms 1.7 A, DCR 140 mohm, molded',
         note='Fallback only: NOT polarity-marked, which the RP2350 ds requires.'),
    dict(cat='d', group='RP2350 regulator inductor (3.3 uH)', code='C18724415', expect='FTC201612S3R3MBCA', rank=3,
         specs='3.3 uH, 2016 (0806), 1.2 mm tall, Isat 2.7 A, Irms 2.4 A, DCR 165 mohm, molded',
         note='Fallback only: NOT polarity-marked.'),
    dict(cat='d', group='STM32', code='C529355', expect='STM32G431CBT6', rank=1,
         specs='Cortex-M4F @170 MHz; 128 KB flash, 32 KB RAM; 38 GPIO; LQFP-48 7x7',
         note='Best-stocked STM32G4; the G4 family has motor-control timers, CORDIC, comparators and op-amps.'),
    dict(cat='d', group='STM32', code='C529356', expect='STM32G431CBU6', rank=2,
         specs='Cortex-M4F @170 MHz; 128 KB flash, 32 KB RAM; 42 GPIO; UFQFPN-48 7x7'),
    dict(cat='d', group='STM32', code='C730123', expect='STM32G474CBT6', rank=3,
         specs='Cortex-M4F @170 MHz; 128 KB flash, 128 KB RAM; 38 GPIO; LQFP-48',
         note='G474 adds the HRTIM. All G474 packages are shallow (<=620).'),
    dict(cat='d', group='STM32', code='C521608', expect='STM32G474RET6', rank=4,
         specs='Cortex-M4F @170 MHz; 512 KB flash, 128 KB RAM; 52 GPIO; LQFP-64',
         note='381 in stock, ~$10.'),
    dict(cat='d', group='STM32', code='C529341', expect='STM32G071C8T6', rank=5,
         specs='Cortex-M0+ @64 MHz; 64 KB flash, 36 KB RAM; 44 GPIO; LQFP-48'),
    dict(cat='d', group='STM32', code='C3446137', expect='STM32G0B1VCT6', rank=6,
         specs='Cortex-M0+ @64 MHz; 256 KB flash, 144 KB RAM; 94 GPIO; LQFP-100',
         note='Smaller G0B1 packages are <450 in stock.'),
    dict(cat='d', group='ESP32 bare chips', code='C2858491', expect='ESP32-C3FH4', rank=1,
         specs='RISC-V @160 MHz; 400 KB SRAM; 4 MB in-package flash; 22 GPIO; Wi-Fi 4 + BLE 5; QFN-32 5x5 [ds]',
         note='No external flash needed; needs a 40 MHz crystal + RF matching network.'),
    dict(cat='d', group='ESP32 bare chips', code='C2838500', expect='ESP32-C3', rank=2,
         specs='RISC-V @160 MHz; 400 KB SRAM; no flash (external SPI flash required); 22 GPIO; QFN-32 5x5 [ds]'),
    dict(cat='d', group='ESP32 bare chips', code='C3013940', expect='ESP32-S3FH4R2', rank=3,
         specs='Dual Xtensa LX7 @240 MHz; 4 MB flash + 2 MB PSRAM in package; Wi-Fi 4 + BLE 5; QFN-56 7x7',
         note='Best-stocked S3 chip.'),
    dict(cat='d', group='ESP32 bare chips', code='C2913196', expect='ESP32-S3FN8', rank=4,
         specs='Dual Xtensa LX7 @240 MHz; 512 KB SRAM; 8 MB in-package flash; 45 GPIO; QFN-56 7x7',
         note='605 in stock.'),
    dict(cat='d', group='ESP32 bare chips', code='C2913192', expect='ESP32-S3', rank=5,
         specs='Dual Xtensa LX7 @240 MHz; no flash; QFN-56 7x7',
         note='762 in stock.'),
    dict(cat='d', group='ESP32 bare chips', code='C5364646', expect='ESP32-C6', rank=6,
         specs='RISC-V @160 MHz; 512 KB SRAM; Wi-Fi 6 + BLE 5 + 802.15.4; no flash; 30 GPIO; QFN-40 5x5',
         note='Only 287 in stock; ESP32-C6FH4/FH8 stock 0.'),
    dict(cat='d', group='ESP32 40 MHz crystal', code='C18214314', expect='XL2EL89COI-111YLC-40M', rank=1,
         specs='40 MHz, CL 12 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 40 ohm, 3.2x2.5 mm'),
    dict(cat='d', group='ESP32 40 MHz crystal', code='C3003278', expect='5YMA40000151SF40E1', rank=2,
         specs='40 MHz, CL 15 pF, +/-10 ppm tol, +/-10 ppm stab, ESR 40 ohm, 3.2x2.5 mm, -20..+85 C',
         note='Tightest stability.'),
    dict(cat='d', group='ESP32 40 MHz crystal', code='C7420757', expect='SX32Y040000BF1T001', rank=3,
         specs='40 MHz, CL 15 pF, +/-10 ppm tol, +/-30 ppm stab, ESR 20 ohm, 3.2x2.5 mm',
         note='Deepest stock (59k).'),
    dict(cat='d', group='ESP32 40 MHz crystal', code='C18213370', expect='K3A400001210', rank=4,
         specs='40 MHz, CL 12 pF, +/-10 ppm tol, +/-20 ppm stab, ESR 30 ohm, 3.2x2.5 mm',
         note='Cheapest.'),
    dict(cat='d', group='FPGA', code='C2678152', expect='ICE40UP5K-SG48I', rank=1,
         specs='iCE40 UltraPlus: 5280 LUTs, 1 Mbit SPRAM + BRAM, 39 I/O, 1.2 V core; QFN-48 7x7',
         note='Only 182 in stock, ~$8; no other iCE40 or Gowin part above 50.'),
    dict(cat='e', group='3-phase drivers (integrated FETs)', code='C5218861', expect='DRV8316RRGFR', rank=1,
         specs='3 half-bridges, 4.5-35 V (40 V abs), 8 A peak, 95 mOhm HS+LS, 6x/3x PWM up to 200 kHz, SPI, integrated current sense, 3.3/5 V buck, VQFN-40 7x5 [ds]',
         note='Most margin for 1-3 A/phase at 12 V; DRV8316CRRGFR (C5447274, ~2.7k) is a second stocked variant'),
    dict(cat='e', group='3-phase drivers (integrated FETs)', code='C92482', expect='DRV8313PWPR', rank=2,
         specs='3 independent half-bridges (EN+IN each), 8-60 V, 2.5 A peak, 0.24+0.24 Ohm, 3.3 V/10 mA LDO, spare comparator, HTSSOP-28 [ds]',
         note='SimpleFOC classic; 2.5 A is peak, plan on ~1.5 A continuous'),
    dict(cat='e', group='3-phase drivers (integrated FETs)', code='C5218862', expect='DRV8311HRRWR', rank=3,
         specs='3 half-bridges, 3-20 V (24 V abs max), 5 A peak, 210 mOhm HS+LS, 6x/3x PWM (H = hardware variant), integrated current sense, WQFN-24 3x3 [ds]',
         note='Cheap with deep stock, but 24 V abs max is tight on a 12 V rail clamped by a 15 V TVS'),
    dict(cat='e', group='3-phase drivers (integrated FETs)', code='C3655732', expect='MP6536DU', rank=4,
         specs='3 half-bridges, 5-26 V, 5.5 A peak, 140 mOhm, QFN-40 5x5 (API)',
         note='Requested; only ~1.2k in stock'),
    dict(cat='e', group='3-phase drivers (integrated FETs)', code='C5296869', expect='AT8313', rank=5,
         specs='DRV8313-style triple half-bridge, 8-35 V, 2.5 A, 450 mOhm, QFN-36 (API)'),
    dict(cat='e', group='Single H-bridge drivers (integrated FETs)', code='C1855818', expect='DRV8874PWPR', rank=1,
         specs='4.5-37 V, 6 A peak, 100+100 mOhm, PMODE: PH/EN, PWM or independent half-bridge, PWM <=100 kHz, IPROPI current sense/regulation, HTSSOP-16 [ds]',
         note='Two of these = dual H-bridge (or 4 independent half-bridges)'),
    dict(cat='e', group='Single H-bridge drivers (integrated FETs)', code='C2827823', expect='AT8236', rank=2,
         specs='5.5-36 V, 6 A peak / 4 A continuous, 200 mOhm HS+LS, IN1/IN2 PWM <=100 kHz, VREF current limit, ESOP-8 [ds]',
         note='ZHONGKEWEI, Chinese-only datasheet; very deep stock and cheap'),
    dict(cat='e', group='Single H-bridge drivers (integrated FETs)', code='C86590', expect='DRV8870DDAR', rank=3,
         specs='6.5-45 V, 3.6 A peak, 565 mOhm HS+LS, IN1/IN2 PWM, current regulation with external sense resistor, SO-8 PowerPAD [ds]',
         note='Deepest stock of any H-bridge'),
    dict(cat='e', group='Single H-bridge drivers (integrated FETs)', code='C545417', expect='TB67H450FNG', rank=4,
         specs='4.5-44 V (50 V abs), 3.5 A max, 0.6 Ohm HS+LS, IN1/IN2 direct PWM or constant-current chopper, HSOP-8 [ds]'),
    dict(cat='e', group='Single H-bridge drivers (integrated FETs)', code='C75864', expect='DRV8871DDAR', rank=5,
         specs='6.5-45 V, 3.6 A peak, 565 mOhm HS+LS, IN1/IN2 PWM, internal current regulation (no sense resistor), SO-8 PowerPAD [ds]',
         note='Requested; ~4x the DRV8870 price'),
    dict(cat='e', group='Dual H-bridge / multi half-bridge drivers (integrated FETs)', code='C177807', expect='DRV8844PWPR', rank=1,
         specs='4 independent half-bridges (EN+IN each), 8-60 V, 2.5 A peak / 1.75 A rms per ch (24 V, 25 C), 0.24+0.24 Ohm, HTSSOP-28 [ds]',
         note='3 coil phases + 1 spare (or 2 H-bridges) from one chip'),
    dict(cat='e', group='Dual H-bridge / multi half-bridge drivers (integrated FETs)', code='C36542', expect='DRV8841PWPR', rank=2,
         specs='Dual H-bridge, 8.2-45 V, 2.5 A peak at 24 V, 400 mOhm HS+LS, IN/IN PWM, 2-bit current control, HTSSOP-28 [ds]'),
    dict(cat='e', group='Dual H-bridge / multi half-bridge drivers (integrated FETs)', code='C2150710', expect='TMC2209-LA', rank=3,
         specs='2-coil stepper driver, 4.75-29 V, 2 A, 340 mOhm, 256 microsteps, STEP/DIR + UART, QFN-28 5x5 (API)',
         note='Current-regulated sinusoidal drive of 2 coils without firmware PWM'),
    dict(cat='e', group='Dual H-bridge / multi half-bridge drivers (integrated FETs)', code='C112630', expect='BTN8962TA', rank=4,
         specs='Single high-current half-bridge (Infineon NovalithIC), 8-18 V, IN/INH inputs, over-current/short/over-temp protection, TO-263-7 (API)',
         note='Only stocked BTN/BTS part (BTS7960 out of stock); oversized for 1-3 A'),
    dict(cat='e', group='Gate drivers (for discrete MOSFETs)', code='C3655801', expect='DRV8300DRGER', rank=1,
         specs='3-phase 100 V gate driver, GVDD 5-20 V, 750 mA source / 1.5 A sink, integrated bootstrap diodes (D variant), cross-conduction prevention, VQFN-24 4x4 [ds]',
         note='Pair with 3x AON7934'),
    dict(cat='e', group='Gate drivers (for discrete MOSFETs)', code='C91879', expect='LM5106MMX', rank=2,
         specs='100 V half-bridge, 1.2 A source / 1.8 A sink, single PWM input + EN, programmable dead time, VDD 8-14 V, VSSOP-10 [ds]'),
    dict(cat='e', group='Gate drivers (for discrete MOSFETs)', code='C2960', expect='IR2104STRPBF', rank=3,
         specs='600 V half-bridge, IN + /SD, internal dead time, VCC 10-20 V, 130/270 mA, SOIC-8 (API)'),
    dict(cat='e', group='Gate drivers (for discrete MOSFETs)', code='C480653', expect='EG2104M', rank=4,
         specs='IR2104-style half-bridge, 600 V bootstrap, VCC 10-20 V, 3.3/5 V logic inputs, built-in dead time, 0.3/0.6 A, SOIC-8 [ds]',
         note='Cheap Chinese IR2104 equivalent'),
    dict(cat='e', group='Gate drivers (for discrete MOSFETs)', code='C913823', expect='UCC27201ADR', rank=5,
         specs='120 V half-bridge, 3 A source/sink, independent HI/LI inputs (no dead time), VDD 8-17 V, SOIC-8 (API)'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C20917', expect='AO3400A', rank=1,
         specs='N, 30 V, 5.7 A, 48 mOhm @2.5 V Vgs, SOT-23 (API)',
         note='Basic; low-side coil/LED switch straight from 3.3 V logic, ~2-3 A'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C22469448', expect='HL3400', rank=2,
         specs='N, 30 V, 5.6 A, 21/25/33 mOhm @10/4.5/2.5 V, SOT-23 (API)',
         note='AO3400A equivalent'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C485677', expect='AON7934', rank=3,
         specs='Dual asymmetric N half-bridge (S1/D2 tied), 30 V, Q1 <10.2 / Q2 <7.7 mOhm @10 V (<15.8/<11.6 @4.5 V), 16/18 A, DFN3x3 [ds]',
         note='One per phase with DRV8300/LM5106'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C477943', expect='AO4882', rank=4,
         specs='Dual N (independent), 40 V, 27 mOhm @4.5 V, SOIC-8 (API)'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C2944312', expect='AO4406A', rank=5,
         specs='N, 30 V, 12 A, 10 mOhm @10 V, SOP-8 (API)',
         note='UMW second source of the AOS part; for ~5 A low-side'),
    dict(cat='e', group='N-MOSFETs (single/dual)', code='C53550', expect='IRLML6344', rank=6,
         specs='N, 30 V, 5 A, 29 mOhm @4.5 V, SOT-23 (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C381116', expect='DC-005-5A-2.0', rank=1,
         specs='THT right-angle, 2.0 mm pin (5.5x2.1 plugs), 5 A, 24 V (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C17701683', expect='DC007B-2.0', rank=2,
         specs='THT right-angle, 2.0 mm pin, 7 A, 20 V (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C720558', expect='DC-005-A250', rank=3,
         specs='THT right-angle, 2.5 mm pin (5.5x2.5 plugs), 5 A, 24 V (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C129006', expect='DC-044A-20A', rank=4,
         specs='THT right-angle, 2.0 mm pin, 5 A, 30 V, low profile (7.2 mm) (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C17701686', expect='DC007B-2.5', rank=5,
         specs='THT right-angle, 2.5 mm pin, 7 A, 20 V (API)'),
    dict(cat='f', group='Barrel jacks (5.5 mm, >=5 A)', code='C22434687', expect='PJ-002AH-SMT', rank=6,
         specs='SMD right-angle, 2.0 mm pin, 5 A, 24 V (API)',
         note='Only SMD >=5 A jack with stock >1k'),
    dict(cat='f', group='TVS (~15 V)', code='C19077569', expect='SMBJ15A', rank=1,
         specs='Unidirectional 600 W, VRWM 15 V, VBR 16.7 V min, VC 24.4 V @24.6 A, SMB (API)'),
    dict(cat='f', group='TVS (~15 V)', code='C19077571', expect='SMBJ16A', rank=2,
         specs='Unidirectional 600 W, VRWM 16 V, VC 26 V @23 A, SMB (API)',
         note='much deeper stock than SMBJ15A'),
    dict(cat='f', group='TVS (~15 V)', code='C19077535', expect='SMAJ15A', rank=3,
         specs='Unidirectional 400 W, VRWM 15 V, VC 24.4 V @16.4 A, SMA (API)'),
    dict(cat='f', group='TVS (~15 V)', code='C113988', expect='SMBJ15A', rank=4,
         specs='Unidirectional 600 W, VRWM 15 V, VC 24.4 V @24.6 A, SMB (API)'),
    dict(cat='f', group='Reverse-polarity P-MOSFETs', code='C2841482', expect='AO4407A', rank=1,
         specs='P, -30 V, 14 A, 9.5 mOhm @10 V, SOP-8 (API)',
         note='UMW; ~0.24 W at 5 A. Add a zener gate clamp if Vin can exceed the Vgs rating'),
    dict(cat='f', group='Reverse-polarity P-MOSFETs', code='C15127', expect='AO3401A', rank=2,
         specs='P, -30 V, 4 A, 47 mOhm @10 V, SOT-23 (API)',
         note='Basic; only for <=2 A'),
    dict(cat='f', group='Reverse-polarity P-MOSFETs', code='C2944310', expect='AO4435', rank=3,
         specs='P, -30 V, 12 A, 15 mOhm @10 V, SOP-8 (API)'),
    dict(cat='f', group='Reverse-polarity P-MOSFETs', code='C431196', expect='AONR21357', rank=4,
         specs='P, -30 V, 34 A, 12.3 mOhm @4.5 V, DFN3x3 (API)',
         note='Genuine AOS'),
    dict(cat='f', group='Reverse-polarity P-MOSFETs', code='C400894', expect='AOD4185', rank=5,
         specs='P, -40 V, 40 A, 15 mOhm @10 V, TO-252 (API)',
         note='Genuine AOS; 40 V margin'),
    dict(cat='f', group='Fuses / PTC', code='C19078763', expect='2920L500/30', rank=1,
         specs='PTC, 5 A hold / 10 A trip, 30 V, 40 A max, 2920 (API)'),
    dict(cat='f', group='Fuses / PTC', code='C20539728', expect='BSMD2920-500-30V', rank=2,
         specs='PTC, 5 A hold / 10 A trip, 30 V, 2920 (API)'),
    dict(cat='f', group='Fuses / PTC', code='C41367230', expect='BSMD1206C-1700T', rank=3,
         specs='One-time fuse, 7 A, 32 V, 150 A breaking, 1206 (API)',
         note='7 A rating for a 5 A load (derating)'),
    dict(cat='f', group='Fuses / PTC', code='C48467', expect='0451005.MRL', rank=4,
         specs='One-time fuse (Littelfuse NANO2), 5 A, 125 V, 50 A breaking, 2410 (API)'),
    dict(cat='f', group='Fuses / PTC', code='C41367229', expect='BSMD1206C-1500T', rank=5,
         specs='One-time fuse, 5 A, 32 V, 150 A breaking, 1206 (API)'),
    dict(cat='f', group='eFuse ICs', code='C2864845', expect='TPS259474LRPWR', rank=1,
         specs='TPS25947: 2.7-23 V, 28 mOhm, 0.5-6 A adj. ILIM (circuit breaker), adj. OVLO, true reverse blocking, -15 V reverse-polarity tolerant, latch-off, VQFN-10 2x2 [ds]',
         note='Replaces the P-FET + PTC; A (auto-retry) variant C3662807 has only ~400 stock'),
    dict(cat='f', group='eFuse ICs', code='C165131', expect='TPS259241DRCR', rank=2,
         specs='TPS25924: 12 V eFuse, 4.5-13.8 V (20 V abs), fixed 15 V OV clamp, 1-5 A adj. ILIM, 28 mOhm, VSON-10 3x3 [ds]'),
    dict(cat='f', group='eFuse ICs', code='C471038', expect='TPS259571DSGR', rank=3,
         specs='TPS2595: 2.7-18 V, 34 mOhm, up to 4 A, no OV clamp, auto-retry, WSON-8 2x2 [ds]',
         note='Requested family; 4 A max'),
    dict(cat='f', group='eFuse ICs', code='C3662793', expect='TPS259470LRPWR', rank=4,
         specs='TPS25947: 2.7-23 V, 28 mOhm, 0.5-6 A active current limit, adj. OVLO, reverse blocking, latch-off, VQFN-10 2x2 [ds]'),
    dict(cat='f', group='eFuse ICs', code='C544399', expect='TPS26600PWPR', rank=5,
         specs='TPS26600: 4.2-60 V, 150 mOhm, 0.1-2.23 A, HTSSOP-16 (API)',
         note='Requested; current too low for a 5 A input'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C46550472', expect='MA35V470M10X13', rank=1,
         specs='Polymer Al, 470 uF 35 V, 16 mOhm, 3.8 A ripple @100 kHz, 2000 h @105 C, D10x12.5 SMD (API)'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C46550466', expect='MA25V470M8x10', rank=2,
         specs='Polymer Al, 470 uF 25 V, 25 mOhm, 4.1 A ripple, D8x10 SMD (API)',
         note='25 V is marginal against a TVS clamp'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C46550469', expect='MA35V220M8X9', rank=3,
         specs='Polymer Al, 220 uF 35 V, 28 mOhm, 2.9 A ripple, D8x9 SMD (API)'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C46550413', expect='JVJ35V470M10x10', rank=4,
         specs='Al electrolytic, 470 uF 35 V, 320 mA ripple @120 Hz, 2000 h @105 C, D10x10.5 SMD (API)',
         note='Cheap but low ripple rating'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C48935389', expect='RV35V470M8X10', rank=5,
         specs='Al electrolytic, 470 uF 35 V, 190 mA ripple @120 Hz, 5000 h @105 C, D8x10.5 SMD (API)'),
    dict(cat='f', group='Bulk capacitors (25 V+, 100-470 uF)', code='C125977', expect='UWT1H221MNL1GS', rank=6,
         specs='Al electrolytic (Nichicon), 220 uF 50 V, 220 mA ripple @120 Hz, 1000 h @105 C, D10x10 SMD (API)'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C311983', expect='TPS54302DDCR', rank=1,
         specs='Sync, 4.5-28 V in (30 V abs), 3 A, fixed 400 kHz, Eco-mode, SOT-23-6; L = 10 uH (5 V) / 6.8 uH (3.3 V) [ds]',
         note='Best balance of input margin, size and stock'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C9864', expect='TPS5430DDAR', rank=2,
         specs='Non-sync, 5.5-36 V in (40 V abs), 3 A cont. (4 A peak), fixed 500 kHz, SOIC-8 PowerPAD; needs Schottky catch diode; datasheet example L = 15 uH [ds]',
         note='Basic part: no setup fee'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C116592', expect='TPS563201DDCR', rank=3,
         specs='Sync, 4.5-17 V in (19 V abs), 3 A, 580 kHz, SOT-23-6; L = 3.3 uH (5 V) / 2.2 uH (3.3 V) [ds]',
         note='Cheapest and deepest, but little margin above a 12 V rail'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C3200405', expect='TPS62933DRLR', rank=4,
         specs='Sync, 3.8-30 V in, 3 A, 200 kHz-2.2 MHz adj., SOT-583 (API)'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C9865', expect='TPS54331DR', rank=5,
         specs='Non-sync, 3.5-28 V in, 3 A, 570 kHz, SOIC-8; needs Schottky catch diode (API)',
         note='requested'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C111875', expect='SY8205FCC', rank=6,
         specs='Sync, 4.5-30 V in, 5 A, 500 kHz, SOIC-8-EP (API)',
         note='Requested'),
    dict(cat='g', group='12V->5V/3.3V bucks 2-3 A', code='C61063', expect='XL1509-5.0E1', rank=7,
         specs='Non-sync, 4.5-40 V in (45 V abs), fixed 5.0 V out, 2 A, 150 kHz, SOIC-8; app circuit 12 V->5 V/2 A uses 68 uH + Schottky [ds]',
         note='the only other Basic buck besides TPS5430DDAR; 5 V only (the ADJ version is not Basic); big inductor'),
    dict(cat='g', group='Other requested 12 V bucks (stocked)', code='C2071106', expect='TPS56339DDCR', rank=1,
         specs='Sync, 4.5-24 V in, 3 A, 500 kHz, SOT-23-6 (API)'),
    dict(cat='g', group='Other requested 12 V bucks (stocked)', code='C479075', expect='SY8113IADC', rank=2,
         specs='Sync, 4.2-18 V in, 3 A, 500 kHz, TSOT-23-6 (API)'),
    dict(cat='g', group='Other requested 12 V bucks (stocked)', code='C5383002', expect='LMR51420YDDCR', rank=3,
         specs='Sync, 4.5-36 V in, 2 A, 1.1 MHz, SOT-23-6 (API)'),
    dict(cat='g', group='Other requested 12 V bucks (stocked)', code='C45889', expect='MP2315GJ-Z', rank=4,
         specs='Sync, 4.5-24 V in, 3 A, 500 kHz, TSOT-23-8 (API)',
         note='Expensive here'),
    dict(cat='g', group='5V->3.3V buck', code='C141836', expect='TLV62569DBVR', rank=1,
         specs='Sync, 2.5-5.5 V in, 2 A, 1.5 MHz, SOT-23-5; L = 2.2 uH [ds]'),
    dict(cat='g', group='5V->3.3V buck', code='C398365', expect='TLV62569PDDCR', rank=2,
         specs='As TLV62569 plus power-good output, SOT-23-6 (API)'),
    dict(cat='g', group='5V->3.3V buck', code='C479074', expect='SY8089A1AAC', rank=3,
         specs='Sync, 2.5-5.5 V in, 2 A, 1.5 MHz, SOT-23-5 (API)'),
    dict(cat='g', group='5V->3.3V buck', code='C5350187', expect='TPS62A02DRLR', rank=4,
         specs='Sync, 2.5-5.5 V in, 2 A, 2.4 MHz, SOT-563 (API)'),
    dict(cat='g', group='Power inductors', code='C167223', expect='FXL0630-100-M', rank=1,
         specs='10 uH, 4.5 A rated / 5.5 A sat, 68 mOhm, molded 7x6.6 mm (API)',
         note='TPS54302 at 5 V out'),
    dict(cat='g', group='Power inductors', code='C167221', expect='FXL0630-6R8-M', rank=2,
         specs='6.8 uH, 5 A rated / 6 A sat, 48 mOhm, molded 7x6.6 mm (API)',
         note='TPS54302 at 3.3 V out'),
    dict(cat='g', group='Power inductors', code='C177243', expect='FXL0630-150-M', rank=3,
         specs='15 uH, 3 A rated / 4 A sat, 115 mOhm, molded 7x6.6 mm (API)',
         note='TPS5430 at 5 V out'),
    dict(cat='g', group='Power inductors', code='C167219', expect='FXL0630-3R3-M', rank=4,
         specs='3.3 uH, 8.5 A rated / 9.5 A sat, 22 mOhm, molded 7x6.6 mm (API)',
         note='TPS563201 at 5 V out'),
    dict(cat='g', group='Power inductors', code='C5832372', expect='FTC252012S2R2MBCA', rank=5,
         specs='2.2 uH, 3 A rated / 3.8 A sat, 55 mOhm, 1008 (2.5x2.0 mm) (API)',
         note='TLV62569 at 3.3 V out'),
    dict(cat='g', group='Power inductors', code='C132141', expect='MWSA0603S-100MT', rank=6,
         specs='10 uH, 4.5 A rated / 5.5 A sat, 67 mOhm, molded 7x6.6 mm (API)',
         note='Sunlord second source for the 10 uH'),
    dict(cat='g', group='Catch diode (non-sync TPS5430/TPS54331)', code='C8678', expect='SS34', rank=1,
         specs='Schottky, 40 V, 3 A, 0.55 V @3 A, SMA (API)',
         note=''),
    dict(cat='g', group='Catch diode (non-sync TPS5430/TPS54331)', code='C22452', expect='SS54', rank=2,
         specs='Schottky, 40 V, 5 A, 0.55 V @5 A, SMA (API)',
         note=''),
    dict(cat='h', group='Accelerometers / IMUs', code='C967633', expect='LSM6DS3TR-C', rank=1,
         specs='6-axis IMU: ±2/4/8/16 g + ±125..2000 dps, ODR to 6.66 kHz, 0.9 mA combo HP, 4 KB FIFO, I2C/SPI, 1.71-3.6 V, LGA-14L 2.5x3x0.83 mm [ds]',
         note='Deepest-stock IMU; no Basic accelerometer exists (only Preferred one: MPU-6050 C24112, ~$15.6, EOL)'),
    dict(cat='h', group='Accelerometers / IMUs', code='C189624', expect='LIS2DW12', rank=2,
         specs='3-axis accel ±2/4/8/16 g, 14-bit HP / 12-bit LP, ODR 1.6-1600 Hz, 50 nA PD, 90 µA HP, tap/free-fall/wake/6D engine, 32-level FIFO, I2C/SPI, 1.62-3.6 V, LGA-12 2x2 [ds]',
         note='Accel-only, lowest power; ST original (MSKSEMI/HXY clones also listed, not recommended)'),
    dict(cat='h', group='Accelerometers / IMUs', code='C19274408', expect='SC7A20H', rank=3,
         specs='3-axis accel ±2/4/8/16 g, 12-bit, ODR 1.56 Hz-4.27 kHz, tap/free-fall/6D/wake, FIFO, I2C/SPI, 1.71-3.6 V, LGA-12 2x2x1.0 mm [ds]',
         note='Silan; cheapest and deepest stock; datasheet in Chinese only'),
    dict(cat='h', group='Accelerometers / IMUs', code='C2836813', expect='BMI270', rank=4,
         specs='6-axis IMU ±2..16 g + ±125..2000 dps, 16-bit, 2 KB FIFO, I2C/SPI, 1.71-3.6 V, 3.5 µA, LGA-14 2.5x3 mm (API)'),
    dict(cat='h', group='Accelerometers / IMUs', code='C2655100', expect='LSM6DSOTR', rank=5,
         specs='6-axis IMU ±2..16 g + ±125..2000 dps, 9 KB FIFO, I2C/SPI/I3C, 1.71-3.6 V, LGA-14 2.5x3 mm (API)',
         note='Newer ST IMU, shallower stock and ~2x the price of LSM6DS3TR-C'),
    dict(cat='h', group='Accelerometers / IMUs', code='C2887190', expect='QMA6100P', rank=6,
         specs='3-axis accel ±2..32 g, 14-bit, motion-event detection, I2C/SPI, 1.71-3.6 V, 500 nA, LGA-12 2x2 mm (API)',
         note='QST; cheap, deep stock, ±32 g for hard shakes'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C3715882', expect='TMAG5273A2', rank=1,
         specs='3D linear Hall ±133/±266 mT, 12-bit, 20 kSPS (1 axis), angle CORDIC, temp sensor, I2C ≤1 MHz + INT, 1.7-3.6 V, 2.3 mA active, SOT-23-6 [ds]',
         note='Right range for tracking NdFeB magnets near the coils; A1 (±40/80 mT) variants have <50 in stock'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C404328', expect='MMC5603NJ', rank=2,
         specs='3-axis AMR magnetometer ±30 G (±3 mT), 20-bit 0.0625 mG/LSB, 2 mG rms noise, BW to 1 kHz, SET/RESET, I2C 400 kHz/I3C, 1.62-3.6 V, WLP-4 0.8x0.8x0.4 mm [ds]',
         note='Earth-field/compass grade: saturates near magnets; tiny 4-ball WLP'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C404329', expect='MMC5983MA', rank=3,
         specs='3-axis AMR magnetometer ±8 G, 18-bit, I2C/SPI, 2.8-3.6 V, 450 µA, LGA-16 3x3 mm (API)',
         note='MEMSIC, -40..+105 °C'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C3716101', expect='TMAG5170A2', rank=4,
         specs='3D linear Hall up to ±300 mT, SPI, 2.3-5.5 V, 3.4 mA, -40..+150 °C, VSSOP-8 (API)',
         note='SPI alternative to TMAG5273; A1 (±100 mT) C5220642 also stocked'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C919695', expect='LIS2MDL', rank=5,
         specs='3-axis magnetometer ±50 G (±5 mT), 16-bit, I2C/SPI, 1.71-3.6 V, 200 µA, LGA-12 2x2 mm (API)',
         note='ST; pricey'),
    dict(cat='h', group='Magnetometers / 3D Hall', code='C2847467', expect='QMC5883P', rank=6,
         specs='3-axis magnetometer ±30 G (±3 mT), 16-bit, I2C, 2.5-3.6 V, 35 µA, LGA-16 3x3 mm (API)',
         note='QMC5883L itself is out of stock (see ABSENT); P version is a different part'),
    dict(cat='h', group='Linear Hall sensors', code='C266123', expect='DRV5055A4', rank=1,
         specs='Ratiometric analog Hall, 12.5 mV/mT @5 V (±169 mT), 7.5 mV/mT @3.3 V (±176 mT), 20 kHz BW, 3.3 or 5 V supply, SOT-23 [ds]',
         note='Range suited to NdFeB magnets close to the sensor'),
    dict(cat='h', group='Linear Hall sensors', code='C962987', expect='DRV5055A1', rank=2,
         specs='Ratiometric analog Hall, 100 mV/mT @5 V (±21 mT), 60 mV/mT @3.3 V (±22 mT), 20 kHz BW, SOT-23 [ds]',
         note='Most sensitive DRV5055, deepest stock; saturates near magnets'),
    dict(cat='h', group='Linear Hall sensors', code='C266128', expect='DRV5055A3', rank=3,
         specs='Ratiometric analog Hall, 25 mV/mT @5 V (±85 mT), 15 mV/mT @3.3 V (±88 mT), 20 kHz BW, SOT-23 [ds]'),
    dict(cat='h', group='Linear Hall sensors', code='C126669', expect='SS39ET', rank=4,
         specs='Honeywell linear Hall (SMD sibling of SS49E), 1.4 mV/G, ±100 mT, 2.7-6.5 V, 6 mA, SOT-23 (API)'),
    dict(cat='h', group='Linear Hall sensors', code='C85697', expect='SS49E', rank=5,
         specs='Honeywell linear Hall, 1.4 mV/G, ±100 mT, 2.7-6.5 V, 6 mA, TO-92S through-hole (API)',
         note='Through-hole; SS39ET is the SMD equivalent'),
    dict(cat='h', group='Linear Hall sensors', code='C5447698', expect='MT9102ET', rank=6,
         specs='NOVOSENSE linear Hall, 1.6-2.5 mV/G, ±88 mT, rail-to-rail output, 3-5.5 V, SOT-23 (API)'),
    dict(cat='h', group='Time-of-flight', code='C190004', expect='VL53L1CX', rank=1,
         specs='VL53L1X: 940 nm Class 1 laser ToF, up to 4 m, 50 Hz, 27° FoV, programmable ROI, I2C ≤1 MHz, 2.6-3.5 V, LGA-12 4.9x2.5x1.56 mm [ds]',
         note='VL53L1CXV0FY/1 is the ordering code of the VL53L1X'),
    dict(cat='h', group='Time-of-flight', code='C3178303', expect='VL53L5CX', rank=2,
         specs='4x4/8x8 multizone ToF, 2-400 cm per zone, up to 60 Hz, 63° diag FoV, 940 nm VCSEL Class 1, I2C ≤1 MHz, 2.8/3.3 V, 6.4x3.0x1.5 mm [ds]',
         note='Depth image for gestures; driven through ST C driver/API'),
    dict(cat='h', group='Time-of-flight', code='C91199', expect='VL53L0CX', rank=3,
         specs='VL53L0X: 940 nm ToF up to 2 m, I2C, 2.6-3.5 V, 19 mA, 4.4x2.4x1.0 mm (API)',
         note='Listed under ordering code VL53L0CXV0DH/1 (keyword "VL53L0X" finds only stock-0 placeholders)'),
    dict(cat='h', group='Time-of-flight', code='C3178291', expect='VL53L4CD', rank=4,
         specs='ToF 1-1300 mm, temperature compensated, I2C, 2.6-3.5 V, 4.4x2.4x1.0 mm (API)'),
    dict(cat='h', group='Time-of-flight', code='C7386355', expect='VL53L8CX', rank=5,
         specs='8x8 multizone ToF, low-power mode, interrupt output, LGA-16 (API)',
         note='Pricier successor of VL53L5CX'),
    dict(cat='h', group='Time-of-flight', code='C2655167', expect='VL6180', rank=6,
         specs='Short-range ToF proximity 0-62 cm, 1.7 mA, I2C, 2.6-3.0 V, 4.8x2.8x1.0 mm (API)'),
    dict(cat='h', group='Ambient light sensors', code='C364577', expect='LTR-303ALS', rank=1,
         specs='0.01-64k lux, 16-bit, gains 1-96x, INT pin, 50/60 Hz flicker rejection, I2C 400 kHz, 2.4-3.6 V, 2.0x2.0x0.7 mm 6-pin ChipLED [ds]'),
    dict(cat='h', group='Ambient light sensors', code='C78960', expect='BH1750FVI', rank=2,
         specs='1-65535 lx, 16-bit, I2C, 2.4-3.6 V, WSOF-6 (API)',
         note='Deepest stock'),
    dict(cat='h', group='Ambient light sensors', code='C1850416', expect='VEML7700', rank=3,
         specs='0-120 klx, 16-bit, I2C, 2.5-3.6 V, 4-pin SMD 6.8x3.0x2.35 mm (API)'),
    dict(cat='h', group='Ambient light sensors', code='C90462', expect='OPT3001DNPR', rank=4,
         specs='0.01-83 klx, eye-matched, I2C, 1.8-3.6 V, 1.8 µA, USON-6 2.1x2.1 mm (API)'),
    dict(cat='h', group='Ambient light sensors', code='C132182', expect='VEML6030', rank=5,
         specs='0-120 klx, 16-bit, I2C, 2.5-3.6 V, SMD-6P 2x2x0.87 mm (API)'),
    dict(cat='h', group='Ambient light sensors', code='C492382', expect='LTR-308ALS', rank=6,
         specs='Up to 157 klx, I2C, 1.7-3.6 V (API)'),
    dict(cat='h', group='MEMS microphones', code='C3171752', expect='MMICT3902', rank=1,
         specs='TDK T3902 PDM, bottom port, −26 dBFS, SNR 64.5 dBA, AOP 120 dB SPL (126 HP mode), 185 µA LP / 12 µA sleep, 1.65-3.63 V, 3.5x2.65x0.98 mm [ds]',
         note='Bottom port needs a PCB hole; PDM needs a PIO/PDM-capable peripheral'),
    dict(cat='h', group='MEMS microphones', code='C481302', expect='ZTS6216', rank=2,
         specs='Analog, top port, −38 dBV/Pa, SNR 65 dBA, AOP 125 dB SPL, 120 µA, 1.5-3.6 V, 2.75x1.85x1.0 mm [ds]',
         note='Top port (no PCB hole); needs AC coupling + gain stage into an ADC'),
    dict(cat='h', group='MEMS microphones', code='C2895290', expect='SD18OB261', rank=3,
         specs='Goertek PDM, −26 dBFS, SNR 65 dB, AOP 120 dB SPL, 1.6-3.6 V, 3.5x2.65 mm [ds]'),
    dict(cat='h', group='MEMS microphones', code='C481300', expect='ZTS6117', rank=4,
         specs='Analog, −42 dBV, SNR 59 dB, 120 µA, 1.5-3.6 V, 2.75x1.85x0.9 mm (API)',
         note='Cheapest analog option'),
    dict(cat='h', group='MEMS microphones', code='C503097', expect='MP34DT06J', rank=5,
         specs='ST PDM, −26 dBFS, SNR 64 dB, 650 µA, HCLGA-4LD 3x4x1 mm (API)'),
    dict(cat='h', group='MEMS microphones', code='C5656610', expect='ICS-43434', rank=6,
         specs='TDK I2S digital output, −26 dBFS, SNR 64 dB, 550 µA, 1.65-3.63 V, LGA-6 3.5x2.65x0.98 mm (API)',
         note='Only I2S-output mic with >1k stock'),
    dict(cat='h', group='Ultrasonic 40 kHz transducers', code='C17701106', expect='HY40A16T12', rank=1,
         specs='40±0.5 kHz open-type transmitter, SPL ≥116 dB, 2200 pF, 70° (−6 dB), ≤140 Vpp, Al can Ø16x12 mm, through-hole [ds]',
         note='Through-hole only; pair with HY40A16R12-1'),
    dict(cat='h', group='Ultrasonic 40 kHz transducers', code='C17701107', expect='HY40A16R12', rank=2,
         specs='40 kHz open-type receiver, −62 dB (0 dB = 1 V/µbar), Ø16x12 mm, through-hole (API)',
         note='Shallow stock'),
    dict(cat='h', group='Ultrasonic 40 kHz transducers', code='C242189', expect='GU1610B-40TR', rank=3,
         specs='INGHAi 40 kHz transceiver, through-hole (API)',
         note='Shallow stock'),
    # ---- i. USB-C receptacle and PD sink controllers --------------------
    dict(cat="i", group="USB-C receptacle", code="C165948", expect="TYPE-C-31-M-12", rank=1,
         specs="HRO 16-pin USB-C receptacle, SMD right angle, 20 V 5 A, 10,000 cycles"),
    dict(cat='i', group='USB-C PD sink controllers', code='C42459160', expect='CH224A', rank=1,
         specs='PD3.2 sink (EPR/AVS/PPS/SPR) + BC1.2; asks 5/9/12/15/20/28 V; 4-30 V; 1-resistor, I/O-level or I2C config; built-in HV LDO + OVP; ESSOP-10 [ds]',
         note='WCH datasheet: "CH224A is pin-compatible with CH224K" (CH224K is out of stock); only peripherals change (VHV pin takes VBUS + cap, no series resistor); CFG1 24 kOhm = 12 V [ds]'),
    dict(cat='i', group='USB-C PD sink controllers', code='C7471904', expect='HUSB238', rank=2,
         specs='PD3.0 sink up to 100 W (5-20 V), Type-C 1.4, BC1.2/Apple; VSET/ISET resistors or I2C; GATE pin drives ext. PMOS; 3-25 V (30 V abs); DFN-10 3x3 [ds]',
         note='USB-IF certified (TID 3666); good second source to CH224A'),
    dict(cat='i', group='USB-C PD sink controllers', code='C3975094', expect='CH224D', rank=3,
         specs='PD3.0 sink up to 100 W (5/9/12/15/20 V); 1-resistor or I/O-level config; 4-30 V; QFN-20 3x3 [ds: CH224 family sheet]'),
    dict(cat='i', group='USB-C PD sink controllers', code='C132291', expect='FUSB302B', rank=4,
         specs='Type-C CC logic + USB-PD BMC PHY, I2C to an MCU; 2.8-5.5 V supply; WQFN-14 2.5x2.5 (API)',
         note='needs a PD stack in MCU firmware; most flexible (any PDO/PPS) but most work'),
    dict(cat='i', group='USB-C PD sink controllers', code='C24833806', expect='HUSB238A', rank=5,
         specs='PD3.1 sink incl. EPR: 5/9/12/15/20/28/48 V, QC2.0/BC1.2; 3.15-29.4 V; QFN-16 3x3 (API)'),
    dict(cat='i', group='USB-C PD sink controllers', code='C2678061', expect='STUSB4500', rank=6,
         specs='standalone PD2.0/3.0 sink controller, PDOs stored in NVM, I2C; QFN-24 4x4 (API)',
         note='the most expensive option'),
    dict(cat='j', group='Qi / wireless-power TX ICs', code='C515682', expect='IP6808', rank=1,
         specs='Qi (WPC 1.2.4) TX SoC, 5-10 W, A11 coil; integrated NMOS full-bridge gate driver + V/I ASK demod, FOD; 4.5-22 V in (25 V abs); QFN-32 5x5 [ds]',
         note='external full-bridge N-FETs needed; pairs with the A11 TX coil below'),
    dict(cat='j', group='Qi / wireless-power TX ICs', code='C2927864', expect='IP6809', rank=2,
         specs='Qi (WPC 1.2.4) TX SoC, 5-15 W, 2-3 coils (A28/MP-A8); integrated NMOS full-bridge driver, FOD, PD3.0 input request; 4.5-22 V; QFN-40 6x6 [ds]'),
    dict(cat='j', group='Qi / wireless-power TX ICs', code='C134094', expect='BQ500101', rank=3,
         specs='NexFET half-bridge power stage (driver + FETs) for Qi TX: VIN <=24 V, 10 A cont./15 A peak, <=600 kHz, 3.3/5 V PWM input; SON 3.5x4.5 [ds]',
         note='power stage only (two = full bridge); suits an MCU-PWM-driven custom resonant link; low stock'),
    dict(cat='j', group='Qi / wireless-power TX ICs', code='C2921390', expect='IP6826', rank=4,
         specs='Qi (WPC 1.2) TX, 15 W, FOD, 4.5-12 V in; QFN-32 5x5 (API)',
         note='LCSC description says "Need to burn firmware"'),
    dict(cat='j', group='Qi / wireless-power TX ICs', code='C5896696', expect='RT3181', rank=5,
         specs='Qi TX controller, 15 W, FOD, watchdog, 5-19 V; WQFN-48 6x6 (API)',
         note='low stock'),
    dict(cat='j', group='Qi / wireless-power RX ICs', code='C55663', expect='BQ51013B', rank=1,
         specs='Qi (WPC 1.1) RX: full sync rectifier + LDO, 5.0 V out (4.95-5.04 V @1 A), <=1.5 A, VRECT 4-10 V (20 V abs), 93% peak eff.; VQFN-20 4.5x3.5 [ds]',
         note='closed loop needs a Qi-type TX (ASK back-modulation; WPC 110-205 kHz)'),
    dict(cat='j', group='Qi / wireless-power RX ICs', code='C42411074', expect='IP6831', rank=2,
         specs='Qi BPP 2 W RX: integrated sync rectifier, 5.0-5.1 V out, <=400 mA, RECT OVP 18 V; QFN-16 3x3 [ds]',
         note='cheapest RX; tuned for small/irregular coils (earbud/wearable class)'),
    dict(cat='j', group='Qi / wireless-power RX ICs', code='C133307', expect='BQ51050B', rank=3,
         specs='Qi RX with integrated Li-ion charger: 4.2 V, <=1.5 A, 4-10 V in, NTC input; QFN-20 (API)',
         note='only if a satellite carries a Li-ion cell'),
    dict(cat='j', group='Schottky rectifiers', code='C191023', expect='1N5819WS', rank=1,
         specs='Schottky 40 V 1 A, Vf 0.6 V @1 A, 25 A surge; SOD-323 (API)',
         note='Basic; four make a full bridge on a small satellite PCB'),
    dict(cat='j', group='Schottky rectifiers', code='C8678', expect='SS34', rank=2,
         specs='Schottky 40 V 3 A, Vf 0.55 V @3 A; SMA (API)',
         note='Basic; for 1-3 A bridges (SS54 C22452 is a Basic 5 A option)'),
    dict(cat='j', group='Schottky rectifiers', code='C2480', expect='SS14', rank=3,
         specs='Schottky 40 V 1 A, Vf 0.55 V @1 A, 25 A surge; SMA (API)',
         note=''),
    dict(cat='j', group='Schottky rectifiers', code='C8598', expect='B5819W', rank=4,
         specs='Schottky 40 V 1 A, Vf 0.6 V @1 A; SOD-123 (API)',
         note='Basic; MDD B5819W C64885 is Preferred with 925k stock'),
    dict(cat='j', group='Schottky rectifiers', code='C19726', expect='BAT54S', rank=5,
         specs='dual Schottky, series pair, 30 V 200 mA, Vf 0.8 V @100 mA; SOT-23 (API)',
         note='two = a full bridge for <=200 mA; BAT54C,215 C37704 (common cathode) is Preferred'),
    dict(cat='j', group='Schottky rectifiers', code='C880909', expect='KMB14F', rank=6,
         specs='Schottky bridge rectifier 40 V 1 A, Vf 0.55 V @1 A, 30 A surge; MBS (API)',
         note='one-part full bridge; AB24S C882375 (MDD, 2 A, ABS) for more current'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C62774', expect='CC0805JRNPO9BN102', rank=1,
         specs='1 nF ±5% 50 V NP0, 0805 (API)',
         note='ladder 1 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C28260', expect='CL21C222JBFNNNE', rank=1,
         specs='2.2 nF ±5% 50 V C0G, 0805 (API)',
         note='ladder 2.2 nF; the only Basic (or Preferred) C0G between 1 and 100 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C77063', expect='GRM2165C1H472JA01D', rank=1,
         specs='4.7 nF ±5% 50 V C0G, 0805 (API)',
         note='ladder 4.7 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C2971995', expect='0805CG103J500NT', rank=1,
         specs='10 nF ±5% 50 V C0G, 0805 (API)',
         note='ladder 10 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C97929', expect='GRM3195C1H223JA01D', rank=1,
         specs='22 nF ±5% 50 V C0G, 1206 (API)',
         note='ladder 22 nF (0805: GRM21B5C1H223JA01L C77069)'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C21812', expect='GRM31M5C1H473JA01L', rank=1,
         specs='47 nF ±5% 50 V C0G, 1206 (API)',
         note='ladder 47 nF; no 0805 C0G >=50 V in stock at 47 nF or 100 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C97946', expect='GRM31C5C1H104JA01L', rank=1,
         specs='100 nF ±5% 50 V C0G, 1206 (API)',
         note='ladder 100 nF'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C405303', expect='GRM31C5C2A104JA01L', rank=2,
         specs='100 nF ±5% 100 V C0G, 1206 (API)',
         note='higher-voltage 100 nF, for series-resonant tanks'),
    dict(cat='j', group='C0G/NP0 resonant capacitors (50 V+)', code='C41370618', expect='FP31N103J631EEG', rank=2,
         specs='10 nF ±5% 630 V C0G, 1206 (API)',
         note='higher-voltage 10 nF'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C113872', expect='CC1206JKNPOCBN102', rank=1,
         specs='1 nF ±5% 1 kV NP0, 1206 (API)'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C4355181', expect='C1206N222J102TDF', rank=2,
         specs='2.2 nF ±5% 1 kV NP0, 1206 (API)'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C5156739', expect='FV32N103J102EGG', rank=3,
         specs='10 nF ±5% 1 kV C0G, 1210 (API)'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C7503858', expect='MT32N223J102EGE', rank=4,
         specs='22 nF ±5% 1 kV C0G, 1210 (API)'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C692314', expect='FV32N102J202EFG', rank=5,
         specs='1 nF ±5% 2 kV C0G, 1210 (API)'),
    dict(cat='j', group='High-voltage C0G (1-2 kV)', code='C22370026', expect='FV43N152J202EFG', rank=6,
         specs='1.5 nF ±5% 2 kV C0G, 1812 (API)',
         note='for HF tanks, 220 pF 2 kV 1206 Yageo CC1206JKNPODBN221 C469629 has 63k stock'),
    dict(cat='j', group='Ferrite sheets', code='C17556940', expect='IFL04-050NB300X200', rank=1,
         specs="flexible ferrite noise-suppression sheet 300x200 mm, 0.06 mm thick; mu' 45, mu'' 1.3 @13.56 MHz (API)",
         note='the only ferrite sheet JLCPCB has in stock (4 pcs); NFC-grade; hand-applied, so buy elsewhere if needed'),
    dict(cat='j', group='Qi coils with ferrite backing (hand-placed)', code='C424425', expect='YX-A11-R500800-R0845', rank=1,
         specs='Qi A11 TX coil: 6.3 uH ±5% @100 kHz, DCR <=75 mOhm, Litz 105x0.08 mm on a 50 mm x 0.8 mm ferrite disc [ds]',
         note='pairs with IP6808; handy reference coil next to PCB-trace coils'),
    dict(cat='j', group='Qi coils with ferrite backing (hand-placed)', code='C22381709', expect='YX-A11-R431231-G3232', rank=2,
         specs='Qi RX coil: 11.5 uH, 175 mOhm (API), on a 43 x 31.5 x 0.3 mm magnetic sheet with adhesive [ds]'),
    dict(cat='j', group='Qi coils with ferrite backing (hand-placed)', code='C3606555', expect='WR222230-26M8-G', rank=3,
         specs='Qi RX coil, 22 mm dia., 0.87 mm thick, 27 uH @100 kHz, 1.1 Ohm, flexible ferrite sheet [ds]',
         note='small enough for a satellite PCB; low stock'),
]

# Requested parts that are not usable (not in the library, or no/low stock).  Each is
# searched again so the claim carries its own timestamp.
ABSENT = [
    dict(cat='c', query='IS31FL3237', note='C2678924 IS31FL3237-QFLS4-TR: stock 12 (36 ch, 16-bit capable) - too few'),
    dict(cat='c', query='IS31FL3236', note='C5714539 IS31FL3236-TQLS2-TR stock 41, C5555029 stock 1; QFN-44 versions stock 0 (8-bit anyway)'),
    dict(cat='c', query='IS31FL3236A', note='C246443 IS31FL3236A-QFLS2-TR stock 200 (API text oddly says 9 mA, "Digital Tube Drivers"); C3198350 -QFLS4-TR stock 38. Clone HTR3236SQER C46955895: stock 1815, 8-bit'),
    dict(cat='c', query='IS31FL3743', note='C2678953 IS31FL3743A, C2962218 and C2678805 IS31FL3743B: stock 0'),
    dict(cat='c', query='IS31FL3746', note='C2961656 IS31FL3746A, C1882554 IS31FL3746B: stock 0'),
    dict(cat='c', query='AW20036', note='C401019 AW20036QNR stock 458; 3x12 matrix, 256-level FADE + 64-level DIM, i.e. 8-bit [ds]'),
    dict(cat='c', query='AW20054', note='C401020 AW20054QNR stock 192'),
    dict(cat='c', query='KTD2058', note='C19842510 KTD2058EUAC-TR stock 0; the search also returns unrelated NPN transistors named KTD2058 (C2910316, C69775)'),
    dict(cat='c', query='KTD2061', note='C5224493 KTD2061EUAC-TR and C19842512 KTD2061QGUAC-TR stock 0; C112866 is an unrelated KEC NPN'),
    dict(cat='d', query='STM32G474', note='usable but shallow in every package: CBT6 C730123 620, QET6 611, CCT6 460, RET6 C521608 381 (~$10), VET6 43, CEU6 35'),
    dict(cat='d', query='ESP32-C6F', note='ESP32-C6FH4 C6908287 and ESP32-C6FH8 C41459370 stock 0; bare ESP32-C6 C5364646 only 287 (modules: ESP32-C6-WROOM-1-N8 C5366877 3177)'),
    dict(cat='d', query='ICE40UP5K', note='only ICE40UP5K-SG48I C2678152 (182); -UWG30ITR C2678192 and -SG48ITR50 C2889329 stock 0; no Gowin GW1N in stock'),
    dict(cat='e', query='DRV8317', note='only C6022114 DRV8317HREER, stock 4'),
    dict(cat='e', query='TMC6300', note='C5274455 TMC6300-LA-T stock 7 (and 2-11 V only)'),
    dict(cat='e', query='L6234', note='C1523896 L6234PD stock 3; others 0'),
    dict(cat='e', query='DRV8412', note='C79852 DRV8412DDWR stock 264 only'),
    dict(cat='e', query='DRV8432', note='C79853 DRV8432DKDR stock 13'),
    dict(cat='e', query='BTS7960', note='C5122776 BTS7960B stock 0 (BTN7960 also 0)'),
    dict(cat='e', query='DRV8833', note='stocked (C50506, ~7.5k) but VM max 10.8 V: unusable on 12 V'),
    dict(cat='e', query='AT8833', note='stocked (C575404 ~8.4k, C5120769 ~10.8k) but 2.7-15 V, 1.2 A: marginal at 12 V'),
    dict(cat='e', query='TB6612FNG', note='stocked (C141517 ~5.7k) but VM 15 V max, ~1.2 A avg: marginal at 12 V'),
    dict(cat='g', query='MP1584', note='MP1584EN-LF-Z C15051 has only ~560; MP1584EN C454188 and the other codes stock 0'),
    dict(cat='g', query='JW5026', note='C185109 / C19712093 stock 0 (and 1 A only)'),
    dict(cat='h', query='LIS3DH', note='LIS3DHTR C15134 listed but only 245 in stock'),
    dict(cat='h', query='LIS2DH12', note='LIS2DH12TR C110926 listed but only 869 in stock'),
    dict(cat='h', query='MC3479', note='MC3479 C3248221 listed but only 860 in stock'),
    dict(cat='h', query='QMC5883', note='QMC5883L C976032 stock 0 (QMC5883P C2847467 is stocked instead)'),
    dict(cat='h', query='ALS31313', note='ALS31313KLEATR-500 C2654988 stock 30; other variants <=21'),
    dict(cat='h', query='DRV5053', note='DRV5053RAQDBZR C2654960 only 1402 (filed under Hall Switches); DRV5053VAQDBZR C962159 only 88'),
    dict(cat='h', query='A1308', note='A1308KUA-5-T C1559904 368 (SIP-3), A1308LLHLX-05-T C2152984 271; 5 V-only parts'),
    dict(cat='h', query='VL53L7CX', note='VL53L7CXV0GC/1 C5270520 only 42 in stock'),
    dict(cat='h', query='LTR-329', note='LTR-329ALS-01 C284894 only 108 in stock'),
    dict(cat='h', query='MSM261S4030H0', note='MSM261S4030H0R C2840615 stock 0'),
    dict(cat='h', query='SPH0645', note='SPH0645LM4H-B (C45337831 and others) all stock 0'),
    dict(cat='h', query='SPH0641', note='SPH0641LU4H-1 C2879853 only 1055 in stock'),
    dict(cat='h', query='ICS-41350', note='ICS-41350 C3171856 only 87 in stock'),
    dict(cat='h', query='IM69D130', note='IM69D130V01 C536262 only 442 in stock'),
    dict(cat='h', query='GMA4030', note='no hits (also none for GMA35/GMA40)'),
    dict(cat='h', query='MA40S4', note='Murata MA40S4S C1519281 and MA40S4R C2912274 stock 0'),
    dict(cat='h', query='SY-US-18', note='only SMD 40 kHz transducer, SY-US-18BRTD C5380075, has 91 in stock'),
    dict(cat='i', query='CH224K', note='C970725 CH224K listed, stock 0 (CH224Q C46061833 also 0); use pin-compatible CH224A C42459160'),
    dict(cat='i', query='AP33772', note='C5244513 AP33772DKZ-13 stock 65; C24374260 AP33772SDKZ-13-FA01 stock 15; C50341643 -FA02 stock 0'),
    dict(cat='i', query='IP2721', note='C603176 IP2721 stock 0; C7426784 IP2721-MAX12 stock 0'),
    dict(cat='j', query='BQ500212', note='C2876641 BQ500212ARGZT stock 0'),
    dict(cat='j', query='BQ500511', note='C3189479 BQ500511RHAT stock 4'),
    dict(cat='j', query='P9235', note='P9235A-RNDGI/-RBNDGI/-RNDGI8/-RBNDGI8 (C1575185, C1012920, C2156195, C1858382) all stock 0'),
    dict(cat='j', query='P9242', note='C2156160 P9242-RNDGI8 stock 5; other P9242 codes stock 0'),
    dict(cat='j', query='P9222', note='C1511994 P9222-RAZGI8 stock 9 (P9221/P9025/P9415 codes: stock 0)'),
    dict(cat='j', query='BQ51003', note='C134093 BQ51003YFPR stock 97 (2.5 W RX, DSBGA)'),
    dict(cat='j', query='CPS4019', note='only consigned "JLCPCB Assembly" placeholders (C9900047042, C9900189128), no stock; CPS4035/CPS4041: no hits'),
    dict(cat='j', query='NU1680', note='NuVolta NU1020/NU1680/NU1708: only consigned placeholders, no stock'),
    dict(cat='j', query='XKT-510', note='XKT-510/XKT-412/T3168/T5336: only consigned placeholders (e.g. C9900041368, C9900003802, C2887878), no stock'),
    dict(cat='j', query='IFL10M', note='ferrite sheets (Noise Suppressors category, 998 listed): TDK IFL10M/IFL12, KEMET EFX all stock 0; only IFL04-050NB300X200 has 4'),
]

# Category-level findings that are not about one MPN.
NOTES = {
    "a": ["No orange (600-615 nm) LED is Basic or Preferred: the only Basic/Preferred LEDs in "
          "'LED Indication - Discrete' are KT-0603R, NCD0805R1 (red 615-630 nm), KT-0805Y (yellow-amber: 584-594 nm per API, 592-594 nm per datasheet), "
          "NCD0603Y2 (Preferred, 586-595 nm), KT-0805G (green) and KT-0603W/KT-0805W (white).",
          "Orange in 2835/3030 is thin: Everlight 67-31EP3-URD1224DBFBZ5 2835 (C5137842, ~1.4k) and an OSRAM 3030 amber "
          "(C37155455, 200); for a bright orange glow use 5050 3-die parts or several 3528s.",
          "Several cheap LED datasheets disagree with the API's mcd figure (e.g. XL-1608UOC-06); [ds] values are the datasheet's."],
    "d": ["No microcontroller or FPGA is Basic.  The Basic crystals are 32.768 kHz, 8, 12, 16 and 25 MHz parts "
          "(e.g. X322512MSB4SI C9002 at 12 MHz); there is no Basic 40 MHz crystal for the ESP32s."],
    "e": ["Only four MOSFETs are Basic and in stock: 2N7002 (C8545), AO3400A (C20917), AO3401A (C15127) and "
          "SI2301CDS-T1-GE3 (C10487); HL3400 (C22469448) is a Preferred AO3400A equivalent.",
          "No motor driver or gate driver (BLDC, brushed-DC, stepper or gate-driver categories) is Basic."],
    "f": ["No DC jack, resettable or one-time fuse, eFuse/power-distribution switch, aluminium electrolytic or "
          "polymer capacitor is Basic (each category searched with the Basic filter).",
          "The only Basic SMBJ/SMAJ TVS is SMBJ6.5CA (C7420377, 6.5 V bidirectional: unusable on 12 V); the hongjiacheng "
          "SMBJ15A/SMBJ16A/SMAJ15A are Preferred (no setup fee)."],
    "g": ["Only two in-stock DC-DC converters are Basic: TPS5430DDAR (C9864) and XL1509-5.0E1 (C61063); both are "
          "non-synchronous and need a Schottky catch diode (SS34 C8678 / SS54 C22452 are Basic).",
          "No power inductor is Basic (neither the 'Power Inductors' nor the 'Molding Power Inductors' category)."],
    "j": ["The C0G ladder lists one pick per value, so it carries several ★.",
          "The resonant-capacitor ladder from 1 nF to 100 nF has exactly one Basic part (2.2 nF CL21C222JBFNNNE, C28260)."],
    "b": ["No datasheet among the violet/UV/purple parts gives an IEC 62471 risk group; they carry only generic "
          "'do not look into the LED' warnings.  The 2835 parts emitting 45-220 mW at 365-400 nm should be treated as eye "
          "hazards at close range (diffuse or shield them, keep them out of direct view of a child).",
          "The 'purple' parts rated in mcd at 5 mA (Vf ~2.6-3.1 V) behave like phosphor-converted purple/pink emitters "
          "(no datasheet gives a spectrum); the violet InGaN "
          "parts (Vf ~3.0-3.6 V) look dim and deep-violet because the eye's photopic sensitivity at 400 nm is only ~0.04 % "
          "of its 555 nm peak, yet their 45-180 mW of radiant power makes fluorescent inks and glow-in-the-dark "
          "pigments light up strongly.",
          "None of these LEDs is Basic or Preferred."],
}

RECOMMEND = {
    "a": "Orange: XINGLIGHT XL-1608UOC-06 (C965800, 0603, 600-610 nm) for indicator-size pumpkins and HONGLITRONIC "
         "HL-AF-5060S22OC (C516304, 5050 3-die) for a bright glow; if a Basic part is required, KT-0603R (C2286, 615-630 nm) "
         "is the closest (red-orange) and KT-0805Y (C2296) the amber.",
    "b": "Violet: TUOZHAN S2-2835UVTA-0.2W (C2827317, 2835, 390-400 nm, 705k stock) for glow/fluorescence effects; "
         "for a visibly purple pixel use GL0603PU01 (C51933300) or a red+blue bi-die XL-1615SURUBC (C965836) mixed by PWM.",
    "i": 'TYPE-C-31-M-12 (C165948) is deeply stocked (Extended). CH224A (C42459160, Extended, 17.6k stock, $0.27): WCH says it is pin-compatible with the out-of-stock CH224K; a single 24 kOhm CFG1 resistor requests 12 V (also 9/15/20/28 V). HUSB238 (C7471904) is the second source.',
    'c': 'LP5036RJVR (C701961, 17k in stock, 36 ch, 12-bit @29 kHz, I2C) for LEDs on a 5 V rail; TLC5971RGER (C543004, 16-bit ES-PWM, 60 mA, runs from 12 V) if 16-bit fades or series strings from 12 V matter. No LED driver is Basic.',
    'd': 'RP2354A (C41378174, 16k, 2 MB flash on chip) + ABM8-272-T3 (C20625731) + AOTA-B201610S3R3-101-T (C42411119, only 677 in stock: enough for a prototype run). No MCU is Basic; STM32G474 is shallow (<=620), so use STM32G431CBT6 (C529355, 4k) if an STM32 is wanted; ESP32-C3FH4 (C2858491, 5.7k) + 40 MHz XL2EL89COI-111YLC-40M (C18214314) for Wi-Fi.',
    'e': 'Coil phases: DRV8316RRGFR (35 V, 8 A peak, 3 half-bridges) or, for 4 independent half-bridges with deep stock, DRV8844PWPR; DRV8874PWPR for single H-bridges; AO3400A (Basic) for simple low-side switching.',
    'f': 'DC-005-5A-2.0 jack (C381116) -> TPS259474LRPWR eFuse (or AO4407A P-FET + 2920L500 PTC) -> SMBJ15A (Preferred) TVS -> MA35V470M10X13 polymer bulk cap.',
    'g': 'TPS54302DDCR (28 V, 3 A) + FXL0630 10/6.8 uH for 12->5/3.3 V (TPS5430DDAR + SS34 if Basic parts matter), TLV62569DBVR + 2.2 uH for 5->3.3 V.',
    'h': 'No sensor is Basic. Motion: LSM6DS3TR-C (6-axis, deepest IMU stock) or LIS2DW12TR for accel-only; magnets: TMAG5273A2 (±266 mT 3D Hall, $0.35) to track NdFeB magnets (MMC5603NJ only as a compass) and DRV5055A4 for analog coil/magnet sensing; ToF: VL53L1X (VL53L1CXV0FY/1, 4 m) or VL53L5CX for 8x8 gestures; light: LTR-303ALS-01; mic: T3902 PDM (bottom port) or ZTS6216 analog top port; 40 kHz ultrasonic only as shallow-stock through-hole HY40A16T12-1/R12-1 pair.',
    'j': 'Qi silicon is optional: a custom resonant link needs only the coil-driver half-bridges, 4x Basic Schottkys (1N5819WS C191023 / SS34 C8678) and C0G tank caps (only 2.2 nF C28260 is Basic; e.g. Murata GRM31C5C1H104JA01L C97946 for 100 nF). For Qi interoperability IP6808 (C515682) + BQ51013B (C55663) are the stocked TX/RX pair. Ferrite sheets are effectively unstocked (hand-apply).',
}

# Datasheets fetched into datasheets/ (gitignored) by the survey scripts.
DATASHEETS = [
    ("XL-1608UOC-06", "C965800", "OK"), ("XL-2012UOC", "C965813", "OK"), ("XL-3216UOC", "C965823", "OK"),
    ("XL-3528UOC", "C2843804", "OK"), ("TJ-S3528UG6W9TLC0A-A5", "C2837014", "OK"),
    ("HL-AF-5060S22OC-3-S1-THL", "C516304", "OK"), ("KT-0603R", "C2286", "OK"),
    ("S2-2835UVTA-0.2W", "C2827317", "OK"), ("XL-HD2835UVA2-A1", "C49652883", "OK"),
    ("XL-2835UVA-02", "C2843877", "OK"), ("XL-1608UVC-04", "C7371898", "OK"),
    ("P2-0802UVTA1-1.0T", "C2827267", "OK"), ("GL0603PU01", "C51933300", "OK"),
    ("XL-HD2835UVA1-A1", "C49652884", "OK"), ("KT-0805Y", "C2296", "OK"), ("NCD0805R1", "C84256", "OK"),
    ("GL0603UO01", "C51933298", "OK"), ("LTST-C190KFKT", "C157740", "OK"), ("NCD0603Y2", "C89811", "OK"),
    ("P2835P1UVS26G12Q-365", "C46641552", "FAILED: JLCPCB lists no datasheet for this part"),
    ('LP5036RJVR', 'C701961', 'OK'),
    ('LP5024RSMR', 'C427525', 'OK'),
    ('LP5012RUKR', 'C1849481', 'OK'),
    ('IS31FL3205-QFLS4-TR', 'C3202873', 'OK'),
    ('TLC5971RGER', 'C543004', 'OK'),
    ('TLC59711PWPR', 'C116842', 'OK'),
    ('MBI5043GP-A', 'C110098', 'OK'),
    ('TLC5947RHBR', 'C702083', 'OK'),
    ('TLC5940PWPR', 'C181653', 'OK'),
    ('TLC5955DCAR', 'C702086', 'OK'),
    ('AW21036QNR', 'C5125743', 'OK'),
    ('PCA9956BTWY', 'https://www.nxp.com/docs/en/data-sheet/PCA9956B.pdf', 'OK (LCSC PDF for C2678558 was not a PDF; fetched from NXP)'),
    ('IS31FL3218-QFLS2-TR', 'C2940546', 'OK'),
    ('IS31FL3741A-QFLS4-TR', 'C2940604', 'OK'),
    ('PCA9685PW/Q900,118', 'https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf', 'OK, saved as PCA9685PW_Q900_118.pdf (LCSC PDF for C92206 was not a PDF; fetched from NXP)'),
    ('AW9523BTQR', 'C148077', 'OK'),
    ('AW20036QNR', 'C401019', 'OK'),
    ('TLC59116IPWR', 'C131194', 'OK'),
    ('WS2816B', 'C22371534', 'OK'),
    ('RP2354A', 'C41378174', 'OK (LCSC serves the full 11 MB RP2350 datasheet)'),
    ('RP2354B', 'C39843328', 'OK (LCSC serves the RP2350 product brief only; the full datasheet is RP2354A.pdf)'),
    ('ESP32-C3', 'C2838500', 'OK (ESP32-C3 Series datasheet v1.5, covers ESP32-C3FH4)'),
    ('DRV8316RRGFR', 'https://www.ti.com/lit/ds/symlink/drv8316.pdf', 'OK (LCSC copy was the Chinese edition; replaced with TI English)'),
    ('DRV8874PWPR', 'C1855818', 'OK'),
    ('DRV8844PWPR', 'C177807', 'OK'),
    ('AON7934', 'C485677', 'OK'),
    ('TPS54302DDCR', 'https://www.ti.com/lit/ds/symlink/tps54302.pdf', 'OK (LCSC copy was the Chinese edition; replaced with TI English)'),
    ('TPS563201DDCR', 'C116592', 'OK'),
    ('TLV62569DBVR', 'C141836', 'OK'),
    ('TPS5430DDAR', 'C9864', 'OK'),
    ('LSM6DS3TR-C', 'C967633', 'OK'),
    ('LIS2DW12TR', 'C189624', 'OK'),
    ('SC7A20HTR', 'C19274408', 'OK (Chinese only)'),
    ('TMAG5273A2QDBVR', 'https://www.ti.com/lit/ds/symlink/tmag5273.pdf', 'OK (JLC copy was the Chinese translation; replaced by TI English rev C)'),
    ('MMC5603NJ', 'C404328', 'OK'),
    ('DRV5055A4QDBZR', 'https://www.ti.com/lit/ds/symlink/drv5055.pdf', 'OK (TI rev C, Jun 2026; covers A1-A4)'),
    ('VL53L1CXV0FY/1', 'C190004', 'OK'),
    ('VL53L5CXV0GC/1', 'C3178303', 'OK'),
    ('LTR-303ALS-01', 'C364577', 'OK'),
    ('MMICT390200012', 'C3171752', 'OK (T3902)'),
    ('ZTS6216', 'C481302', 'OK'),
    ('SD18OB261-060', 'C2895290', 'OK'),
    ('HY40A16T12-1', 'C17701106', 'OK'),
    ('MSM261DDB020', 'C27636198', 'FAILED: no datasheet link in the JLC/LCSC listing (dropped as a candidate)'),
    ('IP6808_NF', 'C515682', 'OK'),
    ('IP6809', 'C2927864', 'OK'),
    ('IP6831', 'C42411074', 'OK'),
    ('BQ51013BRHLR', 'C55663', 'OK'),
    ('BQ500101DPCR', 'C134094', 'OK'),
    ('CH224A', 'C42459160', 'OK'),
    ('HUSB238_002DD', 'C7471904', 'OK'),
    ('XL1509-5.0E1', 'C61063', 'OK'),
    ("ABM8-272-T3", "C20625731", "OK (already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey)"),
    ("AOTA-B201610S3R3-101-T", "C42411119", "OK (already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey)"),
    ("TYPE-C-31-M-12", "C165948", "OK (already present: placed in datasheets/ by another agent at 11:17, not fetched by this survey)"),
]


# ---------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def lookup(c, refresh):
    part, ts = jlc_api.by_code(c["code"], refresh=refresh)
    if part is None:
        raise SystemExit("%s: not found at JLCPCB (queried %s)" % (c["code"], ts))
    mpn = part.get("componentModelEn") or ""
    if _norm(c["expect"]) not in _norm(mpn):
        raise SystemExit("%s: JLCPCB says MPN %r, expected %r -- wrong code?" % (c["code"], mpn, c["expect"]))
    return {
        "cat": c["cat"], "group": c["group"], "rank": c["rank"],
        "lcsc": part["componentCode"], "mpn": mpn,
        "maker": part.get("componentBrandEn") or "",
        "package": part.get("componentSpecificationEn") or "",
        "specs": c["specs"], "note": c.get("note", ""),
        "library": jlc_api.library_type(part),
        "stock": int(part.get("stockCount") or 0),
        "price_usd_at_100": round(jlc_api.unit_price(part, QTY), 4),
        "price_breaks": [(b.get("startNumber"), b.get("endNumber"), b.get("productPrice"))
                         for b in part.get("componentPrices") or []],
        "jlc_category": part.get("firstSortName") or "",
        "api_description": part.get("describe") or "",
        "datasheet_url": part.get("dataManualUrl") or "",
        "lcsc_url": part.get("lcscGoodsUrl") or "",
        "queried": ts,
    }


def absent(a, refresh):
    lst, ts = jlc_api.search(a["query"], page_size=20, refresh=refresh)
    q = _norm(a["query"])
    hits = [it for it in lst if _norm(it.get("componentModelEn")).startswith(q)
            and not (it.get("componentCode") or "").startswith("C99")]   # C99... = customer placeholders
    hits.sort(key=lambda it: -(it.get("stockCount") or 0))
    return {"cat": a["cat"], "query": a["query"], "note": a.get("note", ""), "queried": ts,
            "hits": [{"lcsc": it["componentCode"], "mpn": it.get("componentModelEn"),
                      "stock": int(it.get("stockCount") or 0),
                      "library": jlc_api.library_type(it)} for it in hits[:4]]}


def ds_file(mpn):
    return os.path.join(ROOT, "datasheets", re.sub(r"[^A-Za-z0-9._+-]", "_", mpn.strip()) + ".pdf")


def short_maker(m):
    """'HONGLITRONIC(Hongli Zhihui (HONGLITRONIC))' -> 'HONGLITRONIC'; 'ISSI(Integrated ...)' -> 'ISSI'."""
    m = (m or "").strip()
    head = m.split("(")[0].strip()
    return head or m


def fmt_stock(n):
    return "{:,}".format(n)


def md_escape(s):
    return (s or "").replace("|", "\\|")


def write_md(parts, gone, ts_lo, ts_hi, path):
    L = []
    L.append("# JLCPCB parts survey for halloween1")
    L.append("")
    L.append("Stock, price and library type were queried from JLCPCB's parts API between **%s** and **%s** "
             "(each part's own query time is in `jlc_parts_survey.json`). Regenerate with "
             "`python3 research/survey.py` (`--refresh` to re-query)." % (ts_lo, ts_hi))
    L.append("")
    L.append("* **$@100** is JLCPCB's unit price at a quantity of 100, in USD.")
    L.append("* **Basic** parts carry no setup fee; **Preferred** are Extended parts JLCPCB keeps loaded "
             "(no setup fee either); each distinct **Ext**ended part costs about $3 to set up.")
    L.append("* ★ marks the recommended pick of each group (in the C0G ladder, of each value); [ds] marks specs read from the datasheet "
             "(in `datasheets/`, not committed), the rest are from JLCPCB's description.")
    L.append("* This is a survey of what can be bought and placed, not a design decision.")
    L.append("")
    for cat, title in CATS:
        cp = [p for p in parts if p["cat"] == cat]
        cg = [g for g in gone if g["cat"] == cat]
        if not cp and not cg:
            continue
        L.append("## %s. %s" % (cat, title))
        L.append("")
        if cat in RECOMMEND:
            L.append("**Recommendation:** %s" % RECOMMEND[cat])
            L.append("")
        L.append("| LCSC | MPN | maker | package | key specs | Basic/Ext | stock | $@100 |")
        L.append("|---|---|---|---|---|---|--:|--:|")
        groups = []
        for p in cp:
            if p["group"] not in groups:
                groups.append(p["group"])
        for g in groups:
            if len(groups) > 1 or g:
                L.append("| **%s** | | | | | | | |" % md_escape(g))
            for p in sorted([p for p in cp if p["group"] == g], key=lambda p: p["rank"]):
                spec = p["specs"] + ((" — " + p["note"]) if p["note"] else "")
                lib = {"Basic": "Basic", "Preferred": "Preferred", "Extended": "Ext"}[p["library"]]
                L.append("| %s%s | %s | %s | %s | %s | %s | %s | %.4f |" % (
                    p["lcsc"], " ★" if p["rank"] == 1 else "", md_escape(p["mpn"]), md_escape(short_maker(p["maker"])),
                    md_escape(p["package"]), md_escape(spec), lib, fmt_stock(p["stock"]), p["price_usd_at_100"]))
        L.append("")
        if cg:
            L.append("Requested but not usable (searched by MPN; the note was written during the survey, "
                     "the bracket is the re-query made when this file was generated):")
            L.append("")
            for g in cg:
                hits = ", ".join("%s %s (stock %s)" % (h["lcsc"], h["mpn"], fmt_stock(h["stock"])) for h in g["hits"])
                L.append("* **%s** — %s%s" % (g["query"], g["note"] or "", (" [re-queried: " + hits + "]") if hits else
                                                (" [re-queried: no matching part]" if not g["note"] else "")))
            L.append("")
        for n in NOTES.get(cat, []):
            L.append("* %s" % n)
        if NOTES.get(cat):
            L.append("")
    L.append("## Datasheets")
    L.append("")
    L.append("Saved as `datasheets/<MPN>.pdf` (characters other than letters, digits and `._+-` written as `_`), "
             "with a `pdftotext` copy in `datasheets/txt/`. The directory is gitignored. Only the files listed here "
             "were fetched for (or checked by) this survey; other PDFs in `datasheets/` were placed by other agents.")
    L.append("")
    L.append("| MPN | fetched from | file present | note |")
    L.append("|---|---|---|---|")
    for mpn, src, status in DATASHEETS:
        ok = status.startswith("OK")
        note = status[2:].strip(" ,;:") if ok else status
        if note.startswith("(") and note.endswith(")"):
            note = note[1:-1]
        f = ds_file(mpn)
        present = "yes" if os.path.exists(f) and os.path.getsize(f) > 5000 else "**no**"
        L.append("| %s | %s | %s | %s |" % (md_escape(mpn), md_escape(src), present if ok else "—",
                                             md_escape(note if ok else "**FAILED:** " + note.replace("FAILED:", "").strip())))
    L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def main():
    refresh = "--refresh" in sys.argv
    seen = set()
    for c in CANDIDATES:
        key = (c["cat"], c["group"], c["code"])
        if key in seen:
            raise SystemExit("duplicate candidate %r" % (key,))
        seen.add(key)
    parts = [lookup(c, refresh) for c in CANDIDATES]
    gone = [absent(a, refresh) for a in ABSENT]
    stamps = sorted([p["queried"] for p in parts] + [g["queried"] for g in gone])
    ts_lo, ts_hi = stamps[0], stamps[-1]
    out = {
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "queried_from": ts_lo, "queried_to": ts_hi, "price_qty": QTY,
        "source": "JLCPCB parts API selectSmtComponentList via tools/jlc_api.py",
        "categories": [{"id": cat, "title": title, "recommendation": RECOMMEND.get(cat, ""),
                        "notes": NOTES.get(cat, []),
                        "parts": [p for p in parts if p["cat"] == cat],
                        "not_usable": [g for g in gone if g["cat"] == cat]} for cat, title in CATS],
        "datasheets": [{"mpn": d[0], "source": d[1], "status": d[2]} for d in DATASHEETS],
    }
    json.dump(out, open(os.path.join(HERE, "jlc_parts_survey.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    write_md(parts, gone, ts_lo, ts_hi, os.path.join(HERE, "jlc_parts_survey.md"))
    print("%d parts, %d not-usable queries, queried %s .. %s" % (len(parts), len(gone), ts_lo, ts_hi))


if __name__ == "__main__":
    main()
