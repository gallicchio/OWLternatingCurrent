/* voice.c: see voice.h. */
#include "voice.h"
#include "config.h"
#include <math.h>
#include <string.h>

static float table[VOICE_TABLE + 1];
static int table_ready;

float voice_sine(float c)
{
    c -= floorf(c);
    float x = c * (float)VOICE_TABLE;
    int i = (int)x;
    float f = x - (float)i;
    return table[i] + (table[i + 1] - table[i]) * f;
}

void voice_init(voice *v, float sample_hz)
{
    if (!table_ready) {
        for (int i = 0; i <= VOICE_TABLE; i++)
            table[i] = sinf(6.28318531f * (float)i / (float)VOICE_TABLE);
        table_ready = 1;
    }
    memset(v, 0, sizeof *v);
    v->sample_hz = sample_hz;
    v->freq = v->target_freq = THEREMIN_F_LO_HZ;
    v->k_attack = 1.0f - expf(-1.0f / (VOICE_ATTACK_S * sample_hz));
    v->k_release = 1.0f - expf(-1.0f / (VOICE_RELEASE_S * sample_hz));
    v->k_glide = 1.0f - expf(-1.0f / (VOICE_GLIDE_S * sample_hz));
}

void voice_set(voice *v, float freq_hz, float amp)
{
    if (!(freq_hz > 20.0f))
        freq_hz = 20.0f;
    if (freq_hz > 0.45f * v->sample_hz)
        freq_hz = 0.45f * v->sample_hz;
    if (!(amp > 0.0f))
        amp = 0.0f;
    if (amp > AUDIO_VOLUME_CEILING)
        amp = AUDIO_VOLUME_CEILING;
    if (v->target_amp <= 0.0f && amp > 0.0f) {
        v->onset_s = 0.0f;              /* a new note */
        if (v->amp < 1e-4f)
            v->freq = freq_hz;          /* start at its pitch, no glide from the last */
    }
    v->target_freq = freq_hz;
    v->target_amp = amp;
}

void voice_render(voice *v, float *out, int n)
{
    const float dt = 1.0f / v->sample_hz;
    for (int i = 0; i < n; i++) {
        v->amp += (v->target_amp - v->amp) * (v->target_amp > v->amp ? v->k_attack : v->k_release);
        v->freq += (v->target_freq - v->freq) * v->k_glide;
        if (v->amp < 1e-3f && v->target_amp <= 0.0f) {   /* -60 dB: silence (from full, 2.4 s after the release) */
            out[i] = 0.0f;
            continue;
        }
        v->onset_s += dt;
        float depth = VOICE_VIBRATO * (v->onset_s < VOICE_VIBRATO_IN_S ? v->onset_s / VOICE_VIBRATO_IN_S : 1.0f);
        v->vib_phase += VOICE_VIBRATO_HZ * dt;
        if (v->vib_phase >= 1.0f)
            v->vib_phase -= 1.0f;
        float f = v->freq * (1.0f + depth * voice_sine(v->vib_phase));
        v->phase += f * dt;
        if (v->phase >= 1.0f)
            v->phase -= 1.0f;
        float s = voice_sine(v->phase) + 0.12f * voice_sine(2.0f * v->phase) + 0.05f * voice_sine(3.0f * v->phase);
        out[i] = v->amp * s * (1.0f / 1.17f);
    }
}
