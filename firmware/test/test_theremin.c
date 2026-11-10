/* test_theremin.c: the theremin's mapping (src/theremin.c) and voice (src/voice.c).
 *
 *   - calibration finds the baselines; no hand, no sound, even while the
 *     oscillators drift slowly (the drift is tracked);
 *   - a hand approaching the moon raises the pitch monotonically from
 *     THEREMIN_F_LO_HZ to THEREMIN_F_HI_HZ, exponentially (equal steps of the hand
 *     make equal musical intervals);
 *   - a hand at the pumpkin opens the volume; a dead oscillator silences it;
 *   - the voice sings at the asked pitch, never louder than AUDIO_VOLUME_CEILING,
 *     and starts and stops without a click;
 *   - the voice's speaker equalisation keeps the electrical power into LS1 the same
 *     across the pitch range (the bench's measurement), still under the ceiling.
 */
#include "config.h"
#include "theremin.h"
#include "voice.h"
#include <math.h>
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

#define DT (THEREMIN_WINDOW_MS / 1000.0f)

/* the oscillators as PIO would count them: a whole number of edges per window */
static float counted(float f) { return floorf(f * DT) / DT; }

static void run(theremin *t, float fp, float fv, float seconds)
{
    for (float s = 0.0f; s < seconds; s += DT)
        theremin_update(t, counted(fp), counted(fv), DT);
}

