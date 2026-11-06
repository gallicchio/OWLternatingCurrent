/* bringup_main.c: the bring-up image (owl_bringup), core 0 only.
 *
 * For the first power-up of an untested board.  board_safe_init() first; then the
 * UART (J5, 115200) and USB (CDC "OWL bring-up", and Raspberry Pi's reset interface so
 * `picotool reboot -u -f` and opening the port at 1200 baud reach BOOTSEL); the coil
 * and perch PWM slices configured with their pins still plain and low; the theremin's
 * two PIO edge counters.  Then bringup_cmd.c runs the console.
 *
 * Not here, on purpose: the watchdog, core 1, DMA, the audio's DMA voice, the scenes,
 * any automatic coil, perch or sound.  Every bridge is driven only inside a command,
 * which ends with board_bridges_off() (bringup_cmd.c also calls it after every line).
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "pico/unique_id.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/pwm.h"
#include "hardware/uart.h"
#include "hardware/watchdog.h"
#include "tusb.h"

#include "board.h"
#include "board_pins.h"
#include "bringup_cmd.h"
#include "coils.h"
#include "config.h"
#include "edge_count.pio.h"
#include "i2c_bus.h"
#include "usb_descriptors.h"

/* ---- lines out: the UART always (through a ring, drained between commands and in
 * every wait), USB when a terminal has the port open; whole lines or nothing ------------ */
#define ULOG_SIZE 8192u
static char ulog[ULOG_SIZE];
static uint32_t ulog_head, ulog_tail;

static void ulog_drain(void)
{
    while (ulog_tail != ulog_head && uart_is_writable(uart0)) {
        uart_putc_raw(uart0, ulog[ulog_tail]);
        ulog_tail = (ulog_tail + 1u) % ULOG_SIZE;
    }
}

static void out_line(const char *s)
{
    size_t n = strlen(s);
    uint32_t used = (ulog_head - ulog_tail + ULOG_SIZE) % ULOG_SIZE;
    if (n + 2u < ULOG_SIZE - used) {
        for (size_t i = 0; i < n; i++)
            ulog[ulog_head++ % ULOG_SIZE] = s[i];
        ulog[ulog_head++ % ULOG_SIZE] = '\r';
        ulog[ulog_head++ % ULOG_SIZE] = '\n';
        ulog_head %= ULOG_SIZE;
    }
    if (tud_cdc_connected()) {
        /* wait (briefly) for room rather than drop a line: the host reads continuously */
        uint32_t t0 = time_us_32();
        while (tud_cdc_write_available() < n + 2u && time_us_32() - t0 < 50000u) {
            tud_task();
            tud_cdc_write_flush();
        }
        if (tud_cdc_write_available() >= n + 2u) {
            tud_cdc_write(s, (uint32_t)n);
            tud_cdc_write_str("\r\n");
            tud_cdc_write_flush();
        }
    }
}

static void poll(void)
{
    tud_task();
    ulog_drain();
}

static uint32_t now_us(void) { return time_us_32(); }

static void wait_us(uint32_t us)
{
    uint32_t t0 = time_us_32();
    if (us < 200u) {                     /* short settles: exact, nothing else in between */
        busy_wait_us_32(us);
        return;
    }
    while (time_us_32() - t0 < us)
        poll();
}

static bool input_pending(void) { return tud_cdc_available() > 0 || uart_is_readable(uart0); }

static uint16_t adc_read_input(unsigned input)
{
    adc_select_input(input);
    return adc_read();
}

static void mux_select(unsigned ch) { board_mux_select(ch); }

static bool gpio_level(unsigned pin) { return gpio_get(pin); }

/* the bus's lines as found (with the pads' pull-ups), then nine clocks, then I2C0 */
static bool i2c_up(bool *sda_low, bool *scl_low)
{
    gpio_init(PIN_SDA);
    gpio_init(PIN_SCL);
    gpio_set_dir(PIN_SDA, GPIO_IN);
    gpio_set_dir(PIN_SCL, GPIO_IN);
    gpio_pull_up(PIN_SDA);
    gpio_pull_up(PIN_SCL);
    busy_wait_us_32(20);
    *sda_low = !gpio_get(PIN_SDA);
    *scl_low = !gpio_get(PIN_SCL);
    bool freed = i2c_bus_recover();
    i2c_bus_init();
    return freed;
}

