/* coils.h: the PWM behind the six bridges.
 *
 * DRV8874 (pendulum coils 1-3 and the levitation coil), PMODE high = PWM mode:
 *     IN1 IN2   0 0 coast   1 0 forward   0 1 reverse   1 1 brake (low-side slow decay)
 * Each bridge is one PWM slice in phase-correct mode, IN1 = channel A as is and
 * IN2 = channel B inverted, so with compare values ccA >= ccB every period is
 *     forward (counter < ccB) | brake | reverse (counter >= ccA) | brake | forward
 * (forward centred on the period's start, reverse on its middle):
 *     f_fwd = ccB / P,  f_rev = 1 - ccA / P,  P = TOP + 1,
 * and the coil sees a mean of (f_fwd - f_rev) x 12 V.  Brake, not coast, between
 * the pulses: the current decays slowly (small ripple near zero current) and the
 * DRV8874's current mirror keeps seeing it (IPROPI works in drive and brake, not in
 * coast).  Asking for a little of both directions at once (min_alt) keeps every
 * output pulse at least DRV_MIN_PULSE_S long, so the mean voltage stays linear
 * down to zero; asking for a lot (the levitation coil's 90 kHz carrier) makes the
 * triangular ripple that lights the bat's eyes.
 *
 * UCC27524 (the familiar perches), from 5 V: each leg of the perch's full bridge
 * is one output of a slice, A as is, B inverted, phase-correct, the same compare
 * value cc for both: leg A high for cc counts each side of the period's start, leg
 * B for cc counts each side of its middle.  The coil sees +5 V, 0, -5 V, 0: a
 * three-level wave whose fundamental is (4/pi) 5 V sin(pi duty), duty = cc / P <= 0.5.
 *
 * Pins stay plain outputs, low, until coils_connect(true) hands them to the PWM;
 * board_bridges_off() takes them back from anywhere.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "coil_ids.h"
#include "config.h"

#define TOP_PEND      (SYS_CLK_HZ / (2u * PEND_PWM_HZ) - 1u)
#define TOP_LEV       (SYS_CLK_HZ / (2u * LEV_PWM_HZ) - 1u)
#define TOP_CARRIER   (SYS_CLK_HZ / (2u * LEV_CARRIER_HZ) - 1u)
#define TOP_TICK(top_lev)  ((SYS_CLK_HZ / CTRL_TICK_HZ / (2u * ((top_lev) + 1u))) * (2u * ((top_lev) + 1u)) - 1u)

void coils_init(void);                    /* slices configured, outputs coasting, pins not yet PWM */
void coils_connect(bool on);              /* the DRV8874 pins to the PWM (on) or plain-low (off) */
/* forward and reverse fractions of each period, the rest brake */
void coil_set_fractions(int coil, float f_fwd, float f_rev);
/* a mean voltage fraction u (-1..1), with at least min_alt of each direction */
void coil_set_u(int coil, float u, float min_alt);
void coil_coast(int coil);
uint16_t coil_top(int coil);
/* the levitation coil's frequency: LEV_PWM_HZ, or LEV_CARRIER_HZ for the bat's eyes;
 * returns the TOP the tick slice must then use */
void coil_lev_frequency(bool carrier);
float coil_pwm_hz(int coil);

/* the familiar perches (0: owl's, 1: cat's) */
void perch_init(void);
/* returns the frequency it really set (whole counts of the system clock) */
float perch_set(int perch, bool on, float freq_hz, float duty);
float perch_freq(int perch);
float perch_duty(int perch);
bool perch_on(int perch);
