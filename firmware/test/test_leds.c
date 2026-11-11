/* test_leds.c: no LED ever steps (Jason's rule), on every scene.
 *
 * The scenes (src/scenes.c) and the LED engine (src/led_engine.c) run frame by
 * frame at LED_FPS, as on the board, while the test throws everything at them at
 * random moments: taps, double taps, the SPELL button, the board tilted and
 * flipped, familiars put down and snatched away, a theremin hand jumping, the room
 * lights going on and off, the 12 V adapter unplugged (USB-only ceiling) and back,
 * and the console setting LEDs to arbitrary levels.  For every LED and every frame
 * it checks:
 *   SLEW     the lightness shown moves at most LED_SLEW_PER_FRAME (a 0-to-full fade
 *            in LED_FADE_MIN_S = 300 ms) per frame;
 *   HARDWARE the lightness the LP5036 registers really produce (bank brightness x
 *            colour, dithered) moves at most that plus two of its own steps;
 *   CEILING  no LED exceeds its colour's ceiling (the orange 0603's 20 mA, violet's
 *            eye-safety limit) or the USB-only ceiling;
 *   BANKS    every bank brightness is in 16..255 and unused outputs stay at 0.
 * It also checks the CIE L* curve, that dithering averages to the target, and that
 * no dither pattern is slower than 1 / LED_DITHER_DEADBAND frames.
 */
#include "led_engine.h"
#include "noise.h"
#include "scenes.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...)                                  \
    do {                                                  \
        if (!(cond)) {                                    \
            if (failures < 20) {                          \
                printf("FAIL %s:%d: ", __FILE__, __LINE__); \
                printf(__VA_ARGS__);                      \
                printf("\n");                             \
            }                                             \
            failures++;                                   \
        }                                                 \
    } while (0)

static scenes S;
static led_engine E;

/* the lightness the registers produce, and the size of one of its steps there */
static float shown_l(int i) { return led_y_to_l((float)E.duty[i] / LP5036_DUTY_FULL); }

static float step_l(int i)
{
    const led_info *m = &LED_MAP[i];
    float B = (float)E.reg[m->driver][m->channel / 3];
    float y = (float)E.duty[i] / LP5036_DUTY_FULL;
    float dy = (B / 16.0f) / LP5036_DUTY_FULL;
    return led_y_to_l(y + dy) - led_y_to_l(y > dy ? y - dy : 0.0f);
}

typedef struct {
    float worst_slew, worst_hw, clip_frac, max_target_step;
    long frames;
} run_stats;

