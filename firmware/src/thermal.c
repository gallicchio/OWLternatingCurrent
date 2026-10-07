/* thermal.c: the coils' two-node thermal model (thermal.h).
 *
 * Where the [ASSUMED] numbers in thermal.h come from (the canonical coil: four
 * layers of 12 turns, 0.6 mm track at 1 mm pitch, radii 3-15 mm, 1 oz copper):
 *   copper:  4 layers x 12 turns x 2 pi x 9 mm (mean radius) = 2.7 m of track,
 *            x 0.6 mm x 35 um = 5.7e-8 m^3 = 0.51 g; x 385 J/(kg K) = 0.20 J/K,
 *            plus the thin prepreg the outer layers sit on: C_cu ~ 0.3 J/K.
 *   board:   FR4 under the coil, pi (15 mm)^2 x 1.6 mm = 1.1 cm^3 = 2.1 g, x 1.1 J/(g K)
 *            = 2.3 J/K, and a little of the copper pour round it: C_board ~ 2.5 J/K.
 *   copper -> board: through ~0.3 mm of FR4 (0.3 W/(m K)) over the track's area, plus
 *            lateral spreading inside the coil: a few K/W; 3 K/W gives the copper a
 *            ~1 s time constant over the board (FR4's diffusion time through 0.8 mm
 *            is ~4 s, through the 0.2 mm prepreg ~0.3 s).
 *   board -> ambient: still air, h ~ 10-15 W/(m^2 K) on both faces of the coil's
 *            patch (2 x 7e-4 m^2): 50-70 K/W, in parallel with conduction into the rest
 *            of the board: ~40 K/W.  So 1 W held for minutes would raise the surface
 *            43 K; the limit (45 degC in a 25 degC room) allows ~0.45 W average per coil.
 * The bench calibrates these: the resistance thermometer (thermal_measure_r) watches
 * the real coil, and its corrections show which way the model is off.
 */
#include "thermal.h"
#include "config.h"
#include <math.h>

#define MAX_SUBSTEP_S 0.05f            /* explicit Euler: the fastest mode is ~0.8 s */

void thermal_default_params(thermal_params *p)
{
    p->c_cu_J_per_K = THERMAL_C_CU_J_PER_K;
    p->c_board_J_per_K = THERMAL_C_BOARD_J_PER_K;
    p->r_cu_board_K_per_W = THERMAL_R_CU_BOARD_K_PER_W;
    p->r_board_amb_K_per_W = THERMAL_R_BOARD_AMB_K_PER_W;
    p->r20_ohm = COIL_R20_OHM;
    p->limit_C = COIL_SURFACE_LIMIT_C;
    p->derate_from_C = COIL_DERATE_FROM_C;
}

void thermal_init(thermal_coil *c, const thermal_params *p, float ambient_C)
{
    c->p = *p;
    c->t_cu_C = c->t_board_C = c->t_amb_C = ambient_C;
    c->comp_cu = c->comp_board = 0.0f;
    c->r_ref_ohm = p->r20_ohm;
    c->t_ref_C = 20.0f;
    c->r_calibrated = false;
    c->cold_s = 0.0f;
    c->cal_sum_ohm = 0.0f;
    c->cal_n = 0;
    c->t_meas_C = -273.0f;
    c->p_W = 0.0f;
    c->peak_C = ambient_C;
}

void thermal_assume_cold(thermal_coil *c)
{
    c->t_cu_C = c->t_board_C = c->t_amb_C;
    c->comp_cu = c->comp_board = 0.0f;
    if (c->cold_s < THERMAL_COLD_S)
        c->cold_s = THERMAL_COLD_S;
}

static float r_at(const thermal_coil *c, float t_C)
{
    float r = c->r_ref_ohm * (1.0f + COPPER_TEMPCO * (t_C - c->t_ref_C));
    return r > 0.05f * c->r_ref_ohm ? r : 0.05f * c->r_ref_ohm;
}

/* x += inc, keeping the low-order bits a plain float sum would drop (Kahan).  Do not
 * build this file with -ffast-math, which may reassociate the compensation away. */
static void ksum(float *x, float *comp, float inc)
{
    float y = inc - *comp;
    float t = *x + y;
    *comp = (t - *x) - y;
    *x = t;
}

/* one explicit step of the two nodes; the heating uses the copper's own resistance */
static void step(const thermal_params *p, float *t_cu, float *c_cu, float *t_b, float *c_b, float t_amb, float p_W,
                 float dt)
{
    float q_cb = (*t_cu - *t_b) / p->r_cu_board_K_per_W;
    float q_ba = (*t_b - t_amb) / p->r_board_amb_K_per_W;
    ksum(t_cu, c_cu, (p_W - q_cb) * dt / p->c_cu_J_per_K);
    ksum(t_b, c_b, (q_cb - q_ba) * dt / p->c_board_J_per_K);
}

