/* quantum.h: the quantum ghost, a wave packet walking along the 12-star arc.
 *
 * The time-dependent Schrodinger equation in one dimension, in units where
 * hbar = m = 1:
 *     i dpsi/dt = -1/2 d2psi/dx2 + V(x) psi
 * on QG_N grid points (QG_PER_CELL per star) with hard walls at both ends, and a
 * rectangular barrier: the "wall" the ghost walks into.
 *
 * Crank-Nicolson: (1 + i dt H / 2) psi(t + dt) = (1 - i dt H / 2) psi(t).  The
 * update is a Cayley transform of the Hermitian H, so it is unitary: the total
 * probability stays 1 (to rounding) for any dt, and the scheme is unconditionally
 * stable.  The left side is tridiagonal with constant off-diagonals; it is
 * factorised once (Thomas algorithm) and each step costs O(N).
 *
 * The brightness of star s is the probability of finding the ghost in its cell.
 * test/test_quantum.c checks the norm, the reflection/transmission split against
 * the textbook rectangular-barrier formula's ballpark, and symmetry.
 *
 * Portable: no SDK; single-precision float.
 */
#pragma once
#include <stdbool.h>

#define QG_CELLS     12                 /* the stars of the arc */
#define QG_PER_CELL  10
#define QG_N         (QG_CELLS * QG_PER_CELL)

typedef struct {
    float re, im;
} qcomplex;

typedef struct {
    float x0, sigma, k0;                /* the packet: centre, width (of |psi|^2), momentum */
    float barrier_x, barrier_w, barrier_v;   /* the wall: start, width, height */
    float dt;                           /* time per step */
} quantum_params;

typedef struct {
    quantum_params p;
    qcomplex psi[QG_N];
    float v[QG_N];
    float kd[QG_N];                     /* dt (1 + V) / 2: H's diagonal times dt / 2 */
    qcomplex cprime[QG_N];              /* the factorised left side */
    qcomplex m[QG_N];
    qcomplex offdiag;                   /* -i dt / 4 (h = 1) */
    float t;
    unsigned steps;
} quantum;

/* defaults that make a nice show: about a third tunnels, the rest reflects */
quantum_params quantum_default_params(void);
void quantum_init(quantum *q, const quantum_params *p);
void quantum_step(quantum *q);
float quantum_norm(const quantum *q);
/* probability in each star's cell (QG_CELLS values) */
void quantum_cells(const quantum *q, float out[QG_CELLS]);
/* probability to the right of x (grid units) */
float quantum_prob_right(const quantum *q, float x);
/* the expected position <x> */
float quantum_mean_x(const quantum *q);
