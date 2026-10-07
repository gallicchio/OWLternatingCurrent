/* film.h: film mode, for magnetic viewing film laid over the three pendulum coils.
 *
 * Slow steps of DC current: a coil (or two, or three, sometimes with opposite
 * polarities) fades up over FILM_RAMP_S, holds, fades down, and rests; the dark rings
 * the film shows over each coil appear, change and "walk" from coil to coil
 * (1 -> 1+2 -> 2 -> 2+3 -> 3 ...).  Each step is at most FILM_I_MAX_A, and on for at most
 * FILM_ON_MAX_MS (ramps included).  Before each step it asks the thermal model how much
 * current each coil can take for the step's length without its surface passing
 * COIL_SURFACE_LIMIT_C - FILM_MARGIN_C, and scales the step down to that; a step that
 * would be too faint to see waits for the coils to cool instead.  While a step runs,
 * each coil's output is also multiplied by its thermal derating, and a coil nearing the
 * limit ends the step early with a fade.
 *
 * How the glue calls it (core 0): film_step() at ~100 Hz with the three pendulum coils'
 * thermal models (read-only); it returns the three coil current targets (A, signed),
 * which the coil layer applies with a hold time of a few steps.
 * Portable C (no SDK): test/test_film.c runs ten minutes of it.
 */
#pragma once
#include <stdbool.h>
#include "thermal.h"

#define FILM_COILS        3
#define FILM_RAMP_S       0.4f    /* [CHOICE] >= 0.2 s: rings fade in and out */
#define FILM_HOLD_S       1.1f    /* [CHOICE] ramp + hold + ramp = 1.9 s, within FILM_ON_MAX_MS */
#define FILM_REST_S       2.5f    /* [CHOICE] between steps, at least */
#define FILM_MIN_FRAC     0.35f   /* [CHOICE] a step fainter than this waits for the coils to cool */
#define FILM_MARGIN_C     1.0f    /* [CHOICE] plan to stay this far under the limit */

typedef struct {
    bool active, stopping;
    int step;                     /* the pattern step now (or next) */
    int steps_done;
    int phase;                    /* rest, ramp up, hold, ramp down */
    float t_phase;
    float amp_A[FILM_COILS];      /* this step's peak currents (signed) */
    float level;                  /* where a ramp down starts, 0..1 */
    float scale;                  /* the last step's thermal scaling, 0..1 */
} film_seq;

void film_init(film_seq *f);
void film_start(film_seq *f, float t_s);
/* fade out and stop */
void film_stop(film_seq *f, float t_s);
bool film_active(const film_seq *f);
void film_step(film_seq *f, float t_s, const thermal_coil *const th[FILM_COILS], float i_A[FILM_COILS]);
const char *film_phase_name(const film_seq *f);
