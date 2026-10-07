/* pendulum.c: the pendulum bat's estimator and drive (pendulum.h).
 *
 * Estimator.  The bat's magnet is a dipole of moment mu z (mu < 0: north pole down)
 * at (x, y, h) over the sensor.  At the sensor
 *     (Bx, By) = 3 k mu h (x, y) / r^5,      Bz = k mu (2 h^2 - rho^2) / r^5,
 * so the field's direction alone gives the position, whatever the magnet's strength
 * or the sensor's gain: the azimuth is that of sign(mu) (Bx, By), and with
 * u = rho / h, q = sign(mu) Bz / |Bh| = (2 - u^2) / (3 u), i.e.
 *     u = 4 |Bh| / (3 sign(mu) Bz + sqrt(9 Bz^2 + 8 |Bh|^2))
 * (the root that stays finite from the centre out past rho = sqrt(2) h, where Bz
 * changes sign).  h itself grows as the bat swings up its sphere:
 * h = depth + L - sqrt(L^2 - rho^2).  Each axis is then tracked by a Kalman filter
 * whose model is the pendulum (x'' = -w^2 x + a), with the coils' known push as a,
 * and w learned from the swing's zero crossings.
 *
 * Drive.  Each mode asks for a force (a direction and a fraction of the strongest
 * pulse); the coils share it in proportion to how well each can push that way from
 * where the bat is (f_c . F, f_c = the coil's force per amp there), the best-placed
 * coil getting the full pulse current.  Pushing along the velocity adds energy,
 * against it removes it; so SUSTAIN and CIRCLE are energy (amplitude) controllers,
 * and from rest an open-loop force rotating or oscillating at w starts the swing.
 */
#include "pendulum.h"
#include "config.h"
#include <math.h>
#include <string.h>

#define K_MU0_4PI 1e-7f
#define G_M_S2 9.81f
#define TWO_PI 6.28318531f

/* the canonical coil (sim/physics README): 4 layers, 12 turns each, radii 15..4 mm */
static const float LAYER_Z_M[4] = {0.0f, -0.21e-3f, -1.275e-3f, -1.485e-3f};
#define TURNS 12
#define SEGS 32

static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* the horizontal force (N per A of coil current) on a magnet of moment `moment` held
 * anti-parallel to a positive coil's own moment (so + = repelled), at horizontal
 * distance rho from the coil's axis and dz over its top copper: minus the force on the
 * coil's segments in the magnet's dipole field */
static float circ_c[SEGS + 1], circ_s[SEGS + 1];      /* the unit circle, once (no trig in the loop:
                                                         the table takes ~25 ms on the M33, not 0.5 s) */

static float coil_force_x(float rho, float dz, float moment)
{
    const float mu = -moment;
    float fx = 0.0f;
    for (int l = 0; l < 4; l++) {
        for (int t = 0; t < TURNS; t++) {
            float a = 15e-3f - (float)t * 1e-3f;
            float z = LAYER_Z_M[l];
            for (int s = 0; s < SEGS; s++) {
                float x0 = a * circ_c[s], y0 = a * circ_s[s], x1 = a * circ_c[s + 1], y1 = a * circ_s[s + 1];
                float mx = 0.5f * (x0 + x1), my = 0.5f * (y0 + y1);
                float dly = y1 - y0;
                float dx = mx - rho, dy = my, dzz = z - dz;
                float r2 = dx * dx + dy * dy + dzz * dzz;
                float r = sqrtf(r2);
                float r3 = r2 * r, r5 = r3 * r2;
                float bz = K_MU0_4PI * (3.0f * mu * dzz * dzz / r5 - mu / r3);
                fx += dly * bz;               /* (dl x B)_x with dl in the plane */
            }
        }
    }
    return -fx;
}