/* run `seconds` of frames from the current state, throwing events at it */
static run_stats run(float seconds, bool chaos, uint32_t seed, bool auto_lux)
{
    rng32 r;
    rng_seed(&r, seed);
    scene_inputs in;
    memset(&in, 0, sizeof in);
    in.dt_s = 1.0f / (float)LED_FPS;
    in.gravity[2] = -1.0f;
    in.lux = auto_lux ? 100.0f : 0.5f;
    in.pendulum_choice = -1;
    float target[LED_COUNT], prev_out[LED_COUNT], prev_hw[LED_COUNT], prev_target[LED_COUNT];
    run_stats st = {0};
    long clipped = 0, led_frames = 0;
    int frames = (int)(seconds * (float)LED_FPS);
    for (int i = 0; i < LED_COUNT; i++) {
        prev_out[i] = E.l_out[i];
        prev_hw[i] = shown_l(i);
        prev_target[i] = -1.0f;
    }
    for (int f = 0; f < frames; f++) {
        in.tap = in.double_tap = in.button = false;
        in.spell = 0;
        if (chaos) {
            float u = rng_uniform(&r);
            if (u < 0.002f)
                in.tap = true;
            else if (u < 0.003f)
                in.double_tap = true;
            else if (u < 0.004f)
                in.button = true;
            if (rng_uniform(&r) < 0.003f) {               /* tilt, flip, put down */
                float g = rng_range(&r, -1.0f, 1.0f);
                in.gravity[0] = g;
                in.gravity[2] = -sqrtf(1.0f - g * g);
            }
            if (rng_uniform(&r) < 0.002f)
                in.familiar[rng_next(&r) & 1] = (uint8_t)(rng_next(&r) % 4u);
            if (rng_uniform(&r) < 0.01f) {                /* a theremin hand jumping about */
                in.pitch01 = rng_uniform(&r);
                in.volume01 = rng_uniform(&r);
            }
            if (rng_uniform(&r) < 0.001f)
                in.theremin_active = !in.theremin_active;
            if (rng_uniform(&r) < 0.002f)
                in.lev_holding = !in.lev_holding;
            if (rng_uniform(&r) < 0.002f) {               /* the loop: wait, hold, lost, fault, off */
                static const uint8_t ST[5] = {0, 2, 3, 4, 6};
                in.lev_state = ST[rng_next(&r) % 5u];
            }
            if (rng_uniform(&r) < 0.02f)                  /* the bat bobbing */
                in.lev_err_mm = rng_range(&r, -3.0f, 3.0f);
            if (rng_uniform(&r) < 0.001f)                 /* a spell */
                in.spell = (uint8_t)(1u + rng_next(&r) % 3u);
            if (!auto_lux && rng_uniform(&r) < 0.002f)    /* a hand over the light sensor, or not */
                in.lux = rng_uniform(&r) < 0.5f ? rng_range(&r, 1.0f, 30.0f) : rng_range(&r, 100.0f, 800.0f);
            if (rng_uniform(&r) < 0.002f)
                in.pendulum_choice = (int8_t)((int)(rng_next(&r) % 4u) - 1);
            if (rng_uniform(&r) < 0.001f)                 /* the 12 V adapter unplugged / back */
                led_engine_set_ceiling(&E, E.ceiling < 1.0f ? 1.0f : LED_USB_ONLY_CEILING);
            if (rng_uniform(&r) < 0.001f)                 /* the console */
                led_engine_override(&E, (int)(rng_next(&r) % LED_COUNT), rng_uniform(&r) < 0.3f ? -1.0f : rng_uniform(&r));
            if (rng_uniform(&r) < 0.0005f)
                led_engine_override_all(&E, -1.0f);
        }
        if (auto_lux && rng_uniform(&r) < 0.0004f)        /* the room lights */
            in.lux = in.lux > 10.0f ? 0.3f : 200.0f;
        scenes_render(&S, &in, target);
        led_engine_frame(&E, target);
        for (int i = 0; i < LED_COUNT; i++) {
            float d = fabsf(E.l_out[i] - prev_out[i]);
            if (d > st.worst_slew)
                st.worst_slew = d;
            CHECK(d <= LED_SLEW_PER_FRAME + 1e-6f, "SLEW: %s moved %.4f in a frame (limit %.4f), frame %d",
                  LED_MAP[i].name, d, LED_SLEW_PER_FRAME, f);
            float h = shown_l(i);
            float dh = fabsf(h - prev_hw[i]);
            float tol = LED_SLEW_PER_FRAME + 2.0f * step_l(i) + 1e-4f;
            if (dh - 2.0f * step_l(i) > st.worst_hw)
                st.worst_hw = dh - 2.0f * step_l(i);
            CHECK(dh <= tol, "HARDWARE: %s's registers moved %.4f in L (limit %.4f), frame %d", LED_MAP[i].name, dh,
                  tol, f);
            float ymax = led_colour_ceiling(LED_MAP[i].colour) * E.ceiling * E.master;
            float y = (float)E.duty[i] / LP5036_DUTY_FULL;
            /* the ceiling binds once the limiter has caught up (E.ceiling may just have dropped) */
            if (fabsf(E.l_out[i] - prev_out[i]) < LED_SLEW_PER_FRAME * 0.5f)
                CHECK(y <= ymax * 1.01f + 16.0f / LP5036_DUTY_FULL, "CEILING: %s at %.4f > %.4f", LED_MAP[i].name, y,
                      ymax);
            if (prev_target[i] >= 0.0f) {
                float td = fabsf(target[i] - prev_target[i]);
                if (td > st.max_target_step)
                    st.max_target_step = td;
                if (td > LED_SLEW_PER_FRAME + 1e-6f)
                    clipped++;
            }
            led_frames++;
            prev_out[i] = E.l_out[i];
            prev_hw[i] = h;
            prev_target[i] = target[i];
        }
        for (int d = 0; d < LED_DRIVERS; d++)
            for (int b = 0; b < LED_DRIVER_BANKS; b++) {
                CHECK(E.reg[d][b] >= 16, "BANKS: bank brightness %u < 16", E.reg[d][b]);
                for (int k = 0; k < 3; k++)
                    if (LED_OF_CHANNEL[d][3 * b + k] < 0)
                        CHECK(E.reg[d][LED_DRIVER_BANKS + 3 * b + k] == 0, "BANKS: unused output driven");
            }
    }
    st.frames = frames;
    st.clip_frac = led_frames ? (float)clipped / (float)led_frames : 0.0f;
    return st;
}

