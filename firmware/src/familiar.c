/* familiar.c: find, name and light the familiar tokens on the two perches (familiar.h).
 *
 * The sweep's reading.  At duty d the bridge's supply current is
 *     I(d) = Iq + sum_n (Vn(d)^2 / 2) G(n f) / 5 V,   Vn(d) = (4 / (n pi)) 5 V sin(n pi d)
 * with Iq the drivers' own draw (independent of d).  Two duties per frequency give
 *     G1 = 5 V (I(dhi) - I(dlo)) / ((V1(dhi)^2 - V1(dlo)^2) / 2)
 *        = G(f) + w3 G(3 f) + ...,   w3 = (V3(dhi)^2 - V3(dlo)^2) / (V1(dhi)^2 - V1(dlo)^2)
 * free of Iq; with pulses this narrow w3 is ~0.97, so the 3rd harmonic counts almost
 * as much as the fundamental.
 *
 * The fit.  With a token on the perch
 *     Z = Z1 + (w M)^2 / Z2 = R1 + j w L1 + w k^2 L1 / (1 / Q(f) + j (1 - (ft / f)^2)),
 * Q(f) = Q f / ft (the token's coil resistance about constant), and the model of the
 * reading above the empty perch's is
 *     m(f) = [Re 1/Z(f) - Re 1/Z1(f)] + w3 [Re 1/Z(3 f) - Re 1/Z1(3 f)].
 * The fit tries tunings ft from 78 % to 100 % of each conductance peak's frequency
 * (the peak is the coupled mode, ft / sqrt(1 - k^2)) and of three times it (the peak may
 * be the 3rd harmonic's), with k^2 and Q on a grid, each with its best gain; a coarse
 * pass, then a fine one round the best.  A few candidates per call, so no call is long.
 */
#include "familiar.h"
#include "config.h"
#include <math.h>
#include <string.h>

#define PI_F 3.14159265f
#define V1_MAX (4.0f / PI_F * FAM_VDRIVE_V)
#define KP_DUTY_PER_WS 6.0f          /* power loop: duty per (W s) */
#define FIT_PER_CALL 6               /* candidates per call: ~0.3 ms on the M33 */
#define FAM_OTHER_PERCH_PENALTY 1.5f /* the other perch's token must fit this much better to win there: the owl's
                                        band (142-225 kHz, k to 0.77) and the cat's 3rd-harmonic image (101-160) overlap */
static const float K2C[] = {0.10f, 0.16f, 0.22f, 0.30f, 0.40f, 0.50f, 0.60f};   /* to k 0.77: a token lying on the copper (rev A, 2026-11-07) */
static const float QC[] = {3.0f, 5.0f, 8.0f, 12.0f};
#define NK2 (int)(sizeof K2C / sizeof K2C[0])
#define NQ (int)(sizeof QC / sizeof QC[0])
#define NF_COARSE 20                 /* ft = base x (0.62 .. 1.00), 2 % steps: sqrt(1 - 0.6) = 0.63 */
#define N_COARSE (NF_COARSE * NK2 * NQ)
#define NF_FINE 13                   /* +-3 % in 0.5 % steps */
#define N_FINE (NF_FINE * 3 * 3)

static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* the n-th harmonic's amplitude at duty d, and half its square (W per S) */
static float vn(int n, float duty)
{
    return 4.0f / ((float)n * PI_F) * FAM_VDRIVE_V * sinf((float)n * PI_F * clampf(duty, 0.0f, 0.5f));
}
static float half_sq(float v) { return 0.5f * v * v; }

/* the duty that delivers p_W into conductance g_S (fundamental only) */
static float duty_for_power(float p_W, float g_S)
{
    if (!(p_W > 0.0f) || !(g_S > 0.0f))
        return 0.0f;
    return asinf(clampf(sqrtf(2.0f * p_W / g_S) / V1_MAX, 0.0f, 1.0f)) / PI_F;
}

/* the empty perch's conductance and admittance (the nominal coil) */
static float ge_model(float f)
{
    float x = 2.0f * PI_F * f * FAM_L1_H;
    return FAM_R1_OHM / (FAM_R1_OHM * FAM_R1_OHM + x * x);
}
static float ye_abs(float f)
{
    float x = 2.0f * PI_F * f * FAM_L1_H;
    return 1.0f / sqrtf(FAM_R1_OHM * FAM_R1_OHM + x * x);
}

