/* scenes.c: the light show.  See scenes.h.
 *
 * Every frame: the ambient night (candles, stars, owls, wisps) is brought up to
 * date once; the current scene (and, while cross-fading, the previous one) is
 * drawn from it; then the overlays: the familiars' rings, the pendulum's chosen
 * pumpkin, the perch's downlights.  Every motion is smooth by construction, and
 * slow enough that the LED engine's slew limit rarely has to act (test_leds
 * reports how often it does).
 */
#include "scenes.h"
#include "config.h"
#include <math.h>
#include <string.h>

#define PI 3.14159265f
#define N_STARS_ALL (LED_N_STAR + LED_N_STARX + LED_N_TSTAR)

static const char *const NAMES[SCENE_COUNT] = {
    [SCENE_ASLEEP] = "asleep", [SCENE_DUSK] = "dusk", [SCENE_NIGHT] = "night",
    [SCENE_FIREFLY] = "firefly", [SCENE_QUANTUM] = "quantum", [SCENE_FAMILIAR] = "familiar",
    [SCENE_DAWN] = "dawn", [SCENE_THEREMIN] = "theremin", [SCENE_PLAY] = "play",
};

const char *scene_name(scene_id id) { return (unsigned)id < SCENE_COUNT ? NAMES[id] : "?"; }

int scene_by_name(const char *name)
{
    for (int i = 0; i < SCENE_COUNT; i++)
        if (!strcmp(name, NAMES[i]))
            return i;
    return -1;
}

/* the 22 stars as one list: the arc, the scattered ones, the tree's */
static int star_led(int k)
{
    if (k < LED_N_STAR)
        return LED_GROUP_STAR[k];
    k -= LED_N_STAR;
    if (k < LED_N_STARX)
        return LED_GROUP_STARX[k];
    return LED_GROUP_TSTAR[k - LED_N_STARX];
}

static void shuffle_stars(scenes *s)
{
    for (int k = 0; k < N_STARS_ALL; k++)
        s->star_order[k] = (uint8_t)k;
    for (int k = N_STARS_ALL - 1; k > 0; k--) {
        int j = (int)(rng_uniform(&s->rng) * (float)(k + 1));
        uint8_t t = s->star_order[k];
        s->star_order[k] = s->star_order[j];
        s->star_order[j] = t;
    }
}

/* ---- the ambient night ------------------------------------------------------------ */
static float asleep_pumpkin(const scenes *s, int p)
{
    /* very slow, very dim breathing, each pumpkin a third of a breath behind the last */
    return 0.10f + 0.06f * (0.5f - 0.5f * cosf(2.0f * PI * (s->t / 9.0f + (float)p / 3.0f)));
}

static void ambient_update(scenes *s, const scene_inputs *in, float dt)
{
    /* owls: hold a look for a while, then turn the eyes (raised cosine over 1.2 s) */
    for (int o = 0; o < 3; o++) {
        s->owl_t[o] += dt;
        if (s->owl_t[o] < 1.2f) {
            float w = 0.5f - 0.5f * cosf(PI * s->owl_t[o] / 1.2f);
            s->owl_look[o] = s->owl_from[o] + (s->owl_to[o] - s->owl_from[o]) * w;
        } else {
            s->owl_look[o] = s->owl_to[o];
            if (s->owl_t[o] > 1.2f + s->owl_hold[o]) {
                static const float LOOKS[5] = {-1.0f, -0.5f, 0.0f, 0.5f, 1.0f};
                s->owl_from[o] = s->owl_look[o];
                s->owl_to[o] = LOOKS[rng_next(&s->rng) % 5u];
                s->owl_t[o] = 0.0f;
                s->owl_hold[o] = rng_range(&s->rng, 2.0f, 7.0f);
            }
        }
    }
    /* wisps along the hill: they wander, and roll downhill when the board tilts
     * (gravity's x: positive when the right-hand side is lower).  Units: LED spacings. */
    float gx = clampf(in->gravity[0], -1.0f, 1.0f);
    for (int p = 0; p < SCENE_WISP_PARTICLES; p++) {
        wisp_particle *w = &s->wisp[p];
        float a = 3.0f * gx + 0.8f * noise_value(w->seed, s->t * 0.35f) - 1.0f * w->v;
        w->v += a * dt;
        w->u += w->v * dt;
        if (w->u < 0.0f) {
            w->u = 0.0f;
            w->v = -0.4f * w->v;
        } else if (w->u > (float)(LED_N_WISP - 1)) {
            w->u = (float)(LED_N_WISP - 1);
            w->v = -0.4f * w->v;
        }
    }
    wisp_particle *t = &s->twisp;
    float a = 0.6f * noise_value(t->seed, s->t * 0.3f) - 0.8f * t->v;
    t->v += a * dt;
    t->u += t->v * dt;
    if (t->u < 0.0f) {
        t->u = 0.0f;
        t->v = -0.4f * t->v;
    } else if (t->u > (float)(LED_N_TWISP - 1)) {
        t->u = (float)(LED_N_TWISP - 1);
        t->v = -0.4f * t->v;
    }
}