static void test_cie(void)
{
    /* L* 50 is Y 18.4 %; the curve is monotonic and inverts */
    CHECK(fabsf(led_l_to_y(0.5f) - 0.1842f) < 0.0005f, "L*50 -> %f", led_l_to_y(0.5f));
    float prev = -1.0f, worst = 0.0f;
    for (int k = 0; k <= 1000; k++) {
        float l = (float)k / 1000.0f;
        float y = led_l_to_y(l);
        CHECK(y >= prev, "not monotonic at %f", l);
        prev = y;
        float e = fabsf(led_y_to_l(y) - l);
        if (e > worst)
            worst = e;
    }
    CHECK(worst < 1e-4f, "L* round trip error %g", worst);
    printf("CIE L*: monotonic, round trip within %.1e, L*50 = %.2f %% luminance\n", worst, 100.0f * led_l_to_y(0.5f));
}

static void test_dither(void)
{
    /* a still target: the realised duty averages to it, and any pattern repeats fast */
    static const float levels[] = {0.004f, 0.012f, 0.03f, 0.08f, 0.2f, 0.45f, 0.7f, 0.95f};
    float worst_rel = 0.0f;
    int longest = 0;
    for (unsigned n = 0; n < sizeof levels / sizeof levels[0]; n++) {
        led_engine_init(&E);
        float target[LED_COUNT];
        for (int i = 0; i < LED_COUNT; i++)
            target[i] = levels[n] * (0.6f + 0.4f * (float)(i % 3) / 2.0f);   /* uneven banks */
        for (int f = 0; f < 400; f++)                                         /* settle */
            led_engine_frame(&E, target);
        double sum[LED_COUNT] = {0};
        uint16_t last[LED_COUNT];
        int run[LED_COUNT], longest_here[LED_COUNT];
        bool changed[LED_COUNT];
        for (int i = 0; i < LED_COUNT; i++) {
            last[i] = E.duty[i];
            run[i] = longest_here[i] = 0;
            changed[i] = false;
        }
        const int F = 2000;
        for (int f = 0; f < F; f++) {
            led_engine_frame(&E, target);
            for (int i = 0; i < LED_COUNT; i++) {
                sum[i] += E.duty[i];
                if (E.duty[i] == last[i]) {
                    run[i]++;
                } else {
                    changed[i] = true;
                    if (run[i] > longest_here[i])
                        longest_here[i] = run[i];
                    run[i] = 0;
                    last[i] = E.duty[i];
                }
            }
        }
        for (int i = 0; i < LED_COUNT; i++) {
            float want = led_l_to_y(E.l_out[i]) * LP5036_DUTY_FULL;
            float got = (float)(sum[i] / F);
            const led_info *m = &LED_MAP[i];
            float step = (float)E.reg[m->driver][m->channel / 3] / 16.0f;
            /* the deadband allows up to LED_DITHER_DEADBAND of a step of bias */
            float err = fabsf(got - want) / (step > 1.0f ? step : 1.0f);
            if (err > worst_rel)
                worst_rel = err;
            CHECK(err <= LED_DITHER_DEADBAND + 0.02f, "dither average %s: %.2f vs %.2f (step %.1f)", m->name, got,
                  want, step);
            if (changed[i] && longest_here[i] + 1 > longest)
                longest = longest_here[i] + 1;
        }
    }
    printf("dither: average within %.2f of a step of the target; slowest pattern repeats every %d frames "
           "(%.0f Hz)\n", worst_rel, longest, (float)LED_FPS / (float)longest);
    CHECK(longest <= (int)(1.0f / LED_DITHER_DEADBAND) + 1, "a dither pattern %d frames long", longest);
}