static void drv_sleep(bool asleep) { board_drv_sleep(asleep); }

static void coil_drive(int coil, float u)
{
    coils_connect(true);                 /* the four DRV8874 bridges' pins to their slices, coasting */
    coil_set_u(coil, u, 0.0f);           /* forward (or reverse) for |u| of each period, brake the rest */
}

static void bridges_off(void)
{
    perch_set(0, false, 0.0f, 0.0f);    /* coils.c's own record, so a later perch_set reconnects */
    perch_set(1, false, 0.0f, 0.0f);
    for (int c = 0; c < COIL_COUNT; c++)
        coil_coast(c);
    board_bridges_off();                 /* every bridge pin plain and low, nSLEEP low, FAM_EN low */
}

static float perch_drive(int perch, float freq_hz, float duty) { return perch_set(perch, true, freq_hz, duty); }

/* ---- a test tone: the audio PWM (146 kHz, 10 bits) as a sine, updated by polling; no
 * DMA.  The level rises to mid-scale and falls back slowly at each end (no pop). -------- */
static void audio_level(float x)
{
    if (x < 0.0f)
        x = 0.0f;
    if (x > (float)AUDIO_PWM_TOP)
        x = (float)AUDIO_PWM_TOP;
    pwm_set_chan_level(PWM_SLICE_AUDIO, PWM_CHAN_A, (uint16_t)lroundf(x));
}

static void tone(float hz, uint32_t ms, float amp)
{
    pwm_config c = pwm_get_default_config();
    pwm_config_set_wrap(&c, AUDIO_PWM_TOP);
    pwm_config_set_clkdiv_int(&c, 1);
    pwm_init(PWM_SLICE_AUDIO, &c, true);
    pwm_set_chan_level(PWM_SLICE_AUDIO, PWM_CHAN_A, 0);
    gpio_set_function(PIN_AUDIO, GPIO_FUNC_PWM);
    const float mid = (float)(AUDIO_PWM_TOP + 1u) / 2.0f;
    const uint32_t ramp_us = 100000u;
    uint32_t t0 = time_us_32();
    for (uint32_t t; (t = time_us_32() - t0) < ramp_us;) {
        audio_level(mid * (float)t / (float)ramp_us);
        if ((t & 0x3FFu) < 40u)
            poll();
    }
    t0 = time_us_32();
    uint32_t polled = t0;
    for (uint32_t t; (t = time_us_32() - t0) < ms * 1000u;) {
        audio_level(mid + amp * mid * sinf(6.2831853f * hz * (float)t * 1e-6f));
        if (time_us_32() - polled > 5000u) {    /* USB every 5 ms: a short glitch in the tone */
            poll();
            polled = time_us_32();
        }
    }
    t0 = time_us_32();
    for (uint32_t t; (t = time_us_32() - t0) < ramp_us;)
        audio_level(mid * (1.0f - (float)t / (float)ramp_us));
    pwm_set_chan_level(PWM_SLICE_AUDIO, PWM_CHAN_A, 0);
    gpio_set_function(PIN_AUDIO, GPIO_FUNC_SIO);
    gpio_put(PIN_AUDIO, 0);
    gpio_set_dir(PIN_AUDIO, GPIO_OUT);
}

/* ---- the theremin's oscillators: PIO0 state machines 0 and 1 count rising edges
 * (edge_count.pio: X falls by one an edge, each count pushed without blocking) --------- */
static bool osc_ready;

static void osc_init(void)
{
    uint offset = pio_add_program(pio0, &edge_count_program);
    edge_count_program_init(pio0, 0, offset, PIN_THEREMIN_PITCH);
    edge_count_program_init(pio0, 1, offset, PIN_THEREMIN_VOL);
    osc_ready = true;
}