static float blob(float k, float u, float sigma) { return expf(-(k - u) * (k - u) / (2.0f * sigma * sigma)); }

static void owl_eyes(float *f, int o, float base, float look)
{
    f[LED_GROUP_OWLEYE[2 * o]] = base * (0.65f + 0.35f * look);       /* left eye */
    f[LED_GROUP_OWLEYE[2 * o + 1]] = base * (0.65f - 0.35f * look);   /* right eye */
}

static void ambient(const scenes *s, float *f)
{
    memset(f, 0, LED_COUNT * sizeof *f);
    /* candles: smooth 1/f noise, about 0.7 Hz and three octaves up */
    for (int p = 0; p < LED_N_PUMPKIN; p++) {
        int led = LED_GROUP_PUMPKIN[p];
        f[led] = 0.55f + 0.13f * noise_fractal(s->seed[led], s->t * 0.7f, 4, 0.71f);
    }
    /* stars: slow turbulence */
    for (int k = 0; k < N_STARS_ALL; k++) {
        int led = star_led(k);
        f[led] = s->star_base[led] * (1.0f + 0.18f * noise_fractal(s->seed[led], s->t * 0.25f, 3, 0.6f));
    }
    for (int o = 0; o < 3; o++)
        owl_eyes(f, o, 0.5f, s->owl_look[o]);
    for (int k = 0; k < LED_N_WISP; k++) {
        float sum = 0.0f;
        for (int p = 0; p < SCENE_WISP_PARTICLES; p++)
            sum += blob((float)k, s->wisp[p].u, 0.6f) *
                   (0.85f + 0.15f * noise_value(s->wisp[p].seed + 7u, s->t * 0.3f));
        f[LED_GROUP_WISP[k]] = 0.5f * clampf(sum, 0.0f, 1.3f);
    }
    for (int k = 0; k < LED_N_TWISP; k++)
        f[LED_GROUP_TWISP[k]] = 0.45f * blob((float)k, s->twisp.u, 0.7f);
}

/* ---- the scenes --------------------------------------------------------------------- */
static void scene_asleep(const scenes *s, float *f)
{
    memset(f, 0, LED_COUNT * sizeof *f);
    for (int p = 0; p < LED_N_PUMPKIN; p++)
        f[LED_GROUP_PUMPKIN[p]] = asleep_pumpkin(s, p);
}

static void scene_dusk(const scenes *s, float t, float *f)
{
    ambient(s, f);
    for (int k = 0; k < N_STARS_ALL; k++) {             /* one at a time over 30 s */
        float tk = 1.0f + (float)k * 28.0f / (float)N_STARS_ALL;
        f[star_led(s->star_order[k])] *= smoothstepf(tk, tk + 2.5f, t);
    }
    float w = smoothstepf(0.0f, 25.0f, t);              /* the pumpkins warm up */
    for (int p = 0; p < LED_N_PUMPKIN; p++) {
        int led = LED_GROUP_PUMPKIN[p];
        f[led] = asleep_pumpkin(s, p) * (1.0f - w) + f[led] * w;
    }
    float eyes = smoothstepf(12.0f, 22.0f, t);          /* the owls open their eyes */
    for (int k = 0; k < LED_N_OWLEYE; k++)
        f[LED_GROUP_OWLEYE[k]] *= eyes;
    float wisps = smoothstepf(16.0f, 30.0f, t);
    for (int k = 0; k < LED_N_WISP; k++)
        f[LED_GROUP_WISP[k]] *= wisps;
    for (int k = 0; k < LED_N_TWISP; k++)
        f[LED_GROUP_TWISP[k]] *= wisps;
}

static void scene_dawn(const scenes *s, float t, float *f)
{
    ambient(s, f);
    for (int k = 0; k < N_STARS_ALL; k++) {             /* one at a time */
        float tk = (float)k * 14.0f / (float)N_STARS_ALL;
        f[star_led(s->star_order[k])] *= 1.0f - smoothstepf(tk, tk + 2.5f, t);
    }
    float eyes = 1.0f - smoothstepf(0.0f, 8.0f, t);     /* the owls close their eyes */
    for (int k = 0; k < LED_N_OWLEYE; k++)
        f[LED_GROUP_OWLEYE[k]] *= eyes;
    float wisps = 1.0f - smoothstepf(0.0f, 6.0f, t);
    for (int k = 0; k < LED_N_WISP; k++)
        f[LED_GROUP_WISP[k]] *= wisps;
    for (int k = 0; k < LED_N_TWISP; k++)
        f[LED_GROUP_TWISP[k]] *= wisps;
    float w = smoothstepf(4.0f, 18.0f, t);              /* the pumpkins settle to the day's glow */
    for (int p = 0; p < LED_N_PUMPKIN; p++) {
        int led = LED_GROUP_PUMPKIN[p];
        f[led] = f[led] * (1.0f - w) + asleep_pumpkin(s, p) * w;
    }
}

