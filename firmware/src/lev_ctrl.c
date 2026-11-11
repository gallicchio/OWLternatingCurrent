/* lev_ctrl.c: the levitating bat's controller.  lev_ctrl.h says what it does;
 * sim/physics/levitation_loop.py is the controller this ports, and
 * test/test_lev.c runs it against that simulation's plant (lev_plant.h).
 *
 * Every step, in order:
 *   1. requests from core 0 (enable, calibrate);
 *   2. the measurement: the reading in the bat's frame, minus the bias magnet's
 *      field and the coil's own field (the current believed to flow: the
 *      mirror's reading, signed by the command, above 0.4 A; the command below
 *      0.2 A, where the mirror's +-30 mA offset would dominate; a blend between),
 *      turned into a gap through the bat's field table;
 *   3. the state machine (lev_ctrl.h);
 *   4. in HOLD, the PID in force units, F = Kp(gap) e + Kd de/dt + integral, with
 *      Kp = m wc^2 + k_neg(gap) and the current I = F / k_coil(gap), both read from
 *      the table at the estimated gap (sched = 0 freezes them at the float gap, as
 *      the simulation's controller); the zero-power loop moves the set-point by
 *      -zp_rate * (I - zp_i): zp_i 0 finds the magnets' own float, a positive zp_i
 *      hangs the bat lower, where holding it takes zp_i;
 *   5. the bridge: u = I (R + R_bridge) / v12, limited to +-1.
 * Single precision only: it runs at 10 kHz on a Cortex-M33.
 */
#include "lev_ctrl.h"
#include "config.h"
#include "lev_table.h"
#include <math.h>
#include <stddef.h>
#include <string.h>

#define DT          CTRL_TICK_S
#define G_ACC       9.81f
#define TWO_PI      6.28318531f
#define TICKS(s)    ((uint32_t)((s) * (float)CTRL_TICK_HZ + 0.5f))

#define NOBAT_MT    3.0f        /* the bat's field below this: no bat near (gap > ~20 mm) */
#define FLIP_MT     15.0f       /* a reading this strong against bat_sign: the sensor reads the other way */
#define MIRROR_LO_A 0.2f        /* below: trust the command for the current; above MIRROR_HI_A: the mirror */
#define MIRROR_HI_A 0.4f
#define MEAN_TRIP_A 0.6f        /* 1 s mean lifting current above this: something holds the bat */
#define TRIPS_TO_FAULT 5u       /* mean-current trips within TRIP_WINDOW_S: FAULT */
#define TRIP_WINDOW_S 60.0f
#define KC_MIN      3e-3f       /* N/A: never divide by less coil grip than this */

/* ---- the tables (lev_table.h): uniform in gap ---------------------------------------- */
static float tab_at(const float *t, float gap_m, float *slope_per_m)
{
    float x = (gap_m * 1e3f - LEV_TAB_GAP0_MM) / LEV_TAB_STEP_MM;
    if (x < 0.0f)
        x = 0.0f;
    if (x > (float)(LEV_TAB_N - 1) - 1e-3f)
        x = (float)(LEV_TAB_N - 1) - 1e-3f;
    int i = (int)x;
    float f = x - (float)i;
    float d = t[i + 1] - t[i];
    if (slope_per_m)
        *slope_per_m = d / (LEV_TAB_STEP_MM * 1e-3f);
    return t[i] + f * d;
}

/* the gap at which the bat's field at the sensor is b_mT (the table falls with the gap);
 * *range: -1 nearer than the table (or a saturated sensor), +1 no bat, 0 fine */
