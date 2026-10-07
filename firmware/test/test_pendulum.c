/* test_pendulum.c: the pendulum estimator and drive (src/pendulum.c) against a
 * simulated pendulum.
 *
 * The plant, independent of the module's own shortcuts:
 *   - a spherical pendulum (3-D, a rigid thread of PEND_LENGTH_M) carrying the bat:
 *     3.6 g and one 10 x 2 mm N52 disc, north pole down, air damping for Q = 30;
 *   - each coil's force on the magnet from the canonical coil's 48 turns, segment by
 *     segment (an axisymmetric table of F_rho, F_z per amp over rho and height,
 *     bilinear), at the coils' assumed places (config.h);
 *   - the TMAG5273 at the origin: the magnet's exact dipole field, the coils' own
 *     fields (Biot-Savart), a fixed offset, 0.05 mT of noise per axis;
 *   - 400 Hz sampling with timing jitter, 0.8 ms from a sample to the coils changing,
 *     and each command held for its hold_ms.
 * Checks: the estimate's error on a free swing (and with the magnet upside down);
 * SUSTAIN grows a swing from rest to its target and holds it; CIRCLE holds a circle;
 * CHAOS keeps choosing coils; no bat, no current; no current ever above PEND_I_MAX_A.
 */
#include "pendulum.h"
#include "config.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static int failures;
#define CHECK(cond, ...)                                  \
    do {                                                  \
        if (!(cond)) {                                    \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
            failures++;                                   \
        }                                                 \
    } while (0)

static uint32_t rng = 777u;
static double urand(void)
{
    rng = rng * 1664525u + 1013904223u;
    return ((rng >> 8) + 0.5) / 16777216.0;
}
static double gauss(void) { return sqrt(-2.0 * log(urand())) * cos(6.283185307 * urand()); }

/* ---- the coil, exactly ---------------------------------------------------------- */
#define KMU 1e-7
static const double LZ[4] = {0.0, -0.21e-3, -1.275e-3, -1.485e-3};
#define NSEG 48

/* force per amp on a dipole (0, 0, mu) at (rho, 0, z) over the coil's top copper */
static void coil_force(double rho, double z, double mu, double *frho, double *fz)
{
    double fx = 0, fzz = 0;
    for (int l = 0; l < 4; l++)
        for (int t = 0; t < 12; t++) {
            double a = 15e-3 - t * 1e-3, zz = LZ[l];
            for (int s = 0; s < NSEG; s++) {
                double th0 = 2 * M_PI * s / NSEG, th1 = 2 * M_PI * (s + 1) / NSEG;
                double x0 = a * cos(th0), y0 = a * sin(th0), x1 = a * cos(th1), y1 = a * sin(th1);
                double mx = (x0 + x1) / 2, my = (y0 + y1) / 2, dlx = x1 - x0, dly = y1 - y0;
                double dx = mx - rho, dy = my, dz = zz - z;
                double r2 = dx * dx + dy * dy + dz * dz, r = sqrt(r2), r5 = r2 * r2 * r;
                double md = mu * dz;
                double Bx = KMU * 3 * md * dx / r5, By = KMU * 3 * md * dy / r5;
                double Bz = KMU * (3 * md * dz / r5 - mu / (r2 * r));
                /* force on the segment: I dl x B; on the magnet: minus that */
                fx -= dly * Bz - 0 * By;
                fzz -= dlx * By - dly * Bx;
            }
        }
    *frho = fx;
    *fz = fzz;
}

/* the field (T per A) at point (px, py, pz) from a coil centred at (cx, cy) */
static void coil_field(double cx, double cy, double px, double py, double pz, double B[3])
{
    B[0] = B[1] = B[2] = 0;
    for (int l = 0; l < 4; l++)
        for (int t = 0; t < 12; t++) {
            double a = 15e-3 - t * 1e-3, zz = LZ[l];
            for (int s = 0; s < NSEG; s++) {
                double th0 = 2 * M_PI * s / NSEG, th1 = 2 * M_PI * (s + 1) / NSEG;
                double x0 = cx + a * cos(th0), y0 = cy + a * sin(th0), x1 = cx + a * cos(th1), y1 = cy + a * sin(th1);
                double dl[3] = {x1 - x0, y1 - y0, 0};
                double rr[3] = {px - (x0 + x1) / 2, py - (y0 + y1) / 2, pz - zz};
                double r = sqrt(rr[0] * rr[0] + rr[1] * rr[1] + rr[2] * rr[2]), r3 = r * r * r;
                B[0] += KMU * (dl[1] * rr[2] - dl[2] * rr[1]) / r3;
                B[1] += KMU * (dl[2] * rr[0] - dl[0] * rr[2]) / r3;
                B[2] += KMU * (dl[0] * rr[1] - dl[1] * rr[0]) / r3;
            }
        }
}

