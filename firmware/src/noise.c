/* noise.c: see noise.h. */
#include "noise.h"
#include <math.h>

float rng_uniform(rng32 *r) { return (float)(rng_next(r) >> 8) * (1.0f / 16777216.0f); }

float rng_range(rng32 *r, float lo, float hi) { return lo + (hi - lo) * rng_uniform(r); }

float rng_gauss(rng32 *r)
{
    /* Box-Muller, one of the pair */
    float u = rng_uniform(r);
    float v = rng_uniform(r);
    if (u < 1e-7f)
        u = 1e-7f;
    return sqrtf(-2.0f * logf(u)) * cosf(6.2831853f * v);
}

/* a 32-bit integer hash (Chris Wellons' lowbias32) */
uint32_t noise_hash(uint32_t x)
{
    x ^= x >> 16;
    x *= 0x7feb352du;
    x ^= x >> 15;
    x *= 0x846ca68bu;
    x ^= x >> 16;
    return x;
}

static float lattice(uint32_t seed, int32_t i)
{
    uint32_t h = noise_hash(seed * 0x9e3779b1u ^ (uint32_t)i);
    return (float)(h >> 8) * (2.0f / 16777216.0f) - 1.0f;
}

float noise_value(uint32_t seed, float x)
{
    float fl = floorf(x);
    int32_t i = (int32_t)fl;
    float t = x - fl;
    float f = t * t * t * (t * (t * 6.0f - 15.0f) + 10.0f);
    float a = lattice(seed, i), b = lattice(seed, i + 1);
    return a + (b - a) * f;
}

float noise_fractal(uint32_t seed, float x, int octaves, float gain)
{
    float sum = 0.0f, amp = 1.0f, norm = 0.0f, freq = 1.0f;
    for (int k = 0; k < octaves; k++) {
        sum += amp * noise_value(seed + 101u * (uint32_t)k, x * freq);
        norm += amp;
        amp *= gain;
        freq *= 2.0f;
    }
    return norm > 0.0f ? sum / norm : 0.0f;
}

float noise_fractal_max_slope(float f_hz, int octaves, float gain)
{
    /* each octave: |b - a| <= 2, the fade's slope <= 1.875 */
    float s = 0.0f, amp = 1.0f, norm = 0.0f, freq = 1.0f;
    for (int k = 0; k < octaves; k++) {
        s += amp * 3.75f * freq;
        norm += amp;
        amp *= gain;
        freq *= 2.0f;
    }
    return norm > 0.0f ? f_hz * s / norm : 0.0f;
}
