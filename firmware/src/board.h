/* board.h: the RP2354A's pins, made safe first and then put to work.
 *
 * board_safe_init() runs before anything else in main(): every bridge input is a
 * plain output driven low (DRV8874: coast; UCC27524: output low), the DRV8874s
 * sleep (nSLEEP low) and the UCC27524s are disabled (FAM_EN low).  The board's own
 * pull-downs on nSLEEP and FAM_EN already hold them so in reset; this makes it
 * true in software before the first line that could drive a coil.
 *
 * RP2350-E9: no input here relies on the pad's pull-down.  nFAULT and the SPELL
 * button have the board's 10 k pull-ups (pull-ups work); the IMU's interrupt and the
 * theremin oscillators are driven push-pull; the ADC pins have their digital input
 * buffers off (adc_gpio_init).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

void board_safe_init(void);
/* every coil bridge off: inputs low, DRV8874s asleep, UCC27524s disabled; any core, any time */
void board_bridges_off(void);
void board_drv_sleep(bool asleep);
bool board_drv_fault(void);           /* nFAULT asserted (low) */
void board_fam_enable(bool on);
bool board_button(void);              /* the SPELL button, pressed (raw) */
void board_mux_select(unsigned ch);

/* ADC counts -> volts at the pin */
static inline float adc_volts(float counts) { return counts * (3.3f / 4096.0f); }
