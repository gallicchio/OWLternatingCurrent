/* quantum.c: Crank-Nicolson for the quantum ghost.  See quantum.h. */
#include "quantum.h"
#include <math.h>
#include <string.h>

static inline qcomplex cmul(qcomplex a, qcomplex b) { return (qcomplex){a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re}; }
static inline qcomplex cadd(qcomplex a, qcomplex b) { return (qcomplex){a.re + b.re, a.im + b.im}; }
static inline qcomplex csub(qcomplex a, qcomplex b) { return (qcomplex){a.re - b.re, a.im - b.im}; }

quantum_params quantum_default_params(void)
{
    /* the packet starts over star 2 heading right at k0 = 1 (group velocity sin(k0) = 0.84
     * cells of the grid per unit time); the wall is between stars 7 and 8, a little higher
     * than the packet's mean energy (1 - cos k0 = 0.46 on the grid) */
    return (quantum_params){
        .x0 = 25.0f, .sigma = 5.0f, .k0 = 1.0f,
        .barrier_x = 76.0f, .barrier_w = 2.0f, .barrier_v = 0.50f,
        .dt = 0.10f,
    };
}

void quantum_init(quantum *q, const quantum_params *p)
{
    memset(q, 0, sizeof *q);
    q->p = *p;
    /* the packet: |psi|^2 a Gaussian of s.d. sigma */
    float norm = 0.0f;
    for (int j = 0; j < QG_N; j++) {
        float x = (float)j - p->x0;
        float a = expf(-x * x / (4.0f * p->sigma * p->sigma));
        q->psi[j] = (qcomplex){a * cosf(p->k0 * (float)j), a * sinf(p->k0 * (float)j)};
        norm += a * a;
    }
    float s = 1.0f / sqrtf(norm);
    for (int j = 0; j < QG_N; j++) {
        q->psi[j].re *= s;
        q->psi[j].im *= s;
        float x = (float)j;
        q->v[j] = (x >= p->barrier_x && x < p->barrier_x + p->barrier_w) ? p->barrier_v : 0.0f;
    }
    /* the left side, A = 1 + i dt H / 2: diagonal 1 + i dt (1 + V) / 2, off-diagonal -i dt / 4.
     * Factorised in double (once), so the factors are correctly rounded floats: the
     * recursion's own rounding would otherwise bias every step the same way. */
    q->offdiag = (qcomplex){0.0f, -p->dt / 4.0f};
    double o = (double)q->offdiag.im, cpr = 0.0, cpi = 0.0;     /* o is imaginary */
    for (int j = 0; j < QG_N; j++) {
        q->kd[j] = p->dt * (1.0f + q->v[j]) / 2.0f;   /* the same float on both sides */
        double ar = 1.0, ai = (double)q->kd[j];
        if (j > 0) {                     /* a -= (i o) * c'[j-1] */
            ar -= -o * cpi;
            ai -= o * cpr;
        }
        double d = ar * ar + ai * ai, mr = ar / d, mi = -ai / d;
        q->m[j] = (qcomplex){(float)mr, (float)mi};
        cpr = -o * mi;                   /* c' = (i o) * m */
        cpi = o * mr;
        q->cprime[j] = (qcomplex){(float)cpr, (float)cpi};
    }
}

void quantum_step(quantum *q)
{
    const float dt = q->p.dt;
    const qcomplex up = {0.0f, dt / 4.0f};          /* the right side's off-diagonal */
    qcomplex d[QG_N];
    /* right side, B psi, B = 1 - i dt H / 2; then the forward sweep */
    for (int j = 0; j < QG_N; j++) {
        qcomplex b = {1.0f, -q->kd[j]};
        qcomplex r = cmul(b, q->psi[j]);
        qcomplex nb = {0.0f, 0.0f};
        if (j > 0)
            nb = cadd(nb, q->psi[j - 1]);
        if (j < QG_N - 1)
            nb = cadd(nb, q->psi[j + 1]);
        r = cadd(r, cmul(up, nb));
        if (j > 0)
            r = csub(r, cmul(q->offdiag, d[j - 1]));
        d[j] = cmul(r, q->m[j]);
    }
    /* back substitution */
    q->psi[QG_N - 1] = d[QG_N - 1];
    for (int j = QG_N - 2; j >= 0; j--)
        q->psi[j] = csub(d[j], cmul(q->cprime[j], q->psi[j + 1]));
    q->t += dt;
    q->steps++;
}

float quantum_norm(const quantum *q)
{
    float s = 0.0f;
    for (int j = 0; j < QG_N; j++)
        s += q->psi[j].re * q->psi[j].re + q->psi[j].im * q->psi[j].im;
    return s;
}

void quantum_cells(const quantum *q, float out[QG_CELLS])
{
    for (int c = 0; c < QG_CELLS; c++) {
        float s = 0.0f;
        for (int k = 0; k < QG_PER_CELL; k++) {
            const qcomplex *z = &q->psi[c * QG_PER_CELL + k];
            s += z->re * z->re + z->im * z->im;
        }
        out[c] = s;
    }
}

float quantum_prob_right(const quantum *q, float x)
{
    float s = 0.0f;
    for (int j = 0; j < QG_N; j++)
        if ((float)j >= x)
            s += q->psi[j].re * q->psi[j].re + q->psi[j].im * q->psi[j].im;
    return s;
}

float quantum_mean_x(const quantum *q)
{
    float s = 0.0f, n = 0.0f;
    for (int j = 0; j < QG_N; j++) {
        float p = q->psi[j].re * q->psi[j].re + q->psi[j].im * q->psi[j].im;
        s += p * (float)j;
        n += p;
    }
    return n > 0.0f ? s / n : 0.0f;
}
