"""What a good rev A base board should read at each bring-up step, and where each number
comes from. The steps (steps.py) and BRINGUP.md take their limits from here, so the
procedure and the scripts can't disagree.

Many of these are estimates from the schematic and datasheets, not measurements. After the
first good board, replace them with what it read (and say so in the comment). The second
assembled panel is the reference for anything a datasheet can't predict, such as
resistances to ground.
"""

# ---- the 12 V input, as the bench supply sees it at J1 -------------------------------------
# Below the buck's turn-on, the only loads on +12V are two 100k/22k dividers (EN and the
# V12 sense: 61 kohm together), the DRV8874s asleep (nSLEEP pulled low: ~1 uA each), the
# SMBJ15A's leakage (1 uA at its 15 V stand-off) and C1 charging. So ~0.1 mA at 6 V.
EN_ON_V = 6.7          # the buck starts here: EN 100k/22k, TPS54302 EN threshold 1.21 V (gen/sch_base.py)
BUCK_UVLO_V = 4.5      # TPS54302 VIN UVLO (rising, typ): irrelevant below EN_ON_V, listed for completeness
TVS_STANDOFF_V = 15.0  # D2 SMBJ15A: never go above this (it starts conducting at 16.7 V)
OVP_V = 13.5           # the supply's over-voltage trip, below D2's stand-off
# Rails the ramp stops at, on the coarse scope view (the scope's DC accuracy there is a few
# per cent of full scale, so these are windows for faults, not for tolerances).
RAMP_OVER = {"+4.8V": 5.25, "+3V3": 3.6, "+1V1": 1.3}     # at any step
RAMP_UNDER = {"+4.8V": 4.3, "+3V3": 2.9}                   # once the buck has had 0.5 V more than EN

# The slow first ramp: (volts, the supply's current limit, abort above this many amps over
# the zero reading, what's on). The limits are deliberately tight: a fault shows up as the
# supply going into current limit (CC), which the ramp treats as a failure.
RAMP = [
    (1.0, 0.020, 0.008, "Q1's body diode, the two 122k dividers: ~0 mA"),
    (2.0, 0.020, 0.008, "Q1 turning on (Vgs(th) about -1.9 V): ~0 mA"),
    (3.0, 0.020, 0.008, "+12V follows the input: ~0.05 mA"),
    (4.5, 0.020, 0.008, "~0.07 mA; the buck is still off (EN below 1.21 V)"),
    (6.0, 0.020, 0.008, "~0.1 mA"),
    (6.5, 0.020, 0.008, "~0.1 mA: the last step before the buck starts (6.7 V)"),
    # Just above EN, so that a buck with a broken feedback divider can't put much more than
    # 7 V on the "4.8 V" rail (the NS4150B's absolute maximum is 5.25 V) before the scope
    # sees it and the ramp stops.
    (7.0, 0.150, 0.090, "the buck runs: 4.8 V, VSYS, 3.3 V and the blank RP2354A come up"),
    (7.5, 0.150, 0.080, ""),
    (9.0, 0.150, 0.070, "the same power from a higher voltage: the current falls"),
    (10.5, 0.150, 0.060, ""),
    (12.0, 0.150, 0.055, "nominal: the blank board idles at an estimated 15-40 mA"),
]
# The blank board at 12 V: the RP2354A in its ROM bootloader (~20-30 mA at 3.3 V, RP2350
# datasheet's typical active current), sensors ~3 mA, the UCC27524s' quiescent ~1 mA each
# from 4.8 V, through the XC6206 (linear: 3.3 V loads cost VSYS's 4.5 V) and the buck at
# light load (~75 %): (35 mA * 4.5 V + 2 mA * 4.8 V) / 0.75 / 12 V ~ 18 mA. With USB
# plugged in, VBUS (5 V less a Schottky) is above 4.8 V less one, so the logic moves to USB
# and the 12 V current drops to the buck's own few mA.
IDLE_12V_A = (0.008, 0.055)       # blank or bring-up image, no USB: plausible band
IDLE_12V_USB_A = (0.000, 0.025)   # with USB plugged in: the logic runs from VBUS
HOLD_S = 30                       # hold at 12 V and watch for drift (something heating up)
HOLD_DRIFT = 0.25                 # more than this fractional change in the hold is suspicious