static int firefly_led(int i)
{
    if (i < LED_N_PUMPKIN)
        return LED_GROUP_PUMPKIN[i];
    i -= LED_N_PUMPKIN;
    if (i < LED_N_WISP)
        return LED_GROUP_WISP[i];
    return LED_GROUP_TWISP[i - LED_N_WISP];
}

static void firefly_reset(scenes *s)
{
    for (int i = 0; i < FIREFLY_N; i++) {
        s->theta[i] = rng_range(&s->rng, 0.0f, 2.0f * PI);
        s->omega[i] = 2.0f * PI * 0.45f * (1.0f + clampf(0.15f * rng_gauss(&s->rng), -0.25f, 0.25f));
    }
}

static void scene_firefly(scenes *s, float t, float dt, float *f)
{
    ambient(s, f);
    for (int k = 0; k < N_STARS_ALL; k++)
        f[star_led(k)] *= 0.8f;
    /* the coupling: off (out of step), up over 30 s (they pull into step), held, off again */
    float K = 1.6f * smoothstepf(15.0f, 45.0f, t) * (1.0f - smoothstepf(95.0f, 105.0f, t));
    float cr = 0.0f, ci = 0.0f;                         /* the mean field R e^(i psi) */
    for (int i = 0; i < FIREFLY_N; i++) {
        cr += cosf(s->theta[i]);
        ci += sinf(s->theta[i]);
    }
    cr /= (float)FIREFLY_N;
    ci /= (float)FIREFLY_N;
    s->kuramoto_r = sqrtf(cr * cr + ci * ci);
    for (int i = 0; i < FIREFLY_N; i++) {
        /* K R sin(psi - theta) = K (ci cos theta - cr sin theta) */
        float c = cosf(s->theta[i]), sn = sinf(s->theta[i]);
        s->theta[i] += (s->omega[i] + K * (ci * c - cr * sn)) * dt;
        if (s->theta[i] > 2.0f * PI)
            s->theta[i] -= 2.0f * PI;
        float pulse = 0.5f + 0.5f * cosf(s->theta[i]);
        pulse *= pulse;
        int led = firefly_led(i);
        f[led] = i < LED_N_PUMPKIN ? 0.22f + 0.45f * pulse : 0.04f + 0.5f * pulse;
    }
}

static void scene_quantum(scenes *s, float t, float dt, float *f)
{
    ambient(s, f);
    for (int i = 0; i < LED_COUNT; i++)
        f[i] *= 0.3f;                                   /* everything else hushes */
    for (int k = 0; k < LED_N_WISP; k++)
        f[LED_GROUP_WISP[k]] = 0.0f;
    for (int k = 0; k < LED_N_TWISP; k++)
        f[LED_GROUP_TWISP[k]] = 0.0f;
    int steps = (int)(dt * (float)LED_FPS + 0.5f);      /* one step a frame */
    for (int i = 0; i < steps; i++)
        quantum_step(&s->q);
    float cells[QG_CELLS];
    quantum_cells(&s->q, cells);
    float env = smoothstepf(0.0f, 1.0f, t) * (1.0f - smoothstepf(SCENE_QUANTUM_S - 1.5f, SCENE_QUANTUM_S, t));
    for (int c = 0; c < QG_CELLS && c < LED_N_STAR; c++)
        f[LED_GROUP_STAR[c]] = 0.8f * powf(clampf(cells[c] / 0.30f, 0.0f, 1.0f), 0.6f) * env;
    /* the owls watch the ghost */
    float look = 2.0f * quantum_mean_x(&s->q) / (float)(QG_N - 1) - 1.0f;
    for (int o = 0; o < 3; o++)
        owl_eyes(f, o, 0.45f, clampf(look, -1.0f, 1.0f));
}

