/* familiar.c: find, name and light the familiar tokens on the two perches (familiar.h).
 *
 * The fit.  With a token on the perch the perch coil's impedance is
 *     Z = Z1 + (w M)^2 / Z2,   Z1 = R1 + j w L1,   Z2 = R2 + j w L2 + 1 / (j w C2)
 * and with k^2 = M^2 / (L1 L2), Q(f) = w L2 / R2 (R2 about constant, so Q grows with f)
 * and the token's resonance ft:
 *     (w M)^2 / Z2 = w k^2 L1 / (1 / Q(f) + j (1 - (ft / f)^2)).
 * The sweep measures |Y| = |I| / V; divided by the empty perch's |Y| it is |Z1| / |Z|.
 * The fit tries ft (60 values from just below the dip to 22 % above it), k^2 (6 values)
 * and Q (5 values), each with its best log offset (which absorbs ISENSE's gain), and
 * keeps the least-squares one: a few hundred candidates per call, so no call takes long.
 */
#include "familiar.h"
#include "config.h"
#include <math.h>
#include <string.h>

#define PI_F 3.14159265f
#define V1_MAX (4.0f / PI_F * FAM_VDRIVE_V)
#define FIT_NF 60
#define FIT_FSTEP 1.0035f
static const float FIT_K2[] = {0.08f, 0.12f, 0.17f, 0.23f, 0.30f, 0.38f};
static const float FIT_Q[] = {2.5f, 4.0f, 6.0f, 9.0f, 13.0f};
#define FIT_NK (int)(sizeof FIT_K2 / sizeof FIT_K2[0])
#define FIT_NQ (int)(sizeof FIT_Q / sizeof FIT_Q[0])
#define FIT_TOTAL (FIT_NF * FIT_NK * FIT_NQ)
#define FIT_PER_CALL 12          /* ~300 logf per call: ~0.15 ms on the M33; the fit ends in ~0.15 s */
#define KI_DUTY_PER_AS 10.0f        /* current loop: duty per (A s) */

static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static float v1_of(float duty) { return V1_MAX * sinf(PI_F * clampf(duty, 0.0f, 0.5f)); }

/* the duty that drives current i into admittance y (S) */
static float duty_for(float i, float y)
{
    if (!(y > 0.0f))
        return 0.0f;
    return asinf(clampf(i / (y * V1_MAX), 0.0f, 1.0f)) / PI_F;
}

static float y_empty_model(float f)
{
    float x = 2.0f * PI_F * f * FAM_L1_H;
    return 1.0f / sqrtf(FAM_R1_OHM * FAM_R1_OHM + x * x);
}

/* smooth raised-cosine 0 -> 1 over T */
static float ease(float t, float T)
{
    if (t <= 0.0f)
        return 0.0f;
    if (t >= T)
        return 1.0f;
    return 0.5f - 0.5f * cosf(PI_F * t / T);
}

const char *fam_who_name(fam_who w)
{
    static const char *const n[] = {"none", "owl", "cat", "unknown"};
    return (unsigned)w < 4 ? n[w] : "?";
}

const char *fam_state_name(fam_state s)
{
    static const char *const n[] = {"off", "idle", "sweep", "fit", "ramp_up", "drive", "ramp_down"};
    return (unsigned)s < 7 ? n[s] : "?";
}

void fam_init(fam_perch *p, int index)
{
    memset(p, 0, sizeof *p);
    p->index = index;
    p->state = FAM_ST_OFF;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        p->f[i] = FAM_F_MIN_HZ * powf(FAM_F_MAX_HZ / FAM_F_MIN_HZ, (float)i / (FAM_SWEEP_N - 1));
        p->base[i] = y_empty_model(p->f[i]);
    }
    p->t_last_sweep = -1e9f;
    p->t_prev = -1.0f;
}

static void set_state(fam_perch *p, fam_state s, float t)
{
    p->state = s;
    p->t_state = t;
}

