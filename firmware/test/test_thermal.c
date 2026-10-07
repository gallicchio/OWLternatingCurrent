/* test_thermal.c: the coil thermal model (src/thermal.c).
 *
 *   1. steady state: the surface settles at ambient + P (R_cu-board + R_board-ambient);
 *   2. a demanding pulse train (1 A, 2 s on, 2 s off, 20 minutes) with the derating
 *      applied never takes the surface past the limit;
 *   3. the coil as its own thermometer: a real coil that cools worse than the model
 *      thinks (R_board-ambient 60 K/W, not 40), read through an IPROPI with a +3 %
 *      gain error and 1 % noise, is tracked, and kept under the limit, where the
 *      model alone lets it overheat;
 *   4. the predictions film mode plans with agree with simulating them.
 */
#include "thermal.h"
#include "config.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

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

static uint32_t rng = 12345u;
static float urand(void)
{
    rng = rng * 1664525u + 1013904223u;
    return ((rng >> 8) + 0.5f) / 16777216.0f;
}
static float gauss(void) { return sqrtf(-2.0f * logf(urand())) * cosf(6.2831853f * urand()); }

static const float DT = 0.001f, AMB = 25.0f;

static void test_steady_state(void)
{
    thermal_params p;
    thermal_default_params(&p);
    thermal_coil c;
    thermal_init(&c, &p, AMB);
    const float I = 0.4f;
    for (int k = 0; k < 3000000; k++)
        thermal_update(&c, DT, I * I, AMB);
    float rise = thermal_surface_C(&c) - AMB;
    float want = c.p_W * (p.r_cu_board_K_per_W + p.r_board_amb_K_per_W);
    printf("steady state at %.2f A: P %.3f W, rise %.3f K, P x (R1 + R2) %.3f K, R %.3f ohm\n", I, c.p_W, rise,
           want, thermal_r_ohm(&c));
    CHECK(fabsf(rise - want) < 0.01f * want, "steady rise %.3f K, want %.3f K", rise, want);
}

static void test_derated_pulse_train(void)
{
    thermal_params p;
    thermal_default_params(&p);
    thermal_coil c;
    thermal_init(&c, &p, AMB);
    float worst = 0.0f, min_derate = 1.0f, e_late = 0.0f;
    for (int k = 0; k < 1200000; k++) {
        float t = k * DT;
        float req = fmodf(t, 4.0f) < 2.0f ? 1.0f : 0.0f;
        float d = thermal_derate(&c);
        if (req > 0.0f && d < min_derate)
            min_derate = d;
        float i = req * d;
        thermal_update(&c, DT, i * i, AMB);
        if (thermal_surface_C(&c) > worst)
            worst = thermal_surface_C(&c);
        if (t > 600.0f)
            e_late += c.p_W * DT;
    }
    printf("pulse train 1 A 2 s/2 s, derated: hottest %.3f degC (limit %.1f), smallest derating %.2f, "
           "mean power after 10 min %.3f W\n", worst, p.limit_C, min_derate, e_late / 600.0f);
    CHECK(worst <= p.limit_C + 0.01f, "surface reached %.3f degC", worst);
    CHECK(min_derate < 0.9f, "the derating never acted (%.2f)", min_derate);
    CHECK(e_late / 600.0f > 0.25f, "derated far too much: %.3f W", e_late / 600.0f);
}

