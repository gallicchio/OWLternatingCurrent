/* lev_ctrl.h: the levitating bat's controller (vertical axis), portable C.
 *
 * A port of sim/physics/levitation_loop.py to the one-magnet design (lev_table.h):
 * a PID on the gap with a low-passed derivative, the coil's own field subtracted
 * from the Hall reading, and the slow "zero-power" loop that moves the set-point
 * until the mean coil current is zero, so the bias magnet carries the bat.
 *
 * Who calls it: core 1, once per control tick (CTRL_TICK_HZ, 10 kHz), after the
 * tick's ADC burst, with the burst's averages (lev_input).  It returns the mean
 * bridge voltage as a fraction of the 12 V rail (lev_output.u); the caller turns
 * that into the DRV8874's PWM.  Core 0 (the console) may call lev_enable(),
 * lev_request_cal() and lev_set_param() at any time: they write single words that
 * the next lev_step() picks up.  Telemetry is read with lev_get_telemetry().
 *
 * Frames.  The caller's hall_mT is HALL_POLARITY * (V_hall - VQ_nominal) / S: the
 * field along the sensor's axis, plus the error in the nominal VQ.  Inside, fields
 * count positive along the bat's own field at the sensor (bat_sign flips the
 * reading if the sensor is mounted the other way; it is found automatically when
 * the bat first comes near), and current counts positive when it lifts the bat
 * (coil_pol maps that onto the bridge's forward direction; the CAL procedure
 * measures it).  Physics behind the CAL: a current whose field at the sensor is
 * aligned with the bat's field there attracts the bat.
 *
 * States:
 *   OFF      coil off; lev_enable(true) starts (a CAL first if the coil was never
 *            calibrated and auto_cal is set)
 *   CAL      coil: alternating +-i_cal pulses (bat absent or resting in its
 *            cradle), measures the coil's field at the sensor per amp and its
 *            polarity; zero: coil off, bat removed, measures the Hall offset
 *   WAIT     coil off; catches when the bat is within +-catch_mm of the float gap
 *            and steady for steady_s (resting in the cradle, or held by a hand)
 *   HOLD     levitating.  A catch starts with the set-point where the bat is and
 *            the integrator holding its weight, and walks the set-point to the
 *            float gap at ramp_mm_s (0: a step, as the simulation does)
 *   LOST     the gap left +-loss_mm of the set-point, the Hall saw no bat, the coil
 *            current was pinned at i_max too long, or the 1 s mean current was too
 *            high (a hand holding the bat): current zero at once; WAIT after lost_s
 *   INHIBIT  the caller said the coil may not run (no 12 V, a bridge fault): off
 *            until it may, then WAIT
 *   FAULT    thermal trip, the current mirror disagreeing with the command (open
 *            coil, short), or too many mean-current trips: off until re-enabled
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef enum {
    LEV_OFF = 0, LEV_CAL, LEV_WAIT, LEV_HOLD, LEV_LOST, LEV_INHIBIT, LEV_FAULT, LEV_STATES
} lev_state;

typedef enum { LEV_CAL_COIL = 1, LEV_CAL_ZERO = 2 } lev_cal_kind;

/* what the caller measures, once per tick */
typedef struct {
    float hall_mT;        /* HALL_POLARITY * (V_hall - VQ_nominal) / S, the burst's average */
    float iprop_A;        /* |I| from LEV_IPROPI (V / IPROPI_V_PER_A), the burst's average */
    float v12_V;          /* the bridge's supply */
    float coil_R_ohm;     /* the coil's resistance (thermal module's estimate), bridge excluded */
    bool coil_allowed;    /* 12 V present, bridges awake, no nFAULT: false releases (INHIBIT) */
    bool thermal_trip;    /* the coil's thermal model says stop: FAULT */
} lev_input;

/* what the bridge should do until the next tick */
typedef struct {
    float u;              /* mean bridge voltage / v12_V, -1..1; + = forward (IN1 -> IN2) */
    float i_fwd_A;        /* the current that u should make, in the bridge's forward sense */
    bool active;          /* false: u = 0 and the bridge may coast */
} lev_output;

