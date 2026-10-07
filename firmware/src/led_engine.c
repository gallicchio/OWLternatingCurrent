/* led_engine.c: targets -> slew limit -> CIE L* -> 12-bit duty -> bank split and dither.
 * led_engine.h describes the pipeline. */
#include "led_engine.h"
#include <ctype.h>
#include <math.h>
#include <string.h>

/* CIE 1976: L* = 116 (Y)^(1/3) - 16 above Y = (6/29)^3, linear below (kappa = 903.3) */
#define CIE_KAPPA   903.2963f
#define CIE_EPSILON 0.008856452f

float led_l_to_y(float l)
{
    if (!(l > 0.0f))
        return 0.0f;                     /* also NaN */
    if (l > 1.0f)
        l = 1.0f;
    float L = 100.0f * l;
    if (L <= 8.0f)
        return L / CIE_KAPPA;
    float f = (L + 16.0f) / 116.0f;
    return f * f * f;
}

float led_y_to_l(float y)
{
    if (!(y > 0.0f))
        return 0.0f;
    if (y > 1.0f)
        y = 1.0f;
    if (y <= CIE_EPSILON)
        return y * CIE_KAPPA / 100.0f;
    return (116.0f * cbrtf(y) - 16.0f) / 100.0f;
}

float led_colour_ceiling(unsigned colour)
{
    switch (colour) {
    case LED_COL_ORANGE: return LED_CEIL_ORANGE;
    case LED_COL_AMBER5050: return LED_CEIL_AMBER5050;
    case LED_COL_VIOLET: return LED_CEIL_VIOLET;
    case LED_COL_PURPLE: return LED_CEIL_PURPLE;
    default: return 0.0f;
    }
}

void led_engine_init(led_engine *e)
{
    memset(e, 0, sizeof *e);
    for (int i = 0; i < LED_COUNT; i++)
        e->override_l[i] = -1.0f;
    e->ceiling = 1.0f;
    e->master = 1.0f;
    for (int d = 0; d < LED_DRIVERS; d++) {
        e->driver_present[d] = true;
        for (int b = 0; b < LED_DRIVER_BANKS; b++)
            e->reg[d][b] = 16;
    }
}

void led_engine_set_ceiling(led_engine *e, float f) { e->ceiling = f < 0.0f ? 0.0f : f > 1.0f ? 1.0f : f; }

void led_engine_set_master(led_engine *e, float f) { e->master = f < 0.0f ? 0.0f : f > 1.0f ? 1.0f : f; }

void led_engine_override(led_engine *e, int led, float level)
{
    if (led < 0 || led >= LED_COUNT)
        return;
    e->override_l[led] = level < 0.0f ? -1.0f : level > 1.0f ? 1.0f : level;
}

void led_engine_override_all(led_engine *e, float level)
{
    for (int i = 0; i < LED_COUNT; i++)
        led_engine_override(e, i, level);
}

int led_engine_find(const char *name)
{
    for (int i = 0; i < LED_COUNT; i++) {
        const char *a = LED_MAP[i].name, *b = name;
        while (*a && *b && toupper((unsigned char)*a) == toupper((unsigned char)*b)) {
            a++;
            b++;
        }
        if (!*a && !*b)
            return i;
    }
    return -1;
}

void led_engine_driver_reset(led_engine *e, int driver)
{
    for (int i = 0; i < LED_COUNT; i++)
        if (LED_MAP[i].driver == driver) {
            e->l_out[i] = 0.0f;
            e->dither[i] = 0.0f;
        }
}

/* The colour register for a wanted duty (in 12-bit steps) in a bank at brightness B:
 * error diffusion in the chip's own duty units (so its truncation of C * B / 16 is
 * accounted for), the error carried to the next frame.  A wanted duty within
 * LED_DITHER_DEADBAND of a step of a level the chip can make is rounded to it and
 * the carry dropped, so a dither pattern repeats at least every 1 / LED_DITHER_DEADBAND
 * frames (a slower one would be a visible twinkle). */
static unsigned pick_colour(float want, float *carry, unsigned B)
{
    float w = want + *carry;
    if (!(w > 0.0f)) {
        *carry = 0.0f;
        return 0;
    }
    int c = (int)(w * 16.0f / (float)B);
    if (c > 255)
        c = 255;
    while (c < 255 && (float)lp5036_duty12((unsigned)c + 1u, B) <= w)
        c++;
    while (c > 0 && (float)lp5036_duty12((unsigned)c, B) > w)
        c--;
    float lo = (float)lp5036_duty12((unsigned)c, B);
    float hi = c < 255 ? (float)lp5036_duty12((unsigned)c + 1u, B) : lo;
    if (hi <= lo) {                      /* at the top: as close as it gets */
        *carry = 0.0f;
        return (unsigned)c;
    }
    float f = (w - lo) / (hi - lo);
    unsigned out;
    if (f < LED_DITHER_DEADBAND) {
        out = (unsigned)c;
        *carry = 0.0f;
    } else if (f > 1.0f - LED_DITHER_DEADBAND) {
        out = (unsigned)c + 1u;
        *carry = 0.0f;
    } else {
        out = f >= 0.5f ? (unsigned)c + 1u : (unsigned)c;
        *carry = w - (float)lp5036_duty12(out, B);
    }
    return out;
}

void led_engine_frame(led_engine *e, const float target_l[LED_COUNT])
{
    /* targets, ceilings, slew limit: all in L */
    for (int i = 0; i < LED_COUNT; i++) {
        float l = e->override_l[i] >= 0.0f ? e->override_l[i] : target_l[i];
        float y = led_l_to_y(l) * led_colour_ceiling(LED_MAP[i].colour) * e->ceiling * e->master;
        float d = led_y_to_l(y) - e->l_out[i];
        if (d > LED_SLEW_PER_FRAME)
            d = LED_SLEW_PER_FRAME;
        else if (d < -LED_SLEW_PER_FRAME)
            d = -LED_SLEW_PER_FRAME;
        e->l_out[i] += d;
        if (e->l_out[i] < 0.0f)
            e->l_out[i] = 0.0f;
    }

    /* each bank: brightness B for the brightest, colours C, dithered */
    for (int drv = 0; drv < LED_DRIVERS; drv++) {
        for (int bank = 0; bank < LED_DRIVER_BANKS; bank++) {
            float want[3] = {0.0f, 0.0f, 0.0f};
            int idx[3];
            float most = 0.0f;
            for (int k = 0; k < 3; k++) {
                idx[k] = LED_OF_CHANNEL[drv][3 * bank + k];
                if (idx[k] >= 0) {
                    want[k] = led_l_to_y(e->l_out[idx[k]]) * LP5036_DUTY_FULL;
                    if (want[k] > most)
                        most = want[k];
                }
            }
            /* duty = C * B / 16: B = 16 makes one step of C one step of the PWM */
            int B = (int)ceilf(most * 16.0f / 255.0f);
            if (B < 16)
                B = 16;
            if (B > 255)
                B = 255;
            e->reg[drv][bank] = (uint8_t)B;
            for (int k = 0; k < 3; k++) {
                int ch = 3 * bank + k;
                unsigned c = 0;
                if (idx[k] >= 0) {
                    c = pick_colour(want[k], &e->dither[idx[k]], (unsigned)B);
                    e->duty[idx[k]] = lp5036_duty12(c, (unsigned)B);
                }
                e->reg[drv][LED_DRIVER_BANKS + ch] = (uint8_t)c;
            }
        }
    }
    e->frames++;
}