static float gap_of_field(float b_mT, int *range)
{
    *range = 0;
    if (b_mT >= LEV_TAB_BBAT_MT[0]) {
        *range = -1;
        return LEV_TAB_GAP0_MM * 1e-3f;
    }
    if (b_mT <= NOBAT_MT || b_mT <= LEV_TAB_BBAT_MT[LEV_TAB_N - 1]) {
        *range = +1;
        if (b_mT <= LEV_TAB_BBAT_MT[LEV_TAB_N - 1])
            return (LEV_TAB_GAP0_MM + (LEV_TAB_N - 1) * LEV_TAB_STEP_MM) * 1e-3f;
    }
    int lo = 0, hi = LEV_TAB_N - 1;              /* B[lo] > b >= B[hi] */
    while (hi - lo > 1) {
        int mid = (lo + hi) >> 1;
        if (LEV_TAB_BBAT_MT[mid] > b_mT)
            lo = mid;
        else
            hi = mid;
    }
    float f = (LEV_TAB_BBAT_MT[lo] - b_mT) / (LEV_TAB_BBAT_MT[lo] - LEV_TAB_BBAT_MT[hi]);
    return (LEV_TAB_GAP0_MM + ((float)lo + f) * LEV_TAB_STEP_MM) * 1e-3f;
}

static float k_neg_at(float gap_m)
{
    float slope;
    tab_at(LEV_TAB_FBIAS_N, gap_m, &slope);
    return -slope;
}

static float kc_at(float gap_m)
{
    float k = tab_at(LEV_TAB_KCOIL_N_PER_A, gap_m, NULL);
    return k < KC_MIN ? KC_MIN : k;
}

static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }
static float sgnf(float x) { return x < 0.0f ? -1.0f : 1.0f; }

/* ---- parameters ----------------------------------------------------------------------- */
typedef struct {
    const char *name;
    size_t off;
    float lo, hi;
    bool gains;            /* changing it recomputes the gains */
} param_def;

#define P(n, lo, hi, g) {#n, offsetof(lev_ctrl, n), lo, hi, g}
static const param_def PARAMS[] = {
    P(bw_hz, 2.0f, 40.0f, true),        /* closed-loop bandwidth */
    P(zeta, 0.2f, 2.0f, true),          /* its damping */
    P(ki_div, 1.0f, 100.0f, true),      /* Ki = Kp wc / ki_div */
    P(dfilt_hz, 5.0f, 1000.0f, true),   /* the derivative's low-pass */
    P(zp_rate, 0.0f, 50.0f, false),     /* zero-power loop: set-point mm/s per lifting A */
    P(zp_range_mm, 0.0f, 4.0f, false),  /* how far it may move the set-point from g0 */
    P(zp_i, -0.5f, 0.5f, false),        /* the walk's target lifting current (0: zero power) */
    P(g0_mm, 4.0f, 14.0f, true),        /* the float gap it starts from */
    P(mass_g, 1.0f, 10.0f, true),       /* the bat */
    P(i_max, 0.1f, LEV_I_MAX_A, false), /* lifting current limit */
    P(catch_mm, 0.5f, 8.0f, false),     /* catch window round g0 */
    P(loss_mm, 1.0f, 8.0f, false),      /* lost beyond this from the set-point */
    P(ramp_mm_s, 0.0f, 100.0f, false),  /* the catch walks the set-point this fast (0: a step) */
    P(steady_s, 0.02f, 2.0f, false),    /* the bat must be still this long to be caught */
    P(lost_s, 0.2f, 30.0f, false),      /* rest after a loss */
    P(i_cal, 0.1f, 1.0f, false),        /* CAL's pulses */
    P(sched, 0.0f, 1.0f, true),         /* 1: gains follow the gap through the tables */
    P(auto_cal, 0.0f, 1.0f, false),     /* 1: CAL on enable until the coil is calibrated */
    P(coil_pol, -1.0f, 1.0f, false),    /* +1: forward current lifts the bat */
    P(bat_sign, -1.0f, 1.0f, false),    /* +1: the bat's field reads positive */
    P(kcs, 0.0f, 20.0f, false),         /* the coil's field at the sensor, mT per lifting A */
    P(offset_mT, -40.0f, 40.0f, false), /* subtracted from hall_mT (VQ error) */
};
#undef P
#define NPARAMS ((int)(sizeof PARAMS / sizeof PARAMS[0]))

