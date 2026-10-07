/* test_film.c: film mode (src/film.c) for ten simulated minutes, with the coil thermal
 * model (src/thermal.c) as the coils.
 *
 *   1. the model as the coils, a 25 degC room;
 *   2. coils that cool worse than the model thinks (60 K/W, not 40), watched by the
 *      resistance thermometer through an IPROPI 3 % off;
 *   3. a warm room (32 degC).
 * Each: no surface above COIL_SURFACE_LIMIT_C (case 2: within 1 K, the model being
 * wrong), no current above FILM_I_MAX_A, no coil on for more than FILM_ON_MAX_MS at a
 * stretch, every coil used, no change faster than a 0.2 s fade; and film_stop() fades
 * out and stops.
 */
#include "film.h"
#include "thermal.h"
#include "config.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

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

static uint32_t rng = 4242u;
static float urand(void)
{
    rng = rng * 1664525u + 1013904223u;
    return ((rng >> 8) + 0.5f) / 16777216.0f;
}
static float gauss(void) { return sqrtf(-2.0f * logf(urand())) * cosf(6.2831853f * urand()); }

typedef struct {
    float hottest_true, hottest_model, i_max, on_max_s, dI_max;
    int used[FILM_COILS], steps;
    float mean_scale;
} outcome;

static outcome run(float amb, float true_r_ba, bool measure, float seconds, bool power_on)
{
    outcome o;
    memset(&o, 0, sizeof o);
    thermal_params pf, pt;
    thermal_default_params(&pf);
    pt = pf;
    pt.r_board_amb_K_per_W = true_r_ba;
    if (true_r_ba != pf.r_board_amb_K_per_W)
        pt.c_board_J_per_K = 2.0f;
    thermal_coil fw[FILM_COILS], tr[FILM_COILS];
    const thermal_coil *th[FILM_COILS];
    for (int c = 0; c < FILM_COILS; c++) {
        thermal_init(&fw[c], &pf, amb);
        thermal_init(&tr[c], &pt, amb);
        th[c] = &fw[c];
        if (power_on)
            thermal_assume_cold(&fw[c]);
    }
    film_seq f;
    film_init(&f);
    film_start(&f, 0.0f);
    float i[FILM_COILS] = {0}, prev[FILM_COILS] = {0}, on_since[FILM_COILS] = {-1, -1, -1};
    const float dt = 0.001f;
    double scale_sum = 0;
    int scale_n = 0, last_steps = 0;
    for (long k = 0; k < (long)(seconds / dt); k++) {
        float t = k * dt;
        if (k % 10 == 0) {
            film_step(&f, t, th, i);
            for (int c = 0; c < FILM_COILS; c++) {
                float d = fabsf(i[c] - prev[c]);
                if (d > o.dI_max)
                    o.dI_max = d;
                prev[c] = i[c];
            }
            if (f.steps_done != last_steps) {
                last_steps = f.steps_done;
                scale_sum += f.scale > 1 ? 1 : f.scale;
                scale_n++;
            }
        }
        for (int c = 0; c < FILM_COILS; c++) {
            float a = fabsf(i[c]);
            thermal_update(&tr[c], dt, a * a, amb);
            thermal_update(&fw[c], dt, a * a, amb);
            if (measure && a >= THERMAL_MEAS_MIN_A)
                thermal_measure_r(&fw[c], thermal_r_ohm(&tr[c]) * 1.03f * (1.0f + 0.01f * gauss()), dt);
            if (a > o.i_max)
                o.i_max = a;
            if (a > 1e-5f) {
                o.used[c] = 1;
                if (on_since[c] < 0)
                    on_since[c] = t;
                if (t - on_since[c] + dt > o.on_max_s)
                    o.on_max_s = t - on_since[c] + dt;
            } else {
                on_since[c] = -1;
            }
            if (thermal_surface_C(&tr[c]) > o.hottest_true)
                o.hottest_true = thermal_surface_C(&tr[c]);
            if (thermal_surface_C(&fw[c]) > o.hottest_model)
                o.hottest_model = thermal_surface_C(&fw[c]);
        }
    }
    o.steps = f.steps_done;
    o.mean_scale = scale_n ? (float)(scale_sum / scale_n) : 0.0f;
    return o;
}