/* the perch's conductance with a token tuned to ft (coupling k2, quality q at ft) */
static float gt_model(float f, float ft, float k2, float q)
{
    float w = 2.0f * PI_F * f;
    float x = 1.0f - (ft / f) * (ft / f);
    float iq = ft / (q * f);
    float d = iq * iq + x * x;
    float a = w * k2 * FAM_L1_H;
    float re = FAM_R1_OHM + a * iq / d, im = w * FAM_L1_H - a * x / d;
    return re / (re * re + im * im);
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
    static const char *const n[] = {"off", "idle", "sweep", "fit", "ramp_up", "drive", "ramp_down", "live"};
    return (unsigned)s < 8 ? n[s] : "?";
}

/* the empty perch as the sweep reads it: every harmonic counts nearly fully at these
 * narrow pulses (weights ~0.97, 0.92, 0.85) */
static float base_model_at(float f)
{
    return ge_model(f) + 0.97f * ge_model(3.0f * f) + 0.92f * ge_model(5.0f * f) + 0.85f * ge_model(7.0f * f);
}

static void model_baseline(fam_perch *p, int i) { p->base[i] = base_model_at(p->f[i]); }

void fam_init(fam_perch *p, int index)
{
    memset(p, 0, sizeof *p);
    p->index = index;
    p->state = FAM_ST_OFF;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        p->f[i] = FAM_F_MIN_HZ * powf(FAM_F_MAX_HZ / FAM_F_MIN_HZ, (float)i / (FAM_SWEEP_N - 1));
        model_baseline(p, i);
        p->w3[i] = 0.97f;
    }
    p->t_last_sweep = -1e9f;
    p->t_prev = -1.0f;
}

static float interp(const fam_perch *p, const float *arr, float f);
static float duty_cap_at(float f);

static void set_state(fam_perch *p, fam_state s, float t)
{
    p->state = s;
    p->t_state = t;
}

static void enter_live(fam_perch *p, float t)
{
    p->who = p->index == 0 ? FAM_OWL : FAM_CAT;
    p->f_token = p->f_drive = p->index == 0 ? FAM_OWL_HZ : FAM_CAT_HZ;
    p->iq_drive = interp(p, p->iq, p->f_drive);
    p->live_present = false;
    p->p_live_f = 0.0f;
    p->cmd = (fam_cmd){true, p->f_drive, duty_cap_at(p->f_drive)};
    /* the probe: the owl's coupled mode, or the cat's 3rd-harmonic image of its own */
    p->f_probe = p->index == 0 ? FAM_PROBE_RATIO * FAM_OWL_HZ : FAM_PROBE_RATIO * FAM_CAT_HZ / 3.0f;
    p->probe_empty = 0.0f;
    for (int h = 1; h <= 5; h += 2)
        p->probe_empty += (half_sq(vn(h, FAM_PROBE_DUTY)) - half_sq(vn(h, FAM_PROBE_DUTY_LO))) *
                          ge_model((float)h * p->f_probe) / FAM_VDRIVE_V;
    p->probing = false;
    p->t_probe_next = t + 0.02f;          /* the first breath starts in its trough, with a probe */
    p->t_probe = t;
    p->probe_on = 0.0f;
    p->probe_low = 0;
    p->probe_di = 0.0f;
    set_state(p, FAM_ST_LIVE, t);
}

void fam_set_live(fam_perch *p, bool live)
{
    p->live = live;
    if (live) {
        if (p->enabled && p->state != FAM_ST_OFF && p->state != FAM_ST_LIVE)
            enter_live(p, p->t_prev);
    } else if (p->state == FAM_ST_LIVE) {
        p->live_present = false;
        p->who = FAM_NONE;
        p->cmd = (fam_cmd){false, p->f_drive, 0.0f};
        set_state(p, p->enabled ? FAM_ST_IDLE : FAM_ST_OFF, p->t_prev);
        p->t_last_sweep = -1e9f;
    }
}