static void scene_theremin(scenes *s, const scene_inputs *in, float dt, float *f)
{
    float k = clampf(dt / 0.12f, 0.0f, 1.0f);
    s->pitch_s += (clampf(in->pitch01, 0.0f, 1.0f) - s->pitch_s) * k;
    s->vol_s += (clampf(in->volume01, 0.0f, 1.0f) - s->vol_s) * k;
    ambient(s, f);
    for (int i = 0; i < LED_COUNT; i++)
        f[i] *= 0.45f;
    /* the arc is a meter of the pitch, filling from the moon's end: each star fully on
     * in turn, the top one fractional, the rest off (no floor and no twinkle under it,
     * which read as random dim stars: bench, 2026-11-07) */
    float n = s->pitch_s * (float)LED_N_STAR;
    for (int j = 0; j < LED_N_STAR; j++) {
        int star = SCENE_MOON_STAR >= LED_N_STAR / 2 ? SCENE_MOON_STAR - j : SCENE_MOON_STAR + j;
        if (star < 0 || star >= LED_N_STAR)
            continue;
        f[LED_GROUP_STAR[star]] = 0.75f * clampf(n - (float)j, 0.0f, 1.0f);
    }
    for (int p = 0; p < LED_N_PUMPKIN; p++)
        f[LED_GROUP_PUMPKIN[p]] = 0.04f + 0.7f * s->vol_s;
    float look = (2.0f * s->pitch_s - 1.0f) * (SCENE_MOON_STAR >= LED_N_STAR / 2 ? 1.0f : -1.0f);
    for (int o = 0; o < 3; o++)
        owl_eyes(f, o, 0.5f, look);
}

/* ---- play: every input lights its own LEDs at once (scenes.h) ------------------------ */
#define PLAY_RING_TURN_S 1.0f  /* a token ring's breathing chase goes round once in this (Jason, 2026-11-10) */
#define PLAY_RING_PEAK   0.35f /* its brightest LED (L*): under the tokens' own LEDs */
#define PLAY_LOCK_MM   0.5f    /* locked: the gap within this of the set-point */
#define PLAY_CATCH_MM  1.5f    /* catching: further off than this, or in the hold's first second */
#define PLAY_LEV_WAIT 2
#define PLAY_LEV_HOLD 3
#define PLAY_LEV_LOST 4
#define PLAY_LEV_FAULT 6

static float approach(float x, float target, float rate_per_s, float dt)
{
    return x + clampf(target - x, -rate_per_s * dt, rate_per_s * dt);
}