/* the calibration worth keeping in flash (the caller stores and restores it) */
typedef struct {
    float hall_zero_mT;   /* the bat-free reading (VQ error + bias field), if zero_valid */
    float coil_raw_mT_per_A;  /* d(hall_mT)/d(forward current), if coil_valid */
    int8_t bat_sign;      /* +1: the bat's field reads positive in hall_mT */
    uint8_t zero_valid;
    uint8_t coil_valid;
} lev_cal_data;

typedef struct {
    lev_state state;
    float gap_mm;         /* estimated gap (perch's bottom copper to the bat's magnet) */
    float gref_mm;        /* the set-point now */
    float gzp_mm;         /* the zero-power set-point the catch walks to */
    float bbat_mT;        /* the bat's field at the sensor, coil and bias removed */
    float i_cmd_A;        /* lifting current asked for */
    float i_est_A;        /* lifting current believed (mirror, signed; the command near zero) */
    float mean_I_A;       /* 1 s running mean of the lifting current */
    float rms_I_A;        /* 1 s running rms */
    float peak_I_A;       /* largest |command| since the last catch */
    uint32_t catches, losses, trips;
    const char *reason;   /* why the last LOST / FAULT / CAL failure, or "" */
    const char *cal;      /* the last CAL's result */
    int8_t bat_sign, coil_pol;
    float kcs_mT_per_A;   /* the coil's field at the sensor per lifting amp in use */
    float hall_offset_mT;
} lev_telemetry;

typedef struct {
    /* tunables (lev_set_param) */
    float bw_hz, zeta, ki_div, dfilt_hz, zp_rate, zp_range_mm, g0_mm, mass_g;
    float i_max, catch_mm, loss_mm, ramp_mm_s, steady_s, lost_s, i_cal, sched, auto_cal;
    float coil_pol, bat_sign, kcs, offset_mT;
    /* derived gains (force units: N/m, N s/m, N/(m s)) */
    float kp, kd, ki, a_d;
    /* requests from core 0 */
    volatile int8_t req_enable;          /* -1 none, 0 off, 1 on */
    volatile int8_t req_cal;             /* 0 none, else lev_cal_kind */
    /* state */
    lev_state state;
    uint32_t ticks;                      /* in this state */
    float gap, gap_prev, dgap, gap_lpf, dgap_slow;  /* m, m/s */
    float integ;                         /* N (the integral term's force) */
    float gref, gzp;                     /* m */
    float i_cmd, i_est, i_model;         /* A, lifting: asked for, believed now, what the last u makes */
    float i_model_prev;                  /* what the u before it makes */
    int u_lag;                           /* the bursts lev_step sees ran under the u from this many steps
                                            before the last: 0 if each u is in force for the next
                                            step's burst; 1 on the board since 2026-11-08 (rt.h: the
                                            burst overlaps the step, the u applies after the burst) */
    float mean_i, ms_i, peak_i;
    float bbat;                          /* mT */
    uint32_t steady_ticks, sat_ticks, bad_ticks, flip_ticks, mirror_ticks;
    uint32_t catches, losses, trips;
    float trip_window;                   /* s since the first of the recent trips */
    bool have_gap, ramping;
    const char *reason, *cal_msg;
    /* calibration */
    lev_cal_data cal;
    int cal_kind, cal_return;
    float cal_acc_h, cal_n, cal_n_end;
    float cal_h_off0, cal_h_plus, cal_h_minus, cal_i_plus, cal_i_minus, cal_i_off, cal_n_pulse;
} lev_ctrl;

void lev_init(lev_ctrl *c);                         /* defaults from lev_table.h and config.h; OFF */
void lev_enable(lev_ctrl *c, bool on);              /* any time, any core */
bool lev_request_cal(lev_ctrl *c, lev_cal_kind k);  /* refused (false) while levitating */
void lev_step(lev_ctrl *c, const lev_input *in, lev_output *out);   /* every tick, core 1 */

void lev_get_telemetry(const lev_ctrl *c, lev_telemetry *t);
const char *lev_state_name(lev_state s);

/* calibration kept across resets */
void lev_get_cal(const lev_ctrl *c, lev_cal_data *d);
void lev_set_cal(lev_ctrl *c, const lev_cal_data *d);

/* the console's tunables: `lev tune <name> <value>` */
int lev_param_count(void);
const char *lev_param_name(int i);
float lev_get_param(const lev_ctrl *c, int i);
bool lev_set_param(lev_ctrl *c, const char *name, float value);   /* false: unknown or out of range */