int lev_param_count(void) { return NPARAMS; }

const char *lev_param_name(int i) { return (i >= 0 && i < NPARAMS) ? PARAMS[i].name : NULL; }

float lev_get_param(const lev_ctrl *c, int i)
{
    if (i < 0 || i >= NPARAMS)
        return 0.0f;
    return *(const float *)((const char *)c + PARAMS[i].off);
}

static void update_gains(lev_ctrl *c)
{
    float m = c->mass_g * 1e-3f;
    float wc = TWO_PI * c->bw_hz;
    float g0 = c->g0_mm * 1e-3f;
    c->kp = m * wc * wc;                                 /* + k_neg(gap), added per step */
    c->kd = 2.0f * c->zeta * m * wc;
    c->ki = (c->kp + k_neg_at(g0)) * wc / c->ki_div;
    c->a_d = 1.0f - expf(-TWO_PI * c->dfilt_hz * DT);
}

/* the calibration's consequences: the offset, the coil's polarity and coupling */
static void apply_cal(lev_ctrl *c)
{
    float s = c->bat_sign;
    if (c->cal.zero_valid)
        c->offset_mT = c->cal.hall_zero_mT - s * LEV_BBIAS_MT;
    if (c->cal.coil_valid) {
        c->coil_pol = sgnf(s * c->cal.coil_raw_mT_per_A);
        c->kcs = fabsf(c->cal.coil_raw_mT_per_A);
    }
    c->cal.bat_sign = (int8_t)s;
}

bool lev_set_param(lev_ctrl *c, const char *name, float v)
{
    for (int i = 0; i < NPARAMS; i++) {
        if (strcmp(name, PARAMS[i].name))
            continue;
        if (!(v >= PARAMS[i].lo && v <= PARAMS[i].hi))      /* also refuses NaN */
            return false;
        if (!strcmp(name, "coil_pol") || !strcmp(name, "bat_sign"))
            v = sgnf(v);
        *(float *)((char *)c + PARAMS[i].off) = v;
        if (PARAMS[i].gains)
            update_gains(c);
        if (!strcmp(name, "bat_sign"))
            apply_cal(c);                                    /* re-derive the polarity and offset */
        if (!strcmp(name, "kcs")) {            /* by hand: kept as the calibration, so `save` keeps it */
            c->cal.coil_raw_mT_per_A = v * c->coil_pol * c->bat_sign;
            c->cal.coil_valid = 1;
        }
        if (!strcmp(name, "g0_mm")) {
            c->gzp = v * 1e-3f;
            c->ramping = c->ramp_mm_s > 0.0f;                /* walk there, do not jump */
        }
        return true;
    }
    return false;
}

/* ---- state -------------------------------------------------------------------------------- */
const char *lev_state_name(lev_state s)
{
    static const char *const n[LEV_STATES] = {"off", "cal", "wait", "hold", "lost", "inhibit", "fault"};
    return (unsigned)s < LEV_STATES ? n[s] : "?";
}

static void go(lev_ctrl *c, lev_state s, const char *why)
{
    c->state = s;
    c->ticks = 0;
    c->i_cmd = 0.0f;
    c->steady_ticks = c->sat_ticks = c->bad_ticks = c->mirror_ticks = 0;
    if (why)
        c->reason = why;
}