/* the freshest count: empty the FIFO, then wait (at most 50 us) for the next push */
static bool osc_count(uint sm, uint32_t *x, uint32_t *t_us)
{
    while (!pio_sm_is_rx_fifo_empty(pio0, sm))
        (void)pio_sm_get(pio0, sm);
    uint32_t t0 = time_us_32();
    while (pio_sm_is_rx_fifo_empty(pio0, sm))
        if (time_us_32() - t0 > 50u)
            return false;
    *x = pio_sm_get(pio0, sm);
    *t_us = time_us_32();
    return true;
}

static bool osc(uint32_t ms, float *fp, float *fv)
{
    float f[2] = {0.0f, 0.0f};
    bool ok = osc_ready;
    uint32_t x0[2] = {0, 0}, t0[2] = {0, 0};
    bool got0[2];
    for (uint sm = 0; sm < 2; sm++)
        got0[sm] = osc_count(sm, &x0[sm], &t0[sm]);
    wait_us(ms * 1000u);
    for (uint sm = 0; sm < 2; sm++) {
        uint32_t x1, t1;
        if (!got0[sm] || !osc_count(sm, &x1, &t1) || t1 == t0[sm]) {
            ok = false;
            continue;
        }
        f[sm] = (float)(x0[sm] - x1) * 1e6f / (float)(t1 - t0[sm]);   /* X counts down */
    }
    *fp = f[0];
    *fv = f[1];
    return ok;
}

static void chip_id(char *buf, size_t n)
{
    char s[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
    pico_get_unique_board_id_string(s, sizeof s);
    snprintf(buf, n, "%s", s);
}

static void do_reboot(bool bootsel)
{
    bridges_off();
    uint32_t t0 = time_us_32();
    while (time_us_32() - t0 < 30000u)  /* the last lines out of the UART; no tud_task here:
                                           this can run inside a TinyUSB callback */
        ulog_drain();
    if (bootsel)
        rom_reset_usb_boot_extra(-1, 0, false);
    watchdog_reboot(0, 0, 10);
    for (;;)
        tight_loop_contents();
}

static const bringup_ops OPS = {
    .out = out_line, .now_us = now_us, .wait_us = wait_us, .poll = poll, .input_pending = input_pending,
    .adc_read = adc_read_input, .mux_select = mux_select, .gpio_get = gpio_level, .i2c_init = i2c_up,
    .i2c_probe = i2c_probe, .i2c_read = i2c_read_reg, .i2c_write = i2c_write_reg, .drv_sleep = drv_sleep,
    .coil_drive = coil_drive, .bridges_off = bridges_off, .perch_drive = perch_drive, .tone = tone, .osc = osc,
    .chip_id = chip_id, .reboot = do_reboot,
};

/* the console port at 1200 baud: the Arduino habit for "go to BOOTSEL" */
void tud_cdc_line_coding_cb(uint8_t itf, cdc_line_coding_t const *coding)
{
    if (itf == USB_CDC_CONSOLE && coding->bit_rate == 1200)
        do_reboot(true);
}

static void console_input(void)
{
    if (tud_cdc_available()) {
        char b[64];
        uint32_t n = tud_cdc_read(b, sizeof b);
        for (uint32_t i = 0; i < n; i++)
            bringup_feed(b[i]);
    }
    while (uart_is_readable(uart0))
        bringup_feed((char)uart_getc(uart0));
}

int main(void)
{
    board_safe_init();                   /* before anything else: no coil can be driven */
    stdio_init_all();                    /* UART0 on the debug connector J5, 115200 */
    tusb_init();
    coils_init();                        /* slices running, coasting; pins still plain and low */
    perch_init();
    osc_init();
    bringup_init(&OPS);                  /* boot, i2c, rails, i2c_scan lines (the UART has them all) */
    bool connected = false;
    for (;;) {
        poll();
        console_input();
        bool c = tud_cdc_connected();
        if (c && !connected)
            bringup_hello();             /* a terminal opened the port: say who we are */
        connected = c;
    }
}