void pend_default_params(pend_params *p)
{
    p->length_m = PEND_LENGTH_M;
    p->depth_m = PEND_SENSOR_DEPTH_M;
    p->copper_dz_m = PEND_SENSOR_DEPTH_M + PEND_SENSOR_ABOVE_COPPER_M;
    p->coil_r_m = PEND_COIL_RADIUS_M;
    p->coil_angle0_deg = PEND_COIL_ANGLE0_DEG;
    p->mass_kg = PEND_MASS_KG;
    p->moment_Am2 = PEND_MOMENT_AM2;
    p->i_max_A = PEND_I_MAX_A;
    p->i_pulse_A = PEND_I_PULSE_A < PEND_I_MAX_A ? PEND_I_PULSE_A : PEND_I_MAX_A;
    p->deadband_A = PEND_I_DEADBAND_A;
    p->sustain_amp_m = PEND_SUSTAIN_AMP_M;
    p->sustain_axis_deg = PEND_COIL_ANGLE0_DEG;
    p->circle_radius_m = PEND_COIL_RADIUS_M;
    p->chaos_amp_m = PEND_CHAOS_AMP_M;
    p->noise_mT = PEND_NOISE_MT;
}

static void reset_estimator(pendulum *pd)
{
    for (int a = 0; a < 2; a++) {
        pd->x[a] = pd->v[a] = 0.0f;
        pd->P[a][0] = 1e-4f;          /* 10 mm */
        pd->P[a][1] = 0.0f;
        pd->P[a][2] = 0.01f;          /* 0.1 m/s */
        pd->last_up_s[a] = -1.0f;
        pd->prev_pos[a] = 0.0f;
        pd->amp_axis[a] = 0.0f;
    }
}

void pend_init(pendulum *pd, const pend_params *p)
{
    memset(pd, 0, sizeof *pd);
    pd->p = *p;
    if (pd->p.i_pulse_A > pd->p.i_max_A)
        pd->p.i_pulse_A = pd->p.i_max_A;
    for (int c = 0; c < PEND_COILS; c++) {
        float a = (pd->p.coil_angle0_deg + 120.0f * (float)c) * (TWO_PI / 360.0f);
        pd->coil_x[c] = pd->p.coil_r_m * cosf(a);
        pd->coil_y[c] = pd->p.coil_r_m * sinf(a);
    }
    for (int s = 0; s <= SEGS; s++) {
        circ_c[s] = cosf(TWO_PI * (float)s / SEGS);
        circ_s[s] = sinf(TWO_PI * (float)s / SEGS);
    }
    pd->k_peak = 0.0f;
    for (int i = 0; i < PEND_KERNEL_N; i++) {
        pd->kernel[i] = coil_force_x((float)i * PEND_KERNEL_STEP_M, pd->p.copper_dz_m, pd->p.moment_Am2);
        if (fabsf(pd->kernel[i]) > pd->k_peak)
            pd->k_peak = fabsf(pd->kernel[i]);
    }
    pd->omega0 = pd->omega = sqrtf(G_M_S2 / pd->p.length_m);
    pd->b_centre_mT = 2.0f * K_MU0_4PI * pd->p.moment_Am2 / (pd->p.depth_m * pd->p.depth_m * pd->p.depth_m) * 1e3f;
    pd->sign_m = -1.0f;
    pd->chosen = -1;
    pd->mode = PEND_OFF;
    reset_estimator(pd);
}

static const char *const MODE_NAMES[PEND_MODES] = {"off", "sustain", "circle", "chaos"};

const char *pend_mode_name(pend_mode m) { return (unsigned)m < PEND_MODES ? MODE_NAMES[m] : "?"; }

bool pend_mode_from_name(const char *name, pend_mode *m)
{
    for (int i = 0; i < PEND_MODES; i++)
        if (!strcmp(name, MODE_NAMES[i])) {
            *m = (pend_mode)i;
            return true;
        }
    return false;
}

enum { ST_RUN = 0, ST_PUMP, ST_FREE, ST_REST };
static const char *const STAGE_NAMES[] = {"run", "pump", "free", "rest"};

void pend_set_mode(pendulum *pd, pend_mode m)
{
    if ((unsigned)m >= PEND_MODES)
        m = PEND_OFF;
    pd->mode = m;
    pd->stage = m == PEND_CHAOS ? ST_PUMP : ST_RUN;
    pd->stage_t0 = pd->t_s;
    pd->near_n = 0;
    pd->chaos_axis_deg = pd->p.coil_angle0_deg + 137.5f * (float)pd->chaos_round;
}