void fam_enable(fam_perch *p, bool on)
{
    p->enabled = on;
    if (on) {
        if (p->state == FAM_ST_OFF) {
            p->state = FAM_ST_IDLE;
            p->t_last_sweep = -1e9f;
        }
    } else if (p->state == FAM_ST_RAMP_UP || p->state == FAM_ST_DRIVE) {
        p->ramp_from_A = p->i_target;
        p->ramp_s = FAM_RAMP_DOWN_S;
        p->state = FAM_ST_RAMP_DOWN;
        p->t_state = p->t_prev;
    } else if (p->state != FAM_ST_RAMP_DOWN) {
        p->state = FAM_ST_OFF;
    }
}

/* the measured or modelled value at frequency f, from a sweep array (log-linear) */
static float interp(const fam_perch *p, const float *arr, float f)
{
    if (f <= p->f[0])
        return arr[0];
    if (f >= p->f[FAM_SWEEP_N - 1])
        return arr[FAM_SWEEP_N - 1];
    float u = logf(f / p->f[0]) / logf(p->f[1] / p->f[0]);
    int i = (int)u;
    if (i >= FAM_SWEEP_N - 1)
        i = FAM_SWEEP_N - 2;
    float a = u - (float)i;
    return expf((1.0f - a) * logf(arr[i]) + a * logf(arr[i + 1]));
}

/* ---- the fit ----------------------------------------------------------------------------- */
static float ln_model(float f, float ft, float k2, float q)
{
    float w = 2.0f * PI_F * f;
    float r1 = FAM_R1_OHM, x1 = w * FAM_L1_H;
    float x = 1.0f - (ft / f) * (ft / f);
    float iq = ft / (q * f);
    float d = iq * iq + x * x;
    float a = w * k2 * FAM_L1_H;
    float zr_re = a * iq / d, zr_im = -a * x / d;
    float re = r1 + zr_re, im = x1 + zr_im;
    return 0.5f * logf((r1 * r1 + x1 * x1) / (re * re + im * im));
}

/* the sweep against the baseline: is there a token, and where does the fit start? */
static bool fit_begin(fam_perch *p, float *contrast_out)
{
    float tmp[FAM_SWEEP_N], sm[FAM_SWEEP_N];
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        float y = p->y[i] > 1e-7f ? p->y[i] : 1e-7f;
        p->lr[i] = logf(y / p->base[i]);
        tmp[i] = p->lr[i];
    }
    for (int i = 1; i < FAM_SWEEP_N; i++) {          /* the median, by insertion sort */
        float v = tmp[i];
        int j = i - 1;
        while (j >= 0 && tmp[j] > v) {
            tmp[j + 1] = tmp[j];
            j--;
        }
        tmp[j + 1] = v;
    }
    float med = 0.5f * (tmp[FAM_SWEEP_N / 2 - 1] + tmp[FAM_SWEEP_N / 2]);
    for (int i = 0; i < FAM_SWEEP_N; i++)
        p->lr[i] -= med;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        int a = i > 0 ? i - 1 : i, b = i < FAM_SWEEP_N - 1 ? i + 1 : i;
        sm[i] = 0.25f * (p->lr[a] + 2.0f * p->lr[i] + p->lr[b]);
    }
    int idip = 0;
    for (int i = 1; i < FAM_SWEEP_N; i++)
        if (sm[i] < sm[idip])
            idip = i;
    int ipk = idip;
    for (int i = idip + 1; i < FAM_SWEEP_N && i <= idip + 16; i++)
        if (sm[i] > sm[ipk])
            ipk = i;
    float contrast = sm[ipk] - sm[idip];
    *contrast_out = contrast;
    if (!(contrast > 0.34f && sm[idip] < -0.12f && ipk > idip))
        return false;
    /* the dip's frequency, refined by a parabola through its neighbours (in log f) */
    float fd = p->f[idip];
    if (idip > 0 && idip < FAM_SWEEP_N - 1) {
        float a = sm[idip - 1], b = sm[idip], c = sm[idip + 1];
        float den = a - 2.0f * b + c;
        if (den > 1e-6f)
            fd *= powf(p->f[1] / p->f[0], clampf(0.5f * (a - c) / den, -0.5f, 0.5f));
    }
    p->f_dip = fd;
    p->i_dip = idip;
    p->i_peak = ipk;
    p->fit_lo = idip > 12 ? idip - 12 : 0;
    p->fit_hi = ipk + 4 < FAM_SWEEP_N - 1 ? ipk + 4 : FAM_SWEEP_N - 1;
    p->fit_i = 0;
    p->fit_best = 1e30f;
    return true;
}

