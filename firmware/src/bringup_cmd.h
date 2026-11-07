/* bringup_cmd.h: the bring-up image's console, portable.
 *
 * The bring-up image (owl_bringup, bringup_main.c) is for the first power-up of an
 * untested board: no watchdog, no core 1, no DMA, nothing automatic.  Every coil, perch
 * and sound happens only on a command, for a bounded time, and ends with every bridge
 * off.  So whatever goes wrong points at the hardware, not at the firmware.
 *
 * One command a line in (USB serial "OWL bring-up", or the UART at 115200), one JSON
 * object a line out: replies carry "ok":true, or "ok":false and "error"; events
 * ({"event":...}) go out on the same lines.  `help` lists the commands; the firmware
 * README has the table.
 *
 * This file is the parser, the limits and the sequences (what is read, in what order,
 * how long), behind bringup_ops: the board's side is bringup_main.c, a simulated
 * board's test/bringup_board_sim.c (test/test_bringup.c, test/bringup_sim).
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define BRINGUP_LINE_MAX  160
#define BRINGUP_REPLY_MAX 2048

/* the limits the commands keep (the README's table says them too) */
#define BU_LED_CAP_DEFAULT  0.5f     /* `led` duty above this needs `led cap 1` */
#define BU_COIL_DUTY_MAX    0.5f
#define BU_COIL_MS_MAX      500u
#define BU_COIL_I_MAX_A     1.0f     /* refused if |duty| x V12 / R20 would pass this */
#define BU_COIL_ABORT_A     1.5f     /* the mirror reading this stops the pulse at once */
#define BU_PERCH_DUTY_MAX   0.5f     /* `perch`: a square wave, to light a token; `sweep` keeps 0.1 */
#define BU_SWEEP_DUTY_MAX   0.1f
#define BU_PERCH_ABORT_A    0.2f     /* ISENSE (the bridge's 4.8 V supply current) this high stops the pulse */
#define BU_PERCH_MS_MAX     10000u   /* long enough to hold a scope probe on the coil */
#define BU_PERCH_F_MIN_HZ   50000.0f
#define BU_PERCH_F_MAX_HZ   500000.0f /* the bring-up build's perch_set clamp (CMakeLists) */
#define BU_PERCH_V5_MIN_V   4.5f
#define BU_TONE_AMP_MAX     1.0f     /* full scale: 3.3 Vpp x 1.1 into 8 ohm, 0.2 W (the real
                                        firmware's ceiling is 0.25; the bench wants it loud) */
#define BU_TONE_MS_MAX      20000u

typedef struct {
    void (*out)(const char *json);                       /* one JSON object: one line out */
    uint32_t (*now_us)(void);
    void (*wait_us)(uint32_t us);                        /* at least us; USB stays serviced */
    void (*poll)(void);                                  /* service USB inside long loops */
    bool (*input_pending)(void);                         /* a character is waiting (aborts walks) */
    uint16_t (*adc_read)(unsigned input);                /* one 12-bit conversion of ADC input 1-3 */
    void (*mux_select)(unsigned ch);                     /* the 74HC4051's channel */
    bool (*gpio_get)(unsigned pin);                      /* a pin's level */
    /* the I2C bus up: SDA and SCL as found (low = stuck) before nine clocks freed it;
     * returns whether SDA is free afterwards */
    bool (*i2c_init)(bool *sda_low, bool *scl_low);
    bool (*i2c_probe)(uint8_t addr);
    bool (*i2c_read)(uint8_t addr, uint8_t reg, uint8_t *data, size_t n);
    bool (*i2c_write)(uint8_t addr, uint8_t reg, const uint8_t *data, size_t n);
    void (*drv_sleep)(bool asleep);                      /* all four DRV8874s' nSLEEP */
    void (*coil_drive)(int coil, float u);               /* that bridge's PWM, mean u x 12 V */
    void (*bridges_off)(void);                           /* every bridge low, DRV8874s asleep, FAM_EN low */
    float (*perch_drive)(int perch, float freq_hz, float duty);   /* 0 or 1; FAM_EN on; the frequency set */
    void (*tone)(float hz, uint32_t ms, float amp);      /* blocks for ms (USB serviced), then silent */
    void (*audio_dc)(float level);                       /* the audio PWM held at level 0..1 of full
                                                            scale until the next call; < 0: off, pin low */
    bool (*osc)(uint32_t ms, float *pitch_hz, float *vol_hz);     /* false: an oscillator gave no edges */
    void (*chip_id)(char *buf, size_t n);                /* the unique ID, hex */
    void (*reboot)(bool bootsel);                        /* does not return on the board */
} bringup_ops;

/* the boot lines (boot, i2c, rails, i2c_scan), the LED drivers reset to dark */
void bringup_init(const bringup_ops *ops);
/* the boot event again (when a terminal opens the USB port) */
void bringup_hello(void);
/* one line (modified in place) */
void bringup_command(char *line);
/* characters one at a time; runs complete lines */
void bringup_feed(char c);