int main(void)
{
    theremin t;
    const float FP = 700e3f, FV = 600e3f;
    theremin_init(&t);
    run(&t, FP, FV, 1.5f);
    CHECK(t.calibrated, "not calibrated");
    CHECK(fabsf(t.f0_pitch - FP) / FP < 2e-4f && fabsf(t.f0_vol - FV) / FV < 2e-4f, "baselines %f %f", t.f0_pitch,
          t.f0_vol);
    CHECK(!t.active && t.volume == 0.0f, "sound with no hand");

    /* slow drift, nobody playing: 1 % over two minutes */
    bool false_alarm = false;
    for (int i = 0; i < (int)(120.0f / DT); i++) {
        float d = 1.0f - 0.01f * (float)i * DT / 120.0f;
        theremin_update(&t, counted(FP * d), counted(FV * d), DT);
        if (t.active || t.volume > 0.0f)
            false_alarm = true;
    }
    CHECK(!false_alarm, "a slow drift was taken for a hand");
    printf("drift: 1 %% over 2 min, no false note; baseline now %.0f Hz (followed %.0f %%)\n", t.f0_pitch,
           100.0f * (FP - t.f0_pitch) / (FP * 0.01f));

    /* the hand approaches the moon: pitch rises monotonically, exponentially */
    theremin_init(&t);
    run(&t, FP, FV, 1.5f);
    float prev = 0.0f, lo = 0.0f, hi = 0.0f;
    bool mono = true;
    for (int k = 0; k <= 30; k++) {
        float drop = THEREMIN_PITCH_SPAN * (float)k / 30.0f;
        run(&t, FP * (1.0f - drop), FV * (1.0f - THEREMIN_VOL_SPAN), 0.3f);
        if (k == 0)
            lo = t.pitch_hz;
        if (t.pitch_hz < prev - 0.5f)
            mono = false;
        prev = t.pitch_hz;
        hi = t.pitch_hz;
    }
    printf("pitch: %.0f Hz with the hand away .. %.0f Hz at the moon\n", lo, hi);
    CHECK(mono, "pitch not monotonic");
    CHECK(fabsf(lo - THEREMIN_F_LO_HZ) < 5.0f && fabsf(hi - THEREMIN_F_HI_HZ) < 10.0f, "range %f..%f", lo, hi);
    CHECK(t.active && t.volume > 0.95f, "full volume at the pumpkin: %f", t.volume);

    /* volume: hand away, then a little, then close */
    run(&t, FP, FV, 0.5f);
    CHECK(!t.active && t.volume == 0.0f, "hand away: volume %f", t.volume);
    run(&t, FP, FV * (1.0f - 0.5f * THEREMIN_VOL_SPAN), 0.5f);
    CHECK(t.active && t.volume > 0.3f && t.volume < 0.7f, "half way: volume %f", t.volume);

    /* a dead oscillator */
    run(&t, 0.0f, FV, 0.1f);
    CHECK(!t.ok && !t.active && t.volume == 0.0f, "dead oscillator still sounding");

    /* the voice */
    static float buf[AUDIO_SAMPLE_HZ * 2];
    const float fs = (float)AUDIO_SAMPLE_HZ;
    voice v;
    voice_init(&v, fs);
    voice_render(&v, buf, 1000);
    float peak = 0.0f;
    for (int i = 0; i < 1000; i++)
        peak = fmaxf(peak, fabsf(buf[i]));
    CHECK(peak == 0.0f, "silence is not silent: %f", peak);

    voice_set(&v, 440.0f, 1.0f);                         /* asks for full: gets the ceiling */
    int n = (int)fs;
    voice_render(&v, buf, n);
    peak = 0.0f;
    float step_on = 0.0f, step_mid = 0.0f;
    int crossings = 0;
    for (int i = 1; i < n; i++) {
        peak = fmaxf(peak, fabsf(buf[i]));
        float d = fabsf(buf[i] - buf[i - 1]);
        if (i < (int)(0.02f * fs))
            step_on = fmaxf(step_on, d);
        else
            step_mid = fmaxf(step_mid, d);
        if (i > n / 2 && buf[i - 1] < 0.0f && buf[i] >= 0.0f)
            crossings++;
    }
    float f_meas = (float)crossings / 0.5f;
    printf("voice: asked 440 Hz at full, got %.1f Hz (vibrato +-%.1f %%), peak %.3f (ceiling %.2f), "
           "largest step at the onset %.4f vs steady %.4f\n", f_meas, 100.0f * VOICE_VIBRATO, peak,
           AUDIO_VOLUME_CEILING, step_on, step_mid);
    CHECK(fabsf(f_meas - 440.0f) < 440.0f * 0.02f, "pitch %f", f_meas);
    CHECK(peak <= AUDIO_VOLUME_CEILING + 1e-4f, "louder than the ceiling: %f", peak);
    CHECK(peak > 0.8f * AUDIO_VOLUME_CEILING, "too quiet: %f", peak);
    CHECK(step_on <= step_mid * 1.05f, "a click at the onset");

    voice_set(&v, 440.0f, 0.0f);                         /* release */
    n = 2 * (int)fs;
    voice_render(&v, buf, n);
    float step_off = 0.0f;
    for (int i = 1; i < n; i++)
        step_off = fmaxf(step_off, fabsf(buf[i] - buf[i - 1]));
    CHECK(step_off <= step_mid * 1.05f, "a click at the release");
    voice_render(&v, buf, (int)fs);                      /* a third second: from full, -60 dB takes 2.4 s */
    CHECK(buf[(int)fs - 1] == 0.0f, "not silent 3 s after the release: %f", buf[(int)fs - 1]);

    /* the speaker's equalisation (voice.c: constant electrical power, from the bench's
     * 131913_speaker.json): the power is the 12 V current a full-scale tone added there,
     * d(f), times the amplitude squared, and must come out the same at 200 Hz, 1 kHz and
     * 4 kHz; at full volume the 4 kHz boost still stops at the ceiling */
    {
        const float hz[3] = {200.0f, 1000.0f, 4000.0f}, d_mA[3] = {26.37f, 25.33f, 18.68f};
        float p[3];
        for (int k = 0; k < 3; k++) {
            voice_init(&v, fs);
            voice_set(&v, hz[k], 0.5f);
            voice_render(&v, buf, 2 * (int)fs);
            double ss = 0.0;
            for (int i = (int)fs; i < 2 * (int)fs; i++)
                ss += (double)buf[i] * (double)buf[i];
            p[k] = (float)(ss / fs) * d_mA[k];
        }
        printf("voice eq: gain %.3f at 200 Hz, %.3f at 1 kHz, %.3f at 4 kHz; power 200 Hz / 1 kHz %.3f, "
               "4 kHz / 1 kHz %.3f\n", voice_eq_gain(200.0f), voice_eq_gain(1000.0f), voice_eq_gain(4000.0f),
               p[0] / p[1], p[2] / p[1]);
        CHECK(fabsf(p[0] / p[1] - 1.0f) < 0.02f && fabsf(p[2] / p[1] - 1.0f) < 0.02f,
              "EQ: unequal power %.3f %.3f", p[0] / p[1], p[2] / p[1]);
        CHECK(fabsf(voice_eq_gain(1000.0f) - 1.0f) < 0.005f, "EQ: 1 kHz is not the reference");
        CHECK(voice_eq_gain(50.0f) == voice_eq_gain(200.0f) && voice_eq_gain(9000.0f) == voice_eq_gain(4000.0f),
              "EQ: not held flat outside the measured range");
        voice_init(&v, fs);
        voice_set(&v, 4000.0f, 1.0f);
        voice_render(&v, buf, (int)fs);
        float pk = 0.0f;
        for (int i = 0; i < (int)fs; i++)
            pk = fmaxf(pk, fabsf(buf[i]));
        CHECK(pk <= AUDIO_VOLUME_CEILING + 1e-4f, "EQ: 4 kHz at full exceeds the ceiling: %f", pk);
    }

    if (failures) {
        printf("test_theremin: %d FAILED\n", failures);
        return 1;
    }
    printf("test_theremin: all passed\n");
    return 0;
}