void fam_enable(fam_perch *p, bool on)
{
    p->enabled = on;
    if (on) {
        if (p->state == FAM_ST_OFF) {
            p->state = FAM_ST_IDLE;
            p->t_last_sweep = -1e9f;
            if (p->live)
                enter_live(p, p->t_prev);
        }
    } else if (p->state == FAM_ST_LIVE) {
        p->live_present = false;
        p->who = FAM_NONE;
        p->cmd = (fam_cmd){false, p->f_drive, 0.0f};
        p->state = FAM_ST_OFF;
    } else if (p->state == FAM_ST_RAMP_UP || p->state == FAM_ST_DRIVE) {
        p->ramp_from_W = p->p_target;
        p->ramp_s = FAM_RAMP_DOWN_S;
        p->state = FAM_ST_RAMP_DOWN;
        p->t_state = p->t_prev;
    } else if (p->state != FAM_ST_RAMP_DOWN) {
        p->state = FAM_ST_OFF;
    }
}

/* a sweep array's value at frequency f (linear in log f) */
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
    return (1.0f - a) * arr[i] + a * arr[i + 1];
}

/* ---- the fit ----------------------------------------------------------------------------- */
static float sort_median(float *v, int n)
{
    for (int i = 1; i < n; i++) {
        float x = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > x) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = x;
    }
    return n & 1 ? v[n / 2] : 0.5f * (v[n / 2 - 1] + v[n / 2]);
}

/* the sweep against the empty perch: is there a peak, and where should the fit look? */
static bool fit_begin(fam_perch *p, float *excess_out)
{
    float tmp[FAM_SWEEP_N];
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        p->ge1[i] = ge_model(p->f[i]);
        p->ge3[i] = ge_model(3.0f * p->f[i]);
    }
    /* the readings' noise, from what is left after a local straight line (robust) */
    for (int i = 1; i < FAM_SWEEP_N - 1; i++)
        tmp[i - 1] = fabsf(p->y[i] - 0.5f * (p->y[i - 1] + p->y[i + 1]));
    float sigma = 1.4826f * sort_median(tmp, FAM_SWEEP_N - 2) / 1.2247f + 1e-7f;
    /* a token at least doubles the conductance somewhere; take the empty perch's as up to
     * FAM_BASE_SLACK times the baseline (ISENSE's gain, R1), and the excess must stand
     * well out of the noise */
    int pk[2] = {-1, -1};
    float best = 0.0f;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        p->dg[i] = p->y[i] - FAM_BASE_SLACK * p->base[i];
        float ex = p->dg[i] / sigma;
        if (ex > best)
            best = ex;
    }
    *excess_out = best;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        float l = i > 0 ? p->dg[i - 1] : -1e9f, r = i < FAM_SWEEP_N - 1 ? p->dg[i + 1] : -1e9f;
        if (p->dg[i] < l || p->dg[i] < r || p->dg[i] < 6.0f * sigma)
            continue;
        if (pk[0] < 0 || p->dg[i] > p->dg[pk[0]]) {
            pk[1] = pk[0];
            pk[0] = i;
        } else if (pk[1] < 0 || p->dg[i] > p->dg[pk[1]]) {
            pk[1] = i;
        }
    }
    if (pk[0] < 0)
        return false;
    p->n_base = 0;
    for (int k = 0; k < 2 && pk[k] >= 0; k++) {
        int i = pk[k];
        float fp = p->f[i];
        if (i > 0 && i < FAM_SWEEP_N - 1) {           /* refine by a parabola (in log f) */
            float a = p->y[i - 1], b = p->y[i], c = p->y[i + 1];
            float den = a - 2.0f * b + c;
            if (den < -1e-12f)
                fp *= powf(p->f[1] / p->f[0], clampf(0.5f * (a - c) / den, -0.5f, 0.5f));
        }
        p->fit_base[p->n_base++] = fp;
        if (3.0f * 0.62f * fp <= 1.15f * FAM_F_MAX_HZ)  /* or the 3rd harmonic of a token up there */
            p->fit_base[p->n_base++] = 3.0f * fp;
    }
    /* the sums every candidate shares; and how the baseline compares with the model (1 for
     * the model itself; ISENSE's gain x R1's error once learned from empty sweeps) */
    float bm = 0.0f, mm = 0.0f;
    p->s_bb = p->s_yb = p->s_yy = 0.0f;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        float mb = base_model_at(p->f[i]);
        bm += p->base[i] * mb;
        mm += mb * mb;
        p->s_bb += p->base[i] * p->base[i];
        p->s_yb += p->y[i] * p->base[i];
        p->s_yy += p->y[i] * p->y[i];
    }
    p->base_scale = mm > 0.0f ? bm / mm : 1.0f;
    p->fit_i = 0;
    p->fit_stage = 0;
    p->fit_best = 1e30f;
    return true;
}