void pend_set_offset(pendulum *pd, float bx_mT, float by_mT, float bz_mT)
{
    pd->off[0] = bx_mT;
    pd->off[1] = by_mT;
    pd->off[2] = bz_mT;
}

float pend_kernel_N_per_A(const pendulum *pd, float rho_m, float dz_m)
{
    float dz0 = pd->p.copper_dz_m;
    if (!(dz_m > 1e-3f))
        dz_m = dz0;
    float s = dz0 / dz_m;               /* the field scales roughly as a dipole's with height */
    float f = rho_m * s / PEND_KERNEL_STEP_M;
    if (!(f >= 0.0f))
        f = 0.0f;
    int i = (int)f;
    float k;
    if (i >= PEND_KERNEL_N - 1)
        k = pd->kernel[PEND_KERNEL_N - 1];
    else
        k = pd->kernel[i] + (f - (float)i) * (pd->kernel[i + 1] - pd->kernel[i]);
    return k * s * s * s * s;
}

/* the bat's height over the sensor when it is rho from the rest point */
static float height_at(const pend_params *p, float rho)
{
    float L = p->length_m;
    float r2 = rho * rho;
    if (r2 > 0.81f * L * L)
        r2 = 0.81f * L * L;
    return p->depth_m + L - sqrtf(L * L - r2);
}

/* the bat's horizontal position from one field reading; false if there is no bat */
static bool invert(const pendulum *pd, float bx, float by, float bz, float *px, float *py, float *sigma)
{
    float bh = sqrtf(bx * bx + by * by);
    float bm = sqrtf(bh * bh + bz * bz);
    if (bm < PEND_PRESENT_MT)
        return false;
    float s = pd->sign_m;
    float den = 3.0f * s * bz + sqrtf(9.0f * bz * bz + 8.0f * bh * bh);
    if (den < 1e-6f * bm)
        den = 1e-6f * bm;
    float u = 4.0f * bh / den;
    if (u > 6.0f)
        u = 6.0f;
    float h = pd->p.depth_m, rho = u * h;
    for (int i = 0; i < 3; i++) {
        h = height_at(&pd->p, rho);
        rho = u * h;
    }
    if (bh > 1e-9f) {
        *px = rho * s * bx / bh;
        *py = rho * s * by / bh;
    } else {
        *px = *py = 0.0f;
    }
    float r = sqrtf(rho * rho + h * h);
    *sigma = 1.5f * r * pd->p.noise_mT / bm + 5e-5f;
    return true;
}

static void kf_predict(pendulum *pd, int ax, float dt, float acc)
{
    float w = pd->omega;
    float c = cosf(w * dt), s = sinf(w * dt);
    float x = pd->x[ax], v = pd->v[ax];
    pd->x[ax] = c * x + (s / w) * v + acc * (1.0f - c) / (w * w);
    pd->v[ax] = -w * s * x + c * v + acc * s / w;
    float F00 = c, F01 = s / w, F10 = -w * s, F11 = c;
    float pxx = pd->P[ax][0], pxv = pd->P[ax][1], pvv = pd->P[ax][2];
    float a00 = F00 * pxx + F01 * pxv, a01 = F00 * pxv + F01 * pvv;
    float a10 = F10 * pxx + F11 * pxv, a11 = F10 * pxv + F11 * pvv;
    const float q = 0.15f * 0.15f;        /* unmodelled acceleration, (m/s^2)^2 per Hz: the coils' model is rough */
    pd->P[ax][0] = a00 * F00 + a01 * F01 + q * dt * dt * dt / 3.0f;
    pd->P[ax][1] = a00 * F10 + a01 * F11 + q * dt * dt / 2.0f;
    pd->P[ax][2] = a10 * F10 + a11 * F11 + q * dt;
}

