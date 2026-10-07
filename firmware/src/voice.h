/* voice.h: the ghost's "woo": a soft sine voice for the theremin.
 *
 * A sine with a little second and third harmonic (hollow, flute-like), a slow
 * vibrato that deepens after the note starts, a glide between pitches, and a soft
 * attack and release, so nothing clicks.  Samples in -1..1 at sample_hz; the
 * amplitude can never exceed AUDIO_VOLUME_CEILING (config.h): quiet by default.
 * Portable: no SDK; a sine table, no sinf per sample.
 */
#pragma once

#define VOICE_ATTACK_S     0.12f   /* [CHOICE] */
#define VOICE_RELEASE_S    0.35f
#define VOICE_GLIDE_S      0.06f
#define VOICE_VIBRATO_HZ   5.5f
#define VOICE_VIBRATO      0.012f  /* +-1.2 % at full depth */
#define VOICE_VIBRATO_IN_S 0.6f    /* depth grows over this after the onset */
#define VOICE_TABLE        1024

typedef struct {
    float sample_hz;
    float phase, vib_phase;        /* in cycles, 0..1 */
    float freq, target_freq;
    float amp, target_amp;
    float onset_s;
    float k_attack, k_release, k_glide;
} voice;

void voice_init(voice *v, float sample_hz);
void voice_set(voice *v, float freq_hz, float amp);     /* amp is capped at AUDIO_VOLUME_CEILING */
void voice_render(voice *v, float *out, int n);
float voice_sine(float cycles);                         /* the table, for the test */
