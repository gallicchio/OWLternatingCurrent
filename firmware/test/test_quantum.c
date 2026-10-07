/* test_quantum.c: the quantum ghost's integrator (src/quantum.c).
 *
 *   1. Crank-Nicolson keeps the norm: over the whole show (and 10x longer) the
 *      total probability stays 1 to float rounding.
 *   2. Unconditionally stable: a step 20x too long still keeps the norm.
 *   3. A free packet moves at the grid's group velocity, sin(k0).
 *   4. At the wall it splits: the transmitted part is in the right ballpark of the
 *      rectangular barrier's textbook transmission at the packet's energy, a higher
 *      wall lets less through, and the ghost really does tunnel (its energy is below
 *      the wall's top).
 */
#include "quantum.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

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

/* textbook transmission of a rectangular barrier (height V, width a) for E < V, m = hbar = 1 */
static double t_rect(double E, double V, double a)
{
    double k2 = sqrt(2.0 * (V - E));
    double s = sinh(k2 * a);
    return 1.0 / (1.0 + V * V * s * s / (4.0 * E * (V - E)));
}

/* run until the packet has met the wall and the two parts have separated */
static float transmitted(const quantum_params *p, float *norm_drift)
{
    static quantum q;
    quantum_init(&q, p);
    float worst = 0.0f;
    int steps = (int)(70.0f / p->dt);
    for (int i = 0; i < steps; i++) {
        quantum_step(&q);
        float d = fabsf(quantum_norm(&q) - 1.0f);
        if (d > worst)
            worst = d;
    }
    if (norm_drift)
        *norm_drift = worst;
    return quantum_prob_right(&q, p->barrier_x + p->barrier_w);
}

int main(void)
{
    static quantum q;
    quantum_params p = quantum_default_params();

    /* 1. the norm over the show (the scene takes one step a frame for 14 s: 2800 steps)
     * and ten times longer.  No renormalisation anywhere: what is left is float
     * rounding of the factorised matrix, a fixed ~3e-8 a step. */
    quantum_init(&q, &p);
    float n0 = quantum_norm(&q), worst = 0.0f, at_show = 0.0f;
    for (int i = 1; i <= 28000; i++) {
        quantum_step(&q);
        float d = fabsf(quantum_norm(&q) - 1.0f);
        if (d > worst)
            worst = d;
        if (i == 2800)
            at_show = worst;
    }
    printf("norm: start %.7f; worst drift over the show (2800 steps) %.2e, over 28000 steps %.2e "
           "(%.1e a step)\n", n0, at_show, worst, worst / 28000.0f);
    CHECK(fabsf(n0 - 1.0f) < 1e-5f, "initial norm %f", n0);
    CHECK(at_show < 2e-4f, "norm drift over the show %.2e", at_show);
    CHECK(worst < 2e-3f, "norm drift over 10 shows %.2e", worst);

    /* 2. stability with a step twenty times too long */
    quantum_params big = p;
    big.dt = 2.0f;
    quantum_init(&q, &big);
    float wb = 0.0f;
    for (int i = 0; i < 2000; i++) {
        quantum_step(&q);
        float d = fabsf(quantum_norm(&q) - 1.0f);
        if (d > wb)
            wb = d;
    }
    printf("dt = 2.0 (20x): worst drift over 2000 steps %.2e (no blow-up)\n", wb);
    CHECK(wb < 1e-3f, "unstable with a long step: %.2e", wb);

    /* 3. group velocity of a free packet: d<x>/dt = sin(k0) on the grid */
    quantum_params free = p;
    free.barrier_v = 0.0f;
    quantum_init(&q, &free);
    float x0 = quantum_mean_x(&q);
    int n = (int)(30.0f / free.dt);
    for (int i = 0; i < n; i++)
        quantum_step(&q);
    float v = (quantum_mean_x(&q) - x0) / q.t;
    printf("free packet: group velocity %.3f (grid theory sin(k0) = %.3f)\n", v, sinf(p.k0));
    CHECK(fabsf(v - sinf(p.k0)) < 0.05f, "group velocity %f", v);

    /* 4. the wall */
    float drift;
    float T = transmitted(&p, &drift);
    double E = 1.0 - cos(p.k0);           /* the packet's mean energy on the grid */
    double Ta = t_rect(E, p.barrier_v, p.barrier_w);
    printf("wall: E = %.3f < V = %.3f, width %.0f: transmitted %.3f (rectangular barrier, plane wave: %.3f), "
           "norm drift %.1e\n", E, p.barrier_v, p.barrier_w, T, Ta, drift);
    CHECK(E < p.barrier_v, "the ghost should be below the wall's top (tunnelling, not passing over)");
    CHECK(T > 0.15f && T < 0.6f, "transmitted %.3f: not a good show", T);
    CHECK(fabs(T - Ta) < 0.15, "transmission %.3f far from the textbook %.3f", T, Ta);
    quantum_params high = p;
    high.barrier_v = 0.8f;
    float Th = transmitted(&high, NULL);
    printf("higher wall (V = 0.8): transmitted %.3f\n", Th);
    CHECK(Th < T, "a higher wall should let less through");

    /* the stars: the cells' probabilities add up to the norm */
    float cells[QG_CELLS], sum = 0.0f;
    quantum_init(&q, &p);
    quantum_cells(&q, cells);
    for (int c = 0; c < QG_CELLS; c++)
        sum += cells[c];
    CHECK(fabsf(sum - 1.0f) < 1e-5f, "cells sum %f", sum);

    if (failures) {
        printf("test_quantum: %d FAILED\n", failures);
        return 1;
    }
    printf("test_quantum: all passed\n");
    return 0;
}