/* a share of the candidates; true when all are done */
static bool fit_run(fam_perch *p)
{
    int end = p->fit_i + FIT_PER_CALL;
    if (end > FIT_TOTAL)
        end = FIT_TOTAL;
    for (; p->fit_i < end; p->fit_i++) {
        int k = p->fit_i;
        int iq = k % FIT_NQ;
        k /= FIT_NQ;
        int ik = k % FIT_NK;
        int jf = k / FIT_NK;
        float ft = p->f_dip * 0.98f * powf(FIT_FSTEP, (float)jf);
        float k2 = FIT_K2[ik], q = FIT_Q[iq];
        float d[FAM_SWEEP_N];
        float mean = 0.0f;
        int n = 0;
        for (int i = p->fit_lo; i <= p->fit_hi; i++, n++) {
            d[n] = p->lr[i] - ln_model(p->f[i], ft, k2, q);
            mean += d[n];
        }
        mean /= (float)n;
        float err = 0.0f;
        for (int i = 0; i < n; i++)
            err += (d[i] - mean) * (d[i] - mean);
        if (err < p->fit_best) {
            p->fit_best = err;
            p->fit_ft = ft;
            p->fit_k2 = k2;
            p->fit_q = q;
        }
    }
    return p->fit_i >= FIT_TOTAL;
}

static fam_who classify(float ft)
{
    if (ft > 0.70f * FAM_OWL_HZ && ft < 1.35f * FAM_OWL_HZ)
        return FAM_OWL;
    if (ft > 0.75f * FAM_CAT_HZ && ft < 1.25f * FAM_CAT_HZ)
        return FAM_CAT;
    return FAM_UNKNOWN;
}

/* ---- driving ---------------------------------------------------------------------------- */
static void current_loop(fam_perch *p, float isense, float dt)
{
    float ff = duty_for(p->i_target, p->y_token);
    if (isense > FAM_I_MAX_A)
        p->trim -= 0.02f;                       /* too much: back off at once */
    else
        p->trim += KI_DUTY_PER_AS * (p->i_target - isense) * dt;
    float duty = ff + p->trim;
    float cl = clampf(duty, 0.0f, p->duty_cap);
    p->trim = cl - ff;                          /* no wind-up against the limits */
    if (p->i_target <= 0.0f)
        cl = 0.0f;
    p->cmd.duty = cl;
}