static void scene_play(scenes *s, const scene_inputs *in, float dt, float *f)
{
    memset(f, 0, LED_COUNT * sizeof *f);
    float t = s->t;
    /* alive: the pumpkins glow like candles, bright enough to see in daylight */
    for (int p = 0; p < LED_N_PUMPKIN; p++) {
        int led = LED_GROUP_PUMPKIN[p];
        f[led] = 0.5f + 0.1f * noise_fractal(s->seed[led], t * 0.7f, 3, 0.7f);
    }
    for (int o = 0; o < 3; o++)
        owl_eyes(f, o, 0.25f, 0.0f);

    /* the theremin: the arc fills from the moon with the pitch, the pumpkins rise with
     * the volume, owls B and C look toward the moon or away */
    s->th_level = approach(s->th_level, in->theremin_active ? 1.0f : 0.0f, in->theremin_active ? 6.0f : 2.0f, dt);
    if (in->theremin_active) {
        float k = clampf(dt / 0.06f, 0.0f, 1.0f);
        s->pitch_s += (clampf(in->pitch01, 0.0f, 1.0f) - s->pitch_s) * k;
        s->vol_s += (clampf(in->volume01, 0.0f, 1.0f) - s->vol_s) * k;
    }
    if (s->th_level > 0.0f) {
        float n = s->pitch_s * (float)LED_N_STAR;
        for (int j = 0; j < LED_N_STAR; j++) {
            int star = SCENE_MOON_STAR >= LED_N_STAR / 2 ? SCENE_MOON_STAR - j : SCENE_MOON_STAR + j;
            if (star >= 0 && star < LED_N_STAR)
                f[LED_GROUP_STAR[star]] = s->th_level * clampf(n - (float)j, 0.0f, 1.0f);
        }
        for (int p = 0; p < LED_N_PUMPKIN; p++) {
            int led = LED_GROUP_PUMPKIN[p];
            f[led] += s->th_level * s->vol_s * (1.0f - f[led]);
        }
        float look = (2.0f * s->pitch_s - 1.0f) * (SCENE_MOON_STAR >= LED_N_STAR / 2 ? 1.0f : -1.0f);
        for (int o = 1; o < 3; o++)
            owl_eyes(f, o, 0.25f + 0.75f * s->th_level, look);
    }

    /* shading the light sensor (a hand over it): owls B and C wake, the tree's stars come
     * out.  Against a slow mean, with hysteresis; the mean holds while shaded, so the
     * tree's own light near the sensor cannot end it */
    if (in->lux >= 0.0f) {
        if (s->lux_slow <= 0.0f)
            s->lux_slow = in->lux;
        if (!s->shaded)
            s->lux_slow += (in->lux - s->lux_slow) * clampf(dt / 8.0f, 0.0f, 1.0f);
        if (!s->shaded && s->lux_slow > 2.0f && in->lux < 0.4f * s->lux_slow)
            s->shaded = true;
        else if (s->shaded && (in->lux > 0.7f * s->lux_slow || s->lux_slow <= 2.0f))
            s->shaded = false;
    } else {
        s->shaded = false;
    }
    s->shade = approach(s->shade, s->shaded ? 1.0f : 0.0f, 4.0f, dt);
    if (s->shade > 0.0f) {
        for (int o = 1; o < 3; o++) {
            f[LED_GROUP_OWLEYE[2 * o]] = fmaxf(f[LED_GROUP_OWLEYE[2 * o]], s->shade);
            f[LED_GROUP_OWLEYE[2 * o + 1]] = fmaxf(f[LED_GROUP_OWLEYE[2 * o + 1]], s->shade);
        }
        for (int k = 0; k < LED_N_TSTAR; k++)
            f[LED_GROUP_TSTAR[k]] = fmaxf(f[LED_GROUP_TSTAR[k]], s->shade);
        for (int k = 0; k < LED_N_TWISP; k++)
            f[LED_GROUP_TWISP[k]] = fmaxf(f[LED_GROUP_TWISP[k]], 0.8f * s->shade);
    }

    /* a tap (or the third spell): a twinkle, each star flashing once at its own moment
     * over 0.9 s (each flash 0.6 s, as fast as the no-step slew allows); a double tap
     * twinkles the hill's and the tree's wisps too */
    if (in->tap || in->double_tap || in->spell == 3) {
        s->twinkle_t = 0.0f;
        s->twinkle_wisps = in->double_tap ? 1.0f : 0.0f;
    }
    if (s->twinkle_t >= 0.0f) {
        for (int k = 0; k < N_STARS_ALL + LED_N_WISP + LED_N_TWISP; k++) {
            int led = k < N_STARS_ALL ? star_led(k)
                    : k < N_STARS_ALL + LED_N_WISP ? LED_GROUP_WISP[k - N_STARS_ALL]
                    : LED_GROUP_TWISP[k - N_STARS_ALL - LED_N_WISP];
            if (k >= N_STARS_ALL && s->twinkle_wisps <= 0.0f)
                break;
            float delay = 0.9f * (float)(noise_hash(s->seed[led] + 77u) & 1023u) / 1023.0f;
            float tau = s->twinkle_t - delay;
            float l = clampf(1.0f - fabsf(tau - 0.3f) / 0.3f, 0.0f, 1.0f);
            f[led] = fmaxf(f[led], l);
        }
        s->twinkle_t += dt;
        if (s->twinkle_t > 1.6f)
            s->twinkle_t = -1.0f;
    }

    /* the first spell: the quantum ghost runs along the arc, meets the wall and partly
     * tunnels (quantum.h), for 6 s; the owls watch it */
    if (in->spell == 1) {
        quantum_params qp = quantum_default_params();
        quantum_init(&s->q, &qp);
        s->ghost_t = 0.0f;
    }
    if (s->ghost_t >= 0.0f) {
        int steps = (int)(dt * (float)LED_FPS + 0.5f);
        for (int i = 0; i < steps; i++)
            quantum_step(&s->q);
        float cells[QG_CELLS];
        quantum_cells(&s->q, cells);
        float env = smoothstepf(0.0f, 0.5f, s->ghost_t) * (1.0f - smoothstepf(5.0f, 6.0f, s->ghost_t));
        for (int c = 0; c < QG_CELLS && c < LED_N_STAR; c++) {
            float l = powf(clampf(cells[c] / 0.30f, 0.0f, 1.0f), 0.6f) * env;
            f[LED_GROUP_STAR[c]] = fmaxf(f[LED_GROUP_STAR[c]], l);
        }
        float look = 2.0f * quantum_mean_x(&s->q) / (float)(QG_N - 1) - 1.0f;
        for (int o = 1; o < 3; o++)
            owl_eyes(f, o, fmaxf(0.25f, env), clampf(look, -1.0f, 1.0f));
        s->ghost_t += dt;
        if (s->ghost_t > 6.0f)
            s->ghost_t = -1.0f;
    }

    /* the second spell: everything wakes at once and fades over two seconds */
    if (in->spell == 2)
        s->wake_t = 0.0f;
    if (s->wake_t >= 0.0f) {
        float env = s->wake_t < 0.3f ? s->wake_t / 0.3f : 1.0f - smoothstepf(0.5f, 2.5f, s->wake_t);
        for (int i = 0; i < LED_COUNT; i++)
            f[i] = fmaxf(f[i], env);
        s->wake_t += dt;
        if (s->wake_t > 2.5f)
            s->wake_t = -1.0f;
    }

    /* the familiars' perches: each ring "breathes" round, to say "put a token here"
     * (Jason, 2026-11-10): two neighbouring LEDs trade their brightness, then the one that
     * has become bright trades with the next, once round in PLAY_RING_TURN_S; no blinking.
     * Dim enough that a token's own LEDs are the brightest thing there, and it shines
     * through the token's board (its coil in silhouette).  A perch in live mode drives all
     * the time and cannot yet tell whether a token is on it (familiar[] stays set; the
     * current does not change, the fam_token records in results/2026-11-10), so the ring does not
     * change with it yet */
    static const uint8_t *const RING[2] = {LED_GROUP_OWLRING, LED_GROUP_CATRING};
    for (int p = 0; p < 2; p++) {
        s->ring_idle[p] = approach(s->ring_idle[p], 1.0f, 2.0f, dt);
        float x = 3.0f * (t / PLAY_RING_TURN_S - floorf(t / PLAY_RING_TURN_S));   /* 0..3 */
        int k = (int)x % 3;
        float u = 0.5f - 0.5f * cosf(PI * (x - floorf(x)));                       /* 0..1, smooth */
        for (int i = 0; i < 3; i++)
            f[RING[p][i]] = 0.0f;
        f[RING[p][k]] = s->ring_idle[p] * PLAY_RING_PEAK * (1.0f - u);
        f[RING[p][(k + 1) % 3]] = s->ring_idle[p] * PLAY_RING_PEAK * u;
    }

    /* the bat: the perch's downlights show the loop, owl A's eyes the height */
    if (in->lev_state != s->lev_prev) {
        s->lev_prev = in->lev_state;
        s->lev_t = 0.0f;
    }
    s->lev_t += dt;
    float down = 0.0f;
    switch (in->lev_state) {
    case PLAY_LEV_WAIT:                                    /* breathing: ready for the bat */
        down = 0.35f + 0.35f * (0.5f - 0.5f * cosf(2.0f * PI * s->lev_t / 2.0f));
        break;
    case PLAY_LEV_HOLD: {
        float e = in->lev_err_mm;
        bool catching = s->lev_t < 1.0f || fabsf(e) > PLAY_CATCH_MM;
        /* catching: a quick pulse (2.5 Hz, inside the engine's no-step slew); locked: steady */
        down = catching ? 0.8f + 0.2f * cosf(2.0f * PI * 2.5f * s->lev_t) : 1.0f;
        float off = clampf((fabsf(e) - PLAY_LOCK_MM) / 1.5f, 0.0f, 1.0f);
        float l = fabsf(e) <= PLAY_LOCK_MM ? 0.35f : 0.35f + 0.65f * off;
        f[LED_GROUP_OWLEYE[0]] = e < -PLAY_LOCK_MM || fabsf(e) <= PLAY_LOCK_MM ? l : 0.0f;   /* too close: left */
        f[LED_GROUP_OWLEYE[1]] = e > PLAY_LOCK_MM || fabsf(e) <= PLAY_LOCK_MM ? l : 0.0f;    /* too far: right */
        break;
    }
    case PLAY_LEV_LOST:
    case PLAY_LEV_FAULT:                                   /* three pulses, then dark */
        if (s->lev_t < 2.0f)
            down = 0.5f - 0.5f * cosf(2.0f * PI * 1.5f * s->lev_t);
        break;
    default:
        break;
    }
    for (int k = 0; k < LED_N_PERCH_DOWN; k++)
        f[LED_GROUP_PERCH_DOWN[k]] = fmaxf(f[LED_GROUP_PERCH_DOWN[k]], down);
}