/* the token's excess conductance over the empty perch, as the sweep reads it at point i */
static float token_excess(const fam_perch *p, int i, float ft, float k2, float q)
{
    float f = p->f[i];
    return (gt_model(f, ft, k2, q) - p->ge1[i]) + p->w3[i] * (gt_model(3.0f * f, ft, k2, q) - p->ge3[i]);
}

/* least squares of y = a (base + c m(ft, k2, q)), c the baseline's scale against the model.
 * The token's excess is tied to the empty perch's scale: both are read through the same
 * ISENSE gain, so only R1's error (R1 = FAM_R1_OHM, about +-15 %) separates them.  Left
 * free, the excess's size trades against k^2 and the tuning comes out several per cent
 * low (the peak, at ft / sqrt(1 - k^2), fits either way). */
static float fit_eval(const fam_perch *p, float ft, float k2, float q, float *a_out, float *s_out)
{
    float s_bm = 0.0f, s_mm = 0.0f, s_ym = 0.0f;
    for (int i = 0; i < FAM_SWEEP_N; i++) {
        float m = token_excess(p, i, ft, k2, q);
        s_bm += p->base[i] * m;
        s_mm += m * m;
        s_ym += p->y[i] * m;
    }
    float c = p->base_scale;
    float s_yu = p->s_yb + c * s_ym, s_uu = p->s_bb + 2.0f * c * s_bm + c * c * s_mm;
    if (!(s_uu > 0.0f) || s_yu <= 0.0f) {
        *a_out = *s_out = 0.0f;
        return p->s_yy;
    }
    *a_out = s_yu / s_uu;
    *s_out = *a_out * c;
    return p->s_yy - s_yu * s_yu / s_uu;
}

/* a share of the candidates; true when the fit is done */
static fam_who classify(float ft);

static bool fit_run(fam_perch *p)
{
    for (int n = 0; n < FIT_PER_CALL; n++) {
        float ft, k2, q;
        int k = p->fit_i;
        if (p->fit_stage == 0) {
            if (k >= p->n_base * N_COARSE) {
                p->fit_stage = 1;
                p->fit_i = 0;
                p->fine_ft = p->fit_ft;
                p->fine_k2 = p->fit_k2;
                p->fine_q = p->fit_q;
                continue;
            }
            int b = k / N_COARSE, r = k % N_COARSE;
            int iq = r % NQ, ik = (r / NQ) % NK2, jf = r / (NQ * NK2);
            ft = p->fit_base[b] * (0.62f + 0.02f * (float)jf);
            k2 = K2C[ik];
            q = QC[iq];
        } else {
            if (k >= N_FINE)
                return true;
            int iq = k % 3, ik = (k / 3) % 3, jf = k / 9;
            static const float KM[3] = {1.0f / 1.2f, 1.0f, 1.2f}, QM[3] = {1.0f / 1.4f, 1.0f, 1.4f};
            ft = p->fine_ft * (0.97f + 0.005f * (float)jf);
            k2 = p->fine_k2 * KM[ik];
            q = p->fine_q * QM[iq];
        }
        p->fit_i++;
        if (ft < 0.5f * FAM_F_MIN_HZ || ft > 1.3f * FAM_F_MAX_HZ)
            continue;
        float a, sc;
        float e = fit_eval(p, ft, k2, q, &a, &sc);
        /* only the two tokens this board knows: one bump fixes only the coupled mode
         * ft / sqrt(1 - k^2), so left free the fit read the bare owl's 214 kHz as the
         * image of a 441 kHz stranger (rev A, 2026-11-07); a stranger now simply fits
         * badly and is not driven */
        fam_who who = classify(ft);
        if (who == FAM_UNKNOWN)
            continue;
        if (who != (p->index == 0 ? FAM_OWL : FAM_CAT))
            e *= FAM_OTHER_PERCH_PENALTY;
        if (sc > 0.0f && e < p->fit_best) {
            p->fit_best = e;
            p->fit_ft = ft;
            p->fit_k2 = k2;
            p->fit_q = q;
            p->fit_a = a;
            p->fit_scale = sc;
        }
    }
    return false;
}