static void kf_update(pendulum *pd, int ax, float z, float r)
{
    float pxx = pd->P[ax][0], pxv = pd->P[ax][1], pvv = pd->P[ax][2];
    float S = pxx + r;
    float kx = pxx / S, kv = pxv / S;
    float y = z - pd->x[ax];
    pd->x[ax] += kx * y;
    pd->v[ax] += kv * y;
    pd->P[ax][0] = (1.0f - kx) * pxx;
    pd->P[ax][1] = (1.0f - kx) * pxv;
    pd->P[ax][2] = pvv - kv * pxv;
}

/* the coils' force per amp on the bat at (x, y): f[c] (N/A, + current repels) */
static float coil_vectors(const pendulum *pd, float x, float y, float fx[PEND_COILS], float fy[PEND_COILS])
{
    float dz = pd->p.copper_dz_m + (height_at(&pd->p, sqrtf(x * x + y * y)) - pd->p.depth_m);
    float best = 0.0f;
    for (int c = 0; c < PEND_COILS; c++) {
        float sx = x - pd->coil_x[c], sy = y - pd->coil_y[c];
        float rho = sqrtf(sx * sx + sy * sy);
        float k = pend_kernel_N_per_A(pd, rho, dz);
        if (rho > 1e-6f) {
            fx[c] = k * sx / rho;
            fy[c] = k * sy / rho;
        } else {
            fx[c] = fy[c] = 0.0f;
        }
        if (fabsf(k) > best)
            best = fabsf(k);
    }
    return best;
}

/* share a wanted force (fraction of the strongest pulse's, |F| <= 1) among the coils */
static void share(const pendulum *pd, float x, float y, float Fx, float Fy, float i_out[PEND_COILS])
{
    float fx[PEND_COILS], fy[PEND_COILS];
    float best = coil_vectors(pd, x, y, fx, fy);
    for (int c = 0; c < PEND_COILS; c++)
        i_out[c] = best > 1e-9f ? pd->p.i_pulse_A * (fx[c] * Fx + fy[c] * Fy) / best : 0.0f;
}

static int nearest_coil(const pendulum *pd, float x, float y, float *dist)
{
    int k = 0;
    float best = 1e9f;
    for (int c = 0; c < PEND_COILS; c++) {
        float d = hypotf(x - pd->coil_x[c], y - pd->coil_y[c]);
        if (d < best) {
            best = d;
            k = c;
        }
    }
    if (dist)
        *dist = best;
    return k;
}

/* the swing's size and phase along a unit axis (ux, uy) */
static float along(const pendulum *pd, float ux, float uy, float *a, float *va)
{
    *a = pd->x[0] * ux + pd->x[1] * uy;
    *va = pd->v[0] * ux + pd->v[1] * uy;
    float w = pd->omega;
    return sqrtf(*a * *a + (*va / w) * (*va / w));
}

/* pump a swing along `axis_deg` toward amplitude `target`, damping the cross motion */
static void drive_axis(const pendulum *pd, float axis_deg, float target, float xf, float yf, float i_out[PEND_COILS])
{
    float th = axis_deg * (TWO_PI / 360.0f);
    float ux = cosf(th), uy = sinf(th), nx = -uy, ny = ux;
    float a, va;
    float A = along(pd, ux, uy, &a, &va);
    float vn = pd->v[0] * nx + pd->v[1] * ny;
    float w = pd->omega;
    float Fx, Fy;
    if (A < 3e-3f) {
        float g = sinf(pd->omega0 * pd->t_s);        /* open loop at resonance: the swing starts */
        Fx = ux * g;
        Fy = uy * g;
    } else {
        float g = clampf(10.0f * (target - A) / target, -1.0f, 1.0f) * clampf(va / (w * A), -1.0f, 1.0f);
        Fx = ux * g;
        Fy = uy * g;
    }
    float d = -clampf(vn / (w * 5e-3f), -1.0f, 1.0f);
    Fx += nx * d;
    Fy += ny * d;
    float n = sqrtf(Fx * Fx + Fy * Fy);
    if (n > 1.0f) {
        Fx /= n;
        Fy /= n;
    }
    share(pd, xf, yf, Fx, Fy, i_out);
}

