/* voice.c: see voice.h. */
#include "voice.h"
#include "config.h"
#include <math.h>
#include <string.h>

static float table[VOICE_TABLE + 1];

/* First pass at equalising the voice to LS1 (Jason, 2026-11-07: "the firmware should
 * compensate for the resonant behavior of the speaker"): constant ELECTRICAL power.
 * From bringup/results/2026-11-07/131913_speaker.json: the 12 V current a full-scale tone
 * adds, d(f), is the power the amplifier delivers into the speaker (over 12 V and its
 * efficiency).  At a fixed amplitude d falls from 26.4 mA at 200 Hz to 25.3 mA at 1 kHz,
 * dips to 21.2 mA at the cone's 1.8 kHz resonance (an impedance peak) and falls to
 * 18.7 mA at 4 kHz (the voice coil's inductance).  The gain is sqrt(d(1 kHz) / d(f)):
 * 0.98-1.00 over the theremin's 200-1000 Hz, up to 1.16 at 4 kHz.  It equalises what the
 * speaker takes, not what it radiates: a small cone's sound output falls steeply below
 * its resonance, which no electrical measurement sees.  The acoustic table (a microphone
 * at 1 m) replaces this one after the owl and bat (bringup/REVB.md 1.2). */
static const float EQ_HZ[] = {200, 300, 400, 500, 700, 900, 1100, 1300, 1500, 1600,
                              1700, 1800, 1900, 2000, 2200, 2500, 3000, 3500, 4000};
static const float EQ_GAIN[] = {0.9801f, 0.9871f, 0.9878f, 0.9891f, 0.9923f, 0.9969f, 1.0028f,
                                1.0097f, 1.0227f, 1.0351f, 1.0587f, 1.0925f, 1.0517f, 1.0348f,
                                1.0440f, 1.0612f, 1.0919f, 1.1265f, 1.1644f};
#define EQ_N ((int)(sizeof EQ_HZ / sizeof EQ_HZ[0]))

float voice_eq_gain(float f)
{
    if (!(f > EQ_HZ[0]))
        return EQ_GAIN[0];
    if (f >= EQ_HZ[EQ_N - 1])
        return EQ_GAIN[EQ_N - 1];
    int i = 0;
    while (f > EQ_HZ[i + 1])
        i++;
    float x = logf(f / EQ_HZ[i]) / logf(EQ_HZ[i + 1] / EQ_HZ[i]);   /* in log f */
    return EQ_GAIN[i] + (EQ_GAIN[i + 1] - EQ_GAIN[i]) * x;
}
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
    /* the speaker's equalisation, once a buffer (a few ms) at the pitch now; capped so the
     * output never exceeds the ceiling (|s| <= 1.17 below, so |out| <= amp x g) */
    float g = voice_eq_gain(v->freq);
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
        float a = v->amp * g;
        if (a > AUDIO_VOLUME_CEILING)
            a = AUDIO_VOLUME_CEILING;
        out[i] = a * s * (1.0f / 1.17f);
    }
}