# ---- the rails (test points, DESIGN_REVIEW.md section 3, mfg/release/excluded_from_assembly.csv)
# name: (test point, nominal V, low, high, why the band)
RAILS = {
    "+12V": ("TP1", 12.0, 11.8, 12.1, "the supply less F1 (~0.03 ohm) and Q1 (9.5 mohm)"),
    "+4.8V": ("TP2", 4.80, 4.68, 4.92, "0.596 V x (1 + 36k/5.1k); TPS54302 ref +-1.5 %, 1 % resistors"),
    "VSYS": ("TP4", 4.45, 4.25, 4.70, "4.8 V less a B5819W (0.3-0.45 V at tens of mA), or VBUS less one"),
    "+3V3": ("TP3", 3.30, 3.23, 3.37, "XC6206P332: +-2 %"),
    "+1V1": ("TP5", 1.10, 1.05, 1.16, "the RP2354A's own core regulator, default 1.1 V"),
    "VBUS": ("TP6", 5.00, 4.60, 5.25, "from the USB host, only with USB plugged in"),
}
# The scope's probe plan for the rails (BRINGUP.md): channel -> rail
SCOPE_RAILS = {1: "+12V", 2: "+4.8V", 3: "+3V3", 4: "+1V1"}
RIPPLE_4V8_MAX = 0.050            # V peak-to-peak on +4.8V at idle, 20 MHz bandwidth limit
BUCK_FSW_HZ = (340e3, 460e3)      # TPS54302: 400 kHz +-15 % (it skips pulses at light load)

# ---- the ADC's view of the rails (firmware/src/board_pins.h): the bring-up image's `rails`
RAIL_READ_TOL = 0.05              # fraction: the dividers are 1 %, the ADC ref is the 3.3 V rail (+-2 %)

# ---- I2C (firmware/src/board_pins.h)
I2C_BASE = {"0x30": "LP5036 U3 (base LEDs)", "0x6A": "LSM6DS3TR-C U15 (IMU)",
            "0x29": "LTR-303ALS U16 (light)", "0x35": "TMAG5273A2 U17 (3-axis Hall)",
            "0x1C": "LP5036 broadcast address (every LP50xx answers it)"}
I2C_TREE = {"0x32": "LP5036 U101 (tree LEDs)"}

# ---- the coils (DESIGN_REVIEW.md 5.2; sim/physics/magnetics.py). The bring-up image's
# `coil` reply gives r_loop_ohm = V12 * duty / (mirror's mean - its offset), and r_est_ohm,
# the same less the DRV8874's switches (BRIDGE_R). The mirror reads in drive and in brake
# (slow decay), not in coast (DRV8874 datasheet 7.3.3.1), so its mean is the coil's current.
COIL_R = {"pend1": 2.29, "pend2": 2.29, "pend3": 2.29, "lev": 2.56}
BRIDGE_R = 0.2                    # DRV8874 RDS(on), high + low side together, typ at 25 C (datasheet)
COIL_R_TOL = 0.30                 # the copper's 1 oz is +-10 %, the temperature, the mirror's gain
COIL_TEST_DUTY = 0.08             # ~0.4 A into 2.3 ohm at 12 V
COIL_TEST_MS = 200

# ---- the familiar perches (L6, L7: 30.3 uH, 2.13 ohm) and the tanks
TOKEN_F = {"owl": 142e3, "cat": 303e3, "bat": 82e3}   # gen/sch_boards.py's notes
TOKEN_F_TOL = 0.12                # 100 nF/22 nF C0G 5 %, the coil's L from a field solver
PERCH_SWEEP_PEAK = {"owl": (116e3, 168e3), "cat": (248e3, 358e3)}  # familiar.c FAM_ID_TOL

# ---- the audio: the NS4150B awake (SOUND on) adds ~3 mA at 4.8 V, 1.8 mA at 12 V (read 2026-11-06)
AUDIO_AMP_IDLE_12V_A = 0.0018

# ---- the theremin (firmware/README.md open question 10: 0.5-1 MHz assumed)
THEREMIN_HZ = (200e3, 2e6)        # wide: anything steady in here works; the firmware adapts

# ---- LEDs: the extra 12 V current when one LED is lit at duty 0.5 in the bring-up image.
# IREF 3.3 k: ~22 mA a channel at full scale (gen/sch_base.py), half of it on average,
# from 4.8 V through the buck (~85 %): 11 mA * 4.8 / 0.85 / 12 = 5.2 mA.
LED_DELTA_12V_A = 0.0052
LED_DELTA_MIN_FRACTION = 0.4      # an LED that adds less than this x the median is suspect
