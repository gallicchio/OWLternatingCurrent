/* theremin.c: see theremin.h. */
#include "theremin.h"
#include "config.h"
#include <math.h>
#include <string.h>

void theremin_init(theremin *t)
{
    memset(t, 0, sizeof *t);
    t->pitch_hz = THEREMIN_F_LO_HZ;
    theremin_calibrate(t);
}

void theremin_calibrate(theremin *t)
{
    t->cal_left = THEREMIN_CAL_S;
    t->cal_sum_p = t->cal_sum_v = 0.0;
    t->cal_n = 0;
}

static float clamp01(float x) { return x < 0.0f ? 0.0f : x > 1.0f ? 1.0f : x; }

void theremin_update(theremin *t, float fp, float fv, float dt)
{
    t->ok = fp > THEREMIN_F_MIN_OK_HZ && fv > THEREMIN_F_MIN_OK_HZ;
    if (!t->ok) {
        t->active = false;
        t->volume = 0.0f;
        return;
    }
    if (t->cal_left > 0.0f) {
        t->cal_sum_p += (double)fp;
        t->cal_sum_v += (double)fv;
        t->cal_n++;
        t->cal_left -= dt;
        if (t->cal_left <= 0.0f) {
            t->f0_pitch = t->f_pitch = (float)(t->cal_sum_p / t->cal_n);
            t->f0_vol = t->f_vol = (float)(t->cal_sum_v / t->cal_n);
            t->calibrated = true;
        }
        t->active = false;
        t->volume = 0.0f;
        return;
    }
    if (!t->calibrated)
        return;
    float k = dt / (THEREMIN_SMOOTH_S + dt);
    t->f_pitch += (fp - t->f_pitch) * k;
    t->f_vol += (fv - t->f_vol) * k;

    float drop_p = (t->f0_pitch - t->f_pitch) / t->f0_pitch;
    float drop_v = (t->f0_vol - t->f_vol) / t->f0_vol;
    t->near_pitch = powf(clamp01(drop_p / THEREMIN_PITCH_SPAN), 0.6f);
    t->near_vol = clamp01((drop_v - THEREMIN_VOL_GATE) / (THEREMIN_VOL_SPAN - THEREMIN_VOL_GATE));
    t->pitch_hz = THEREMIN_F_LO_HZ * powf(THEREMIN_F_HI_HZ / THEREMIN_F_LO_HZ, t->near_pitch);
    t->volume = t->near_vol;
    if (t->active)
        t->active = t->near_vol > 0.03f;
    else
        t->active = t->near_vol > 0.06f;

    /* nobody playing for a while: follow the oscillators' slow drift.  Only while the
     * readings are close to the baselines, so a hand held still is not learned away. */
    t->idle_s = t->active || drop_p > THEREMIN_PITCH_SPAN * 0.25f ? 0.0f : t->idle_s + dt;
    if (t->idle_s > 5.0f) {
        float kd = dt / THEREMIN_DRIFT_S;
        t->f0_pitch += (t->f_pitch - t->f0_pitch) * kd;
        t->f0_vol += (t->f_vol - t->f0_vol) * kd;
    }
}