/* +-FAM_DITHER round f_drive at 100 Hz; the admittance's log slope from each pair */
static void dither(fam_perch *p, float t, float isense, const fam_cmd *app)
{
    float v1 = v1_of(app->duty);
    if (t - p->t_step >= FAM_DITHER_HALF_S) {
        if (p->dith_side == 1 && p->dith_cnt[0] > 0 && p->dith_cnt[1] > 0) {
            float ym = p->dith_acc[0] / p->dith_cnt[0], yp = p->dith_acc[1] / p->dith_cnt[1];
            /* the frequencies the PWM really made (quantised: 0.44 % steps at 330 kHz) */
            float fm = p->dith_f[0] / p->dith_cnt[0], fp = p->dith_f[1] / p->dith_cnt[1];
            if (ym > 0.0f && yp > 0.0f && fp > 1.001f * fm) {
                float s = logf(yp / ym) / logf(fp / fm);
                if (!p->slope_ok) {
                    p->slope = s;
                    p->slope_ok = true;
                } else {
                    p->slope += 0.05f * (s - p->slope);
                }
            }
            p->dith_acc[0] = p->dith_acc[1] = 0.0f;
            p->dith_f[0] = p->dith_f[1] = 0.0f;
            p->dith_cnt[0] = p->dith_cnt[1] = 0;
        }
        p->dith_side ^= 1;
        p->t_step = t;
    } else if (t - p->t_step >= FAM_DITHER_HALF_S - 0.0021f && v1 > 0.0f) {
        p->dith_acc[p->dith_side] += isense / v1;      /* the last ~2 ms of each half */
        p->dith_f[p->dith_side] += app->freq_hz;
        p->dith_cnt[p->dith_side]++;
    }
    p->cmd.freq_hz = p->f_drive * (p->dith_side ? 1.0f + FAM_DITHER : 1.0f - FAM_DITHER);
    /* Hold the perch current, and so the token's light, steady through the dither: the
     * admittance goes as f^slope here, so scale the drive by the inverse.  (At the token's
     * resonance its tank voltage per perch amp is flat, so its LEDs do not see the dither.)
     * The admittance is still measured: it uses the duty actually applied on each side. */
    if (p->slope_ok && p->cmd.duty > 0.0f) {
        float g = 1.0f + (p->dith_side ? 1.0f : -1.0f) * clampf(p->slope, -3.0f, 8.0f) * FAM_DITHER;
        float s = sinf(PI_F * p->cmd.duty) / clampf(g, 0.5f, 1.5f);
        p->cmd.duty = clampf(asinf(clampf(s, 0.0f, 1.0f)) / PI_F, 0.0f, p->duty_cap);
    }
}

static void start_ramp_down(fam_perch *p, float t, float seconds)
{
    p->ramp_from_A = p->i_target;
    p->ramp_s = seconds;
    set_state(p, FAM_ST_RAMP_DOWN, t);
}