#define TR_N 141       /* rho 0..70 mm, 0.5 mm */
#define TZ_N 41        /* height 8..28 mm over the copper, 0.5 mm */
static double TFR[TR_N][TZ_N], TFZ[TR_N][TZ_N];

static void table_init(double mu)
{
    for (int i = 0; i < TR_N; i++)
        for (int j = 0; j < TZ_N; j++)
            coil_force(i * 0.5e-3, 8e-3 + j * 0.5e-3, mu, &TFR[i][j], &TFZ[i][j]);
}

static void table_force(double rho, double z, double *fr, double *fz)
{
    double fi = rho / 0.5e-3, fj = (z - 8e-3) / 0.5e-3;
    if (fi < 0) fi = 0;
    if (fj < 0) fj = 0;
    if (fi > TR_N - 1.001) fi = TR_N - 1.001;
    if (fj > TZ_N - 1.001) fj = TZ_N - 1.001;
    int i = (int)fi, j = (int)fj;
    double a = fi - i, b = fj - j;
    *fr = (1 - a) * (1 - b) * TFR[i][j] + a * (1 - b) * TFR[i + 1][j] + (1 - a) * b * TFR[i][j + 1] + a * b * TFR[i + 1][j + 1];
    *fz = (1 - a) * (1 - b) * TFZ[i][j] + a * (1 - b) * TFZ[i + 1][j] + (1 - a) * b * TFZ[i][j + 1] + a * b * TFZ[i + 1][j + 1];
}

/* ---- the pendulum ------------------------------------------------------------------- */
typedef struct {
    double r[3], v[3];
    double pivot[3];
    double L, m, c, mu;
    double coil_x[3], coil_y[3];
    double cop_below_sensor;        /* the coils' top copper below the sensor's point */
    double Bc[3][3];                /* coil c's field at the sensor, T/A */
    double I[3];
} plant;

static void plant_init(plant *p, double mu, double Q)
{
    memset(p, 0, sizeof *p);
    p->L = PEND_LENGTH_M;
    p->m = PEND_MASS_KG;
    p->mu = mu;
    p->pivot[2] = PEND_SENSOR_DEPTH_M + p->L;
    double w0 = sqrt(9.81 / p->L);
    p->c = p->m * w0 / Q;
    p->cop_below_sensor = PEND_SENSOR_ABOVE_COPPER_M;
    for (int c = 0; c < 3; c++) {
        double a = (PEND_COIL_ANGLE0_DEG + 120.0 * c) * M_PI / 180;
        p->coil_x[c] = PEND_COIL_RADIUS_M * cos(a);
        p->coil_y[c] = PEND_COIL_RADIUS_M * sin(a);
        coil_field(p->coil_x[c], p->coil_y[c], 0, 0, p->cop_below_sensor, p->Bc[c]);
    }
    p->r[2] = PEND_SENSOR_DEPTH_M;
}

/* put the bob at horizontal (x, y) on its sphere, with horizontal velocity (vx, vy) */
static void plant_place(plant *p, double x, double y, double vx, double vy)
{
    double h = sqrt(p->L * p->L - x * x - y * y);
    p->r[0] = x;
    p->r[1] = y;
    p->r[2] = p->pivot[2] - h;
    double vz = (x * vx + y * vy) / h;  /* tangent to the sphere */
    p->v[0] = vx;
    p->v[1] = vy;
    p->v[2] = vz;
}