void lev_init(lev_ctrl *c)
{
    memset(c, 0, sizeof *c);
    c->bw_hz = 10.0f;            /* the simulation's choice: 25 Hz chatters (sim/physics/README 3b) */
    c->zeta = 0.7f;
    c->ki_div = 8.0f;
    c->dfilt_hz = 50.0f;         /* the sim's 80 Hz doubles the noise current with the A4's coarser 7.5 mV/mT */
    c->zp_rate = 4.0f;           /* mm/s per A: ~1 s to find the float point */
    c->zp_range_mm = 2.0f;
    c->zp_i = 0.0f;              /* zero power; main.c sets LEV_ZP_I_A at boot */
    c->g0_mm = LEV_G0_BENCH_MM;
    c->mass_g = LEV_MASS_KG * 1e3f;
    c->i_max = LEV_I_MAX_A;
    c->catch_mm = 7.0f;          /* a bat 3 mm off, plus the DRV5055's VQ tolerance until `lev cal zero`
                                    has measured it: 8 mT reads as up to 2.7 mm at g0 + 3 mm, where the
                                    field only changes 3 mT/mm (review 2026-10-09: at 5 mm a -8 mT part
                                    never caught a bat resting 3 mm low) */
    c->loss_mm = 5.0f;
    c->ramp_mm_s = 6.0f;
    c->steady_s = 0.15f;
    c->lost_s = 2.0f;
    c->i_cal = 0.3f;             /* lifts at most 4.5 mN: the bat stays in its cradle (8.5 mN at +2 mm) */
    c->sched = 1.0f;
    c->auto_cal = 1.0f;
    c->coil_pol = 1.0f;
    c->bat_sign = 1.0f;          /* hall_mT already carries HALL_POLARITY: the bat should read + */
    c->kcs = LEV_BCOIL_MT_PER_A;
    c->offset_mT = 0.0f;
    c->cal.bat_sign = 1;
    c->req_enable = -1;
    c->gzp = c->gref = c->g0_mm * 1e-3f;
    c->reason = "";
    c->cal_msg = "never";
    update_gains(c);
    c->state = LEV_OFF;
}

void lev_enable(lev_ctrl *c, bool on) { c->req_enable = on ? 1 : 0; }

bool lev_request_cal(lev_ctrl *c, lev_cal_kind k)
{
    lev_state s = c->state;
    if (s == LEV_HOLD || s == LEV_CAL || (k != LEV_CAL_COIL && k != LEV_CAL_ZERO))
        return false;
    c->req_cal = (int8_t)k;
    return true;
}

void lev_get_cal(const lev_ctrl *c, lev_cal_data *d) { *d = c->cal; }

void lev_set_cal(lev_ctrl *c, const lev_cal_data *d)
{
    c->cal = *d;
    c->bat_sign = d->bat_sign < 0 ? -1.0f : 1.0f;
    apply_cal(c);
}

void lev_get_telemetry(const lev_ctrl *c, lev_telemetry *t)
{
    t->state = c->state;
    t->gap_mm = c->gap * 1e3f;
    t->gref_mm = c->gref * 1e3f;
    t->gzp_mm = c->gzp * 1e3f;
    t->bbat_mT = c->bbat;
    t->i_cmd_A = c->i_cmd;
    t->i_est_A = c->i_est;
    t->mean_I_A = c->mean_i;
    t->rms_I_A = sqrtf(c->ms_i > 0.0f ? c->ms_i : 0.0f);
    t->peak_I_A = c->peak_i;
    t->catches = c->catches;
    t->losses = c->losses;
    t->trips = c->trips;
    t->reason = c->reason;
    t->cal = c->cal_msg;
    t->bat_sign = (int8_t)c->bat_sign;
    t->coil_pol = (int8_t)c->coil_pol;
    t->kcs_mT_per_A = c->kcs;
    t->hall_offset_mT = c->offset_mT;
}

/* ---- calibration ------------------------------------------------------------------------ */
/* coil: 30 ms off, CAL_CYCLES of (+i_cal, -i_cal) 15 ms each, 30 ms off; each segment
 * skips its first part (the current settles in ~50 us, the reading lags a tick) */
#define CAL_CYCLES   4
#define N_OFF_SETTLE TICKS(0.010f)
#define N_OFF_ACC    TICKS(0.020f)
#define N_P_SETTLE   TICKS(0.005f)
#define N_P_ACC      TICKS(0.010f)
#define N_ZERO_SETTLE TICKS(0.020f)
#define N_ZERO_ACC   TICKS(0.300f)

