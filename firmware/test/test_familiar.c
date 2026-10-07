/* test_familiar.c: the familiar perches (src/familiar.c) against a simulated perch.
 *
 * The perch, from sim/physics/familiar.py's numbers: the perch coil (28.5 uH, R1 4.2 ohm
 * at these frequencies), the token's coil (11.5 uH, R2 2.3 ohm) with its C0G tank
 * capacitor, coupled with M = 8.5 uH at the 3 mm gap (k = 0.47), and the token's two
 * LEDs (orange 1.85 V and violet 2.85 V, each through 68 ohm plus its own ~10 ohm) as a
 * describing function at the fundamental: the tank voltage is solved self-consistently,
 * so the token's Q falls as it lights, as the real one's will.  The bridge: 5 V, a
 * 3-level wave, harmonics n = 1, 3, 5, 7 of amplitude (4 / (n pi)) 5 V sin(n pi duty),
 * frequency and duty quantised by phase-correct PWM from 150 MHz.  The last cases put the
 * readings through the board's ADC (whole counts, noise, 8x averaging) at 2 and 10 V/A
 * (asserted) and at config.h's FAM_ISENSE_V_PER_A (reported: a warning if too coarse).
 *
 * What the firmware sees (FAMn_ISENSE): the bridge's 5 V supply current, the coil's
 * power (all four harmonics) / 5 V, plus the drivers' own draw (2.5 mA static and up
 * to 3 mA more with the switching frequency), through a 1 ms filter, with a gain error
 * and 0.1 mA of noise per 1 ms reading.
 *
 * Checks: an empty perch stays empty, and so does one with a coin on it (no
 * resonance); the owl and the cat are found and named within 5 % of their tuning (also
 * at a wider gap, with ISENSE's gain 10 % off and the drivers drawing twice as much,
 * with the perch coil's resistance 15 % off what the firmware assumes, and with three
 * times the ISENSE noise); a token tuned to 240 kHz is "unknown"; the token lights; the
 * perch current
 * (here known exactly) never passes FAM_I_MAX_A, not even when a lit token is lifted
 * off; that is noticed within a second; the sweep keeps every token dark (its tank,
 * harmonics included, under the orange LED's 1.85 V); the dither does not flicker.
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
    double coin_M, coin_L, coin_R;   /* a non-resonant metal object, or 0 */
    double iq0, iq_sw;          /* the drivers' draw: static, and at 400 kHz switching */
    double vt;                  /* the token's tank amplitude at the fundamental, warm start */
    double vt_all;              /* its peak tank voltage, harmonics included */
    double led_o, led_v;        /* its mean LED currents now */
    double i1;                  /* perch current, fundamental amplitude */
} perch;

static double r1_scale = 1.0;      /* the real perch coil against familiar.py's */
static double noise_A = 0.1e-3;     /* ISENSE noise per 1 ms reading */
/* > 0: the board's measuring chain instead: ISENSE volts = this x the supply current, read
 * by the 12-bit ADC (3.3 V / 4096 a count, about 1.5 counts of noise), eight samples
 * averaged a reading (one of core 1's bursts) */
static double adc_v_per_a = 0.0;
static double adc_reading(double amps)
{
    const double lsb = 3.3 / 4096.0;
    double v = amps * adc_v_per_a, sum = 0.0;
    for (int k = 0; k < 8; k++) {
        double c = floor(v / lsb + 1.5 * gauss() + 0.5);
        sum += c < 0.0 ? 0.0 : c;
    }
    return sum / 8.0 * lsb / adc_v_per_a;
}
static double R1(double f) { return r1_scale * (4.15 + 0.12 * (f - 100e3) / 300e3); }
static double R2(double f) { return 2.32 + 0.07 * (f - 100e3) / 300e3; }
static double vn(int n, double duty) { return 4.0 / (n * M_PI) * FAM_VDRIVE_V * sin(n * M_PI * duty); }

static double complex z_coin(const perch *p, double w)
{
    if (p->coin_M <= 0) return 0;
    return (w * p->coin_M) * (w * p->coin_M) / (p->coin_R + I * w * p->coin_L);
}