static void mag_force(const plant *p, const double r[3], double F[3])
{
    F[0] = F[1] = F[2] = 0;
    for (int c = 0; c < 3; c++) {
        if (p->I[c] == 0)
            continue;
        double sx = r[0] - p->coil_x[c], sy = r[1] - p->coil_y[c];
        double rho = sqrt(sx * sx + sy * sy);
        double z = r[2] + p->cop_below_sensor;
        double fr, fz;
        table_force(rho, z, &fr, &fz);
        if (rho > 1e-9) {
            F[0] += p->I[c] * fr * sx / rho;
            F[1] += p->I[c] * fr * sy / rho;
        }
        F[2] += p->I[c] * fz;
    }
}

static void accel(const plant *p, const double r[3], const double v[3], const double Fm[3], double a[3])
{
    double e[3], F[3];
    for (int k = 0; k < 3; k++)
        e[k] = (r[k] - p->pivot[k]) / p->L;
    F[0] = Fm[0] - p->c * v[0];
    F[1] = Fm[1] - p->c * v[1];
    F[2] = Fm[2] - p->c * v[2] - p->m * 9.81;
    double vv = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    double T = F[0] * e[0] + F[1] * e[1] + F[2] * e[2] + p->m * vv / p->L;
    for (int k = 0; k < 3; k++)
        a[k] = (F[k] - T * e[k]) / p->m;
}

static void plant_step(plant *p, double dt)
{
    double Fm[3];
    mag_force(p, p->r, Fm);
    double r0[3], v0[3], k1r[3], k1v[3], k2r[3], k2v[3], k3r[3], k3v[3], k4r[3], k4v[3], rt[3], vt[3];
    memcpy(r0, p->r, sizeof r0);
    memcpy(v0, p->v, sizeof v0);
    accel(p, r0, v0, Fm, k1v);
    memcpy(k1r, v0, sizeof k1r);
    for (int k = 0; k < 3; k++) { rt[k] = r0[k] + 0.5 * dt * k1r[k]; vt[k] = v0[k] + 0.5 * dt * k1v[k]; }
    accel(p, rt, vt, Fm, k2v);
    memcpy(k2r, vt, sizeof k2r);
    for (int k = 0; k < 3; k++) { rt[k] = r0[k] + 0.5 * dt * k2r[k]; vt[k] = v0[k] + 0.5 * dt * k2v[k]; }
    accel(p, rt, vt, Fm, k3v);
    memcpy(k3r, vt, sizeof k3r);
    for (int k = 0; k < 3; k++) { rt[k] = r0[k] + dt * k3r[k]; vt[k] = v0[k] + dt * k3v[k]; }
    accel(p, rt, vt, Fm, k4v);
    memcpy(k4r, vt, sizeof k4r);
    for (int k = 0; k < 3; k++) {
        p->r[k] = r0[k] + dt / 6 * (k1r[k] + 2 * k2r[k] + 2 * k3r[k] + k4r[k]);
        p->v[k] = v0[k] + dt / 6 * (k1v[k] + 2 * k2v[k] + 2 * k3v[k] + k4v[k]);
    }
    /* back onto the sphere */
    double d[3], n = 0;
    for (int k = 0; k < 3; k++) { d[k] = p->r[k] - p->pivot[k]; n += d[k] * d[k]; }
    n = sqrt(n);
    double e[3], ve = 0;
    for (int k = 0; k < 3; k++) { e[k] = d[k] / n; p->r[k] = p->pivot[k] + p->L * e[k]; ve += p->v[k] * e[k]; }
    for (int k = 0; k < 3; k++)
        p->v[k] -= ve * e[k];
}

static double OFFSET_MT[3] = {0.03, -0.02, 0.04};
static const double NOISE_MT[3] = {0.052, 0.052, 0.031};   /* TMAG5273A2 at 8x averaging */

static void sensor(const plant *p, double B_mT[3])
{
    /* the magnet's dipole field at the origin */
    double d[3] = {-p->r[0], -p->r[1], -p->r[2]};
    double r2 = d[0] * d[0] + d[1] * d[1] + d[2] * d[2], r = sqrt(r2), r5 = r2 * r2 * r;
    double md = p->mu * d[2];
    double B[3] = {KMU * 3 * md * d[0] / r5, KMU * 3 * md * d[1] / r5, KMU * (3 * md * d[2] / r5 - p->mu / (r2 * r))};
    for (int c = 0; c < 3; c++)
        for (int k = 0; k < 3; k++)
            B[k] += p->I[c] * p->Bc[c][k];
    for (int k = 0; k < 3; k++)
        B_mT[k] = B[k] * 1e3 + OFFSET_MT[k] + NOISE_MT[k] * gauss();
}

