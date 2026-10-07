/* film.c: film mode's slow walk of DC currents through the pendulum coils (film.h). */
#include "film.h"
#include "config.h"
#include <math.h>
#include <string.h>

enum { PH_REST = 0, PH_UP, PH_HOLD, PH_DOWN };

/* each step: the three coils' currents, in units of FILM_I_MAX_A */
static const signed char PATTERN[][FILM_COILS] = {
    {1, 0, 0},  {1, 1, 0},  {0, 1, 0},   {0, 1, 1},   {0, 0, 1},  {1, 0, 1},    /* round, one polarity */
    {1, -1, 0}, {0, 1, -1}, {-1, 0, 1},                                           /* neighbours opposed */
    {-1, 0, 0}, {-1, -1, 0}, {0, -1, 0}, {0, -1, -1}, {0, 0, -1}, {-1, 0, -1},   /* round, the other */
    {1, 1, 1},  {1, -1, 1}, {-1, 1, -1},                                          /* all three */
};
#define PATTERN_N (int)(sizeof PATTERN / sizeof PATTERN[0])

static float ease(float t, float T)
{
    if (t <= 0.0f)
        return 0.0f;
    if (t >= T)
        return 1.0f;
    return 0.5f - 0.5f * cosf(3.14159265f * t / T);
}

void film_init(film_seq *f) { memset(f, 0, sizeof *f); }

void film_start(film_seq *f, float t_s)
{
    if (f->active && !f->stopping)
        return;
    f->active = true;
    f->stopping = false;
    if (f->phase == PH_REST) {
        f->t_phase = t_s - FILM_REST_S + 0.3f;     /* the first step soon */
    }
}

void film_stop(film_seq *f, float t_s)
{
    if (!f->active)
        return;
    f->stopping = true;
    if (f->phase == PH_UP || f->phase == PH_HOLD) {
        float el = t_s - f->t_phase;
        f->level = f->phase == PH_UP ? ease(el, FILM_RAMP_S) : 1.0f;
        f->phase = PH_DOWN;
        f->t_phase = t_s;
    }
}

bool film_active(const film_seq *f) { return f->active; }

const char *film_phase_name(const film_seq *f)
{
    static const char *const n[] = {"rest", "up", "hold", "down"};
    if (!f->active)
        return "off";
    return n[f->phase & 3];
}

/* how far the step can go: the smallest of each lit coil's thermal allowance */
static float plan(const signed char *pat, const thermal_coil *const th[FILM_COILS])
{
    const float on_s = 2.0f * FILM_RAMP_S + FILM_HOLD_S;   /* counted at full current: errs cool */
    float scale = 1.0f;
    for (int c = 0; c < FILM_COILS; c++) {
        if (!pat[c])
            continue;
        float want = fabsf((float)pat[c]) * FILM_I_MAX_A;
        float ok = thermal_max_current_A(th[c], on_s, th[c]->p.limit_C - FILM_MARGIN_C);
        float s = ok / want;
        if (s < scale)
            scale = s;
    }
    return scale < 0.0f ? 0.0f : scale;
}

void film_step(film_seq *f, float t_s, const thermal_coil *const th[FILM_COILS], float i_A[FILM_COILS])
{
    for (int c = 0; c < FILM_COILS; c++)
        i_A[c] = 0.0f;
    if (!f->active)
        return;
    float el = t_s - f->t_phase;
    float k = 0.0f;
    switch (f->phase) {
    case PH_REST:
        if (f->stopping) {
            f->active = false;
            return;
        }
        if (el >= FILM_REST_S) {
            const signed char *pat = PATTERN[f->step % PATTERN_N];
            float s = plan(pat, th);
            f->scale = s;
            if (s < FILM_MIN_FRAC) {
                f->t_phase = t_s - FILM_REST_S + 0.5f;     /* still too warm: look again in 0.5 s */
                return;
            }
            for (int c = 0; c < FILM_COILS; c++)
                f->amp_A[c] = (float)pat[c] * FILM_I_MAX_A * (s > 1.0f ? 1.0f : s);
            f->phase = PH_UP;
            f->t_phase = t_s;
            el = 0.0f;
        } else {
            return;
        }
        /* fall through */
    case PH_UP:
        k = ease(el, FILM_RAMP_S);
        if (el >= FILM_RAMP_S) {
            f->phase = PH_HOLD;
            f->t_phase = t_s;
        }
        break;
    case PH_HOLD:
        k = 1.0f;
        if (el >= FILM_HOLD_S) {
            f->phase = PH_DOWN;
            f->t_phase = t_s;
            f->level = 1.0f;
        }
        break;
    case PH_DOWN:
        k = f->level * (1.0f - ease(el, FILM_RAMP_S));
        if (el >= FILM_RAMP_S) {
            f->phase = PH_REST;
            f->t_phase = t_s;
            f->step++;
            f->steps_done++;
            k = 0.0f;
        }
        break;
    }
    /* a coil close to its limit ends the step early, with a fade */
    if (f->phase == PH_UP || f->phase == PH_HOLD) {
        for (int c = 0; c < FILM_COILS; c++)
            if (f->amp_A[c] != 0.0f && thermal_surface_C(th[c]) >= th[c]->p.limit_C - 0.5f * FILM_MARGIN_C) {
                f->level = k;
                f->phase = PH_DOWN;
                f->t_phase = t_s;
                break;
            }
    }
    for (int c = 0; c < FILM_COILS; c++)
        i_A[c] = f->amp_A[c] * k * thermal_derate(th[c]);
}