void thermal_update(thermal_coil *c, float dt_s, float i2_mean_A2, float ambient_C)
{
    if (!(dt_s > 0.0f))
        return;
    if (ambient_C > -40.0f && ambient_C < 125.0f)
        c->t_amb_C = ambient_C;
    if (!(i2_mean_A2 >= 0.0f))
        i2_mean_A2 = 0.0f;
    float left = dt_s;
    while (left > 0.0f) {
        float h = left > MAX_SUBSTEP_S ? MAX_SUBSTEP_S : left;
        c->p_W = i2_mean_A2 * r_at(c, c->t_cu_C);
        step(&c->p, &c->t_cu_C, &c->comp_cu, &c->t_board_C, &c->comp_board, c->t_amb_C, c->p_W, h);
        left -= h;
    }
    if (fabsf(c->t_cu_C - c->t_amb_C) < THERMAL_COLD_BAND_K) {
        c->cold_s += dt_s;
    } else {
        /* no longer cold: finish a calibration that has enough readings */
        if (!c->r_calibrated && c->cal_n >= THERMAL_CAL_READINGS) {
            c->r_ref_ohm = c->cal_sum_ohm / (float)c->cal_n;
            c->t_ref_C = c->t_amb_C;
            c->r_calibrated = true;
        }
        c->cold_s = 0.0f;
        c->cal_n = 0;
        c->cal_sum_ohm = 0.0f;
    }
    if (c->t_cu_C > c->peak_C)
        c->peak_C = c->t_cu_C;
}

void thermal_measure_r(thermal_coil *c, float r_meas_ohm, float dt_s)
{
    /* plausible: from a quarter to three times nominal (-150 .. +530 degC) */
    if (!(r_meas_ohm > 0.25f * c->p.r20_ohm && r_meas_ohm < 3.0f * c->p.r20_ohm) || !(dt_s > 0.0f))
        return;
    if (!c->r_calibrated && c->cold_s >= THERMAL_COLD_S) {
        /* the coil is at ambient: this reading, whatever IPROPI's gain error, is R(ambient).
         * The pulse heats the copper only ~7 K/s at 1 A, so the first ~40 ms of readings
         * of a pulse that starts cold are taken here. */
        c->cal_sum_ohm += r_meas_ohm * (1.0f - COPPER_TEMPCO * (c->t_cu_C - c->t_amb_C));
        c->cal_n++;
        return;
    }
    float t_meas = c->t_ref_C + (r_meas_ohm / c->r_ref_ohm - 1.0f) / COPPER_TEMPCO;
    c->t_meas_C = t_meas;
    float err = t_meas - c->t_cu_C;
    if (!c->r_calibrated && err < 0.0f)
        return;                 /* not calibrated: a reading may only make us more careful */
    float g = dt_s / (THERMAL_CORR_TAU_S + dt_s);
    /* Shift both nodes: the fast copper-to-board part is fixed by geometry and the
     * measured power; what is least certain is the slow part (convection, spreading),
     * which moves the board node and the copper together. */
    ksum(&c->t_cu_C, &c->comp_cu, g * err);
    ksum(&c->t_board_C, &c->comp_board, g * err);
    if (c->t_cu_C > c->peak_C)
        c->peak_C = c->t_cu_C;
}

float thermal_surface_C(const thermal_coil *c) { return c->t_cu_C; }

float thermal_r_ohm(const thermal_coil *c) { return r_at(c, c->t_cu_C); }

float thermal_derate(const thermal_coil *c)
{
    float span = c->p.limit_C - c->p.derate_from_C;
    float f = span > 0.0f ? (c->p.limit_C - c->t_cu_C) / span : (c->t_cu_C < c->p.limit_C ? 1.0f : 0.0f);
    return f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
}

/* the surface temperature after on_s at i_A (the copper is hottest when the current stops) */
static float predict_end_C(const thermal_coil *c, float i_A, float on_s, float limit_C, float *t_reach)
{
    float t_cu = c->t_cu_C, t_b = c->t_board_C, k_cu = c->comp_cu, k_b = c->comp_board;
    const float h = 0.01f;
    float t = 0.0f;
    while (t < on_s) {
        float dt = on_s - t < h ? on_s - t : h;
        step(&c->p, &t_cu, &k_cu, &t_b, &k_b, c->t_amb_C, i_A * i_A * r_at(c, t_cu), dt);
        t += dt;
        if (t_reach && t_cu >= limit_C) {
            *t_reach = t - dt;
            return t_cu;
        }
    }
    return t_cu;
}

float thermal_max_on_s(const thermal_coil *c, float i_A, float limit_C, float horizon_s)
{
    if (c->t_cu_C >= limit_C)
        return 0.0f;
    float reach = horizon_s;
    predict_end_C(c, i_A, horizon_s, limit_C, &reach);
    return reach;
}

float thermal_max_current_A(const thermal_coil *c, float on_s, float limit_C)
{
    if (c->t_cu_C >= limit_C)
        return 0.0f;
    float lo = 0.0f, hi = 5.0f;
    if (predict_end_C(c, hi, on_s, limit_C, 0) < limit_C)
        return hi;
    for (int i = 0; i < 22; i++) {
        float mid = 0.5f * (lo + hi);
        if (predict_end_C(c, mid, on_s, limit_C, 0) < limit_C)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}
