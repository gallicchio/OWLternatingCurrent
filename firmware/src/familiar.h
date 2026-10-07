/* familiar.h: the wireless familiars (PLAN.md C1): find a token on a perch, say
 * which it is, and light it.
 *
 * A token is a coil with a C0G capacitor across it (a parallel tank, the owl tuned to
 * FAM_OWL_HZ, the cat to FAM_CAT_HZ) and two LEDs.  On the perch it reflects an
 * impedance into the perch coil, so the perch current against frequency shows a
 * dispersive dip-and-peak round the token's resonance (sim/physics/familiar.py; the
 * coupling is strong, k ~ 0.47, and the token's Q low, ~5-10, so the dip sits a few
 * per cent below the tuning).  Each perch, on its own:
 *
 *   IDLE      bridge off; every FAM_SWEEP_PERIOD_S a
 *   SWEEP     FAM_F_MIN_HZ..FAM_F_MAX_HZ in FAM_SWEEP_N log steps at a drive so low that a
 *             token stays dark (duty FAM_SWEEP_DUTY: 0.6 V of fundamental; the cat's tank
 *             then reaches 1.4 V at most, under its LEDs' 1.85 V), recording the
 *             admittance |I| / V at each;
 *   FIT       against the empty perch's admittance (a model, then learned from sweeps that
 *             found nothing): a dip followed by a peak means a token; a fit of the coupled-
 *             tank model gives its resonance; owl, cat or unknown by that frequency;
 *   RAMP_UP   at the token's resonance (best LED drive per amp of perch current), the
 *             perch current rises smoothly to FAM_I_TARGET_A (closed loop on ISENSE, the
 *             duty never above what would put FAM_I_MAX_A x 1.15 into an empty perch);
 *   DRIVE     holds it; the frequency is dithered +-FAM_DITHER at 100 Hz (no visible
 *             flicker) and the admittance's local slope both follows the token (keep the
 *             slope) and notices it leave (the slope of an empty perch is -1);
 *   RAMP_DOWN when it leaves or the perch is switched off.
 *
 * How the glue calls it (core 0): fam_step() every ~1 ms per perch, with the perch
 * current amplitude from FAMn_ISENSE (A, after FAM_ISENSE_V_PER_A) and what it actually
 * applied (frequency and duty after the PWM's quantisation; NULL: as commanded).  It
 * sets the bridge from the returned command: phase-correct PWM at freq_hz, leg A's
 * pulse duty centred on the period's start, leg B's (inverted) on its middle, so the
 * coil sees a 3-level wave whose fundamental is (4/pi) FAM_VDRIVE_V sin(pi duty).
 * FAM_EN is on while either perch's command is enabled.
 * Portable C (no SDK): test/test_familiar.c runs it against a simulated perch.
 */
#pragma once
#include <stdbool.h>

/* ---- tunables ---------------------------------------------------------------------- */
#define FAM_SWEEP_N            48         /* [CHOICE] 3 % steps from 100 to 400 kHz */
#define FAM_SWEEP_DUTY         0.03f      /* [CHOICE] 0.6 V fundamental: tokens stay dark */
#define FAM_SETTLE_S           0.004f     /* [ASSUMED] ISENSE's filter settles in 4 ms (tau <= 1 ms) */
#define FAM_AVG_N              2          /* samples averaged per sweep step, after settling */
#define FAM_SWEEP_PERIOD_S     2.0f       /* [CHOICE] an empty perch looks this often */
#define FAM_I_TARGET_A         (0.9f * FAM_I_MAX_A)   /* [CHOICE] 0.18 A */
#define FAM_RAMP_S             2.5f       /* [CHOICE] dark to lit: orange first, then violet */
#define FAM_RAMP_DOWN_S        1.5f
#define FAM_DITHER             0.01f      /* [CHOICE] +-1 % frequency dither in DRIVE ... */
#define FAM_DITHER_HALF_S      0.005f     /* ... 5 ms each side: 100 Hz */
#define FAM_L1_H               28.5e-6f   /* [SIM] familiar.py: the perch coil */
#define FAM_R1_OHM             3.5f       /* [ASSUMED] perch coil + bridge, 150-330 kHz */

typedef enum { FAM_NONE = 0, FAM_OWL, FAM_CAT, FAM_UNKNOWN } fam_who;
typedef enum { FAM_ST_OFF = 0, FAM_ST_IDLE, FAM_ST_SWEEP, FAM_ST_FIT, FAM_ST_RAMP_UP, FAM_ST_DRIVE,
               FAM_ST_RAMP_DOWN } fam_state;
enum { FAM_EV_NONE = 0, FAM_EV_ARRIVED, FAM_EV_LEFT };

typedef struct {
    bool enable;          /* bridge on (else both legs low) */
    float freq_hz;
    float duty;           /* 0 .. 0.5: each leg's pulse, a fraction of the period */
} fam_cmd;

typedef struct {
    int kind;             /* FAM_EV_* */
    int perch;
    fam_who who;
    float freq_hz;        /* the token's resonance */
} fam_event;

typedef struct {
    int index;
    bool enabled;
    fam_state state;
    float t_state;               /* when the state began */
    float t_last_sweep;
    fam_cmd cmd;
    /* sweep */
    float f[FAM_SWEEP_N];
    float y[FAM_SWEEP_N];        /* measured admittance, S */
    float base[FAM_SWEEP_N];     /* the empty perch's admittance, S */
    int base_learned;            /* sweeps that found nothing and taught the baseline */
    int step, n_avg;
    float acc;
    float t_step;
    /* fit (run a few candidates per call) */
    float lr[FAM_SWEEP_N];       /* log admittance ratio, normalised */
    int i_dip, i_peak, fit_i, fit_lo, fit_hi;
    float fit_best, fit_ft, fit_k2, fit_q, f_dip;
    /* the token */
    fam_who who;
    float f_token, f_drive;
    float y_token;               /* its admittance at f_drive in the sweep */
    float y_empty;               /* an empty perch's there */
    float duty_cap, trim;
    float i_target, i_meas_f;
    float ramp_from_A;
    float ramp_s;
    /* dither in DRIVE */
    int dith_side, dith_n;
    float dith_acc[2], dith_f[2];
    int dith_cnt[2];
    float slope, slope0;
    bool slope_ok;
    float t_low_slope;
    float t_prev;
} fam_perch;

void fam_init(fam_perch *p, int index);
/* off: a lit token fades out, then the bridge stops */
void fam_enable(fam_perch *p, bool on);
void fam_step(fam_perch *p, float t_s, float isense_A, const fam_cmd *applied, fam_cmd *cmd, fam_event *ev);
const char *fam_who_name(fam_who w);
const char *fam_state_name(fam_state s);
