/* console.h: the JSON console, for a person or an LLM bringing the board up.
 *
 * One command a line in (USB serial "OWLternating console", or the UART), one JSON
 * object a line out.  Replies carry "ok":true or "error":"...".  Unsolicited events
 * ({"event":...}) go out on the same lines.
 *
 *   status                          rails, I2C devices, temperatures, faults, currents,
 *                                   Hall readings, every subsystem's state
 *   scene <name>|auto               hold a scene (asleep dusk night firefly quantum
 *                                   familiar dawn theremin), or back to automatic
 *   led <name|all> <0..1|off>       set LEDs' lightness (still slew-limited), or release
 *   coil <pend1|pend2|pend3|lev> <duty> <ms>
 *                                   drive a coil: duty -1..1 of the 12 V bridge, for ms;
 *                                   refused beyond CONSOLE_I_MAX_A, CONSOLE_ON_MAX_MS,
 *                                   without 12 V, or when the coil is too warm
 *   sweep fam1|fam2                 sweep a perch now; the curve comes back as an event
 *   lev on|off|status               the levitation loop
 *   lev cal [coil|zero]             calibrate: the coil's field and polarity (bat in its
 *                                   cradle or away), or the Hall zero (bat removed)
 *   lev tune <param> <value>        a loop parameter (lev status lists them)
 *   lev eyes <0..1>                 the 80 kHz carrier that lights the bat's eyes (while it floats)
 *   pend off|sustain|circle|chaos   the pendulum
 *   pend cal                        the 3-axis Hall sensor's zero (bat away)
 *   theremin on|off|cal             the theremin (cal: hands away)
 *   film on|off                     film mode (coil fields for magnetic viewing film)
 *   volume <0..1>                   the theremin's loudness (capped at AUDIO_VOLUME_CEILING)
 *   i2c scan                        who answers on the bus
 *   adc dump                        every ADC input and multiplexer channel, raw and scaled
 *   clear                           clear latched faults
 *   save                            save the settings (only with every coil off)
 *   reboot | reboot bootsel | bootsel
 *   help
 *
 * This file is the parser and the limits, portable (test/test_console.c); the
 * actions are the board's (main.c), behind console_ops.
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "coil_ids.h"

#define CONSOLE_LINE_MAX 160
#define CONSOLE_REPLY_MAX 3072

enum { LEV_OP_ON, LEV_OP_OFF, LEV_OP_CAL, LEV_OP_STATUS, LEV_OP_TUNE, LEV_OP_EYES };
enum { PEND_MODE_OFF, PEND_MODE_SUSTAIN, PEND_MODE_CIRCLE, PEND_MODE_CHAOS, PEND_OP_CAL };
enum { THEREMIN_OP_ON, THEREMIN_OP_OFF, THEREMIN_OP_CAL };

/* The board's side.  An action returns NULL when done, or a short error message.
 * The *_json actions write one JSON object (no newline) into buf. */
typedef struct {
    void (*reply)(const char *json);
    const char *(*scene)(int id);                       /* -1: automatic */
    const char *(*led)(int led, float level);           /* led -1: all; level < 0: release */
    const char *(*coil)(int coil, float duty, uint32_t ms);
    const char *(*sweep)(int perch);                    /* 0 or 1 */
    const char *(*lev)(int op, const char *param, float value);
    const char *(*pend)(int mode);
    const char *(*theremin)(int op);
    const char *(*film)(bool on);
    const char *(*volume)(float v);
    const char *(*clear)(void);
    const char *(*save)(void);
    void (*status_json)(char *buf, size_t n);
    void (*lev_json)(char *buf, size_t n);
    void (*i2c_scan_json)(char *buf, size_t n);
    void (*adc_dump_json)(char *buf, size_t n);
    void (*reboot)(bool bootsel);
} console_ops;

void console_init(const console_ops *ops);
/* one line (modified in place); replies through ops->reply */
void console_command(char *line);
/* feed characters one at a time (from USB or the UART); runs complete lines */
void console_feed(char c);

/* the limits on `coil`, shared with the board's action: NULL if allowed.
 * v12: the 12 V rail now; r_ohm: the coil's resistance now (thermal model);
 * the expected current is duty * v12 / (r_ohm + DRV_RDSON_OHM). */
const char *console_coil_limits(float duty, uint32_t ms, float v12, float r_ohm);
const char *coil_name(int coil);