/* A token is named when its tank is within FAM_ID_TOL of its own frequency: real tokens
 * are within about 7 % (C0G capacitors and the drawn coils, 5 % each), and a stranger
 * between the two (240 kHz, between the owl's 142 and the cat's 303) is "unknown". */
#define FAM_ID_TOL 0.18f

static fam_who classify(float ft)
{
    if (ft > (1.0f - FAM_ID_TOL) * FAM_OWL_HZ && ft < (1.0f + FAM_ID_TOL) * FAM_OWL_HZ)
        return FAM_OWL;
    if (ft > (1.0f - FAM_ID_TOL) * FAM_CAT_HZ && ft < (1.0f + FAM_ID_TOL) * FAM_CAT_HZ)
        return FAM_CAT;
    return FAM_UNKNOWN;
}

/* ---- driving ---------------------------------------------------------------------------- */
static float duty_cap_at(float f)
{
    /* what puts FAM_CAP_MARGIN x FAM_I_MAX_A into an empty perch: with a token the perch's
     * impedance is only higher at and below the token's tuning, so this holds either way */
    float c = asinf(clampf(FAM_CAP_MARGIN * FAM_I_MAX_A / (ye_abs(f) * V1_MAX), 0.0f, 1.0f)) / PI_F;
    return clampf(c, 0.0f, 0.5f);
}

float fam_duty_cap(float f_hz) { return duty_cap_at(f_hz); }

static void power_loop(fam_perch *p, float isense, float dt)
{
    float p_meas = FAM_VDRIVE_V * (isense - p->iq_drive);
    p->p_meas_f += 0.2f * (p_meas - p->p_meas_f);
    float g_ff = p->fit_scale * gt_model(p->f_drive, p->f_token, p->fit_k2, p->fit_q);
    float ff = duty_for_power(p->p_target, g_ff);
    if (p_meas > 1.6f * (p->p_target > 0.05f ? p->p_target : 0.05f))
        p->trim -= 0.01f;                          /* far too much: back off at once */
    else
        p->trim += KP_DUTY_PER_WS * (p->p_target - p_meas) * dt;
    float cap = duty_cap_at(p->f_drive);
    float d = clampf(ff + p->trim, 0.0f, cap);
    p->trim = d - ff;                              /* no wind-up against the limits */
    p->cmd.duty = p->p_target > 0.0f ? d : 0.0f;
}

/* +-FAM_DITHER round f_drive at 100 Hz: the conductance's log slope from each pair, and
 * the drive scaled so that the delivered power (and the light) does not follow the dither */
static void dither(fam_perch *p, float t, float isense, const fam_cmd *app)
{
    float h = half_sq(vn(1, app->duty));
    if (t - p->t_step >= FAM_DITHER_HALF_S) {
        if (p->dith_side == 1 && p->dith_cnt[0] > 0 && p->dith_cnt[1] > 0) {
            float gm = p->dith_acc[0] / p->dith_cnt[0], gp = p->dith_acc[1] / p->dith_cnt[1];
            float fm = p->dith_f[0] / p->dith_cnt[0], fp = p->dith_f[1] / p->dith_cnt[1];
            if (gm > 0.0f && gp > 0.0f && fp > 1.001f * fm) {
                float s = logf(gp / gm) / logf(fp / fm);
                if (!p->slope_ok) {
                    p->slope = s;
                    p->slope_ok = true;
                } else {
                    p->slope += 0.05f * (s - p->slope);
                }
                float g = 0.5f * (gm + gp);
                p->g_acc += 0.05f * (g - p->g_acc);       /* the conductance now, for leaving */
                p->g_n++;
            }
            p->dith_acc[0] = p->dith_acc[1] = 0.0f;
            p->dith_f[0] = p->dith_f[1] = 0.0f;
            p->dith_cnt[0] = p->dith_cnt[1] = 0;
        }
        p->dith_side ^= 1;
        p->t_step = t;
    } else if (t - p->t_step >= FAM_DITHER_HALF_S - 0.0021f && h > 1e-4f) {
        p->dith_acc[p->dith_side] += FAM_VDRIVE_V * (isense - p->iq_drive) / h;   /* last ~2 ms of each half */
        p->dith_f[p->dith_side] += app->freq_hz;
        p->dith_cnt[p->dith_side]++;
    }
    float sgn = p->dith_side ? 1.0f : -1.0f;
    p->cmd.freq_hz = p->f_drive * (1.0f + sgn * FAM_DITHER);
    if (p->slope_ok && p->cmd.duty > 0.0f) {
        /* G goes as f^slope here: scale V1 by its inverse square root */
        float g = powf(1.0f + sgn * FAM_DITHER, clampf(p->slope, -4.0f, 10.0f));
        float s = sinf(PI_F * p->cmd.duty) / sqrtf(clampf(g, 0.5f, 2.0f));
        p->cmd.duty = clampf(asinf(clampf(s, 0.0f, 1.0f)) / PI_F, 0.0f, duty_cap_at(p->cmd.freq_hz));
    }
}