static void drive_circle(const pendulum *pd, float xf, float yf, float i_out[PEND_COILS])
{
    float r = sqrtf(pd->x[0] * pd->x[0] + pd->x[1] * pd->x[1]);
    float Fx, Fy;
    if (r < 3e-3f) {
        Fx = cosf(pd->omega0 * pd->t_s);             /* a force rotating at w starts a circle */
        Fy = sinf(pd->omega0 * pd->t_s);
    } else {
        float tx = -pd->x[1] / r, ty = pd->x[0] / r, rx = pd->x[0] / r, ry = pd->x[1] / r;
        float vt = pd->v[0] * tx + pd->v[1] * ty, vr = pd->v[0] * rx + pd->v[1] * ry;
        float vg = pd->omega * pd->p.circle_radius_m;
        float gt = clampf(8.0f * (vg - vt) / vg, -1.0f, 1.0f);
        float gr = -clampf(vr / (0.5f * vg), -1.0f, 1.0f);
        Fx = tx * gt + rx * gr;
        Fy = ty * gt + ry * gr;
        float n = sqrtf(Fx * Fx + Fy * Fy);
        if (n > 1.0f) {
            Fx /= n;
            Fy /= n;
        }
    }
    share(pd, xf, yf, Fx, Fy, i_out);
}

static void chose(pendulum *pd, int k, pend_cmd *out)
{
    pd->chosen = k;
    out->event = PEND_EV_CHOSE;
    out->event_arg = k;
    pd->stage = ST_REST;
    pd->stage_t0 = pd->t_s;
}

static void drive_chaos(pendulum *pd, float xf, float yf, pend_cmd *out)
{
    float r = sqrtf(pd->x[0] * pd->x[0] + pd->x[1] * pd->x[1]);
    float el = pd->t_s - pd->stage_t0;
    if (pd->stage == ST_PUMP) {
        float th = pd->chaos_axis_deg * (TWO_PI / 360.0f), a, va;
        float A = along(pd, cosf(th), sinf(th), &a, &va);
        drive_axis(pd, pd->chaos_axis_deg, pd->p.chaos_amp_m, xf, yf, out->i_A);
        if (A >= 0.9f * pd->p.chaos_amp_m || el > 30.0f) {
            pd->stage = ST_FREE;
            pd->stage_t0 = pd->t_s;
            pd->near_n = 0;
            pd->prev_vr = 0.0f;
            pd->last_turn_x = pd->x[0];
            pd->last_turn_y = pd->x[1];
        }
        return;
    }
    if (pd->stage == ST_REST) {
        if (el > PEND_CHAOS_REST_S) {
            pd->chaos_round++;
            pd->chaos_axis_deg = pd->p.coil_angle0_deg + 137.5f * (float)pd->chaos_round;
            pd->stage = ST_PUMP;
            pd->stage_t0 = pd->t_s;
        }
        return;
    }
    /* FREE: each coil pulls the bat toward itself as it passes within reach */
    float dz = pd->p.copper_dz_m + (height_at(&pd->p, r) - pd->p.depth_m);
    for (int c = 0; c < PEND_COILS; c++) {
        float rho = hypotf(xf - pd->coil_x[c], yf - pd->coil_y[c]);
        float k = pend_kernel_N_per_A(pd, rho, dz);
        out->i_A[c] = k > 0.15f * pd->k_peak ? -pd->p.i_pulse_A * clampf(k / pd->k_peak, 0.0f, 1.0f) : 0.0f;
    }
    /* the last turning point: where the bat stopped moving outward */
    float vr = r > 1e-4f ? (pd->v[0] * pd->x[0] + pd->v[1] * pd->x[1]) / r : 0.0f;
    if (pd->prev_vr > 0.0f && vr <= 0.0f && r > 8e-3f) {
        pd->last_turn_x = pd->x[0];
        pd->last_turn_y = pd->x[1];
    }
    pd->prev_vr = vr;
    float dist;
    int k = nearest_coil(pd, pd->x[0], pd->x[1], &dist);
    if (dist < 8e-3f && k == pd->near_coil) {
        pd->near_n++;
    } else {
        pd->near_coil = k;
        pd->near_n = dist < 8e-3f ? 1 : 0;
    }
    float w = pd->omega;
    float vv = pd->v[0] * pd->v[0] + pd->v[1] * pd->v[1];
    float A = sqrtf(r * r + vv / (w * w));
    if (pd->near_n > (int)TMAG_RATE_HZ) {                     /* held over one coil for a second */
        chose(pd, k, out);
    } else if (A < 10e-3f || el > PEND_CHAOS_FREE_S) {         /* run down: its last big swing chose */
        chose(pd, nearest_coil(pd, pd->last_turn_x, pd->last_turn_y, 0), out);
    }
    if (pd->stage == ST_REST)
        for (int c = 0; c < PEND_COILS; c++)
            out->i_A[c] = 0.0f;
}