static void render(scenes *s, scene_id id, float t, const scene_inputs *in, float *f)
{
    float dt = in->dt_s;
    switch (id) {
    case SCENE_ASLEEP: scene_asleep(s, f); break;
    case SCENE_DUSK: scene_dusk(s, t, f); break;
    case SCENE_NIGHT: ambient(s, f); break;
    case SCENE_FIREFLY: scene_firefly(s, t, dt, f); break;
    case SCENE_QUANTUM: scene_quantum(s, t, dt, f); break;
    case SCENE_FAMILIAR: ambient(s, f); break;          /* the rings are an overlay */
    case SCENE_DAWN: scene_dawn(s, t, f); break;
    case SCENE_THEREMIN: scene_theremin(s, in, dt, f); break;
    case SCENE_PLAY: scene_play(s, in, dt, f); break;
    default: memset(f, 0, LED_COUNT * sizeof *f); break;
    }
}

/* ---- changes of scene ---------------------------------------------------------------- */
static void enter(scenes *s, scene_id id)
{
    if (id == SCENE_QUANTUM || id == SCENE_THEREMIN) {
        if (s->cur != SCENE_QUANTUM && s->cur != SCENE_THEREMIN)
            s->resume = s->dark ? SCENE_NIGHT : SCENE_ASLEEP;
    }
    s->prev = s->cur;
    s->t_prev = s->t_cur;
    s->cur = id;
    s->t_cur = 0.0f;
    s->xfade = s->prev == id ? 1.0f : 0.0f;
    switch (id) {
    case SCENE_DUSK:
    case SCENE_DAWN: shuffle_stars(s); break;
    case SCENE_FIREFLY: firefly_reset(s); break;
    case SCENE_QUANTUM: {
        quantum_params p = quantum_default_params();
        quantum_init(&s->q, &p);
        break;
    }
    case SCENE_NIGHT: s->next_firefly = s->t + rng_range(&s->rng, 180.0f, 300.0f); break;
    case SCENE_THEREMIN: s->theremin_idle = 0.0f; break;
    default: break;
    }
}

