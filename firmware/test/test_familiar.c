/* test_familiar.c: the familiar perches (src/familiar.c) against a simulated perch.
 *
 * The perch, from sim/physics/familiar.py's numbers: the perch coil (28.5 uH, R1 4.2 ohm
 * at these frequencies), the token's coil (11.5 uH, R2 2.3 ohm) with its C0G tank
 * capacitor, coupled with M = 8.5 uH at the 3 mm gap (k = 0.47), and the token's two
 * LEDs (orange 1.85 V and violet 2.85 V, each through 68 ohm plus its own ~10 ohm) as a
 * describing function: the tank voltage is solved self-consistently, so the token's Q
 * falls as it lights, as the real one's will.  The bridge: 5 V, a 3-level wave whose
 * fundamental is (4/pi) 5 V sin(pi duty), frequency and duty quantised by phase-correct
 * PWM from 150 MHz.  ISENSE: the fundamental's amplitude through a 1 ms filter, with
 * 0.5 mA of noise.
 * Checks: an empty perch stays empty; the owl and the cat are found and named within
 * 5 % of their tuning (also at a wider gap, and with ISENSE's gain 10 % off); an
 * untuned token is "unknown"; the token lights; the perch current never passes
 * FAM_I_MAX_A while a token is on it; a token lifted off is noticed within a second.
 */
#include "familiar.h"
#include "config.h"
#include <complex.h>
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

static uint32_t rng = 99u;
static double urand(void)
{
    rng = rng * 1664525u + 1013904223u;
    return ((rng >> 8) + 0.5) / 16777216.0;
}
static double gauss(void) { return sqrt(-2.0 * log(urand())) * cos(6.283185307 * urand()); }

/* ---- the token's LEDs as a describing function ----------------------------------------- */
#define DF_N 4000
#define DF_DV 0.0075            /* 0 .. 30 V of tank amplitude */
static double DF_G[DF_N];       /* fundamental current / amplitude, S */
static double DF_IO[DF_N], DF_IV[DF_N];   /* mean LED currents, A */

static void df_init(void)
{
    const int K = 720;
    for (int n = 0; n < DF_N; n++) {
        double V = n * DF_DV, fund = 0, io = 0, iv = 0;
        for (int k = 0; k < K; k++) {
            double th = 2 * M_PI * (k + 0.5) / K, v = V * sin(th);
            double i = 0;
            if (v > 1.85) { i = (v - 1.85) / 77.0; io += i; }
            if (-v > 2.85) { double j = (-v - 2.85) / 82.0; i = -j; iv += j; }
            fund += i * sin(th);
        }
        fund *= 2.0 / K;
        DF_G[n] = V > 0 ? fund / V : 0;
        DF_IO[n] = io / K;
        DF_IV[n] = iv / K;
    }
}

static double df(const double *t, double V)
{
    double u = V / DF_DV;
    if (u >= DF_N - 1) return t[DF_N - 1];
    int i = (int)u;
    double a = u - i;
    return (1 - a) * t[i] + a * t[i + 1];
}

/* ---- the perch -------------------------------------------------------------------------- */
typedef struct {
    double L1, L2, M, ft;       /* ft = 0: no token */
    double vt;                  /* the token's tank amplitude, warm start */
    double led_o, led_v;        /* its mean LED currents now */
    double i1;                  /* perch current amplitude now */
} perch;

static double R1(double f) { return 4.15 + 0.12 * (f - 100e3) / 300e3; }
static double R2(double f) { return 2.32 + 0.07 * (f - 100e3) / 300e3; }

static double perch_current(perch *p, double f, double V1)
{
    double w = 2 * M_PI * f;
    double complex Z1 = R1(f) + I * w * p->L1;
    if (p->ft <= 0) {
        p->led_o = p->led_v = 0;
        p->vt = 0;
        return cabs(V1 / Z1);
    }
    double C2 = 1.0 / (pow(2 * M_PI * p->ft, 2) * p->L2);
    double vt = p->vt;
    double complex I1 = 0;
    for (int it = 0; it < 60; it++) {
        double complex Zl = 1.0 / (I * w * C2 + df(DF_G, vt));
        double complex Z2 = R2(f) + I * w * p->L2 + Zl;
        double complex Z = Z1 + (w * p->M) * (w * p->M) / Z2;
        I1 = V1 / Z;
        double complex I2 = -I * w * p->M * I1 / Z2;
        double vn = cabs(I2 * Zl);
        if (fabs(vn - vt) < 1e-5)
            break;
        vt = 0.6 * vt + 0.4 * vn;
    }
    p->vt = vt;
    p->led_o = df(DF_IO, vt);
    p->led_v = df(DF_IV, vt);
    return cabs(I1);
}