static void begin_cal(lev_ctrl *c, int kind, lev_state back)
{
    go(c, LEV_CAL, NULL);
    c->cal_kind = kind;
    c->cal_return = (int)back;
    c->cal_acc_h = c->cal_n = c->cal_n_end = c->cal_n_pulse = 0.0f;
    c->cal_h_off0 = c->cal_h_plus = c->cal_h_minus = c->cal_i_plus = c->cal_i_minus = c->cal_i_off = 0.0f;
    c->cal_msg = "running";
}

static void end_cal(lev_ctrl *c, const char *msg, bool ok)
{
    c->cal_msg = msg;
    if (!ok)
        c->reason = msg;
    go(c, (lev_state)c->cal_return, NULL);
}

/* one CAL tick (c->ticks counts them from 1): returns the forward current to drive now */
static float cal_step(lev_ctrl *c, const lev_input *in)
{
    uint32_t j = c->ticks - 1;
    c->cal_coast = 0;
    if (c->cal_kind == LEV_CAL_ZERO) {
        if (j >= N_ZERO_SETTLE) {
            c->cal_acc_h += in->hall_mT;
            c->cal_n += 1.0f;
        }
        if (j + 1 >= N_ZERO_SETTLE + N_ZERO_ACC) {
            float h0 = c->cal_acc_h / c->cal_n;
            /* VQ is 1.65 V +- 60 mV (8 mT); the bias magnet adds 6.4 mT */
            if (fabsf(h0 - c->bat_sign * LEV_BBIAS_MT) > 10.0f) {
                end_cal(c, "zero: reading too far from the bias field alone: is the bat removed?", false);
            } else {
                c->cal.hall_zero_mT = h0;
                c->cal.zero_valid = 1;
                apply_cal(c);
                end_cal(c, "zero ok", true);
            }
        }
        return 0.0f;
    }
    const uint32_t a_end = N_OFF_SETTLE + N_OFF_ACC;
    const uint32_t np = N_P_SETTLE + N_P_ACC;
    const uint32_t b_end = a_end + CAL_CYCLES * 2 * np;
    const uint32_t c_end = b_end + N_OFF_SETTLE + N_OFF_ACC;
    /* The off windows coast the bridge, not drive it at zero: at zero the PWM still makes
     * its shortest pulses both ways, a zero-mean ripple of about 0.07 A that the mirror
     * (|I|, no sign) reads as current, which was then taken off both pulses as an offset
     * ("IPROPI disagrees" and kcs 2.15 against 3.5, bench 2026-11-11).  Coasting, only the
     * mirror's own offset is left. */
    if (j < a_end) {                                     /* off: the reading without the coil */
        c->cal_coast = 1;
        if (j >= N_OFF_SETTLE) {
            c->cal_acc_h += in->hall_mT;
            c->cal_i_off += in->iprop_A;     /* the mirror's offset (when it is positive) */
            c->cal_n += 1.0f;
        }
        if (j + 1 == a_end) {
            c->cal_h_off0 = c->cal_acc_h / c->cal_n;
            c->cal_i_off /= c->cal_n;
            c->cal_acc_h = c->cal_n = 0.0f;
        }
        return 0.0f;
    }
    if (j < b_end) {                                     /* the pulses */
        uint32_t jp = j - a_end, kk = jp / np, inp = jp % np;
        bool plus = (kk & 1u) == 0u;
        if (inp >= N_P_SETTLE) {
            if (plus) {
                c->cal_h_plus += in->hall_mT;
                c->cal_i_plus += in->iprop_A;
            } else {
                c->cal_h_minus += in->hall_mT;
                c->cal_i_minus += in->iprop_A;
                c->cal_n_pulse += 1.0f;
            }
        }
        /* the last tick of the last pulse drives nothing: its reading is already taken */
        return (j + 1 == b_end) ? 0.0f : (plus ? c->i_cal : -c->i_cal);
    }
    if (j < c_end) {                                     /* off again: did the bat move? */
        c->cal_coast = 1;
        if (j >= b_end + N_OFF_SETTLE) {
            c->cal_acc_h += in->hall_mT;
            c->cal_n_end += 1.0f;
        }
        if (j + 1 < c_end)
            return 0.0f;
    }
    float n = c->cal_n_pulse;                            /* samples per polarity */
    float hp = c->cal_h_plus / n, hm = c->cal_h_minus / n;
    float ip = c->cal_i_plus / n - c->cal_i_off, im = c->cal_i_minus / n - c->cal_i_off;
    float h_off1 = c->cal_acc_h / c->cal_n_end;
    bool mirror_ok = ip > 0.5f * c->i_cal && im > 0.5f * c->i_cal && ip < 1.5f * c->i_cal &&
                     im < 1.5f * c->i_cal;
    float i_sum = mirror_ok ? ip + im : 2.0f * c->i_cal; /* else trust the command, and say so */
    float k = (hp - hm) / i_sum;
    if (fabsf(h_off1 - c->cal_h_off0) > 0.5f) {
        end_cal(c, "coil: the bat moved during the pulses: leave it in its cradle, or take it away", false);
    } else if (fabsf(k) < 1.0f || fabsf(k) > 10.0f) {
        end_cal(c, "coil: no field from the coil at the sensor (open coil? dead Hall sensor?)", false);
    } else {
        c->cal.coil_raw_mT_per_A = k;
        c->cal.coil_valid = 1;
        apply_cal(c);
        end_cal(c, mirror_ok ? "coil ok" : "coil ok, but IPROPI disagrees with the command", true);
    }
    return 0.0f;
}

