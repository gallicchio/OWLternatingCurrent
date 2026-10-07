/* rt.h: core 1, the board's realtime half.
 *
 * A 10 kHz tick (CTRL_TICK_HZ) from PWM slice PWM_SLICE_TICK, phase-locked to the
 * levitation coil's PWM (both started together through the PWM block's EN register,
 * the tick's period a whole number of the coil's).  Each tick:
 *   1. the tick's wrap interrupt starts an ADC burst: round robin over ADC0 (the
 *      Hall sensor), ADC1 (the levitation coil's IPROPI) and ADC2 (the multiplexer),
 *      ADC_OVERSAMPLE times each, 24 conversions in 48 us, collected by DMA.  It
 *      starts at the same point of the coil's PWM period every time (the period's
 *      start: the centre of the forward pulse), so the PWM ripple lands in the
 *      averages the same way every tick;
 *   2. the DMA's completion interrupt: the averages; the multiplexer moves on to its
 *      next channel (each of the eight is read every 0.8 ms, settling for 50 us);
 *      the rails and the safety checks; the levitation controller (lev_ctrl.h); the
 *      pendulum coils' requests from core 0; the coils' PWM; at 1 kHz the coils'
 *      thermal models.
 *
 * Safety, here because it must not wait for core 0:
 *   - no coil runs without 12 V (V12_PRESENT_V to start, V12_BROWNOUT_V stops all
 *     at once), and none on USB power alone;
 *   - the DRV8874s' nFAULT (wired-OR) held low for 1 ms: every coil off and the
 *     bridges asleep; a retry 100 ms later; three in a minute latch everything off
 *     until `clear`;
 *   - every request from core 0 carries a deadline: a core 0 that stops talking
 *     leaves no coil on;
 *   - current limits per owner (pendulum, film, console), scaled down by the coil's
 *     thermal model from COIL_DERATE_FROM_C to zero at COIL_SURFACE_LIMIT_C;
 *     overcurrent and open-coil checks against the current mirrors;
 *   - core 0 feeds the watchdog only while this tick runs (rt.ticks advances), so a
 *     stalled core 1 resets the chip, and a reset leaves every bridge asleep.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "coil_ids.h"
#include "lev_ctrl.h"
#include "thermal.h"

enum {
    RT_FAULT_NFAULT = 1u << 0,        /* the DRV8874s' nFAULT (latched until `clear`) */
    RT_FAULT_BROWNOUT = 1u << 1,      /* 12 V fell while a coil was driven */
    RT_FAULT_OVERCURRENT = 1u << 2,   /* a mirror read far above the request */
    RT_FAULT_THERMAL = 1u << 3,       /* a coil reached its limit */
    RT_FAULT_OPEN_COIL = 1u << 4,     /* current asked for, none flowed */
    RT_FAULT_ADC = 1u << 5,           /* bursts overrunning, conversion errors */
    RT_FAULT_WATCHDOG = 1u << 6,      /* the last reset was the watchdog (core 0 sets it) */
    RT_FAULT_LATCHED_OFF = 1u << 7,   /* nFAULT kept coming back: coils off until `clear` */
};
#define RT_FAULT_NAMES {"nfault", "brownout", "overcurrent", "thermal", "open_coil", "adc", "watchdog_reset", "latched_off"}

enum { RT_OWNER_NONE = 0, RT_OWNER_PEND, RT_OWNER_FILM, RT_OWNER_CONSOLE };

#define LEV_EYES_MAX 0.8f   /* [CHOICE] the carrier's share of each period at most (0.4 each way).
                              The carrier's fundamental is about (4/pi) 12 V sin(pi m) / (2 pi f L),
                              m = eyes / 2: eyes 0.3 makes ~0.45 A, which lights the eyes (bat_power.py) */

typedef struct {
    /* written by core 1 */
    volatile uint32_t ticks, overruns, adc_errors;
    volatile float v12, v5, vbus;              /* V */
    volatile float hall_mT;                    /* as lev_input.hall_mT */
    volatile float i_meas[COIL_COUNT];         /* |I| from the mirrors, A */
    volatile float u[COIL_COUNT];              /* mean bridge voltage / 12 V applied */
    volatile float fam_isense[2];              /* perch current amplitude, A */
    volatile float temp_C[COIL_COUNT], r_ohm[COIL_COUNT];
    volatile uint32_t faults;                  /* RT_FAULT_* */
    volatile bool power_ok;                    /* 12 V present: coils may run */
    volatile bool drv_awake;
    volatile bool carrier_on;
    volatile uint16_t raw_adc[3], raw_mux[8];  /* the last averages, ADC counts (raw_adc by ADC_SLOT_*) */
    volatile uint32_t nfault_events;
    volatile uint32_t tick_cycles_max;         /* the longest tick's work, in clk_sys cycles */
    /* written by core 0 */
    volatile float ambient_C;                  /* the board's temperature, for the thermal models */
    volatile float lev_eyes;                   /* 0..1: the 80 kHz carrier for the bat's eyes */
    volatile uint32_t clear_req;               /* incremented to clear latched faults */
} rt_shared;

extern rt_shared rt;
extern lev_ctrl rt_lev;                        /* core 0: lev_enable, lev_request_cal, lev_set_param,
                                                  lev_get_telemetry */
extern thermal_coil rt_thermal[COIL_COUNT];    /* core 0 reads */

/* core 0, once: launches core 1.  cold_boot: a power-on (the coils are at room
 * temperature); cal: the levitation's saved calibration, or NULL */
void rt_start(bool cold_boot, const lev_cal_data *cal);
/* core 0: a mean current (A, + = forward) for ms milliseconds; false if refused */
bool rt_coil_request(int coil, float amps, uint32_t ms, int owner);
void rt_coil_release_owner(int owner);         /* every coil this owner holds: off now */
int rt_coil_owner(int coil);                   /* RT_OWNER_* holding it now */
bool rt_coils_idle(void);                      /* nothing driven and the bridges asleep */
const char *rt_fault_name(unsigned bit);
