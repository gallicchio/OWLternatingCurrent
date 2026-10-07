/* led_engine.h: from what the scenes want to what the LP5036s are told.
 *
 * Per frame (LED_FPS, 200 a second), for every LED:
 *   1. the scene's target lightness L in 0..1 (CIE L* / 100: equal steps of L look
 *      equal), or the console's override;
 *   2. the ceilings, applied to luminance: the LED colour's own (LED_CEIL_*: the
 *      0603 orange's 20 mA, violet's eye safety), the power state's (USB only:
 *      dim) and a master dimmer;
 *   3. THE SLEW LIMIT, in L: no LED's L moves more than LED_SLEW_PER_FRAME in a
 *      frame, i.e. nothing changes faster than a fade from 0 to full in
 *      LED_FADE_MIN_S (300 ms).  Every input, ceilings included, passes through it,
 *      so no LED ever steps, whatever a scene or the console asks
 *      (test/test_leds.c proves it on every scene);
 *   4. L -> luminance Y (CIE L*), -> the LP5036's 12-bit duty;
 *   5. the bank split: three outputs share a bank brightness register B and each
 *      has its own colour register C; the duty is their product.  B is the
 *      smallest that lets the bank's brightest output reach its duty (and at
 *      least 16, where one step of C is one step of the 12-bit PWM), so dim
 *      LEDs keep the finest steps;
 *   6. temporal dithering of what the registers cannot make exactly: error
 *      diffusion in the chip's own duty units (its truncation of C * B / 16
 *      included), the error carried to the next frame; but a duty within
 *      LED_DITHER_DEADBAND of a step of a level the chip can make is rounded to it,
 *      so no dither pattern is slower than about 30 Hz (a slow pattern at the
 *      bottom of the range would be a visible twinkle).
 *
 * The result is the register image the glue writes in one I2C burst per driver:
 * LEDx_BRIGHTNESS (0x08-0x13) then OUTx_COLOR (0x14-0x37), auto-increment.
 *
 * Portable: no SDK.  Single-precision float throughout.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "config.h"
#include "led_map.h"

#define LED_SLEW_PER_FRAME   (1.0f / (LED_FADE_MIN_S * (float)LED_FPS))   /* in L (0..1) */
#define LED_DITHER_DEADBAND  0.15f      /* of a step: rounded, not dithered */

/* LP5036 registers (datasheet table 4) */
#define LP5036_DEVICE_CONFIG0   0x00    /* bit 6 Chip_EN */
#define LP5036_DEVICE_CONFIG1   0x01    /* Log_Scale_EN 5, Power_Save_EN 4, Auto_Incr_EN 3,
                                           PWM_Dithering_EN 2, Max_Current_Option 1, LED_Global_Off 0 */
#define LP5036_LED_CONFIG0      0x02    /* LEDx_Bank_EN: 0 = independent (ours) */
#define LP5036_LED_CONFIG1      0x03
#define LP5036_LED0_BRIGHTNESS  0x08    /* ... LED11_BRIGHTNESS 0x13: one per bank of three */
#define LP5036_OUT0_COLOR       0x14    /* ... OUT35_COLOR 0x37 */
#define LP5036_RESET            0x38    /* write 0xFF */
#define LP5036_CHIP_EN          0x40
/* linear dimming (we do our own curve), no power save (no wake-up glitch), auto-increment,
 * the chip's 3-bit PWM dithering (12-bit duty), 25.5 mA, LEDs on */
#define LP5036_CONFIG1_VALUE    ((0u << 5) | (0u << 4) | (1u << 3) | (1u << 2) | (0u << 1) | 0u)
#define LP5036_FRAME_REG        LP5036_LED0_BRIGHTNESS
#define LP5036_FRAME_BYTES      (LED_DRIVER_BANKS + LED_DRIVER_CHANNELS)    /* 48 */

/* The chip's duty from a colour register C and its bank's brightness B, in 12-bit
 * steps.  [ASSUMED] the 8 x 8-bit product truncated to 12 bits (the datasheet says
 * only "the product ... 12 bits of control accuracy"); a photodiode on the bench
 * confirms.  Full scale (255, 255) is 4064. */
static inline uint16_t lp5036_duty12(unsigned colour, unsigned bank) { return (uint16_t)((colour * bank) >> 4); }
#define LP5036_DUTY_FULL     4064.0f

typedef struct {
    float l_out[LED_COUNT];          /* the slew-limited lightness being shown, 0..1 */
    float override_l[LED_COUNT];     /* the console's level, or < 0 for none */
    float dither[LED_COUNT];         /* the carried error, in 12-bit duty steps */
    float ceiling;                   /* power-state ceiling on luminance, 0..1 */
    float master;                    /* dimmer on luminance, 0..1 */
    bool driver_present[LED_DRIVERS];
    uint8_t reg[LED_DRIVERS][LP5036_FRAME_BYTES];   /* the register image, from 0x08 */
    uint16_t duty[LED_COUNT];        /* the 12-bit duty the image sets (lp5036_duty12) */
    uint32_t frames;
} led_engine;

void led_engine_init(led_engine *e);
/* one frame: targets in L (0..1), one per LED (led_map.h's order) */
void led_engine_frame(led_engine *e, const float target_l[LED_COUNT]);
void led_engine_set_ceiling(led_engine *e, float luminance_fraction);
void led_engine_set_master(led_engine *e, float luminance_fraction);
/* the console's `led <name|all> <level>`: level 0..1 in L, or < 0 to hand back to the scene */
void led_engine_override(led_engine *e, int led, float level);
void led_engine_override_all(led_engine *e, float level);
int led_engine_find(const char *name);           /* LED index by name (case-insensitive), or -1 */
/* a driver just (re)started from reset, dark: its LEDs restart from 0 and fade in */
void led_engine_driver_reset(led_engine *e, int driver);
float led_colour_ceiling(unsigned colour);

/* CIE 1976 lightness, both normalised to 0..1 */
float led_l_to_y(float l);
float led_y_to_l(float y);