void fam_step(fam_perch *p, float t, float isense, const fam_cmd *applied, fam_cmd *cmd, fam_event *ev)
{
    ev->kind = FAM_EV_NONE;
    ev->perch = p->index;
    ev->who = p->who;
    ev->freq_hz = p->f_token;
    float dt = (p->t_prev >= 0.0f && t > p->t_prev && t - p->t_prev < 0.1f) ? t - p->t_prev : 0.001f;
    p->t_prev = t;
    fam_cmd app = applied ? *applied : p->cmd;
    float v1 = v1_of(app.duty);
    p->i_meas_f += 0.1f * (isense - p->i_meas_f);

    switch (p->state) {
    case FAM_ST_OFF:
        p->cmd.enable = false;
        p->cmd.duty = 0.0f;
        break;

    case FAM_ST_IDLE:
        p->cmd.enable = false;
        p->cmd.duty = 0.0f;
        if (p->enabled && t - p->t_last_sweep >= FAM_SWEEP_PERIOD_S) {
            set_state(p, FAM_ST_SWEEP, t);
            p->step = 0;
            p->n_avg = 0;
            p->acc = 0.0f;
            p->t_step = t;
            p->cmd = (fam_cmd){true, p->f[0], FAM_SWEEP_DUTY};
        }
        break;

    case FAM_ST_SWEEP:
        if (t - p->t_step >= FAM_SETTLE_S && v1 > 0.0f) {
            p->acc += isense / v1;
            if (++p->n_avg >= FAM_AVG_N) {
                p->y[p->step] = p->acc / (float)p->n_avg;
                p->step++;
                p->n_avg = 0;
                p->acc = 0.0f;
                p->t_step = t;
            }
        }
        if (p->step >= FAM_SWEEP_N) {
            p->t_last_sweep = t;
            p->cmd.enable = false;
            p->cmd.duty = 0.0f;
            float contrast;
            if (fit_begin(p, &contrast)) {
                set_state(p, FAM_ST_FIT, t);
            } else {
                if (contrast < 0.15f) {                    /* clearly empty: learn what empty looks like */
                    for (int i = 0; i < FAM_SWEEP_N; i++) {
                        float y = p->y[i] > 1e-7f ? p->y[i] : 1e-7f;
                        p->base[i] *= expf(0.3f * logf(y / p->base[i]));
                    }
                    p->base_learned++;
                }
                set_state(p, FAM_ST_IDLE, t);
            }
        } else {
            p->cmd = (fam_cmd){true, p->f[p->step], FAM_SWEEP_DUTY};
        }
        break;

    case FAM_ST_FIT:
        p->cmd.enable = false;
        if (fit_run(p)) {
            p->who = classify(p->fit_ft);
            p->f_token = p->fit_ft;
            p->f_drive = p->fit_ft;
            p->y_token = interp(p, p->y, p->f_drive);
            p->y_empty = interp(p, p->base, p->f_drive);
            p->duty_cap = clampf(duty_for(1.15f * FAM_I_MAX_A, p->y_empty), 0.0f, 0.5f);
            if (!(p->y_empty * V1_MAX > 1.15f * FAM_I_MAX_A))
                p->duty_cap = 0.5f;                   /* an empty perch cannot reach the limit here */
            p->trim = 0.0f;
            p->i_target = 0.0f;
            p->slope_ok = false;
            p->dith_side = 0;
            p->dith_acc[0] = p->dith_acc[1] = 0.0f;
            p->dith_f[0] = p->dith_f[1] = 0.0f;
            p->dith_cnt[0] = p->dith_cnt[1] = 0;
            p->t_step = t;
            p->t_low_slope = -1.0f;
            ev->kind = FAM_EV_ARRIVED;
            ev->who = p->who;
            ev->freq_hz = p->f_token;
            if (p->enabled) {
                set_state(p, FAM_ST_RAMP_UP, t);
                p->cmd = (fam_cmd){true, p->f_drive, 0.0f};
            } else {
                set_state(p, FAM_ST_OFF, t);
            }
        }
        break;

    case FAM_ST_RAMP_UP:
    case FAM_ST_DRIVE:
        p->cmd.enable = true;
        if (p->state == FAM_ST_RAMP_UP) {
            p->i_target = FAM_I_TARGET_A * ease(t - p->t_state, FAM_RAMP_S);
            if (t - p->t_state >= FAM_RAMP_S) {
                set_state(p, FAM_ST_DRIVE, t);
                p->slope0 = p->slope;
            }
        } else {
            p->i_target = FAM_I_TARGET_A;
        }
        current_loop(p, isense, dt);
        dither(p, t, isense, &app);
        if (p->state == FAM_ST_DRIVE && p->slope_ok) {
            /* an empty perch's admittance falls as 1/f (slope -1); a token's rises here */
            if (p->slope < -0.3f) {
                if (p->t_low_slope < 0.0f)
                    p->t_low_slope = t;
                else if (t - p->t_low_slope > 0.25f) {
                    ev->kind = FAM_EV_LEFT;
                    ev->who = p->who;
                    ev->freq_hz = p->f_token;
                    p->who = FAM_NONE;
                    start_ramp_down(p, t, 0.3f);
                    break;
                }
            } else {
                p->t_low_slope = -1.0f;
            }
            /* follow the token: hold the slope found at full drive (slowly; within 8 %) */
            if (t - p->t_state > 1.0f && p->slope > 0.0f) {
                if (p->t_state + 1.0f > t - dt)
                    p->slope0 = p->slope;
                p->f_drive *= expf(0.02f * (p->slope0 - p->slope) * dt);
                p->f_drive = clampf(p->f_drive, 0.92f * p->f_token, 1.08f * p->f_token);
            }
        }
        break;

    case FAM_ST_RAMP_DOWN:
        p->i_target = p->ramp_from_A * (1.0f - ease(t - p->t_state, p->ramp_s));
        current_loop(p, isense, dt);
        p->cmd.freq_hz = p->f_drive;
        if (t - p->t_state >= p->ramp_s) {
            p->cmd = (fam_cmd){false, p->f_drive, 0.0f};
            p->i_target = 0.0f;
            p->who = FAM_NONE;
            if (p->enabled) {
                set_state(p, FAM_ST_IDLE, t);
                p->t_last_sweep = t - FAM_SWEEP_PERIOD_S + 0.5f;    /* look again soon */
            } else {
                set_state(p, FAM_ST_OFF, t);
            }
        }
        break;
    }
    *cmd = p->cmd;
}
