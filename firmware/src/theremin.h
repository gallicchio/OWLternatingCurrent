/* theremin.h: two hand-capacitance oscillators -> a ghost's pitch and loudness.
 *
 * Each antenna loads an RC oscillator (74LVC1G14, ~0.5-1 MHz): a hand near the moon
 * lowers the pitch oscillator's frequency, a hand near the pumpkin the volume
 * oscillator's.  PIO counts their edges over THEREMIN_WINDOW_MS (theremin_hw.c);
 * this file turns the two frequencies into a pitch and a volume:
 *   - calibration, hands away: the baselines f0 (THEREMIN_CAL_S of averaging), then
 *     a slow drift tracking while nobody plays (the RC oscillators drift with
 *     temperature);
 *   - the fractional drop (f0 - f) / f0 of each, over its span (THEREMIN_*_SPAN, the
 *     drop with a hand at the antenna), is the hand's nearness 0..1;
 *   - pitch: exponential, THEREMIN_F_LO_HZ .. THEREMIN_F_HI_HZ (equal steps of the
 *     hand, equal musical intervals); volume: a gate above the noise, then 0..1.
 * Portable: no SDK.
 */
#pragma once
#include <stdbool.h>

#define THEREMIN_CAL_S          1.0f      /* [CHOICE] averaging for the baselines */
#define THEREMIN_PITCH_SPAN     0.03f     /* [ASSUMED] 3 % lower with a hand at the moon */
#define THEREMIN_VOL_SPAN       0.03f     /* [ASSUMED] the same at the pumpkin */
#define THEREMIN_VOL_GATE       0.003f    /* [CHOICE] drops below 0.3 % are noise (and drift) */
#define THEREMIN_F_MIN_OK_HZ    10000.0f  /* below this an oscillator is dead */
#define THEREMIN_SMOOTH_S       0.03f     /* [CHOICE] frequency smoothing */
#define THEREMIN_DRIFT_S        10.0f     /* [CHOICE] baseline tracking, while idle */

typedef struct {
    float f0_pitch, f0_vol;       /* baselines, hands away (Hz) */
    float f_pitch, f_vol;         /* smoothed readings (Hz) */
    float near_pitch, near_vol;   /* 0..1 */
    float pitch_hz;               /* the voice's pitch */
    float volume;                 /* 0..1, before the loudness setting and its ceiling */
    bool active;                  /* a hand is playing */
    bool ok;                      /* both oscillators running */
    bool calibrated;
    float cal_left;               /* seconds of calibration still to go */
    double cal_sum_p, cal_sum_v;
    int cal_n;
    float idle_s;
} theremin;

void theremin_init(theremin *t);
void theremin_calibrate(theremin *t);           /* hands away; takes THEREMIN_CAL_S */
/* once per counting window: the two measured frequencies, and the window's length */
void theremin_update(theremin *t, float f_pitch_hz, float f_vol_hz, float dt_s);