void pend_sample(pendulum *pd, uint32_t t_us, float bx_mT, float by_mT, float bz_mT,
                 const float applied_A[PEND_COILS], pend_cmd *out)
{
    memset(out, 0, sizeof *out);
    out->hold_ms = PEND_HOLD_MS;
    float dt = 0.0f;
    if (pd->have_t)
        dt = (float)(uint32_t)(t_us - pd->last_us) * 1e-6f;
    pd->last_us = t_us;
    pd->have_t = true;
    if (dt > 0.0f && dt < 1.0f)
        pd->t_s += dt;

    float bx = bx_mT - pd->off[0], by = by_mT - pd->off[1], bz = bz_mT - pd->off[2];
    float sum_i = 0.0f;
    if (applied_A)
        for (int c = 0; c < PEND_COILS; c++)
            sum_i += fabsf(applied_A[c]);

    /* Which way up is the magnet?  Inside rho = sqrt(2) h, Bz has mu's sign, and there
     * the field is strong: a quarter of its value straight overhead keeps the vote
     * well inside (rho < ~12 mm at the assumed depth), whatever the sign. */
    float bh = sqrtf(bx * bx + by * by);
    float bmag = sqrtf(bh * bh + bz * bz);
    if (bmag > 0.25f * pd->b_centre_mT && fabsf(bz) > 0.05f * pd->b_centre_mT) {
        pd->sign_votes += bz > 0.0f ? 1 : -1;
        if (pd->sign_votes > 50)
            pd->sign_votes = 50;
        if (pd->sign_votes < -50)
            pd->sign_votes = -50;
        float want = pd->sign_votes >= 10 ? 1.0f : (pd->sign_votes <= -10 ? -1.0f : pd->sign_m);
        if (want != pd->sign_m) {          /* everything tracked so far was mirrored */
            pd->sign_m = want;
            pd->reinit = true;
        }
    }

    float mx, my, sig;
    bool seen = invert(pd, bx, by, bz, &mx, &my, &sig);
    if (!seen) {
        pd->present_n = 0;
        if (pd->present && ++pd->absent_n > 40) {
            pd->present = false;
            reset_estimator(pd);
            out->event = PEND_EV_GONE;
        }
        pd->last = *out;
        return;
    }
    pd->absent_n = 0;
    if (!pd->present) {
        if (++pd->present_n < 10) {
            pd->last = *out;
            return;
        }
        pd->present = true;
        reset_estimator(pd);
        pd->x[0] = mx;
        pd->x[1] = my;
        out->event = PEND_EV_ARRIVED;
        dt = 0.0f;
    }
    if (dt > 0.2f || pd->reinit) {       /* a long gap: keep the position, forget the speed */
        pd->reinit = false;
        reset_estimator(pd);
        pd->x[0] = mx;
        pd->x[1] = my;
        dt = 0.0f;
    }
    if (dt > 0.0f) {
        float ax = 0.0f, ay = 0.0f;
        if (applied_A && sum_i > 0.0f) {
            float fx[PEND_COILS], fy[PEND_COILS];
            coil_vectors(pd, pd->x[0], pd->x[1], fx, fy);
            for (int c = 0; c < PEND_COILS; c++) {
                ax += applied_A[c] * fx[c];
                ay += applied_A[c] * fy[c];
            }
            ax /= pd->p.mass_kg;
            ay /= pd->p.mass_kg;
        }
        kf_predict(pd, 0, dt, ax);
        kf_predict(pd, 1, dt, ay);
    }
    /* the coils' own field at the sensor (~0.08 mT/A) spoils readings a little */
    float s_eff = sig * (1.0f + 0.1f * sum_i / pd->p.noise_mT);
    kf_update(pd, 0, mx, s_eff * s_eff);
    kf_update(pd, 1, my, s_eff * s_eff);

    /* learn the swing's frequency from its upward zero crossings */
    for (int a = 0; a < 2; a++) {
        float w = pd->omega;
        pd->amp_axis[a] = sqrtf(pd->x[a] * pd->x[a] + (pd->v[a] / w) * (pd->v[a] / w));
        if (pd->prev_pos[a] < 0.0f && pd->x[a] >= 0.0f && pd->amp_axis[a] > 4e-3f) {
            if (pd->last_up_s[a] > 0.0f) {
                float T = pd->t_s - pd->last_up_s[a];
                float T0 = TWO_PI / pd->omega0;
                if (T > 0.6f * T0 && T < 1.6f * T0)
                    pd->omega = clampf(pd->omega + 0.1f * (TWO_PI / T - pd->omega), 0.75f * pd->omega0,
                                       1.3f * pd->omega0);
            }
            pd->last_up_s[a] = pd->t_s;
        }
        pd->prev_pos[a] = pd->x[a];
    }

    /* drive: where the bat will be when the pulse acts (a few ms on) */
    const float lead = 3e-3f;
    float xf = pd->x[0] + pd->v[0] * lead, yf = pd->x[1] + pd->v[1] * lead;
    switch (pd->mode) {
    case PEND_SUSTAIN:
        drive_axis(pd, pd->p.sustain_axis_deg, pd->p.sustain_amp_m, xf, yf, out->i_A);
        break;
    case PEND_CIRCLE:
        drive_circle(pd, xf, yf, out->i_A);
        break;
    case PEND_CHAOS:
        drive_chaos(pd, xf, yf, out);
        break;
    default:
        break;
    }
    float lim = pd->p.i_max_A;
    for (int c = 0; c < PEND_COILS; c++) {
        float i = clampf(out->i_A[c], -lim, lim);
        out->i_A[c] = fabsf(i) < pd->p.deadband_A ? 0.0f : i;
    }
    pd->last = *out;
}