/* ---- the run ---------------------------------------------------------------------------- */
typedef struct {
    int arrived, left;
    fam_who who;
    double f_found, t_arrived, t_left;
    double i_max_with_token, i_max_any, over_ms;
    double led_o_max, led_v_max, i_end, duty_end;
    double sweep_duty_max_empty;
    double led_mod;             /* the LED current's ripple in DRIVE, peak-to-peak / mean */
} result;

/* token present from t_on to t_off; isense gain error g */
static result run(double ft, double M, double t_end, double t_off, double gain, bool print)
{
    result r;
    memset(&r, 0, sizeof r);
    perch pc = {28.50e-6, 11.51e-6, M, ft, 0, 0, 0, 0};
    fam_perch fp;
    fam_init(&fp, 0);
    fam_enable(&fp, true);
    fam_cmd cmd = {false, 150e3, 0}, app = cmd;
    double isense_f = 0, t = 0;
    const double dt = 0.25e-3;
    double next_step = 0, over_since = -1;
    double lo_min = 1e9, lo_max = 0;
    while (t < t_end) {
        if (t >= t_off && pc.ft > 0)
            pc.ft = 0;                  /* lifted off */
        /* the PWM: phase-correct from 150 MHz */
        double fq = 150e3, V1 = 0;
        if (app.enable) {
            double P = round(150e6 / (2 * cmd.freq_hz));
            fq = 150e6 / (2 * P);
            double dq = round(cmd.duty * P) / P;
            app.freq_hz = (float)fq;
            app.duty = (float)dq;
            V1 = 4 / M_PI * FAM_VDRIVE_V * sin(M_PI * dq);
        }
        double i1 = app.enable ? perch_current(&pc, fq, V1) : 0;
        if (!app.enable) { pc.led_o = pc.led_v = 0; }
        isense_f += (i1 - isense_f) * (1 - exp(-dt / 1e-3));
        if (pc.ft > 0 && i1 > r.i_max_with_token) r.i_max_with_token = i1;
        if (i1 > r.i_max_any) r.i_max_any = i1;
        if (i1 > FAM_I_MAX_A) {
            if (over_since < 0) over_since = t;
            double ms = (t - over_since) * 1e3;
            if (ms > r.over_ms) r.over_ms = ms;
        } else {
            over_since = -1;
        }
        if (pc.led_o > r.led_o_max) r.led_o_max = pc.led_o;
        if (pc.led_v > r.led_v_max) r.led_v_max = pc.led_v;
        if (fp.state == FAM_ST_DRIVE && t < t_off && pc.ft > 0) {
            if (pc.led_o < lo_min) lo_min = pc.led_o;
            if (pc.led_o > lo_max) lo_max = pc.led_o;
        }
        if (ft <= 0 && app.enable && app.duty > r.sweep_duty_max_empty)
            r.sweep_duty_max_empty = app.duty;
        if (t >= next_step) {
            fam_event ev;
            float meas = (float)(gain * isense_f + 0.5e-3 * gauss());
            fam_step(&fp, (float)t, meas, &app, &cmd, &ev);
            app.enable = cmd.enable;
            if (!cmd.enable) app.duty = 0;
            if (ev.kind == FAM_EV_ARRIVED && !r.arrived) {
                r.arrived = 1;
                r.who = ev.who;
                r.f_found = ev.freq_hz;
                r.t_arrived = t;
            }
            if (ev.kind == FAM_EV_LEFT && !r.left) {
                r.left = 1;
                r.t_left = t;
            }
            next_step += 1e-3;
            if (t < t_off && t > t_off - 0.01) {
                r.i_end = i1;
                r.duty_end = app.duty;
            }
        }
        t += dt;
    }
    if (lo_max > 0)
        r.led_mod = (lo_max - lo_min) / (0.5 * (lo_max + lo_min));
    if (print)
        printf("  found %s at %.1f kHz after %.2f s; perch %.0f mA at duty %.2f; LEDs up to %.1f / %.1f mA "
               "(orange/violet), ripple %.0f %%; perch max %.0f mA with the token, %.0f mA ever (%.1f ms over %.0f mA); "
               "%s",
               r.arrived ? fam_who_name(r.who) : "nothing", r.f_found / 1e3, r.t_arrived, r.i_end * 1e3, r.duty_end,
               r.led_o_max * 1e3, r.led_v_max * 1e3, r.led_mod * 100, r.i_max_with_token * 1e3, r.i_max_any * 1e3,
               r.over_ms, FAM_I_MAX_A * 1e3,
               ft <= 0 ? "" : (r.left ? "lifted off: noticed in" : "lifted off: NOT noticed"));
    if (print)
        r.left ? printf(" %.2f s\n", r.t_left - t_off) : printf("\n");
    return r;
}

