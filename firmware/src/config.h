/* config.h: the numbers the firmware depends on that are not in gen/pins.py or
 * gen/leds.py (those are generated into board_pins.h and led_map.h).
 *
 * Each is marked with where it comes from:
 *   [DS]       a datasheet (named)
 *   [SIM]      sim/physics/ (the file named)
 *   [ASSUMED]  not decided yet: the board designer confirms or corrects it.
 *              The README's "open questions" lists every one.
 *   [CHOICE]   a firmware choice (safe to change)
 *
 * Pure #defines: the host tests include this too.
 */
#pragma once

/* ---- clocks and timing ------------------------------------------------------- */
#ifndef SYS_CLK_HZ                         /* the SDK's (platform_defs.h); this for the host tests */
#define SYS_CLK_HZ            150000000u   /* [CHOICE] the SDK's RP2350 default */
#endif
#define CTRL_TICK_HZ          10000u       /* [CHOICE] core 1: ADC burst, levitation, safety */
#define CTRL_TICK_S           (1.0f / CTRL_TICK_HZ)
#define WATCHDOG_MS           250u         /* [CHOICE] short: a stalled core must not leave a coil on */
#define CRASHES_TO_BOOTSEL    3u           /* [CHOICE] as GPiBridge */

/* ---- ADC ---------------------------------------------------------------------------- */
#define ADC_VREF_V            3.3f         /* [ASSUMED] ADC_AVDD = the 3.3 V rail */
#define ADC_COUNTS            4096.0f
#define ADC_OVERSAMPLE        8u           /* [SIM] levitation_loop.py: 8 samples per loop step */

/* ---- DRV8874 bridges (pendulum coils 1-3, the levitation coil) ----------------------- */
#define DRV_A_IPROPI          450e-6f      /* [DS] DRV8874: IPROPI = 450 uA per A */
#define R_IPROPI_OHM          2200.0f      /* the designer, 2026-10-07 (schematic A1) */
#define IPROPI_V_PER_A        (DRV_A_IPROPI * R_IPROPI_OHM)    /* 0.99 V/A */
#define DRV_ITRIP_A           3.3f         /* the designer: VREF 3.3 V / (2.2 k x 450 uA/A) */
#define DRV_RDSON_OHM         0.2f         /* [DS] high side + low side, 0.1 + 0.1 ohm typ */
#define DRV_WAKE_US           1000u        /* [DS] tWAKE <= 1 ms after nSLEEP rises */
#define DRV_MIN_PULSE_S       300e-9f      /* [CHOICE] shorter output pulses are not reproduced
                                              (tPD 400 ns, rise/fall 150 ns, dead time 100 ns) */
#define PEND_PWM_HZ           30000u       /* [CHOICE] pendulum and film drive: above hearing */
#define LEV_PWM_HZ            40000u       /* [CHOICE] levitation, carrier off: 4 periods per tick */
#define LEV_CARRIER_HZ        80000u       /* [SIM] bat_power.py: the bat's tank is 82 kHz as drawn
                                              (gen/coils.py: 37 uH with 100 nF) with a Q of 2.5; 80 kHz
                                              is exactly 8 PWM periods a control tick and gets 99 % of
                                              the resonance */

/* ---- the coils (all four are the canonical 4-layer spiral) --------------------------- */
#define COIL_R20_OHM          2.29f        /* [SIM] gen/coils.py: the pendulum coil as drawn, 1 oz on
                                              every layer, 20 degC, leads and vias included */
#define COIL_L_H              33.2e-6f     /* [SIM] gen/coils.py: the pendulum coil as drawn (49 turns) */
#define LEV_COIL_L_H          30.1e-6f     /* [SIM] gen/coils.py: the levitation coil as drawn (3 layers,
                                              43 turns, r 4-15 mm; 2.56 ohm) */
#define COPPER_TEMPCO         0.0039f      /* copper: +0.39 %/degC; the coil is its own thermometer */
#define COIL_SURFACE_LIMIT_C  45.0f        /* [CHOICE] PLAN.md 7: nothing a hand reaches passes ~45 C */
#define COIL_DERATE_FROM_C    40.0f        /* [CHOICE] current limits shrink from here to the limit */
#define AMBIENT_DEFAULT_C     25.0f        /* until a board temperature sensor has answered */

/* firmware current limits, below the hardware's DRV_ITRIP_A */
#define PEND_I_MAX_A          0.5f         /* [SIM] pendulum pulses need 0.1-0.3 A */
#define FILM_I_MAX_A          1.0f         /* [CHOICE] film mode: up to ~1 A ... */
#define FILM_ON_MAX_MS        2000u        /* ... for at most 2 s at a time */
#define CONSOLE_I_MAX_A       1.0f         /* the console's `coil` command */
#define CONSOLE_ON_MAX_MS     2000u
#define LEV_I_MAX_A           3.0f         /* [SIM] catches from +-3 mm peak at 2.4 A */

/* ---- the rails (dividers are generated from gen/pins.py into board_pins.h) ------------- */
#define V12_PRESENT_V         10.8f        /* [CHOICE] coils may run above this ... */
#define V12_BROWNOUT_V        10.0f        /* ... and stop below this (UVLO of the DRV8874 is 4.45 V) */
#define V12_ABSENT_V          6.0f         /* below: no adapter, USB power only */
#define V5_PRESENT_V          4.4f         /* the familiar bridges need their "5 V" (4.8 V nominal) */
#define VBUS_PRESENT_V        4.0f

