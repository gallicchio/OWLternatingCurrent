/* noise.h: a small random number generator and smooth noise for the scenes.
 *
 * Value noise: random values on the integers, joined by the quintic fade
 * (6t^5 - 15t^4 + 10t^3), so it is smooth (C2) with a bounded slope: at most
 * 3.75 per unit of x for one octave of amplitude 1.  The fractal sum adds
 * octaves at doubling frequencies with amplitudes gain^k, normalised to -1..1:
 * gain 0.71 is about 1/f ("pink"), the candle's flicker.
 *
 * Portable: no SDK.
 */
#pragma once
#include <stdint.h>

typedef struct {
    uint32_t s;
} rng32;

static inline void rng_seed(rng32 *r, uint32_t seed) { r->s = seed ? seed : 0x9e3779b9u; }

/* xorshift32 */
static inline uint32_t rng_next(rng32 *r)
{
    uint32_t x = r->s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return r->s = x;
}

float rng_uniform(rng32 *r);                     /* [0, 1) */
float rng_range(rng32 *r, float lo, float hi);   /* [lo, hi) */
float rng_gauss(rng32 *r);                       /* mean 0, sd 1 */

uint32_t noise_hash(uint32_t x);
float noise_value(uint32_t seed, float x);       /* -1..1, smooth */
float noise_fractal(uint32_t seed, float x, int octaves, float gain);   /* -1..1 */
/* the largest slope of noise_fractal(seed, f*t, ...) per second, for checking a scene's speed */
float noise_fractal_max_slope(float f_hz, int octaves, float gain);

static inline float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }
static inline float smoothstepf(float e0, float e1, float x)
{
    float t = clampf((x - e0) / (e1 - e0), 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}