/* ---- the step ------------------------------------------------------------------------------ */
static void start(lev_ctrl *c)
{
    c->reason = "";
    c->trips = 0;
    c->trip_window = 0.0f;
    if (!c->cal.coil_valid && c->auto_cal >= 0.5f)
        begin_cal(c, LEV_CAL_COIL, LEV_WAIT);
    else
        go(c, LEV_WAIT, NULL);
}

static void engage(lev_ctrl *c)
{
    float m = c->mass_g * 1e-3f;
    go(c, LEV_HOLD, NULL);
    c->catches++;
    c->peak_i = 0.0f;
    c->mean_i = c->ms_i = 0.0f;
    /* every catch starts from g0: a walk that a hand drove (pushing the bat up into the
     * coil, which the loop answers by pushing down) must not carry over.  Before
     * 2026-11-09 it did, and nine catches in a row started at the walk's top, 11.5 mm,
     * where the magnets cannot carry the bat */
    c->gzp = c->g0_mm * 1e-3f;
    c->ramping = c->ramp_mm_s > 0.0f;
    c->gref = c->ramping ? c->gap : c->gzp;
    /* the integral starts out holding the bat's weight where it is */
    c->integ = clampf(m * G_ACC - tab_at(LEV_TAB_FBIAS_N, c->gap, NULL), -2.0f * m * G_ACC, 2.0f * m * G_ACC);
}