void scenes_select(scenes *s, scene_id id)
{
    if ((unsigned)id >= SCENE_COUNT)
        return;
    s->manual = true;
    enter(s, id);
}

void scenes_auto(scenes *s) { s->manual = false; }

scene_id scenes_current(const scenes *s) { return s->cur; }

bool scenes_is_manual(const scenes *s) { return s->manual; }

void scenes_init(scenes *s, uint32_t seed)
{
    memset(s, 0, sizeof *s);
    rng_seed(&s->rng, seed);
    for (int i = 0; i < LED_COUNT; i++) {
        s->seed[i] = rng_next(&s->rng);
        s->star_base[i] = rng_range(&s->rng, 0.30f, 0.55f);
    }
    for (int o = 0; o < 3; o++) {
        s->owl_hold[o] = rng_range(&s->rng, 1.0f, 5.0f);
        s->owl_t[o] = 1.2f;
    }
    for (int p = 0; p < SCENE_WISP_PARTICLES; p++) {
        s->wisp[p].u = rng_range(&s->rng, 0.0f, (float)(LED_N_WISP - 1));
        s->wisp[p].seed = rng_next(&s->rng);
    }
    s->twisp.u = 1.5f;
    s->twisp.seed = rng_next(&s->rng);
    s->ring_t[0] = s->ring_t[1] = -1.0f;
    s->twinkle_t = s->ghost_t = s->wake_t = -1.0f;
    s->choice = -1;
    s->dark = false;
    s->cur = s->prev = SCENE_ASLEEP;
    s->xfade = 1.0f;
    s->resume = SCENE_NIGHT;
    shuffle_stars(s);
    firefly_reset(s);
}

/* the automatic sequence (scenes.h) */
static void sequence(scenes *s, const scene_inputs *in)
{
    float dt = in->dt_s;
    if (in->lux <= SCENE_LUX_PENDING)
        return;                                          /* the light sensor has not spoken yet */
    if (in->lux >= 0.0f && !s->lux_seen) {               /* its first word counts at once */
        s->lux_seen = true;
        s->dark = in->lux < 0.5f * (ALS_DARK_LUX + ALS_LIGHT_LUX);
    }
    if (in->lux >= 0.0f) {
        s->lux_dark_for = in->lux < ALS_DARK_LUX ? s->lux_dark_for + dt : 0.0f;
        s->lux_light_for = in->lux > ALS_LIGHT_LUX ? s->lux_light_for + dt : 0.0f;
        if (s->lux_dark_for > ALS_HOLD_S)
            s->dark = true;
        if (s->lux_light_for > ALS_HOLD_S)
            s->dark = false;
    } else {
        s->dark = true;                                  /* no light sensor: it is always night */
    }
    if (s->manual) {
        if (s->cur == SCENE_QUANTUM && s->t_cur > SCENE_QUANTUM_S + 3.0f)
            enter(s, SCENE_QUANTUM);                     /* again */
        if (s->cur == SCENE_FIREFLY && s->t_cur > SCENE_FIREFLY_S)
            s->t_cur = 0.0f;
        return;
    }
    bool next = in->tap || in->button;
    if (in->theremin_active && s->cur != SCENE_THEREMIN) {
        enter(s, SCENE_THEREMIN);
        return;
    }
    if (in->double_tap && s->cur != SCENE_QUANTUM) {
        enter(s, SCENE_QUANTUM);
        return;
    }
    switch (s->cur) {
    case SCENE_ASLEEP:
        if (s->dark || next)
            enter(s, SCENE_DUSK);
        break;
    case SCENE_DUSK:
        if (!s->dark && in->lux >= 0.0f)
            enter(s, SCENE_DAWN);
        else if (s->t_cur > SCENE_DUSK_S)
            enter(s, SCENE_NIGHT);
        break;
    case SCENE_NIGHT:
        if (!s->dark)
            enter(s, SCENE_DAWN);
        else if (next || s->t > s->next_firefly)
            enter(s, SCENE_FIREFLY);
        break;
    case SCENE_FIREFLY:
        if (!s->dark)
            enter(s, SCENE_DAWN);
        else if (next)
            enter(s, SCENE_QUANTUM);
        else if (s->t_cur > SCENE_FIREFLY_S)
            enter(s, SCENE_NIGHT);
        break;
    case SCENE_QUANTUM:
        if (next || s->t_cur > SCENE_QUANTUM_S)
            enter(s, s->resume);
        break;
    case SCENE_FAMILIAR:
        if (next || s->t_cur > 12.0f)
            enter(s, s->dark ? SCENE_NIGHT : SCENE_ASLEEP);
        break;
    case SCENE_DAWN:
        if (s->dark)
            enter(s, SCENE_DUSK);
        else if (s->t_cur > SCENE_DAWN_S)
            enter(s, SCENE_ASLEEP);
        break;
    case SCENE_THEREMIN:
        s->theremin_idle = in->theremin_active ? 0.0f : s->theremin_idle + dt;
        if (s->theremin_idle > 4.0f)
            enter(s, s->resume);
        break;
    default:
        enter(s, SCENE_NIGHT);
        break;
    }
}