void pend_status_get(const pendulum *pd, pend_status *s)
{
    s->present = pd->present;
    s->x_m = pd->x[0];
    s->y_m = pd->x[1];
    s->vx_m_s = pd->v[0];
    s->vy_m_s = pd->v[1];
    s->f_hz = pd->omega / TWO_PI;
    s->chosen = pd->chosen;
    s->mode = pend_mode_name(pd->mode);
    s->stage = STAGE_NAMES[pd->stage];
    float r = sqrtf(pd->x[0] * pd->x[0] + pd->x[1] * pd->x[1]);
    if (pd->mode == PEND_SUSTAIN || (pd->mode == PEND_CHAOS && pd->stage == ST_PUMP)) {
        float th = (pd->mode == PEND_SUSTAIN ? pd->p.sustain_axis_deg : pd->chaos_axis_deg) * (TWO_PI / 360.0f);
        float a, va;
        s->amp_m = along(pd, cosf(th), sinf(th), &a, &va);
        s->phase_rad = atan2f(-va / pd->omega, a);
    } else if (pd->mode == PEND_CIRCLE) {
        s->amp_m = r;
        s->phase_rad = atan2f(pd->x[1], pd->x[0]);
    } else {
        float vv = pd->v[0] * pd->v[0] + pd->v[1] * pd->v[1];
        s->amp_m = sqrtf(r * r + vv / (pd->omega * pd->omega));
        s->phase_rad = atan2f(pd->x[1], pd->x[0]);
    }
}