static void start_ramp_down(fam_perch *p, float t, float seconds)
{
    p->ramp_from_W = p->p_target;
    p->ramp_s = seconds;
    set_state(p, FAM_ST_RAMP_DOWN, t);
}

static void sweep_step_cmd(fam_perch *p)
{
    p->cmd = (fam_cmd){true, p->f[p->step], p->level ? FAM_SWEEP_DUTY : FAM_SWEEP_DUTY_LO};
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

    switch (p->state) {
    case FAM_ST_OFF:
        p->cmd.enable = false;
        p->cmd.duty = 0.0f;
        break;

    case FAM_ST_LIVE: {
        float cap = duty_cap_at(p->f_drive);
        if (!p->probing && t >= p->t_probe_next) {
            p->probing = true;
            p->t_probe = t;
            p->probe_acc = 0.0f;
            p->probe_n = 0;
            p->probe_level = 0;
        }
        if (p->probing) {
            float d_hi = FAM_PROBE_DUTY, d_lo = FAM_PROBE_DUTY_LO;
            p->cmd = (fam_cmd){true, p->f_probe, p->probe_level ? d_lo : d_hi};
            float since = t - p->t_probe;
            if (since >= FAM_PROBE_SETTLE_S) {
                p->probe_acc += isense;
                p->probe_n++;
            }
            if (since >= FAM_PROBE_SETTLE_S + FAM_PROBE_AVG_S && p->probe_n > 0 && p->probe_level == 0) {
                p->probe_i_hi = p->probe_acc / (float)p->probe_n;  /* the upper level done: the lower */
                p->probe_level = 1;
                p->probe_acc = 0.0f;
                p->probe_n = 0;
                p->t_probe = t;
                p->cmd.duty = d_lo;
            } else if (since >= FAM_PROBE_SETTLE_S + FAM_PROBE_AVG_S && p->probe_n > 0) {
                /* the owl's perch sees its token in the fundamental; the cat's in the 3rd
                 * harmonic (the narrow pulses' 3rd is nearly as strong as their 1st) */
                float g = p->probe_i_hi - p->probe_acc / (float)p->probe_n;
                float e = p->probe_empty;
                p->probe_di = g;
                p->probing = false;
                p->t_probe_next += FAM_PROBE_PERIOD_S;
                if (p->t_probe_next < t)
                    p->t_probe_next = t + FAM_PROBE_PERIOD_S;
                p->t_probe = t;                             /* the breath's clock: from the trough */
                p->cmd = (fam_cmd){true, p->f_drive, cap * FAM_BREATH_MIN};
                float on_at = fmaxf(FAM_PROBE_ON * e, FAM_PROBE_ON_MIN_A);
                if (!p->live_present && g > on_at) {
                    p->live_present = true;
                    p->probe_on = g;
                    ev->kind = FAM_EV_ARRIVED;
                } else if (p->live_present && g < fmaxf(FAM_PROBE_OFF * p->probe_on, FAM_PROBE_OFF_EMPTY * e)) {
                    p->live_present = false;
                    ev->kind = FAM_EV_LEFT;
                } else if (p->live_present) {
                    p->probe_on += 0.3f * (g - p->probe_on);  /* the token settles, or is nudged */
                }
                if (!p->live_present && g > 0.0f && g < on_at)
                    p->probe_empty += FAM_PROBE_LEARN * (g - e);   /* an empty perch teaches its reading */
                ev->who = p->who;
                ev->freq_hz = p->f_token;
            }
            break;
        }
        /* the breath: the probe was in its trough */
        float ph = (t - p->t_probe) / FAM_PROBE_PERIOD_S;
        float env = 0.5f - 0.5f * cosf(2.0f * PI_F * (ph - floorf(ph)));
        p->cmd = (fam_cmd){true, p->f_drive, cap * (FAM_BREATH_MIN + (1.0f - FAM_BREATH_MIN) * env)};
        /* reported only: the power beyond an empty perch's at this drive (the drivers'
         * draw, and the fundamental into the empty perch's conductance as modelled or
         * learned); right after a probe ISENSE is still settling, so wait */
        if (t - p->t_probe < FAM_PROBE_SETTLE_S + FAM_PROBE_AVG_S + 0.01f)
            break;
        float d = app.enable ? app.duty : cap;
        float g_empty = interp(p, p->base, p->f_drive);
        float i_empty = p->iq_drive + half_sq(vn(1, d)) * g_empty / FAM_VDRIVE_V;
        p->p_live_f += 0.3f * (FAM_VDRIVE_V * (isense - i_empty) - p->p_live_f);
        p->p_meas_f = p->p_live_f;
        break;
    }

    case FAM_ST_IDLE:
        p->cmd.enable = false;
        p->cmd.duty = 0.0f;
        if (p->live && p->enabled) {
            enter_live(p, t);
            break;
        }
        if (p->enabled && t - p->t_last_sweep >= FAM_SWEEP_PERIOD_S) {
            set_state(p, FAM_ST_SWEEP, t);
            p->step = 0;
            p->level = 0;
            p->n_avg = 0;
            p->acc = p->acc_v1sq = 0.0f;
            p->v3sq_lo = 0.0f;
            p->t_step = t;
            sweep_step_cmd(p);
        }
        break;

    case FAM_ST_SWEEP:
        if (t - p->t_step >= FAM_SETTLE_S) {
            p->acc += isense;
            p->acc_v1sq += half_sq(vn(1, app.duty));
            p->v3sq_lo += half_sq(vn(3, app.duty)) * (p->level ? -1.0f : 1.0f);   /* lo - hi, summed */
            if (++p->n_avg >= FAM_AVG_N) {
                float I = p->acc / (float)p->n_avg, v1sq = p->acc_v1sq / (float)p->n_avg;
                if (p->level == 0) {
                    p->i_lo = I;
                    p->v1sq_lo = v1sq;
                    p->level = 1;
                } else {
                    float dv = v1sq - p->v1sq_lo;
                    int i = p->step;
                    if (dv > 1e-5f) {
                        p->y[i] = FAM_VDRIVE_V * (I - p->i_lo) / dv;
                        p->w3[i] = clampf(-p->v3sq_lo / (float)p->n_avg / dv, 0.0f, 1.2f);
                        p->iq[i] = p->i_lo - p->v1sq_lo * p->y[i] / FAM_VDRIVE_V;
                    } else {
                        p->y[i] = 0.0f;
                        p->iq[i] = p->i_lo;
                    }
                    p->v3sq_lo = 0.0f;
                    p->level = 0;
                    p->step++;
                }
                p->n_avg = 0;
                p->acc = p->acc_v1sq = 0.0f;
                p->t_step = t;
            }
        }
        if (p->step >= FAM_SWEEP_N) {
            p->t_last_sweep = t;
            p->cmd.enable = false;
            p->cmd.duty = 0.0f;
            float excess;
            if (fit_begin(p, &excess)) {
                set_state(p, FAM_ST_FIT, t);
            } else {
                if (excess < 3.0f) {                       /* clearly empty: learn what empty looks like */
                    /* (the model's 1/f^2 shape, scaled to this sweep, smooths the noise) */
                    float num = 0.0f, den = 0.0f;
                    for (int i = 0; i < FAM_SWEEP_N; i++) {
                        num += p->y[i] * p->base[i];
                        den += p->base[i] * p->base[i];
                    }
                    float a = den > 0.0f ? clampf(num / den, 0.3f, 3.0f) : 1.0f;
                    for (int i = 0; i < FAM_SWEEP_N; i++)
                        p->base[i] += 0.3f * (a * p->base[i] - p->base[i]);
                    p->base_learned++;
                }
                set_state(p, FAM_ST_IDLE, t);
            }
        } else {
            sweep_step_cmd(p);
        }
        break;

    case FAM_ST_FIT:
        p->cmd.enable = false;
        p->cmd.duty = 0.0f;
        if (fit_run(p)) {
            /* how much of what the baseline alone leaves unexplained the token explains */
            float e_base = p->s_yy - p->s_yb * p->s_yb / p->s_bb;
            p->fit_r2 = e_base > 0.0f ? 1.0f - p->fit_best / e_base : 0.0f;
            p->gain = p->fit_a;
            if (p->fit_r2 < 0.8f || p->fit_a < 0.2f || p->fit_a > 5.0f) {
                set_state(p, FAM_ST_IDLE, t);              /* no resonance: not a token, not driven */
                break;
            }
            p->who = classify(p->fit_ft);
            p->f_token = p->f_drive = p->fit_ft;
            p->iq_drive = interp(p, p->iq, p->f_drive);
            p->trim = 0.0f;
            p->p_target = 0.0f;
            p->p_meas_f = 0.0f;
            p->slope_ok = false;
            p->g_acc = 0.0f;
            p->g_n = 0;
            p->g_lit = 0.0f;
            p->dith_side = 0;
            p->dith_acc[0] = p->dith_acc[1] = 0.0f;
            p->dith_f[0] = p->dith_f[1] = 0.0f;
            p->dith_cnt[0] = p->dith_cnt[1] = 0;
            p->t_step = t;
            p->t_low = -1.0f;
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
            p->p_target = FAM_P_TARGET_W * ease(t - p->t_state, FAM_RAMP_S);
            if (t - p->t_state >= FAM_RAMP_S)
                set_state(p, FAM_ST_DRIVE, t);
        } else {
            p->p_target = FAM_P_TARGET_W;
        }
        power_loop(p, isense, dt);
        dither(p, t, isense, &app);
        if (p->state == FAM_ST_DRIVE && p->slope_ok) {
            if (p->g_lit <= 0.0f && t - p->t_state > 0.5f)
                p->g_lit = p->g_acc;                   /* the lit token's conductance */
            /* leaving: the slope turns negative (an empty perch's falls as ~1/f^2), or the
             * conductance sinks most of the way back to the empty perch's */
            float g_empty = p->fit_scale * ge_model(p->f_drive);
            bool low = p->slope < 0.0f ||
                       (p->g_lit > 0.0f && p->g_acc < g_empty + 0.35f * (p->g_lit - g_empty));
            if (low) {
                if (p->t_low < 0.0f)
                    p->t_low = t;
                else if (t - p->t_low > 0.25f) {
                    ev->kind = FAM_EV_LEFT;
                    ev->who = p->who;
                    ev->freq_hz = p->f_token;
                    p->who = FAM_NONE;
                    start_ramp_down(p, t, 0.3f);
                    break;
                }
            } else {
                p->t_low = -1.0f;
            }
            /* No frequency tracking: the token's tuning is its own coil and C0G capacitor and
             * does not move; moving the token changes the coupling, which moves the
             * conductance peak (the coupled mode) but not the tuning, where it is driven.
             * (At the tuning the lit token's slope is at its maximum, so there is nothing to
             * hold on to there anyway.)  A token set down again is fitted afresh. */
        }
        break;

    case FAM_ST_RAMP_DOWN:
        p->p_target = p->ramp_from_W * (1.0f - ease(t - p->t_state, p->ramp_s));
        power_loop(p, isense, dt);
        p->cmd.freq_hz = p->f_drive;
        if (t - p->t_state >= p->ramp_s) {
            p->cmd = (fam_cmd){false, p->f_drive, 0.0f};
            p->p_target = 0.0f;
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