/* ---- the loop: plant, sampling, latency, holds ----------------------------------------- */
typedef struct {
    double t, t_next_sample, t_apply, t_expire;
    pend_cmd pending;
    bool have_pending;
    float applied[3];
    double i_max_seen;
    int chose_n, chose_bad, chose_hist[3];
    double est_se, est_n, vel_se;
    double i2_sum[3], i2_t;
} sim;

static void run(plant *p, pendulum *pd, sim *s, double until, bool use_offset_cal, void (*observe)(plant *, pendulum *, sim *))
{
    const double dt = 0.5e-3;
    while (s->t < until) {
        if (s->t >= s->t_next_sample) {
            double B[3];
            sensor(p, B);
            uint32_t t_us = (uint32_t)((s->t + 0.1e-3 * urand()) * 1e6);
            pend_cmd cmd;
            for (int c = 0; c < 3; c++)
                s->applied[c] = (float)p->I[c];
            pend_sample(pd, t_us, (float)B[0], (float)B[1], (float)B[2], s->applied, &cmd);
            if (cmd.event == PEND_EV_CHOSE) {
                s->chose_n++;
                if (cmd.event_arg < 0 || cmd.event_arg > 2)
                    s->chose_bad++;
                else
                    s->chose_hist[cmd.event_arg]++;
            }
            s->pending = cmd;
            s->have_pending = true;
            s->t_apply = s->t + 0.8e-3;
            s->t_next_sample = s->t + 2.5e-3 + (urand() - 0.5) * 0.6e-3;
            if (observe)
                observe(p, pd, s);
        }
        if (s->have_pending && s->t >= s->t_apply) {
            for (int c = 0; c < 3; c++) {
                p->I[c] = s->pending.i_A[c];
                if (fabs(p->I[c]) > s->i_max_seen)
                    s->i_max_seen = fabs(p->I[c]);
            }
            s->t_expire = s->t + s->pending.hold_ms * 1e-3;
            s->have_pending = false;
        }
        if (s->t >= s->t_expire)
            for (int c = 0; c < 3; c++)
                p->I[c] = 0;
        for (int c = 0; c < 3; c++)
            s->i2_sum[c] += p->I[c] * p->I[c] * dt;
        s->i2_t += dt;
        plant_step(p, dt);
        s->t += dt;
    }
    (void)use_offset_cal;
}

static double est_from = 2.0;
static void observe_estimate(plant *p, pendulum *pd, sim *s)
{
    if (s->t < est_from)
        return;
    pend_status st;
    pend_status_get(pd, &st);
    double ex = st.x_m - p->r[0], ey = st.y_m - p->r[1];
    double evx = st.vx_m_s - p->v[0], evy = st.vy_m_s - p->v[1];
    s->est_se += ex * ex + ey * ey;
    s->vel_se += evx * evx + evy * evy;
    s->est_n += 1;
}

static pendulum PD;

static void setup(plant *p, sim *s, double mu)
{
    plant_init(p, mu, 30.0);
    memset(s, 0, sizeof *s);
    pend_params prm;
    pend_default_params(&prm);
    pend_init(&PD, &prm);
    pend_set_offset(&PD, (float)OFFSET_MT[0], (float)OFFSET_MT[1], (float)OFFSET_MT[2]);
}

static void test_estimator(double mu, const char *what, bool calibrated)
{
    plant p;
    sim s;
    setup(&p, &s, mu);
    if (!calibrated)
        pend_set_offset(&PD, 0, 0, 0);       /* the sensor's own offset left in */
    plant_place(&p, 0.020, 0.005, 0.0, 0.06);
    pend_set_mode(&PD, PEND_OFF);
    run(&p, &PD, &s, 12.0, true, observe_estimate);
    double e = sqrt(s.est_se / s.est_n) * 1e3, ev = sqrt(s.vel_se / s.est_n) * 1e3;
    pend_status st;
    pend_status_get(&PD, &st);
    double f0 = sqrt(9.81 / PEND_LENGTH_M) / (2 * M_PI);
    printf("estimator, free swing (%s): position error %.2f mm rms, velocity %.1f mm/s rms, "
           "frequency %.3f Hz (small-swing %.3f Hz)\n", what, e, ev, st.f_hz, f0);
    CHECK(e < (calibrated ? 1.0 : 2.0), "position error %.2f mm rms", e);
    CHECK(ev < 20.0, "velocity error %.1f mm/s rms", ev);
    CHECK(fabs(st.f_hz - f0) < 0.03 * f0, "frequency %.3f Hz", st.f_hz);
    CHECK(s.i_max_seen == 0.0, "OFF drove a coil (%.3f A)", s.i_max_seen);
}