void lev_step(lev_ctrl *c, const lev_input *in, lev_output *out)
{
    /* 1. requests */
    int8_t r = c->req_enable;
    if (r >= 0) {
        c->req_enable = -1;
        if (!r)
            go(c, LEV_OFF, "");
        else if (c->state == LEV_OFF || c->state == LEV_FAULT)
            start(c);                        /* already running: enabling again changes nothing */
    }
    int8_t k = c->req_cal;
    if (k) {
        c->req_cal = 0;
        if (c->state != LEV_HOLD && c->state != LEV_CAL)
            begin_cal(c, k, c->state == LEV_OFF || c->state == LEV_FAULT ? LEV_OFF : LEV_WAIT);
    }

    /* 2. the measurement */
    float R = (in->coil_R_ohm > 0.5f ? in->coil_R_ohm : COIL_R20_OHM) + DRV_RDSON_OHM;
    float v12 = in->v12_V > 1.0f ? in->v12_V : 1.0f;
    float i_mod = c->u_lag ? c->i_model_prev : c->i_model;   /* the lifting current the u in force
                                                                during this burst makes */
    float i_mir = sgnf(i_mod) * in->iprop_A;
    float w = clampf((fabsf(i_mod) - MIRROR_LO_A) / (MIRROR_HI_A - MIRROR_LO_A), 0.0f, 1.0f);
    float i_now = w * i_mir + (1.0f - w) * i_mod;        /* believed to flow during this burst */
    c->i_est = i_now;
    float b = c->bat_sign * (in->hall_mT - c->offset_mT);
    c->bbat = b - LEV_BBIAS_MT - c->kcs * i_now;
    int range;
    float gap = gap_of_field(c->bbat, &range);
    if (!c->have_gap) {
        c->gap_prev = c->gap_lpf = gap;
        c->have_gap = true;
    }
    c->gap = gap;
    c->dgap += c->a_d * ((gap - c->gap_prev) / DT - c->dgap);
    c->gap_prev = gap;
    c->gap_lpf += (gap - c->gap_lpf) * (DT / 0.05f);
    c->dgap_slow += (c->dgap - c->dgap_slow) * (DT / 0.05f);    /* the stillness test's speed */
    c->ticks++;
    if (c->trip_window <= TRIP_WINDOW_S)
        c->trip_window += DT;                /* capped: a float stops counting 0.1 ms steps near 2048 s */

    /* faults that end everything */
    if (c->state != LEV_OFF && c->state != LEV_FAULT) {
        if (in->thermal_trip) {
            go(c, LEV_FAULT, "thermal: the coil's model says it is too hot");
        } else if (!in->coil_allowed && c->state != LEV_INHIBIT) {
            if (c->state == LEV_CAL)
                c->cal_msg = "aborted: the coil may not run";
            go(c, LEV_INHIBIT, "the coil may not run (12 V, a bridge fault)");
        }
    }
    /* the mirror against the command, whenever the coil is driven hard */
    if (c->state == LEV_HOLD || c->state == LEV_CAL) {
        float a = fabsf(i_mod);
        bool open = a > 0.6f && in->iprop_A < 0.15f;
        bool shorted = in->iprop_A > a + 1.0f && in->iprop_A > 1.5f;
        c->mirror_ticks = (open || shorted) ? c->mirror_ticks + 1 : 0;
        if (c->mirror_ticks > TICKS(open ? 0.020f : 0.005f))
            go(c, LEV_FAULT, open ? "the coil's current is missing: open coil or bridge?"
                                  : "the coil's current is far above the command: short?");
    }

    /* 3. the states */
    float i_fwd = 0.0f;
    bool active = false;
    switch (c->state) {
    case LEV_OFF:
    case LEV_FAULT:
        break;
    case LEV_INHIBIT:
        if (in->coil_allowed)
            go(c, LEV_WAIT, NULL);
        break;
    case LEV_CAL:
        i_fwd = cal_step(c, in);
        active = c->state == LEV_CAL && !c->cal_coast;
        if (!active)
            i_fwd = 0.0f;
        break;
    case LEV_LOST:
        if (c->ticks >= TICKS(c->lost_s))
            go(c, LEV_WAIT, NULL);
        break;
    case LEV_WAIT: {
        /* a strong field of the other sign: the sensor reads the bat negative */
        float raw = in->hall_mT - c->offset_mT;
        c->flip_ticks = (c->bat_sign * raw < -FLIP_MT) ? c->flip_ticks + 1 : 0;
        if (c->flip_ticks > TICKS(0.1f)) {
            c->bat_sign = -c->bat_sign;
            c->flip_ticks = 0;
            apply_cal(c);
            c->reason = "the bat's field reads negative: bat_sign flipped";
            break;
        }
        float g0 = c->g0_mm * 1e-3f;
        bool in_range = range == 0 && fabsf(gap - g0) <= c->catch_mm * 1e-3f;
        bool still = fabsf(gap - c->gap_lpf) < 0.15e-3f && fabsf(c->dgap_slow) < 4e-3f;
        c->steady_ticks = (in_range && still) ? c->steady_ticks + 1 : 0;
        if (c->steady_ticks >= TICKS(c->steady_s))
            engage(c);
        break;
    }
    case LEV_HOLD:
        break;
    default:
        break;
    }

    if (c->state == LEV_HOLD) {
        float m = c->mass_g * 1e-3f;
        float g0 = c->g0_mm * 1e-3f;
        /* the set-point: walk from the catch to the zero-power gap, then let that loop move it */
        if (c->ramping) {
            float stepm = c->ramp_mm_s * 1e-3f * DT;
            float d = c->gzp - c->gref;
            if (fabsf(d) <= stepm) {
                c->gref = c->gzp;
                c->ramping = false;
            } else {
                c->gref += d > 0.0f ? stepm : -stepm;
            }
        } else {
            float zr = c->zp_range_mm * 1e-3f;
            c->gzp = clampf(c->gzp - c->zp_rate * 1e-3f * (c->i_cmd - c->zp_i) * DT, g0 - zr, g0 + zr);
            c->gref = c->gzp;
        }
        float e = gap - c->gref;                     /* + : too low, lift */
        bool sch = c->sched >= 0.5f;
        float kp = c->kp + k_neg_at(sch ? gap : g0);
        float kc = kc_at(sch ? gap : g0);
        float f = kp * e + c->kd * c->dgap + c->integ;
        float i = f / kc;
        bool sat = fabsf(i) >= c->i_max;
        i = clampf(i, -c->i_max, c->i_max);
        /* integrate unless that would drive further into the limit */
        if (!sat || (i > 0.0f) != (e > 0.0f))
            c->integ = clampf(c->integ + c->ki * e * DT, -2.0f * m * G_ACC, 2.0f * m * G_ACC);
        c->i_cmd = i;
        if (fabsf(i) > c->peak_i)
            c->peak_i = fabsf(i);
        c->sat_ticks = sat ? c->sat_ticks + 1 : 0;
        c->mean_i += (i_now - c->mean_i) * DT;       /* 1 s running mean and mean square */
        c->ms_i += (i_now * i_now - c->ms_i) * DT;

        bool far = fabsf(e) > c->loss_mm * 1e-3f || range != 0;
        c->bad_ticks = far ? c->bad_ticks + 1 : 0;
        if (c->bad_ticks > TICKS(0.002f)) {
            c->losses++;
            go(c, LEV_LOST, range > 0 ? "lost: no bat in front of the sensor"
                            : range < 0 ? "lost: the bat is against the perch"
                                        : "lost: the gap left the window");
        } else if (c->sat_ticks > TICKS(0.1f)) {
            c->losses++;
            go(c, LEV_LOST, "lost: the current stayed at its limit");
        } else if (c->ticks > TICKS(2.0f) && fabsf(c->mean_i) > MEAN_TRIP_A) {
            c->losses++;
            if (c->trip_window > TRIP_WINDOW_S) {
                c->trips = 0;
                c->trip_window = 0.0f;
            }
            if (++c->trips >= TRIPS_TO_FAULT)
                go(c, LEV_FAULT, "too many mean-current trips: is the bat stuck, or the tuning wrong?");
            else
                go(c, LEV_LOST, "lost: the mean current was too high (held?)");
        } else {
            i_fwd = c->coil_pol * c->i_cmd;
            active = true;
        }
    }

    /* 4. the bridge */
    float u = clampf(i_fwd * R / v12, -1.0f, 1.0f);
    if (!active)
        u = 0.0f;
    out->u = u;
    out->i_fwd_A = u * v12 / R;
    out->active = active;
    /* the lifting current this u will make: next tick's model current */
    c->i_model_prev = c->i_model;
    c->i_model = c->coil_pol * out->i_fwd_A;
    if (c->state != LEV_HOLD)
        c->i_cmd = c->coil_pol * out->i_fwd_A;
}