/* ---- the levitation Hall sensor (DRV5055A4 at the perch coil's centre) ---------------- */
#define HALL_MV_PER_MT        7.5f         /* [DS] DRV5055A4 at VCC = 3.3 V (7.1-7.9) */
#define HALL_VQ_FRACTION      0.5f         /* [DS] quiescent output VCC/2 (1.59-1.71 V) */
#define HALL_POLARITY         (+1)         /* [ASSUMED] +1: the marked side faces the bat, so its
                                              field reads positive; `lev cal` checks it */

/* ---- the familiar perches (UCC27524 full bridges from 5 V) ---------------------------- */
#define FAM_VDRIVE_V          4.8f         /* the designer: the "+5V" rail is 4.8 V (36 k / 5.1 k);
                                              familiar_resistors.py: the rail caps the current */
#define FAM_ISENSE_V_PER_A    10.3f        /* the designer (f68cf45): the bridge's supply current through
                                              0.5 ohm, filtered 10 k / 100 n (1 ms), then x20.6 (OPA2333):
                                              a count is 0.08 mA (0.5 V/A alone could not see a token) */
#define FAM_I_MAX_A           0.2f         /* [SIM] familiar.py: 0.1-0.2 A; the other token stays dark */
#define FAM_F_MIN_HZ          100000.0f    /* [CHOICE] sweep range */
#define FAM_F_MAX_HZ          400000.0f
#define FAM_OWL_HZ            142000.0f    /* [SIM] the owl token's tank: 12.5 uH (gen/coils.py) with 100 nF */
#define FAM_CAT_HZ            303000.0f    /* [SIM] the cat token's tank: 12.5 uH with 22 nF */

/* ---- the pendulum (TMAG5273 under the swing, three coils round it) ------------------- */
#define PEND_LENGTH_M         0.119f       /* the board: the perch's underside 129 mm over the base
                                              (8.5 mm socket, 112 mm tree, 8.5 mm socket), the bat's
                                              magnet 10 mm over it at rest (ORDER_LIST.md, the thread) */
#define PEND_SENSOR_DEPTH_M   0.012f       /* the thread is cut for it: the TMAG5273 sits under the base
                                              (its die 2 mm below the top copper), the magnet 10 mm above */
#define PEND_COIL_RADIUS_M    0.018f       /* the designer: coil centres 18 mm from the rest point (31 mm
                                              apart; the coils are 30 mm across) */
#define PEND_COIL_ANGLE0_DEG  90.0f        /* gen/layout.py PEND_COILS: coil 1 (L3) at 90 deg, toward the
                                              viewer; coil 2 (L4) at 210, coil 3 (L5) at 330 */
#define TMAG_RATE_HZ          400u         /* [CHOICE] >= 200 Hz */

/* ---- theremin and audio --------------------------------------------------------------- */
#define THEREMIN_WINDOW_MS    10u          /* [CHOICE] edge-count window */
#define THEREMIN_F_LO_HZ      200.0f       /* [CHOICE] the ghost's range, exponential */
#define THEREMIN_F_HI_HZ      1000.0f
#define AUDIO_PWM_TOP         1023u        /* [CHOICE] 150 MHz / 1024 = 146 kHz carrier, 10 bits */
#define AUDIO_SAMPLE_DIV      4u           /* [CHOICE] one sample per 4 carrier periods: 36.6 kHz */
#define AUDIO_SAMPLE_HZ       (SYS_CLK_HZ / ((AUDIO_PWM_TOP + 1u) * AUDIO_SAMPLE_DIV))
#define AUDIO_VOLUME_CEILING  0.25f        /* [CHOICE] fraction of full scale: quiet by default */
#define AUDIO_VOLUME_DEFAULT  0.12f

/* ---- LEDs -------------------------------------------------------------------------------- */
#define LED_FPS               200u         /* [CHOICE] PLAN.md 3 */
#define LED_FADE_MIN_S        0.3f         /* Jason's rule: no change faster than 0 -> full in 300 ms */
#define LED_IMAX_MA           25.5f        /* [DS] LP5036 Max_Current_Option = 0 */
#define LED_CEIL_ORANGE       0.75f        /* [DS] XL-1608UOC: 20 mA continuous of 25.5 */
#define LED_CEIL_AMBER5050    1.0f         /* [DS] three dice in parallel: 60 mA */
#define LED_CEIL_VIOLET       0.6f         /* [CHOICE] 405 nm: eye safety at 2 cm (PLAN.md 7) */
#define LED_CEIL_PURPLE       1.0f         /* [DS] GL0603PU01: 30 mA */
#define LED_USB_ONLY_CEILING  0.15f        /* [CHOICE] USB power alone: LEDs dim, coils off */
#define I2C_BAUD              400000u      /* [DS] LP5036, LSM6DS3TR-C, LTR-303: fast mode */

/* ---- light sensor ---------------------------------------------------------------------- */
#define ALS_DARK_LUX          3.0f         /* [CHOICE] dusk below this ... */
#define ALS_LIGHT_LUX         30.0f        /* ... dawn above this (hysteresis: the board's own glow) */
#define ALS_HOLD_S            20.0f        /* [CHOICE] the level must hold this long */