/* along-axis and cross-axis amplitude of the true swing over a window */
static double win_from, win_to, max_along, max_cross, ang_prev, ang_total, r_sum, r_sq, r_n;
static bool have_ang;
static void observe_window(plant *p, pendulum *pd, sim *s)
{
    if (s->t < win_from || s->t > win_to)
        return;
    double th = PEND_COIL_ANGLE0_DEG * M_PI / 180;
    double a = p->r[0] * cos(th) + p->r[1] * sin(th), n = -p->r[0] * sin(th) + p->r[1] * cos(th);
    if (fabs(a) > max_along) max_along = fabs(a);
    if (fabs(n) > max_cross) max_cross = fabs(n);
    double ang = atan2(p->r[1], p->r[0]);
    if (have_ang) {
        double d = ang - ang_prev;
        while (d > M_PI) d -= 2 * M_PI;
        while (d < -M_PI) d += 2 * M_PI;
        ang_total += d;
    }
    ang_prev = ang;
    have_ang = true;
    double r = hypot(p->r[0], p->r[1]);
    r_sum += r;
    r_sq += r * r;
    r_n += 1;
}

static void reset_window(double from, double to)
{
    win_from = from;
    win_to = to;
    max_along = max_cross = ang_total = r_sum = r_sq = r_n = 0;
    have_ang = false;
}

static void test_sustain(void)
{
    plant p;
    sim s;
    setup(&p, &s, -PEND_MOMENT_AM2);
    plant_place(&p, 0.0003, 0.0005, 0, 0);
    pend_set_mode(&PD, PEND_SUSTAIN);
    reset_window(20.0, 25.0);
    run(&p, &PD, &s, 25.0, true, observe_window);
    double grown = max_along;
    reset_window(40.0, 70.0);
    run(&p, &PD, &s, 70.0, true, observe_window);
    double rms_I = sqrt((s.i2_sum[0] + s.i2_sum[1] + s.i2_sum[2]) / 3 / s.i2_t);
    printf("SUSTAIN from rest: swing %.1f mm at 20-25 s; %.1f mm along, %.1f mm across at 40-70 s "
           "(target %.0f mm); peak %.3f A, rms %.3f A per coil\n", grown * 1e3, max_along * 1e3, max_cross * 1e3,
           PEND_SUSTAIN_AMP_M * 1e3, s.i_max_seen, rms_I);
    CHECK(max_along > 0.8 * PEND_SUSTAIN_AMP_M && max_along < 1.25 * PEND_SUSTAIN_AMP_M, "held %.1f mm",
          max_along * 1e3);
    CHECK(max_cross < 5e-3, "cross swing %.1f mm", max_cross * 1e3);
    CHECK(s.i_max_seen <= PEND_I_MAX_A + 1e-6, "current %.3f A over the limit", s.i_max_seen);
}

static void test_circle(void)
{
    plant p;
    sim s;
    setup(&p, &s, -PEND_MOMENT_AM2);
    plant_place(&p, 0.0003, -0.0002, 0, 0);
    pend_set_mode(&PD, PEND_CIRCLE);
    reset_window(45.0, 65.0);
    run(&p, &PD, &s, 65.0, true, observe_window);
    double mean = r_sum / r_n, sd = sqrt(r_sq / r_n - mean * mean);
    double revs = ang_total / (2 * M_PI);
    double rms_I = sqrt((s.i2_sum[0] + s.i2_sum[1] + s.i2_sum[2]) / 3 / s.i2_t);
    printf("CIRCLE from rest: radius %.1f +- %.1f mm (target %.0f mm), %.1f turns in 20 s; peak %.3f A, rms %.3f A per coil\n",
           mean * 1e3, sd * 1e3, PEND_COIL_RADIUS_M * 1e3, revs, s.i_max_seen, rms_I);
    CHECK(mean > 0.7 * PEND_COIL_RADIUS_M && mean < 1.3 * PEND_COIL_RADIUS_M, "radius %.1f mm", mean * 1e3);
    CHECK(sd < 0.25 * mean, "not round: radius varies %.1f mm", sd * 1e3);
    CHECK(revs > 18.0, "only %.1f turns (counter-clockwise) in 20 s", revs);
    CHECK(s.i_max_seen <= PEND_I_MAX_A + 1e-6, "current %.3f A over the limit", s.i_max_seen);
}

