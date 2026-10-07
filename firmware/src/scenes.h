/* scenes.h: the light show (PLAN.md section 3).
 *
 *   asleep    room lights on: the pumpkins breathe very slowly and dimly
 *   dusk      the room goes dark (or a tap): stars fade in one at a time over 30 s,
 *             the pumpkins warm up, the owls open their eyes, the wisps come out
 *   night     pumpkins glow like candles (smooth 1/f noise, never a blink), stars
 *             scintillate gently, owls look left and right (light moving between
 *             their eyes), purple wisps drift and roll downhill when the board tilts
 *   firefly   pumpkins and wisps pulse out of step, pull into step (Kuramoto
 *             coupling), hold, and drift apart
 *   quantum   a wave packet runs along the 12-star arc (|psi|^2 = brightness), meets
 *             the wall and partly tunnels through (quantum.h)
 *   familiar  the perches' rings swirl, as when a familiar arrives (a demo; the
 *             swirl itself is an overlay on every scene)
 *   dawn      the reverse of dusk: the owls close their eyes and go to sleep
 *   theremin  while a hand plays: the moon-side stars brighten with the pitch, the
 *             pumpkins with the volume
 *
 * Automatic sequencing (scenes_auto): the light sensor drives asleep <-> dusk ->
 * night and night -> dawn -> asleep with hysteresis (ALS_DARK_LUX, ALS_LIGHT_LUX,
 * ALS_HOLD_S); every few minutes the night becomes a firefly synchrony; a tap or the
 * SPELL button moves to the next scene; a double tap calls the quantum ghost.  The
 * console's `scene <name>` holds a scene until `scene auto`.
 *
 * Changes of scene cross-fade over SCENE_XFADE_S, and the LED engine's slew limit
 * stands behind everything: no LED steps.
 *
 * Portable: no SDK.  Output: the target lightness L (0..1) of every LED.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "led_map.h"
#include "noise.h"
#include "quantum.h"

typedef enum {
    SCENE_ASLEEP,
    SCENE_DUSK,
    SCENE_NIGHT,
    SCENE_FIREFLY,
    SCENE_QUANTUM,
    SCENE_FAMILIAR,
    SCENE_DAWN,
    SCENE_THEREMIN,
    SCENE_COUNT
} scene_id;

#define SCENE_XFADE_S      1.5f
#define SCENE_DUSK_S       32.0f
#define SCENE_DAWN_S       20.0f
#define SCENE_FIREFLY_S    140.0f
#define SCENE_QUANTUM_S    15.0f
#define SCENE_RING_SWIRL_S 8.0f
#define SCENE_MOON_STAR    0           /* the arc's star nearest the moon (theremin): STAR0, at the
                                          arc's left end (gen/layout.py: the moon is at the left) */

enum { FAMILIAR_NONE = 0, FAMILIAR_OWL = 1, FAMILIAR_CAT = 2, FAMILIAR_UNKNOWN = 3 };
#define SCENE_LUX_PENDING (-2.0f)

typedef struct {
    float dt_s;                    /* this frame's length (1 / LED_FPS) */
    float gravity[3];              /* "down" in the board's frame, in g: x right, y toward the
                                      sky, z out of the board's face; flat on a table: (0,0,-1) */
    bool tap, double_tap, button;  /* events since the last frame */
    float lux;                     /* ambient light; -1 without the sensor (always night);
                                      SCENE_LUX_PENDING while its first reading is awaited */
    uint8_t familiar[2];           /* per perch (owl's, cat's): FAMILIAR_* */
    bool theremin_active;          /* theremin on and a hand near */
    float pitch01, volume01;       /* the theremin's hand, 0..1 */
    bool lev_holding;              /* the bat floats under the perch */
    int8_t pendulum_choice;        /* the chaos pendulum's pumpkin (0-2), or -1 */
} scene_inputs;

/* the wisps that roll downhill */
#define SCENE_WISP_PARTICLES 2
typedef struct {
    float u, v;                    /* position along the row of LEDs, and speed */
    uint32_t seed;
} wisp_particle;

#define FIREFLY_N (LED_N_PUMPKIN + LED_N_WISP + LED_N_TWISP)

typedef struct {
    rng32 rng;
    float t;                       /* since start */
    scene_id cur, prev;
    float t_cur;                   /* time in the current scene */
    float t_prev;
    float xfade;                   /* 0..1: how far from prev to cur */
    bool manual;
    scene_id resume;               /* where the quantum ghost / theremin return to */

    /* the light sensor's verdict, with hysteresis */
    bool dark, lux_seen;
    float lux_dark_for, lux_light_for;
    float next_firefly;            /* night -> firefly, when */

    /* ambient night: per-LED noise seeds, star levels, owls, wisps */
    uint32_t seed[LED_COUNT];
    float star_base[LED_COUNT];
    float owl_look[3], owl_from[3], owl_to[3], owl_t[3], owl_hold[3];
    wisp_particle wisp[SCENE_WISP_PARTICLES];
    wisp_particle twisp;

    /* dusk and dawn: the order stars come and go */
    uint8_t star_order[LED_N_STAR + LED_N_STARX + LED_N_TSTAR];

    /* firefly: Kuramoto oscillators (pumpkins, wisps, tree wisps) */
    float theta[FIREFLY_N], omega[FIREFLY_N];
    float kuramoto_r;              /* order parameter, 0 (scattered) .. 1 (in step) */

    /* the quantum ghost */
    quantum q;

    /* theremin, smoothed */
    float pitch_s, vol_s;
    float theremin_idle;

    /* overlays */
    float ring_t[2];               /* time since a familiar arrived, < 0: none */
    float ring_level[2];
    float choice_t;
    int8_t choice;
    float downlight;

    float frame[LED_COUNT];        /* scratch */
    float frame_prev[LED_COUNT];
} scenes;

void scenes_init(scenes *s, uint32_t seed);
void scenes_render(scenes *s, const scene_inputs *in, float out_l[LED_COUNT]);
void scenes_select(scenes *s, scene_id id);    /* hold this scene (the console) */
void scenes_auto(scenes *s);                   /* back to the automatic sequence */
scene_id scenes_current(const scenes *s);
bool scenes_is_manual(const scenes *s);
const char *scene_name(scene_id id);
int scene_by_name(const char *name);           /* -1 if unknown */