static void judge(const char *what, outcome o, float limit_slack)
{
    printf("%s: %d steps in 10 min (mean strength %.0f %%), hottest coil %.2f degC (model %.2f), "
           "peak %.3f A, longest on %.2f s, biggest change %.3f A per 10 ms, coils used %d%d%d\n", what, o.steps,
           o.mean_scale * 100, o.hottest_true, o.hottest_model, o.i_max, o.on_max_s, o.dI_max, o.used[0], o.used[1],
           o.used[2]);
    CHECK(o.hottest_true <= COIL_SURFACE_LIMIT_C + limit_slack, "%s: a coil reached %.2f degC", what, o.hottest_true);
    CHECK(o.i_max <= FILM_I_MAX_A + 1e-5f, "%s: %.3f A", what, o.i_max);
    CHECK(o.on_max_s <= FILM_ON_MAX_MS * 1e-3f, "%s: on for %.3f s", what, o.on_max_s);
    CHECK(o.used[0] && o.used[1] && o.used[2], "%s: not every coil used", what);
    /* a 0 -> 1 A raised-cosine fade over 0.2 s changes at most pi/2 x 1 A / 0.2 s = 79 mA per 10 ms */
    CHECK(o.dI_max <= 0.079f * FILM_I_MAX_A, "%s: steps of %.3f A per 10 ms", what, o.dI_max);
    CHECK(o.steps >= 40, "%s: only %d steps", what, o.steps);
}

static void test_stop(void)
{
    thermal_params p;
    thermal_default_params(&p);
    thermal_coil c[FILM_COILS];
    const thermal_coil *th[FILM_COILS];
    for (int k = 0; k < FILM_COILS; k++) {
        thermal_init(&c[k], &p, 25.0f);
        th[k] = &c[k];
    }
    film_seq f;
    film_init(&f);
    film_start(&f, 0.0f);
    float i[FILM_COILS], t = 0, worst_jump = 0, prev[FILM_COILS] = {0};
    for (; t < 1.2f; t += 0.01f)                 /* into a step's hold */
        film_step(&f, t, th, i);
    float before = fabsf(i[0]) + fabsf(i[1]) + fabsf(i[2]);
    memcpy(prev, i, sizeof prev);
    film_stop(&f, t);
    float t_stop = t, t_zero = -1;
    for (; t < 3.0f; t += 0.01f) {
        film_step(&f, t, th, i);
        for (int k = 0; k < FILM_COILS; k++) {
            if (fabsf(i[k] - prev[k]) > worst_jump)
                worst_jump = fabsf(i[k] - prev[k]);
            prev[k] = i[k];
        }
        if (t_zero < 0 && fabsf(i[0]) + fabsf(i[1]) + fabsf(i[2]) == 0.0f)
            t_zero = t;
    }
    printf("stop during a step (%.2f A): faded to zero in %.2f s, largest change %.3f A per 10 ms, %s\n", before,
           t_zero - t_stop, worst_jump, film_active(&f) ? "still active" : "stopped");
    CHECK(before > 0.5f, "the test did not catch a step (%.2f A)", before);
    CHECK(t_zero > 0 && t_zero - t_stop <= FILM_RAMP_S + 0.02f, "fade-out took %.2f s", t_zero - t_stop);
    CHECK(!film_active(&f), "film mode did not stop");
    CHECK(worst_jump <= 0.079f * FILM_I_MAX_A, "stopping stepped by %.3f A", worst_jump);
}

int main(void)
{
    judge("model as the coils, 25 degC", run(25.0f, THERMAL_R_BOARD_AMB_K_PER_W, false, 600.0f, true), 0.0f);
    judge("coils cool worse (60 K/W), R thermometer calibrated at power-on",
          run(25.0f, 60.0f, true, 600.0f, true), 1.0f);
    judge("coils cool worse (60 K/W), R thermometer never calibrated (after a watchdog reset)",
          run(25.0f, 60.0f, true, 600.0f, false), 1.0f);
    judge("warm room, 32 degC", run(32.0f, THERMAL_R_BOARD_AMB_K_PER_W, false, 600.0f, true), 0.0f);
    test_stop();
    if (failures) {
        printf("test_film: %d FAILED\n", failures);
        return 1;
    }
    printf("test_film: all passed\n");
    return 0;
}
