/* pendulum.h: the bat that never stops flying (PLAN.md C2).
 *
 * The bat (one 10 x 2 mm N52 disc, axis vertical) hangs on a thread over the
 * TMAG5273; three coils sit round the swing's rest point.  This module turns the
 * TMAG5273's samples into the bat's position and velocity, and decides which coil
 * gets a short current pulse when, in one of four modes:
 *
 *   OFF      nothing
 *   SUSTAIN  swing along one axis (through coil 1 by default): pump energy along it,
 *            damp the motion across it
 *   CIRCLE   circle the moon: a force that rotates through the three coils, 120 deg
 *            apart, always along the bat's direction of travel, holding a radius
 *   CHAOS    "which pumpkin will it choose": pump up a swing, then let it go with the
 *            coils attracting it as it passes; it wanders, chaotically, and the coil
 *            under its last big swing is the one it chose (PEND_EV_CHOSE); a rest,
 *            then again
 *
 * Signs: a positive current repels the bat from that coil (pushes it away from the
 * coil's centre).  The bridge polarity that does that depends on the coil's winding
 * and on which way up the bat's magnet is: the glue multiplies by PEND_POLARITY.
 *
 * The coil's force on the bat is computed at start-up from the canonical coil's real
 * geometry (four layers of 12 turns, radii 4-15 mm): 11.4 mN/A at most when the
 * magnet is 10 mm above the copper (sim/physics README section 4), 6.4 mN/A at the
 * assumed 12.6 mm, and only 11 % of that at the rest point, 25 mm from each coil.
 *
 * How the glue calls it (core 0, with the I2C bus):
 *   pend_sample() at each TMAG5273 reading (TMAG_RATE_HZ, ~400 Hz, timestamps may
 *   jitter), passing the currents the coils carried during that reading; it returns
 *   the currents to apply now (each |I| <= PEND_I_MAX_A, scaled further by the thermal
 *   derating in the glue), to hold for hold_ms and then drop unless renewed.
 * Portable C (no SDK): test/test_pendulum.c flies it against a simulated pendulum.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define PEND_COILS 3

/* ---- tunables ---------------------------------------------------------------------- */
#define PEND_POLARITY               (+1)      /* [ASSUMED] bridge sign that repels; the bench sets it */
#define PEND_MASS_KG                3.6e-3f   /* [SIM] levitation_onemagnet.py: the bat */
#define PEND_MOMENT_AM2             0.179f    /* [SIM] 10 x 2 mm N52: Br V / mu0 */
#define PEND_SENSOR_ABOVE_COPPER_M  0.6e-3f   /* [ASSUMED] TMAG5273's sensing point over the top copper */
#define PEND_I_PULSE_A              0.3f      /* [SIM] pulses of 0.1-0.3 A keep it flying */
#define PEND_I_DEADBAND_A           0.03f     /* [CHOICE] smaller requests are dropped */
#define PEND_HOLD_MS                10u       /* [CHOICE] a command lapses after this */
#define PEND_SUSTAIN_AMP_M          0.025f    /* [CHOICE] */
#define PEND_CHAOS_AMP_M            0.030f    /* [CHOICE] pumped up to this, then let go */
#define PEND_CHAOS_FREE_S           25.0f     /* [CHOICE] the longest it wanders */
#define PEND_CHAOS_REST_S           4.0f      /* [CHOICE] the choice shows for this long */
#define PEND_NOISE_MT               0.05f     /* [DS] TMAG5273A2, CONV_AVG 8x: ~52 uT x/y, ~31 uT z rms */
#define PEND_PRESENT_MT             0.15f     /* [CHOICE] below this |B| there is no bat over the sensor */
#define PEND_KERNEL_STEP_M          1e-3f     /* force table: 0..60 mm */
#define PEND_KERNEL_N               61

typedef enum { PEND_OFF = 0, PEND_SUSTAIN, PEND_CIRCLE, PEND_CHAOS, PEND_MODES } pend_mode;
enum { PEND_EV_NONE = 0, PEND_EV_CHOSE, PEND_EV_ARRIVED, PEND_EV_GONE };

