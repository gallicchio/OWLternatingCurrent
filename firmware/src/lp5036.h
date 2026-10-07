/* lp5036.h: the two TI LP5036 LED drivers (base 0x30, tree 0x31; the tree may be
 * absent).  Independent (not bank) mode, linear dimming (led_engine.c does the
 * curve), the chip's 12-bit dithered PWM, 25.5 mA.  One frame is one write of the
 * engine's register image from LED0_BRIGHTNESS (0x08) to OUT35_COLOR (0x37); only
 * the span that changed is sent. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "led_engine.h"

typedef struct {
    uint8_t addr;
    bool present;
    uint8_t shadow[LP5036_FRAME_BYTES];   /* what the chip holds */
    bool shadow_valid;
    uint32_t frames, bytes, errors;
} lp5036;

/* reset, enable, configure; false if it does not answer as an LP5036 */
bool lp5036_init(lp5036 *d, uint8_t addr);
/* the engine's image for this driver: writes what changed */
bool lp5036_write_frame(lp5036 *d, const uint8_t image[LP5036_FRAME_BYTES]);
/* all outputs off at once (LED_Global_Off), e.g. before a reset */
void lp5036_all_off(lp5036 *d);