static void overlays(scenes *s, const scene_inputs *in, float *f)
{
    float dt = in->dt_s;
    /* a familiar on a perch: its ring swirls, then glows */
    static const uint8_t *const RING[2] = {LED_GROUP_OWLRING, LED_GROUP_CATRING};
    for (int p = 0; p < 2 && s->cur != SCENE_PLAY; p++) {   /* play draws its own rings */
        bool present = in->familiar[p] != FAMILIAR_NONE || s->cur == SCENE_FAMILIAR;
        if (present)
            s->ring_t[p] = s->ring_t[p] < 0.0f ? 0.0f : s->ring_t[p] + dt;
        else
            s->ring_t[p] = -1.0f;
        float target = present ? 1.0f : 0.0f;
        s->ring_level[p] += clampf(target - s->ring_level[p], -dt, dt);   /* over a second */
        if (s->ring_level[p] <= 0.0f)
            continue;
        float rt = s->ring_t[p] < 0.0f ? SCENE_RING_SWIRL_S : s->ring_t[p];
        if (s->cur == SCENE_FAMILIAR)
            rt = fmodf(s->t_cur, SCENE_RING_SWIRL_S + 4.0f);
        float w = smoothstepf(SCENE_RING_SWIRL_S - 2.0f, SCENE_RING_SWIRL_S, rt);
        for (int i = 0; i < 3; i++) {
            float c = 0.5f + 0.5f * cosf(2.0f * PI * 0.7f * rt - 2.0f * PI * (float)i / 3.0f);
            float swirl = 0.15f + 0.6f * c * c;
            float l = (swirl * (1.0f - w) + 0.45f * w) * s->ring_level[p];
            int led = RING[p][i];
            if (l > f[led])
                f[led] = l;
        }
    }
    /* the chaos pendulum chose a pumpkin */
    if (in->pendulum_choice != s->choice) {
        s->choice = in->pendulum_choice;
        s->choice_t = 0.0f;
    }
    if (s->choice >= 0 && s->choice < LED_N_PUMPKIN) {
        s->choice_t += dt;
        float env = smoothstepf(0.0f, 0.8f, s->choice_t) * (1.0f - smoothstepf(4.8f, 6.8f, s->choice_t));
        int led = LED_GROUP_PUMPKIN[s->choice];
        if (0.85f * env > f[led])
            f[led] = 0.85f * env;
    }
    /* the floating bat's downlights, faded over a second (play draws its own) */
    float want = in->lev_holding && s->cur != SCENE_PLAY ? (s->cur == SCENE_ASLEEP ? 0.12f : 0.3f) : 0.0f;
    s->downlight += clampf(want - s->downlight, -0.3f * dt, 0.3f * dt);
    for (int k = 0; k < LED_N_PERCH_DOWN; k++)
        if (s->downlight > f[LED_GROUP_PERCH_DOWN[k]])
            f[LED_GROUP_PERCH_DOWN[k]] = s->downlight;
}

void scenes_render(scenes *s, const scene_inputs *in, float out_l[LED_COUNT])
{
    float dt = in->dt_s > 0.0f ? in->dt_s : 1.0f / (float)LED_FPS;
    s->t += dt;
    sequence(s, in);
    ambient_update(s, in, dt);
    render(s, s->cur, s->t_cur, in, s->frame);
    if (s->xfade < 1.0f && s->prev != s->cur) {
        render(s, s->prev, s->t_prev, in, s->frame_prev);
        float w = smoothstepf(0.0f, 1.0f, s->xfade);
        for (int i = 0; i < LED_COUNT; i++)
            s->frame[i] = s->frame_prev[i] * (1.0f - w) + s->frame[i] * w;
        s->xfade += dt / SCENE_XFADE_S;
        s->t_prev += dt;
    }
    s->t_cur += dt;
    overlays(s, in, s->frame);
    for (int i = 0; i < LED_COUNT; i++)
        out_l[i] = clampf(s->frame[i], 0.0f, 1.0f);
}