typedef struct {
    float length_m;            /* thread: pivot to magnet (PEND_LENGTH_M) */
    float depth_m;             /* sensor to magnet at rest (PEND_SENSOR_DEPTH_M) */
    float copper_dz_m;         /* coils' top copper to magnet at rest */
    float coil_r_m;            /* coil centres from the rest point (PEND_COIL_RADIUS_M) */
    float coil_angle0_deg;     /* coil 1's direction (PEND_COIL_ANGLE0_DEG); then +120, +240 */
    float mass_kg, moment_Am2;
    float i_pulse_A;           /* the strongest pulse (<= i_max_A) */
    float i_max_A;             /* PEND_I_MAX_A */
    float deadband_A;
    float sustain_amp_m, sustain_axis_deg;
    float circle_radius_m;
    float chaos_amp_m;
    float noise_mT;
} pend_params;

typedef struct {
    float i_A[PEND_COILS];     /* + repels the bat from that coil */
    uint32_t hold_ms;          /* drop them after this unless a new command arrives */
    int event;                 /* PEND_EV_* */
    int event_arg;             /* PEND_EV_CHOSE: the coil (0-2) */
} pend_cmd;

typedef struct {
    bool present;              /* a bat over the sensor */
    float x_m, y_m;            /* horizontal position from the rest point (x right, y toward coil 1 at 90 deg) */
    float vx_m_s, vy_m_s;
    float amp_m;               /* SUSTAIN: along the axis; CIRCLE: radius; else the swing's size */
    float phase_rad;           /* of the swing along the axis (SUSTAIN) or round the circle */
    float f_hz;                /* the swing's frequency (learned) */
    int chosen;                /* CHAOS: the last coil chosen, -1 before the first */
    const char *mode;
    const char *stage;
} pend_status;

typedef struct {
    pend_params p;
    pend_mode mode;
    /* geometry */
    float coil_x[PEND_COILS], coil_y[PEND_COILS];
    float kernel[PEND_KERNEL_N];  /* horizontal force per amp at the rest height, + = away from the coil */
    float k_peak;                 /* its largest value */
    /* estimator */
    float off[3];                 /* the field with no bat (pend_set_offset) */
    float sign_m;                 /* -1: the magnet's north pole points down (learned) */
    float b_centre_mT;            /* the field straight over the sensor at rest, nominal */
    int sign_votes;
    bool present, have_t, reinit;
    int absent_n, present_n;
    uint32_t last_us;
    float t_s;                    /* time since init, from the samples' timestamps */
    float x[2], v[2];             /* state per axis */
    float P[2][3];                /* covariance per axis: Pxx, Pxv, Pvv */
    float omega, omega0;          /* learned and nominal natural frequency, rad/s */
    float last_up_s[2];           /* last upward zero crossing per axis */
    float prev_pos[2];
    float amp_axis[2];
    /* controller */
    int stage;
    float stage_t0;
    float chaos_axis_deg;
    int chaos_round;
    int chosen;
    float last_turn_x, last_turn_y;
    float prev_vr;
    int near_coil, near_n;
    float sustain_phase;
    pend_cmd last;
} pendulum;

void pend_default_params(pend_params *p);
void pend_init(pendulum *pd, const pend_params *p);
void pend_set_mode(pendulum *pd, pend_mode m);
/* the field the sensor reads with no bat near (offsets, the Earth, other magnets), mT */
void pend_set_offset(pendulum *pd, float bx_mT, float by_mT, float bz_mT);
/* one TMAG5273 reading (mT, the sensor's axes: z up out of the board); applied_A: the
 * currents the coils carried during it (+ = repel); fills out with what to do now */
void pend_sample(pendulum *pd, uint32_t t_us, float bx_mT, float by_mT, float bz_mT,
                 const float applied_A[PEND_COILS], pend_cmd *out);
void pend_status_get(const pendulum *pd, pend_status *s);
const char *pend_mode_name(pend_mode m);
bool pend_mode_from_name(const char *name, pend_mode *m);
/* horizontal force per amp (N/A) on the bat rho_m from a coil's centre, at height dz_m
 * over its top copper; + = away from the coil (positive current repels) */
float pend_kernel_N_per_A(const pendulum *pd, float rho_m, float dz_m);