static void test_chaos(void)
{
    plant p;
    sim s;
    setup(&p, &s, -PEND_MOMENT_AM2);
    plant_place(&p, 0.0004, 0.0001, 0, 0);
    pend_set_mode(&PD, PEND_CHAOS);
    run(&p, &PD, &s, 240.0, true, 0);
    printf("CHAOS for 4 minutes: %d choices (coil 1: %d, coil 2: %d, coil 3: %d); peak %.3f A\n", s.chose_n,
           s.chose_hist[0], s.chose_hist[1], s.chose_hist[2], s.i_max_seen);
    CHECK(s.chose_n >= 4, "only %d choices in 4 minutes", s.chose_n);
    CHECK(s.chose_bad == 0, "%d choices of no coil", s.chose_bad);
    CHECK(s.i_max_seen <= PEND_I_MAX_A + 1e-6, "current %.3f A over the limit", s.i_max_seen);
}

static void test_absent(void)
{
    pend_params prm;
    pend_default_params(&prm);
    pend_init(&PD, &prm);
    pend_set_mode(&PD, PEND_SUSTAIN);
    float zero[3] = {0, 0, 0};
    double worst = 0;
    for (int k = 0; k < 4000; k++) {
        pend_cmd cmd;
        pend_sample(&PD, (uint32_t)(k * 2500), (float)(0.05 * gauss()), (float)(0.05 * gauss()),
                    (float)(0.05 * gauss()), zero, &cmd);
        for (int c = 0; c < 3; c++)
            if (fabs(cmd.i_A[c]) > worst)
                worst = fabs(cmd.i_A[c]);
    }
    printf("no bat: largest current asked %.3f A\n", worst);
    CHECK(worst == 0.0, "drove %.3f A with no bat", worst);
}

int main(void)
{
    double t0 = PEND_SENSOR_DEPTH_M + PEND_SENSOR_ABOVE_COPPER_M;
    table_init(-PEND_MOMENT_AM2);
    double fr, fz;
    table_force(10e-3, 10e-3, &fr, &fz);
    printf("coil force at 10 mm over the copper, 10 mm off axis: %.2f mN/A sideways (README: ~11)\n", fr * 1e3);
    pend_params prm;
    pend_default_params(&prm);
    pend_init(&PD, &prm);
    printf("module's table at the rest height %.1f mm: peak %.2f mN/A, %.2f mN/A at the rest point (25 mm)\n",
           t0 * 1e3, PD.k_peak * 1e3, pend_kernel_N_per_A(&PD, PEND_COIL_RADIUS_M, (float)t0) * 1e3);
    CHECK(fabs(fr * 1e3 - 11.4) < 1.0, "coil force model off: %.2f mN/A", fr * 1e3);

    test_estimator(-PEND_MOMENT_AM2, "north pole down", true);
    test_estimator(+PEND_MOMENT_AM2, "magnet upside down", true);
    double keep[3] = {OFFSET_MT[0], OFFSET_MT[1], OFFSET_MT[2]};
    OFFSET_MT[0] = 0.3;
    OFFSET_MT[1] = -0.3;
    OFFSET_MT[2] = 0.3;
    test_estimator(-PEND_MOMENT_AM2, "0.3 mT offsets not calibrated out", false);
    for (int k = 0; k < 3; k++)
        OFFSET_MT[k] = keep[k];
    test_sustain();
    test_circle();
    test_chaos();
    test_absent();
    if (failures) {
        printf("test_pendulum: %d FAILED\n", failures);
        return 1;
    }
    printf("test_pendulum: all passed\n");
    return 0;
}