/* the perch's impedance at f, with the token's LEDs dark (harmonics), and its tank voltage per volt */
static double complex z_linear(const perch *p, double f, double *vt_per_v)
{
    double w = 2 * M_PI * f;
    double complex Z1 = R1(f) + I * w * p->L1 + z_coin(p, w);
    *vt_per_v = 0;
    if (p->ft <= 0)
        return Z1;
    double C2 = 1.0 / (pow(2 * M_PI * p->ft, 2) * p->L2);
    double complex Zl = 1.0 / (I * w * C2);
    double complex Z2 = R2(f) + I * w * p->L2 + Zl;
    double complex Z = Z1 + (w * p->M) * (w * p->M) / Z2;
    *vt_per_v = cabs(-I * w * p->M / Z / Z2 * Zl);
    return Z;
}

/* the supply current at f and duty; fills the perch current, tank voltage and LED currents */
static double supply_current(perch *p, double f, double duty)
{
    double w = 2 * M_PI * f, V1 = vn(1, duty), P = 0;
    double complex Z1 = R1(f) + I * w * p->L1 + z_coin(p, w), Z = Z1;
    if (p->ft > 0) {
        double C2 = 1.0 / (pow(2 * M_PI * p->ft, 2) * p->L2);
        double vt = p->vt;
        for (int it = 0; it < 60; it++) {
            double complex Zl = 1.0 / (I * w * C2 + df(DF_G, vt));
            double complex Z2 = R2(f) + I * w * p->L2 + Zl;
            Z = Z1 + (w * p->M) * (w * p->M) / Z2;
            double complex I2 = -I * w * p->M * (V1 / Z) / Z2;
            double vnew = cabs(I2 * Zl);
            if (fabs(vnew - vt) < 1e-5)
                break;
            vt = 0.6 * vt + 0.4 * vnew;
        }
        p->vt = vt;
        p->led_o = df(DF_IO, vt);
        p->led_v = df(DF_IV, vt);
    } else {
        p->vt = p->led_o = p->led_v = 0;
    }
    p->i1 = V1 / cabs(Z);
    P += 0.5 * V1 * V1 * creal(1.0 / Z);
    p->vt_all = p->vt;
    for (int n = 3; n <= 7; n += 2) {
        double per_v, Vn = vn(n, duty);
        double complex Zn = z_linear(p, n * f, &per_v);
        P += 0.5 * Vn * Vn * creal(1.0 / Zn);
        p->vt_all += fabs(Vn) * per_v;
    }
    return P / FAM_VDRIVE_V + p->iq0 + p->iq_sw * f / 400e3;
}

/* ---- the run ---------------------------------------------------------------------------- */
typedef struct {
    int arrived, left;
    fam_who who;
    double f_found, t_arrived, t_left;
    double i_max, power_end, i_end, duty_end, isense_end;
    double led_o_max, led_v_max;
    double sweep_duty_max_empty, vt_sweep_max;
    double led_mod;             /* the LED current's ripple in DRIVE, peak-to-peak / mean */
} result;