static void expect_token(const char *what, double ft, double M, double gain, fam_who want, double t_off)
{
    printf("%s:\n", what);
    result r = run(ft, M, t_off + 2.0, t_off, gain, true);
    CHECK(r.arrived, "%s: nothing found", what);
    CHECK(r.who == want, "%s: named %s", what, fam_who_name(r.who));
    if (want != FAM_UNKNOWN)
        CHECK(fabs(r.f_found / ft - 1) < 0.05, "%s: resonance %.1f kHz, tuned %.1f kHz", what, r.f_found / 1e3,
              ft / 1e3);
    CHECK(r.i_max_with_token <= FAM_I_MAX_A * 1.0001, "%s: %.1f mA with the token on", what,
          r.i_max_with_token * 1e3);
    CHECK(r.led_o_max > 3e-3, "%s: the token never lit (%.1f mA)", what, r.led_o_max * 1e3);
    CHECK(r.left && r.t_left - t_off < 1.0, "%s: lifting it off went unnoticed (%.2f s)", what,
          r.left ? r.t_left - t_off : -1.0);
    CHECK(r.over_ms <= 10.0 && r.i_max_any <= 1.2 * FAM_I_MAX_A, "%s: after lifting, %.0f mA for %.1f ms", what,
          r.i_max_any * 1e3, r.over_ms);
    CHECK(r.led_mod < 0.10, "%s: the LEDs flicker %.0f %% at the dither", what, r.led_mod * 100);
}

int main(void)
{
    df_init();
    const double M0 = 8.53e-6;
    printf("empty perch, 12 s:\n");
    result e = run(0, M0, 12.0, 1e9, 1.0, true);
    CHECK(!e.arrived, "an empty perch reported a %s", fam_who_name(e.who));
    CHECK(e.sweep_duty_max_empty < 0.04, "an empty perch was driven at duty %.3f", e.sweep_duty_max_empty);

    expect_token("owl (150 kHz), 3 mm", 150e3, M0, 1.0, FAM_OWL, 9.0);
    expect_token("cat (330 kHz), 3 mm", 330e3, M0, 1.0, FAM_CAT, 9.0);
    expect_token("owl at 5 mm (k 0.38)", 150e3, M0 * 0.38 / 0.471, 1.0, FAM_OWL, 9.0);
    expect_token("cat at 5 mm (k 0.38)", 330e3, M0 * 0.38 / 0.471, 1.0, FAM_CAT, 9.0);
    expect_token("owl, ISENSE gain 10 % high", 150e3, M0, 1.10, FAM_OWL, 9.0);
    expect_token("a token tuned to 240 kHz", 240e3, M0, 1.0, FAM_UNKNOWN, 9.0);

    /* the cat's tank while the perch sweeps: must stay dark */
    perch pc = {28.50e-6, 11.51e-6, M0, 330e3, 0, 0, 0, 0};
    double worst = 0;
    for (double f = FAM_F_MIN_HZ; f <= FAM_F_MAX_HZ; f *= 1.002) {
        perch_current(&pc, f, 4 / M_PI * FAM_VDRIVE_V * sin(M_PI * 0.035));
        if (pc.vt > worst) worst = pc.vt;
    }
    printf("sweeping at duty 0.035 the cat's tank reaches %.2f V (its orange LED needs 1.85 V)\n", worst);
    CHECK(worst < 1.85, "the sweep lights the cat (%.2f V)", worst);

    if (failures) {
        printf("test_familiar: %d FAILED\n", failures);
        return 1;
    }
    printf("test_familiar: all passed\n");
    return 0;
}