/* play: each input lights its own LEDs, at full, within a second */
static void play_frames(scene_inputs *in, float secs, float *out)
{
    int n = (int)(secs * (float)LED_FPS);
    for (int k = 0; k < n; k++) {
        scenes_render(&S, in, out);
        in->tap = in->double_tap = in->button = false;
        in->spell = 0;
    }
}

static void test_play(void)
{
    float f[LED_COUNT];
    scene_inputs in;
    memset(&in, 0, sizeof in);
    in.dt_s = 1.0f / (float)LED_FPS;
    in.lux = 300.0f;
    in.pendulum_choice = -1;
    scenes_init(&S, 5u);
    scenes_select(&S, SCENE_PLAY);
    play_frames(&in, 3.0f, f);
    CHECK(f[LED_GROUP_PUMPKIN[0]] > 0.35f, "PLAY: idle pumpkins dark (%.2f)", f[LED_GROUP_PUMPKIN[0]]);
    CHECK(f[LED_GROUP_STAR[5]] == 0.0f && f[LED_GROUP_PERCH_DOWN[0]] == 0.0f, "PLAY: idle, something lit that should not be");
    {   /* the rings' breathing chase: two neighbours trade, round once a second (Jason, 2026-11-10) */
        float lo = 1.0f, hi = 0.0f, smin = 1.0f, smax = 0.0f;
        int most_lit = 0;
        for (int k = 0; k < 4 * (int)LED_FPS; k++) {
            play_frames(&in, 1.0f / (float)LED_FPS, f);
            lo = fminf(lo, f[LED_GROUP_OWLRING[0]]);
            hi = fmaxf(hi, f[LED_GROUP_OWLRING[0]]);
            float sum = 0.0f;
            int lit = 0;
            for (int i = 0; i < 3; i++) {
                sum += f[LED_GROUP_CATRING[i]];
                lit += f[LED_GROUP_CATRING[i]] > 0.01f;
            }
            smin = fminf(smin, sum);
            smax = fmaxf(smax, sum);
            most_lit = lit > most_lit ? lit : most_lit;
        }
        CHECK(lo < 0.01f && hi > 0.3f && hi < 0.4f, "PLAY: a ring's LED should breathe from dark to its peak (%.2f..%.2f)",
              lo, hi);
        CHECK(smin > 0.3f && smax < 0.4f && most_lit <= 2, "PLAY: a ring's chase: two LEDs share one brightness "
              "(sum %.2f..%.2f, up to %d lit)", smin, smax, most_lit);
    }
    CHECK(scenes_current(&S) == SCENE_PLAY, "PLAY: left play in daylight");

    in.theremin_active = true; in.pitch01 = 1.0f; in.volume01 = 1.0f;
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_STAR[0]] > 0.95f && f[LED_GROUP_STAR[11]] > 0.95f, "PLAY: theremin at top pitch, arc not full (%.2f, %.2f)",
          f[LED_GROUP_STAR[0]], f[LED_GROUP_STAR[11]]);
    CHECK(f[LED_GROUP_PUMPKIN[1]] > 0.95f, "PLAY: theremin at full volume, pumpkin %.2f", f[LED_GROUP_PUMPKIN[1]]);
    in.pitch01 = 0.25f;
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_STAR[0]] > 0.95f && f[LED_GROUP_STAR[11]] < 0.05f, "PLAY: a low pitch should fill from the moon only");
    in.theremin_active = false;
    play_frames(&in, 1.5f, f);
    CHECK(f[LED_GROUP_STAR[0]] < 0.05f, "PLAY: the arc stays after the hand leaves (%.2f)", f[LED_GROUP_STAR[0]]);

    {   /* a token on its target: its ring fades out, the other keeps turning; back when it leaves */
        in.familiar[0] = FAMILIAR_OWL;
        play_frames(&in, 1.0f, f);
        float owl = 0.0f, cat = 0.0f;
        for (int k = 0; k < (int)LED_FPS; k++) {
            play_frames(&in, 1.0f / (float)LED_FPS, f);
            for (int i = 0; i < 3; i++) {
                owl = fmaxf(owl, f[LED_GROUP_OWLRING[i]]);
                cat = fmaxf(cat, f[LED_GROUP_CATRING[i]]);
            }
        }
        CHECK(owl < 0.01f && cat > 0.3f, "PLAY: owl token on: its ring %.2f (want dark), the cat's %.2f", owl, cat);
        in.familiar[0] = FAMILIAR_NONE; in.familiar[1] = FAMILIAR_CAT;
        play_frames(&in, 1.0f, f);
        owl = cat = 0.0f;
        for (int k = 0; k < (int)LED_FPS; k++) {
            play_frames(&in, 1.0f / (float)LED_FPS, f);
            for (int i = 0; i < 3; i++) {
                owl = fmaxf(owl, f[LED_GROUP_OWLRING[i]]);
                cat = fmaxf(cat, f[LED_GROUP_CATRING[i]]);
            }
        }
        CHECK(cat < 0.01f && owl > 0.3f, "PLAY: cat token on: its ring %.2f (want dark), the owl's back %.2f", cat, owl);
        in.familiar[1] = FAMILIAR_NONE;
    }

    /* the bat */
    float lo = 1.0f, hi = 0.0f;
    in.lev_state = 2;                                       /* waiting: breathing */
    for (int k = 0; k < 2 * (int)LED_FPS; k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        lo = fminf(lo, f[LED_GROUP_PERCH_DOWN[0]]); hi = fmaxf(hi, f[LED_GROUP_PERCH_DOWN[0]]);
    }
    CHECK(lo < 0.4f && hi > 0.65f, "PLAY: waiting, the downlights should breathe (%.2f..%.2f)", lo, hi);
    in.lev_state = 3; in.lev_err_mm = 0.1f;                 /* caught, then locked */
    lo = 1.0f;
    for (int k = 0; k < (int)LED_FPS / 2; k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        lo = fminf(lo, f[LED_GROUP_PERCH_DOWN[1]]);
    }
    CHECK(lo < 0.7f, "PLAY: catching, the downlights should pulse (low %.2f)", lo);
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_PERCH_DOWN[1]] > 0.99f, "PLAY: locked, downlights %.2f", f[LED_GROUP_PERCH_DOWN[1]]);
    CHECK(fabsf(f[LED_GROUP_OWLEYE[0]] - 0.35f) < 0.01f && fabsf(f[LED_GROUP_OWLEYE[1]] - 0.35f) < 0.01f,
          "PLAY: locked, owl A's eyes %.2f %.2f", f[LED_GROUP_OWLEYE[0]], f[LED_GROUP_OWLEYE[1]]);
    in.lev_err_mm = -2.0f;                                  /* too close */
    play_frames(&in, 0.1f, f);
    CHECK(f[LED_GROUP_OWLEYE[0]] > 0.95f && f[LED_GROUP_OWLEYE[1]] == 0.0f, "PLAY: too close, eyes %.2f %.2f",
          f[LED_GROUP_OWLEYE[0]], f[LED_GROUP_OWLEYE[1]]);
    in.lev_err_mm = 1.2f;                                   /* too far */
    play_frames(&in, 0.1f, f);
    CHECK(f[LED_GROUP_OWLEYE[1]] > 0.6f && f[LED_GROUP_OWLEYE[0]] == 0.0f, "PLAY: too far, eyes %.2f %.2f",
          f[LED_GROUP_OWLEYE[0]], f[LED_GROUP_OWLEYE[1]]);
    in.lev_state = 4;                                       /* lost: pulses, then dark */
    play_frames(&in, 2.5f, f);
    CHECK(f[LED_GROUP_PERCH_DOWN[0]] == 0.0f, "PLAY: lost, the downlights stay on");
    in.lev_state = 0;

    /* a hand over the light sensor */
    in.lux = 30.0f;
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_TSTAR[0]] > 0.95f && f[LED_GROUP_OWLEYE[2]] > 0.95f, "PLAY: shaded, tree star %.2f, owl B %.2f",
          f[LED_GROUP_TSTAR[0]], f[LED_GROUP_OWLEYE[2]]);
    in.lux = 300.0f;
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_TSTAR[0]] < 0.05f, "PLAY: the shade stays after the hand leaves (%.2f)", f[LED_GROUP_TSTAR[0]]);

    /* a tap: every star flashes once, at its own moment, within 1.5 s */
    float peak[LED_COUNT] = {0};
    in.tap = true;
    for (int k = 0; k < (int)(1.6f * (float)LED_FPS); k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        for (int i = 0; i < LED_COUNT; i++)
            peak[i] = fmaxf(peak[i], f[i]);
    }
    int lit = 0;
    for (int k = 0; k < LED_N_STAR; k++)
        lit += peak[LED_GROUP_STAR[k]] > 0.9f;
    CHECK(lit == LED_N_STAR && peak[LED_GROUP_TSTAR[3]] > 0.9f && peak[LED_GROUP_WISP[0]] < 0.01f,
          "PLAY: a tap: %d of %d arc stars flashed; a wisp %.2f", lit, LED_N_STAR, peak[LED_GROUP_WISP[0]]);
    play_frames(&in, 0.5f, f);
    CHECK(f[LED_GROUP_STARX[0]] == 0.0f, "PLAY: the twinkle stays");
    in.double_tap = true;
    memset(peak, 0, sizeof peak);
    for (int k = 0; k < (int)(1.6f * (float)LED_FPS); k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        for (int i = 0; i < LED_COUNT; i++)
            peak[i] = fmaxf(peak[i], f[i]);
    }
    CHECK(peak[LED_GROUP_WISP[3]] > 0.9f && peak[LED_GROUP_TWISP[1]] > 0.9f, "PLAY: a double tap, the wisps %.2f %.2f",
          peak[LED_GROUP_WISP[3]], peak[LED_GROUP_TWISP[1]]);

    /* the spells */
    in.spell = 1;                                           /* the ghost on the arc */
    memset(peak, 0, sizeof peak);
    for (int k = 0; k < 3 * (int)LED_FPS; k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        in.spell = 0;
        for (int j = 0; j < LED_N_STAR; j++)
            peak[LED_GROUP_STAR[j]] = fmaxf(peak[LED_GROUP_STAR[j]], f[LED_GROUP_STAR[j]]);
    }
    lit = 0;
    for (int j = 0; j < LED_N_STAR; j++)
        lit += peak[LED_GROUP_STAR[j]] > 0.3f;
    CHECK(lit >= 3, "PLAY: the ghost lit only %d arc stars", lit);
    play_frames(&in, 3.5f, f);
    CHECK(f[LED_GROUP_STAR[6]] == 0.0f, "PLAY: the ghost stays");
    in.spell = 2;                                           /* everything wakes */
    play_frames(&in, 0.4f, f);
    CHECK(f[LED_GROUP_WISP[2]] > 0.95f && f[LED_GROUP_OWLEYE[4]] > 0.95f && f[LED_GROUP_STARX[1]] > 0.95f,
          "PLAY: wake: wisp %.2f, owl C %.2f, star %.2f", f[LED_GROUP_WISP[2]], f[LED_GROUP_OWLEYE[4]], f[LED_GROUP_STARX[1]]);
    play_frames(&in, 2.5f, f);
    CHECK(f[LED_GROUP_WISP[2]] == 0.0f, "PLAY: the wake stays");
    in.spell = 3;                                           /* a twinkle (and main's chirp) */
    float pk = 0.0f;
    for (int k = 0; k < (int)(1.6f * (float)LED_FPS); k++) {
        play_frames(&in, 1.0f / (float)LED_FPS, f);
        in.spell = 0;
        pk = fmaxf(pk, f[LED_GROUP_STAR[4]]);
    }
    CHECK(pk > 0.9f, "PLAY: the third spell's twinkle %.2f", pk);

    /* the pendulum's choice */
    in.pendulum_choice = 2;
    play_frames(&in, 1.0f, f);
    CHECK(f[LED_GROUP_PUMPKIN[2]] > 0.8f, "PLAY: chosen pumpkin %.2f", f[LED_GROUP_PUMPKIN[2]]);
    printf("play: every input lights its LEDs\n");
}