static result run(double ft, double M, double t_end, double t_off, double gain, double iq0, bool coin, bool print)
{
    result r;
    memset(&r, 0, sizeof r);
    perch pc;
    memset(&pc, 0, sizeof pc);
    pc.L1 = 28.50e-6;
    pc.L2 = 11.51e-6;
    pc.M = M;
    pc.ft = ft;
    pc.iq0 = iq0;
    pc.iq_sw = 3e-3;
    if (coin) {                 /* a coin: one turn of ~30 nH, 1 mohm, coupled k = 0.3 */
        pc.coin_L = 30e-9;
        pc.coin_R = 1e-3;
        pc.coin_M = 0.3 * sqrt(pc.L1 * pc.coin_L);
    }
    fam_perch fp;
    fam_init(&fp, 0);
    fam_enable(&fp, true);
    fam_cmd cmd = {false, 150e3, 0}, app = cmd;
    double isense_f = iq0, t = 0;
    const double dt = 0.25e-3;
    double next_step = 0;
    double lo_min = 1e9, lo_max = 0;
    while (t < t_end) {
        if (t >= t_off && pc.ft > 0)
            pc.ft = 0;                  /* lifted off */
        double i_supply = 0;
        if (app.enable) {
            double P = round(150e6 / (2 * cmd.freq_hz));     /* phase-correct PWM from 150 MHz */
            double fq = 150e6 / (2 * P), dq = round(cmd.duty * P) / P;
            app.freq_hz = (float)fq;
            app.duty = (float)dq;
            i_supply = supply_current(&pc, fq, dq);
        } else {
            pc.i1 = pc.vt = pc.vt_all = pc.led_o = pc.led_v = 0;
            i_supply = 0;               /* FAM_EN off: the drivers draw nothing */
        }
        isense_f += (i_supply - isense_f) * (1 - exp(-dt / 1e-3));
        if (pc.i1 > r.i_max) r.i_max = pc.i1;
        if (pc.led_o > r.led_o_max) r.led_o_max = pc.led_o;
        if (pc.led_v > r.led_v_max) r.led_v_max = pc.led_v;
        if (fp.state == FAM_ST_SWEEP && pc.vt_all > r.vt_sweep_max) r.vt_sweep_max = pc.vt_all;
        if (fp.state == FAM_ST_DRIVE && t < t_off && pc.ft > 0 && t - fp.t_state > 0.5) {
            if (pc.led_o < lo_min) lo_min = pc.led_o;
            if (pc.led_o > lo_max) lo_max = pc.led_o;
        }
        if (ft <= 0 && app.enable && app.duty > r.sweep_duty_max_empty)
            r.sweep_duty_max_empty = app.duty;
        if (t >= next_step) {
            fam_event ev;
            float meas = adc_v_per_a > 0.0 ? (float)adc_reading(gain * isense_f)
                                           : (float)(gain * isense_f + noise_A * gauss());
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
                r.i_end = pc.i1;
                r.duty_end = app.duty;
                r.isense_end = i_supply;
                r.power_end = (i_supply - iq0 - pc.iq_sw * app.freq_hz / 400e3) * FAM_VDRIVE_V;
            }
        }
        t += dt;
    }
    if (lo_max > 0)
        r.led_mod = (lo_max - lo_min) / (0.5 * (lo_max + lo_min));
    if (print) {
        printf("  found %s at %.1f kHz %.2f s after start; lit: %.0f mW in (supply %.1f mA), perch %.0f mA at duty "
               "%.2f, LEDs %.1f / %.1f mA (orange/violet), ripple %.0f %%; perch never above %.0f mA; sweep tank "
               "<= %.2f V", r.arrived ? fam_who_name(r.who) : "nothing", r.f_found / 1e3, r.t_arrived,
               r.power_end * 1e3, r.isense_end * 1e3, r.i_end * 1e3, r.duty_end, r.led_o_max * 1e3,
               r.led_v_max * 1e3, r.led_mod * 100, r.i_max * 1e3, r.vt_sweep_max);
        if (ft > 0 && t_off < t_end)
            r.left ? printf("; lifted off: noticed in %.2f s\n", r.t_left - t_off) : printf("; lifted off: NOT noticed\n");
        else
            printf("\n");
    }
    return r;
}

static void expect_token(const char *what, double ft, double M, double gain, double iq0, fam_who want)
{
    const double t_off = 11.0;
    printf("%s:\n", what);
    result r = run(ft, M, t_off + 2.0, t_off, gain, iq0, false, true);
    CHECK(r.arrived, "%s: nothing found", what);
    CHECK(r.who == want, "%s: named %s", what, fam_who_name(r.who));
    if (want != FAM_UNKNOWN)
        CHECK(fabs(r.f_found / ft - 1) < 0.05, "%s: tuning %.1f kHz, really %.1f kHz", what, r.f_found / 1e3,
              ft / 1e3);
    CHECK(r.i_max <= FAM_I_MAX_A, "%s: the perch carried %.1f mA", what, r.i_max * 1e3);
    CHECK(r.led_o_max > 3e-3, "%s: the token never lit (%.1f mA)", what, r.led_o_max * 1e3);
    CHECK(r.left && r.t_left - t_off < 1.0, "%s: lifting it off went unnoticed (%.2f s)", what,
          r.left ? r.t_left - t_off : -1.0);
    CHECK(r.vt_sweep_max < 1.85, "%s: the sweep lit the token (tank %.2f V)", what, r.vt_sweep_max);
    CHECK(r.led_mod < 0.10, "%s: the LEDs flicker %.0f %% at the dither", what, r.led_mod * 100);
}

