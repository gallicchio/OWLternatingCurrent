/* bringup_board_sim.h: a simulated OWLternating Current board behind the bring-up
 * console's ops (src/bringup_cmd.h), for test/test_bringup.c and test/bringup_sim.
 *
 * Virtual time: every ADC conversion takes 2 us, wait_us() advances the clock (and
 * sleeps for real when sim.realtime is set).  The rails, the I2C devices' registers,
 * the coils' current mirrors, the perches' supply current (with a token's resonance),
 * the theremin oscillators and nFAULT are modelled just enough to exercise every
 * command's sequence and limits. */
#pragma once
#include "bringup_cmd.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    /* the knobs (set before sim_init's reset, or changed between commands) */
    bool no12v;                 /* the adapter unplugged: V12 0, V5 0 */
    bool usb_off;               /* VBUS 0 */
    bool missing[128];          /* I2C addresses that do not answer */
    bool sda_stuck;             /* SDA held low at boot (freed by the nine clocks) */
    int token;                  /* 0 none, 1 owl (~160 kHz peak), 2 cat (~350 kHz) */
    bool nfault_on_drive;       /* nFAULT asserts once a coil is driven */
    int short_coil;             /* -1, or a coil whose mirror reads ten times too much */
    bool osc_dead;              /* the theremin oscillators give no edges */
    bool button;                /* the SPELL button pressed */
    int pending_after_events;   /* input_pending() turns true after this many events (-1: never) */
    bool realtime;              /* wait_us() sleeps for real too */

    /* the state */
    uint64_t t_us;
    unsigned mux;
    bool drv_awake, fam_en;
    int coil;                   /* the coil being driven, or -1 */
    float coil_u;
    int perch;                  /* the perch being driven, or -1 */
    float perch_f, perch_duty;
    uint8_t reg[128][256];      /* every I2C device's registers */
    int events;                 /* lines out that were events */
    int lines;                  /* every line out */
    bool rebooted, bootsel;
    float tone_hz, tone_amp;
    uint32_t tone_ms;
    uint32_t noise;
} board_sim;

extern board_sim sim;
extern const bringup_ops SIM_OPS;
/* the knobs from the environment (OWL_SIM_NO12V=1, OWL_SIM_USB_OFF=1,
 * OWL_SIM_MISSING=0x32,0x29, OWL_SIM_TOKEN=owl|cat, OWL_SIM_NFAULT=1,
 * OWL_SIM_SHORT=pend2, OWL_SIM_OSC_DEAD=1, OWL_SIM_SDA_STUCK=1, OWL_SIM_REALTIME=1) */
void sim_from_env(void);
/* the devices' registers to their power-on values; the clock and outputs reset */
void sim_reset(void);
/* where a line goes: the test captures it, the simulator prints it */
extern void (*sim_line_out)(const char *line);
/* the simulator's stdin, for input_pending() (NULL: none) */
extern bool (*sim_stdin_pending)(void);