int main(void)
{
    test_play();
    test_cie();
    test_dither();

    printf("%-9s %8s %10s %12s %14s %12s\n", "scene", "frames", "max |dL|", "hw max |dL|", "scene's step", "limiter on");
    float worst = 0.0f;
    for (int sc = 0; sc < SCENE_COUNT; sc++) {
        scenes_init(&S, 1234u + (uint32_t)sc);
        led_engine_init(&E);
        scenes_select(&S, (scene_id)sc);
        float secs = sc == SCENE_FIREFLY ? 150.0f : 60.0f;
        run_stats a = run(secs, false, 99u + (uint32_t)sc, false);     /* the scene alone */
        run_stats b = run(secs, true, 7u + (uint32_t)sc, false);       /* and with everything happening */
        printf("%-9s %8ld %10.4f %12.4f %14.4f %11.3f%%   (alone: limiter on %.3f%%)\n", scene_name((scene_id)sc),
               a.frames + b.frames, fmaxf(a.worst_slew, b.worst_slew), fmaxf(a.worst_hw, b.worst_hw),
               fmaxf(a.max_target_step, b.max_target_step), 100.0f * b.clip_frac, 100.0f * a.clip_frac);
        if (fmaxf(a.worst_slew, b.worst_slew) > worst)
            worst = fmaxf(a.worst_slew, b.worst_slew);
    }
    /* the automatic sequence: the room's lights going on and off, taps, everything */
    scenes_init(&S, 42u);
    led_engine_init(&E);
    run_stats c = run(1800.0f, true, 4242u, true);
    printf("%-9s %8ld %10.4f %12.4f %14.4f %11.3f%%\n", "auto 30m", c.frames, c.worst_slew, c.worst_hw,
           c.max_target_step, 100.0f * c.clip_frac);
    if (c.worst_slew > worst)
        worst = c.worst_slew;
    printf("largest per-frame change of any LED in any scene: %.4f of full lightness (limit %.4f = 0 to full in "
           "%.0f ms)\n", worst, LED_SLEW_PER_FRAME, 1000.0f * LED_FADE_MIN_S);

    if (failures) {
        printf("test_leds: %d FAILED\n", failures);
        return 1;
    }
    printf("test_leds: all passed\n");
    return 0;
}