int main(void)
{
    df_init();
    const double M0 = 8.53e-6, M5 = M0 * 0.38 / 0.471;
    printf("empty perch, 12 s:\n");
    result e = run(0, M0, 12.0, 1e9, 1.0, 2.5e-3, false, true);
    CHECK(!e.arrived, "an empty perch reported a %s", fam_who_name(e.who));
    CHECK(e.sweep_duty_max_empty < 0.04, "an empty perch was driven at duty %.3f", e.sweep_duty_max_empty);
    printf("a coin on the perch (no resonance), 12 s:\n");
    result c = run(0, M0, 12.0, 1e9, 1.0, 2.5e-3, true, true);
    CHECK(!c.arrived, "a coin was taken for a %s", fam_who_name(c.who));
    CHECK(c.sweep_duty_max_empty < 0.04, "a coin was driven at duty %.3f", c.sweep_duty_max_empty);

    expect_token("owl (150 kHz), 3 mm", 150e3, M0, 1.0, 2.5e-3, FAM_OWL);
    expect_token("cat (330 kHz), 3 mm", 330e3, M0, 1.0, 2.5e-3, FAM_CAT);
    expect_token("owl at 5 mm (k 0.38)", 150e3, M5, 1.0, 2.5e-3, FAM_OWL);
    expect_token("cat at 5 mm (k 0.38)", 330e3, M5, 1.0, 2.5e-3, FAM_CAT);
    expect_token("owl, ISENSE gain 10 % high, drivers drawing 5 mA", 150e3, M0, 1.10, 5e-3, FAM_OWL);
    expect_token("cat, ISENSE gain 10 % low", 330e3, M0, 0.90, 2.5e-3, FAM_CAT);
    expect_token("a token tuned to 240 kHz", 240e3, M0, 1.0, 2.5e-3, FAM_UNKNOWN);
    r1_scale = 0.85;
    expect_token("owl, perch coil 15 % less resistive than assumed", 150e3, M0, 1.0, 2.5e-3, FAM_OWL);
    expect_token("cat, perch coil 15 % less resistive than assumed", 330e3, M0, 1.0, 2.5e-3, FAM_CAT);
    r1_scale = 1.15;
    expect_token("owl, perch coil 15 % more resistive", 150e3, M0, 1.0, 2.5e-3, FAM_OWL);
    r1_scale = 1.0;
    noise_A = 0.3e-3;
    expect_token("owl, ISENSE noise 0.3 mA per reading", 150e3, M0, 1.0, 2.5e-3, FAM_OWL);
    expect_token("cat, ISENSE noise 0.3 mA per reading", 330e3, M0, 1.0, 2.5e-3, FAM_CAT);
    printf("empty perch, ISENSE noise 0.3 mA, 12 s:\n");
    result e3 = run(0, M0, 12.0, 1e9, 1.0, 2.5e-3, false, true);
    CHECK(!e3.arrived, "a noisy empty perch reported a %s", fam_who_name(e3.who));
    noise_A = 0.1e-3;

    /* the board's measuring chain: whole ADC counts.  The sweep's signals are 0.2-0.5 mA, so
     * the sense gain decides whether a token can be seen at all */
    static const double GAINS[2] = {2.0, 10.0};
    for (int gi = 0; gi < 2; gi++) {
        adc_v_per_a = GAINS[gi];
        char what[96];
        snprintf(what, sizeof what, "owl, ISENSE %.0f V/A through the 12-bit ADC (a count is %.2f mA)", GAINS[gi],
                 3.3 / 4096.0 / GAINS[gi] * 1e3);
        expect_token(what, 150e3, M0, 1.0, 2.5e-3, FAM_OWL);
        snprintf(what, sizeof what, "cat, ISENSE %.0f V/A through the 12-bit ADC", GAINS[gi]);
        expect_token(what, 330e3, M0, 1.0, 2.5e-3, FAM_CAT);
    }
    adc_v_per_a = FAM_ISENSE_V_PER_A;                    /* the board as drawn: reported, not asserted */
    printf("owl, ISENSE at the board's %.2f V/A (config.h) through the ADC (a count is %.2f mA):\n",
           (double)FAM_ISENSE_V_PER_A, 3.3 / 4096.0 / FAM_ISENSE_V_PER_A * 1e3);
    result b = run(150e3, M0, 6.0, 1e9, 1.0, 2.5e-3, false, true);
    if (!b.arrived || b.who != FAM_OWL)
        printf("WARNING: at %.2f V/A the familiars cannot be found; the sense needs >= 2 V/A, ideally ~10 V/A "
               "(README: open questions)\n", (double)FAM_ISENSE_V_PER_A);
    adc_v_per_a = 0.0;

    if (failures) {
        printf("test_familiar: %d FAILED\n", failures);
        return 1;
    }
    printf("test_familiar: all passed\n");
    return 0;
}