/* returns the true coil's hottest temperature; err_rms: firmware estimate vs truth after 200 s */
static float run_mismatch(bool measure, float *err_rms, bool *calibrated)
{
    thermal_params pf, pt;
    thermal_default_params(&pf);
    pt = pf;
    pt.r_board_amb_K_per_W = 60.0f;              /* the real coil cools worse than the model thinks */
    pt.c_board_J_per_K = 2.0f;
    thermal_coil fw, truth;
    thermal_init(&fw, &pf, AMB);
    thermal_init(&truth, &pt, AMB);
    float hottest = 0.0f, se = 0.0f;
    long n = 0;
    for (int k = 0; k < 900000; k++) {
        float t = k * DT;
        float req = (t > 100.0f && fmodf(t, 4.0f) < 2.0f) ? 0.8f : 0.0f;
        float i = req * thermal_derate(&fw);
        thermal_update(&truth, DT, i * i, AMB);
        thermal_update(&fw, DT, i * i, AMB);
        if (measure && i >= THERMAL_MEAS_MIN_A) {
            float r_true = thermal_r_ohm(&truth);
            float r_meas = r_true * 1.03f * (1.0f + 0.01f * gauss());   /* IPROPI gain error and noise */
            thermal_measure_r(&fw, r_meas, DT);
        }
        if (thermal_surface_C(&truth) > hottest)
            hottest = thermal_surface_C(&truth);
        if (t > 200.0f) {
            float e = thermal_surface_C(&fw) - thermal_surface_C(&truth);
            se += e * e;
            n++;
        }
    }
    *err_rms = sqrtf(se / (float)n);
    *calibrated = fw.r_calibrated;
    return hottest;
}

static void test_resistance_thermometer(void)
{
    float e_with, e_without;
    bool cal_with, cal_without;
    float hot_with = run_mismatch(true, &e_with, &cal_with);
    float hot_without = run_mismatch(false, &e_without, &cal_without);
    printf("model mismatch (real coil 60 K/W, model 40 K/W), 0.8 A pulses with derating:\n"
           "  model alone:            real coil peaks at %.2f degC, estimate off by %.2f K rms\n"
           "  with the R thermometer: real coil peaks at %.2f degC, estimate off by %.2f K rms (calibrated: %s)\n",
           hot_without, e_without, hot_with, e_with, cal_with ? "yes" : "no");
    CHECK(cal_with, "never calibrated the resistance");
    CHECK(hot_with <= COIL_SURFACE_LIMIT_C + 1.0f, "with measurement the real coil reached %.2f degC", hot_with);
    CHECK(e_with < 1.5f, "the estimate wanders %.2f K rms from the truth", e_with);
    CHECK(hot_without > hot_with + 1.0f, "the test does not show the thermometer helping (%.2f vs %.2f)",
          hot_without, hot_with);
}

static void test_predictions(void)
{
    thermal_params p;
    thermal_default_params(&p);
    thermal_coil c;
    thermal_init(&c, &p, AMB);
    /* warm it a little first */
    for (int k = 0; k < 20000; k++)
        thermal_update(&c, DT, 0.36f, AMB);
    float t_on = thermal_max_on_s(&c, 1.0f, p.limit_C, 600.0f);
    thermal_coil s = c;
    for (float t = 0.0f; t < t_on; t += DT)
        thermal_update(&s, DT, 1.0f, AMB);
    printf("from %.2f degC, 1 A may flow %.2f s; simulating that ends at %.3f degC\n", thermal_surface_C(&c), t_on,
           thermal_surface_C(&s));
    CHECK(fabsf(thermal_surface_C(&s) - p.limit_C) < 0.15f, "max_on_s inconsistent: %.3f", thermal_surface_C(&s));
    float i2 = thermal_max_current_A(&c, 2.0f, p.limit_C);
    s = c;
    for (int k = 0; k < 2000; k++)
        thermal_update(&s, DT, i2 * i2, AMB);
    printf("for 2 s, at most %.3f A; simulating that ends at %.3f degC\n", i2, thermal_surface_C(&s));
    CHECK(fabsf(thermal_surface_C(&s) - p.limit_C) < 0.15f, "max_current inconsistent: %.3f",
          thermal_surface_C(&s));
    CHECK(i2 > 1.0f, "a cool coil should take 1 A for 2 s (got %.3f A)", i2);
}

int main(void)
{
    test_steady_state();
    test_derated_pulse_train();
    test_resistance_thermometer();
    test_predictions();
    if (failures) {
        printf("test_thermal: %d FAILED\n", failures);
        return 1;
    }
    printf("test_thermal: all passed\n");
    return 0;
}
