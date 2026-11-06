/* main.c: OWLternating Current's firmware, core 0.
 *
 * Start-up, in this order:
 *   1. board_safe_init(): every bridge input low, the DRV8874s asleep, the perch
 *      drivers disabled; before anything else can run;
 *   2. the UART log (GPIO16/17, 115200) and USB (one CDC serial port, the JSON console,
 *      and Raspberry Pi's reset interface for `picotool reboot -u`);
 *   3. the I2C bus (freed if stuck), a scan reported on the console, the LED drivers
 *      (the tree's may be absent: it is looked for again every few seconds), the
 *      sensors;
 *   4. core 1 (rt.c): the 10 kHz tick, the ADC, the safety checks, the coils;
 *   5. the audio (silent), the theremin's counters, the watchdog.
 *
 * Then a loop of 2.5 ms slots (the I2C bus is core 0's): the 3-axis Hall sensor at
 * 400 Hz (the pendulum), one LED driver's frame per slot (200 frames a second, both
 * drivers), the IMU at 100 Hz, the light sensor at 5 Hz, the theremin and film mode at
 * 100 Hz; the familiars at 1 kHz; USB and the console between slots.
 *
 * The watchdog (WATCHDOG_MS) is fed only while core 1's tick is advancing, so either
 * core stalling resets the chip, and a reset leaves every bridge asleep.  Three
 * watchdog resets in a row restart in BOOTSEL (GPiBridge's rule), so a bad image can
 * always be replaced over USB.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/watchdog.h"
#include "tusb.h"

#include "audio.h"
#include "board.h"
#include "board_pins.h"
#include "coils.h"
#include "config.h"
#include "console.h"
#include "familiar.h"
#include "film.h"
#include "i2c_bus.h"
#include "jsonbuf.h"
#include "led_engine.h"
#include "lp5036.h"
#include "pendulum.h"
#include "rt.h"
#include "scenes.h"
#include "sensors.h"
#include "settings.h"
#include "theremin.h"
#include "theremin_hw.h"
#include "usb_descriptors.h"
#include "version.h"

#define SLOT_US 2500u

static lp5036 drv[LED_DRIVERS];
static led_engine leds;
static scenes show;
static scene_inputs sin_;
static imu_state imu;
static als_state als;
static tmag_state tmag;
static pendulum pend;
static fam_perch perch[2];
static fam_cmd perch_applied[2];
static film_seq film;
static theremin thr;
static settings_data cfg;
static bool theremin_on, familiars_on;
static int sweep_watch[2];               /* 1: report this perch's next sweep; 2: in progress */
static int pend_cal_left;                /* TMAG readings still to average for `pend cal` */
static float pend_cal_sum[3];
static uint64_t t0_us;

static float now_s(void) { return (float)((time_us_64() - t0_us) * 1e-6); }

/* ---- the console's lines out: the UART always, USB when a terminal is open ----------
 * The UART (115200 baud, 11.5 bytes a millisecond) would hold the loop for 130 ms on a
 * long reply if written directly, so lines queue in a ring and drain between slots; a
 * line that does not fit whole is dropped and counted. */
#define ULOG_SIZE 8192u
static char ulog[ULOG_SIZE];
static uint32_t ulog_head, ulog_tail, ulog_dropped;

static void ulog_line(const char *s)
{
    size_t n = strlen(s);
    uint32_t used = (ulog_head - ulog_tail) % ULOG_SIZE;
    if (n + 2u >= ULOG_SIZE - used) {
        ulog_dropped++;
        return;
    }
    for (size_t i = 0; i < n; i++)
        ulog[ulog_head++ % ULOG_SIZE] = s[i];
    ulog[ulog_head++ % ULOG_SIZE] = '\r';
    ulog[ulog_head++ % ULOG_SIZE] = '\n';
    ulog_head %= ULOG_SIZE;
}

static void ulog_drain(void)
{
    while (ulog_tail != ulog_head && uart_is_writable(uart0)) {
        uart_putc_raw(uart0, ulog[ulog_tail]);
        ulog_tail = (ulog_tail + 1u) % ULOG_SIZE;
    }
}

static uint32_t usb_dropped;

static void out_line(const char *s)
{
    ulog_line(s);
    if (tud_cdc_connected()) {
        uint32_t n = (uint32_t)strlen(s);
        if (tud_cdc_write_available() >= n + 2u) {   /* whole lines or nothing: never half a JSON object */
            tud_cdc_write(s, n);
            tud_cdc_write_str("\r\n");
            tud_cdc_write_flush();
        } else {
            usb_dropped++;
        }
    }
}

static void event(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void event(const char *fmt, ...)
{
    static char buf[CONSOLE_REPLY_MAX];      /* core 0's main loop only */
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    out_line(buf);
}

/* ---- status --------------------------------------------------------------------------- */
static void faults_json(jsonbuf *j, uint32_t f)
{
    jb_add(j, "[");
    bool first = true;
    for (unsigned b = 0; b < 32; b++)
        if (f & (1u << b)) {
            jb_add(j, "%s\"%s\"", first ? "" : ",", rt_fault_name(b));
            first = false;
        }
    jb_add(j, "]");
}

static void lev_json(char *buf, size_t n)
{
    lev_telemetry t;
    lev_get_telemetry(&rt_lev, &t);
    jsonbuf j = jb_start(buf, n);
    jb_add(&j, "{\"state\":\"%s\",\"gap_mm\":%.3f,\"gref_mm\":%.3f,\"gzp_mm\":%.3f,\"bbat_mT\":%.2f,"
               "\"i_cmd_A\":%.3f,\"i_est_A\":%.3f,\"mean_I_mA\":%.1f,\"rms_I_mA\":%.1f,\"peak_I_A\":%.2f,"
               "\"catches\":%lu,\"losses\":%lu,\"trips\":%lu,\"reason\":\"%s\",\"cal\":\"%s\",\"bat_sign\":%d,"
               "\"coil_pol\":%d,\"kcs_mT_per_A\":%.3f,\"hall_offset_mT\":%.2f,\"eyes\":%.2f,\"carrier\":%s,\"params\":{",
           lev_state_name(t.state), (double)t.gap_mm, (double)t.gref_mm, (double)t.gzp_mm, (double)t.bbat_mT,
           (double)t.i_cmd_A, (double)t.i_est_A, (double)(t.mean_I_A * 1e3f), (double)(t.rms_I_A * 1e3f),
           (double)t.peak_I_A, (unsigned long)t.catches, (unsigned long)t.losses, (unsigned long)t.trips,
           t.reason ? t.reason : "", t.cal ? t.cal : "", t.bat_sign, t.coil_pol, (double)t.kcs_mT_per_A,
           (double)t.hall_offset_mT, (double)rt.lev_eyes, rt.carrier_on ? "true" : "false");
    for (int i = 0; i < lev_param_count(); i++)
        jb_add(&j, "%s\"%s\":%g", i ? "," : "", lev_param_name(i), (double)lev_get_param(&rt_lev, i));
    jb_add(&j, "}}");
}

static void status_json(char *buf, size_t n)
{
    jsonbuf j = jb_start(buf, n);
    jb_add(&j, "{\"version\":\"%s\",\"board\":\"%s\",\"uptime_s\":%lu,", OWL_FW_VERSION, OWL_BOARD,
           (unsigned long)(time_us_64() / 1000000u));
    jb_add(&j, "\"rails\":{\"v12\":%.2f,\"v5\":%.2f,\"vbus\":%.2f,\"coils_powered\":%s,\"usb_only\":%s},",
           (double)rt.v12, (double)rt.v5, (double)rt.vbus, rt.power_ok ? "true" : "false",
           (!rt.power_ok && rt.vbus > VBUS_PRESENT_V) ? "true" : "false");
    jb_add(&j, "\"i2c\":{\"led_base\":%s,\"led_tree\":%s,\"imu\":%s,\"als\":%s,\"tmag\":%s,\"errors\":%lu},",
           drv[0].present ? "true" : "false", drv[1].present ? "true" : "false", imu.present ? "true" : "false",
           als.present ? "true" : "false", tmag.present ? "true" : "false", (unsigned long)i2c_errors());
    jb_add(&j, "\"faults\":");
    faults_json(&j, rt.faults);
    jb_add(&j, ",\"temps_C\":{\"pend1\":%.1f,\"pend2\":%.1f,\"pend3\":%.1f,\"lev\":%.1f,\"imu\":%.1f,\"tmag\":%.1f},",
           (double)rt.temp_C[0], (double)rt.temp_C[1], (double)rt.temp_C[2], (double)rt.temp_C[3],
           (double)(imu.present ? imu.temp_C : NAN), (double)(tmag.present ? tmag.temp_C : NAN));
    jb_add(&j, "\"coils\":{\"awake\":%s,\"i_meas_A\":[%.3f,%.3f,%.3f,%.3f],\"u\":[%.3f,%.3f,%.3f,%.3f],"
               "\"r_ohm\":[%.2f,%.2f,%.2f,%.2f]},",
           rt.drv_awake ? "true" : "false", (double)rt.i_meas[0], (double)rt.i_meas[1], (double)rt.i_meas[2],
           (double)rt.i_meas[3], (double)rt.u[0], (double)rt.u[1], (double)rt.u[2], (double)rt.u[3],
           (double)rt.r_ohm[0], (double)rt.r_ohm[1], (double)rt.r_ohm[2], (double)rt.r_ohm[3]);
    jb_add(&j, "\"hall_mT\":%.2f,\"tmag_mT\":[%.3f,%.3f,%.3f],", (double)rt.hall_mT, (double)tmag.b_mT[0],
           (double)tmag.b_mT[1], (double)tmag.b_mT[2]);
    lev_telemetry lt;
    lev_get_telemetry(&rt_lev, &lt);
    jb_add(&j, "\"lev\":{\"state\":\"%s\",\"gap_mm\":%.3f,\"mean_I_mA\":%.1f,\"reason\":\"%s\"},",
           lev_state_name(lt.state), (double)lt.gap_mm, (double)(lt.mean_I_A * 1e3f), lt.reason ? lt.reason : "");
    pend_status ps;
    pend_status_get(&pend, &ps);
    jb_add(&j, "\"pend\":{\"mode\":\"%s\",\"stage\":\"%s\",\"present\":%s,\"x_mm\":%.1f,\"y_mm\":%.1f,"
               "\"amp_mm\":%.1f,\"f_hz\":%.3f,\"chosen\":%d},",
           ps.mode ? ps.mode : "", ps.stage ? ps.stage : "", ps.present ? "true" : "false",
           (double)(ps.x_m * 1e3f), (double)(ps.y_m * 1e3f), (double)(ps.amp_m * 1e3f), (double)ps.f_hz, ps.chosen);
    jb_add(&j, "\"familiars\":[");
    for (int p = 0; p < 2; p++)
        jb_add(&j, "%s{\"perch\":\"fam%d\",\"state\":\"%s\",\"who\":\"%s\",\"f_hz\":%.0f,\"duty\":%.3f,\"isense_A\":%.3f}",
               p ? "," : "", p + 1, fam_state_name(perch[p].state), fam_who_name(perch[p].who),
               (double)perch_freq(p), (double)perch_duty(p), (double)rt.fam_isense[p]);
    jb_add(&j, "],\"scene\":{\"name\":\"%s\",\"manual\":%s,\"kuramoto_r\":%.2f},",
           scene_name(scenes_current(&show)), scenes_is_manual(&show) ? "true" : "false", (double)show.kuramoto_r);
    jb_add(&j, "\"theremin\":{\"on\":%s,\"ok\":%s,\"active\":%s,\"f_pitch\":%.0f,\"f_vol\":%.0f,\"pitch_hz\":%.0f,"
               "\"volume\":%.2f,\"loudness\":%.2f},",
           theremin_on ? "true" : "false", thr.ok ? "true" : "false", thr.active ? "true" : "false",
           (double)thr.f_pitch, (double)thr.f_vol, (double)thr.pitch_hz, (double)thr.volume, (double)cfg.volume);
    jb_add(&j, "\"film\":{\"on\":%s,\"phase\":\"%s\"},", film_active(&film) ? "true" : "false",
           film_phase_name(&film));
    jb_add(&j, "\"light\":{\"lux\":%.2f},\"imu\":{\"g\":[%.3f,%.3f,%.3f],\"taps\":%lu,\"double_taps\":%lu},",
           (double)als.lux, (double)imu.g[0], (double)imu.g[1], (double)imu.g[2], (unsigned long)imu.taps,
           (unsigned long)imu.double_taps);
    jb_add(&j, "\"rt\":{\"ticks\":%lu,\"overruns\":%lu,\"adc_errors\":%lu,\"tick_us_max\":%lu},",
           (unsigned long)rt.ticks, (unsigned long)rt.overruns, (unsigned long)rt.adc_errors,
           (unsigned long)rt.tick_cycles_max);
    jb_add(&j, "\"leds\":{\"frames\":%lu,\"errors\":[%lu,%lu]},\"lines_dropped\":{\"uart\":%lu,\"usb\":%lu}}",
           (unsigned long)leds.frames, (unsigned long)drv[0].errors, (unsigned long)drv[1].errors,
           (unsigned long)ulog_dropped, (unsigned long)usb_dropped);
}

static void adc_dump_json(char *buf, size_t n)
{
    static const char *const MUX_NAMES[MUX_CHANNELS] = {
        [MUX_CH_PEND1_IPROPI] = "pend1_ipropi", [MUX_CH_PEND2_IPROPI] = "pend2_ipropi",
        [MUX_CH_PEND3_IPROPI] = "pend3_ipropi", [MUX_CH_FAM1_ISENSE] = "fam1_isense",
        [MUX_CH_FAM2_ISENSE] = "fam2_isense", [MUX_CH_V12_SENSE] = "v12_sense",
        [MUX_CH_V5_SENSE] = "v5_sense", [MUX_CH_VBUS_SENSE] = "vbus_sense",
    };
    jsonbuf j = jb_start(buf, n);
    jb_add(&j, "{\"adc_hall\":{\"raw\":%u,\"V\":%.4f,\"mT\":%.2f},", rt.raw_adc[ADC_SLOT_HALL],
           (double)adc_volts(rt.raw_adc[ADC_SLOT_HALL]), (double)rt.hall_mT);
    jb_add(&j, "\"adc_lev_ipropi\":{\"raw\":%u,\"V\":%.4f,\"A\":%.3f},\"mux\":{", rt.raw_adc[ADC_SLOT_LEV_IPROPI],
           (double)adc_volts(rt.raw_adc[ADC_SLOT_LEV_IPROPI]), (double)rt.i_meas[COIL_LEV]);
    for (int c = 0; c < MUX_CHANNELS; c++)
        jb_add(&j, "%s\"%s\":{\"raw\":%u,\"V\":%.4f}", c ? "," : "", MUX_NAMES[c] ? MUX_NAMES[c] : "?",
               rt.raw_mux[c], (double)adc_volts(rt.raw_mux[c]));
    jb_add(&j, "},\"scaled\":{\"v12\":%.3f,\"v5\":%.3f,\"vbus\":%.3f,\"i_A\":[%.3f,%.3f,%.3f,%.3f],"
               "\"fam_isense_A\":[%.3f,%.3f]}}",
           (double)rt.v12, (double)rt.v5, (double)rt.vbus, (double)rt.i_meas[0], (double)rt.i_meas[1],
           (double)rt.i_meas[2], (double)rt.i_meas[3], (double)rt.fam_isense[0], (double)rt.fam_isense[1]);
}

/* ---- the console's actions --------------------------------------------------------------- */
static const char *a_scene(int id)
{
    if (id < 0)
        scenes_auto(&show);
    else
        scenes_select(&show, (scene_id)id);
    return NULL;
}

static const char *a_led(int led, float level)
{
    if (led < 0)
        led_engine_override_all(&leds, level);
    else
        led_engine_override(&leds, led, level);
    return NULL;
}

static const char *a_coil(int c, float duty, uint32_t ms)
{
    const char *e = console_coil_limits(duty, ms, rt.v12, rt.r_ohm[c] > 0.0f ? rt.r_ohm[c] : COIL_R20_OHM);
    if (e)
        return e;
    if (c == COIL_LEV && rt_lev.state != LEV_OFF)
        return "the levitation loop has the coil (lev off first)";
    float amps = duty * rt.v12 / (thermal_r_ohm(&rt_thermal[c]) + DRV_RDSON_OHM);
    float room = thermal_max_on_s(&rt_thermal[c], fabsf(amps), COIL_SURFACE_LIMIT_C, (float)ms / 1000.0f);
    if (room < (float)ms / 1000.0f)
        return "the coil is too warm for that (status: temps_C)";
    if (!rt_coil_request(c, amps, ms, RT_OWNER_CONSOLE))
        return "refused: no 12 V or the bridges are latched off (status: faults; clear)";
    return NULL;
}

static const char *a_sweep(int p)
{
    if (!familiars_on)
        return "the familiars are off";
    if (!rt.power_ok || rt.v5 < V5_PRESENT_V)
        return "no 12 V / 5 V: the perches stay off";
    perch[p].t_last_sweep = -1e9f;      /* sweep at its next idle moment */
    sweep_watch[p] = 1;
    return NULL;
}

static const char *a_lev(int op, const char *param, float v)
{
    switch (op) {
    case LEV_OP_ON:
        lev_enable(&rt_lev, true);          /* without 12 V it waits (INHIBIT) */
        return NULL;
    case LEV_OP_OFF:
        lev_enable(&rt_lev, false);
        return NULL;
    case LEV_OP_CAL:
        if (!lev_request_cal(&rt_lev, param && !strcmp(param, "zero") ? LEV_CAL_ZERO : LEV_CAL_COIL))
            return "refused while the bat floats (lev off first)";
        return NULL;
    case LEV_OP_TUNE:
        return lev_set_param(&rt_lev, param, v) ? NULL : "unknown parameter or out of range (lev status lists them)";
    case LEV_OP_EYES:
        rt.lev_eyes = v;
        return NULL;
    default:
        return "?";
    }
}

static const char *a_pend(int m)
{
    if (m == PEND_OP_CAL) {
        if (!tmag.present)
            return "no TMAG5273";
        pend_cal_left = 200;            /* half a second at 400 Hz */
        pend_cal_sum[0] = pend_cal_sum[1] = pend_cal_sum[2] = 0.0f;
        return NULL;
    }
    if (m != PEND_MODE_OFF && film_active(&film))
        return "film mode is on (film off first)";
    if (m != PEND_MODE_OFF && !tmag.present)
        return "no TMAG5273: the pendulum cannot see the bat";
    pend_set_mode(&pend, (pend_mode)m);
    if (m == PEND_MODE_OFF)
        rt_coil_release_owner(RT_OWNER_PEND);
    return NULL;
}

static const char *a_theremin(int op)
{
    if (op == THEREMIN_OP_ON)
        theremin_on = true;
    else if (op == THEREMIN_OP_OFF)
        theremin_on = false;
    else
        theremin_calibrate(&thr);
    cfg.theremin_on = theremin_on;
    return NULL;
}

static const char *a_film(bool on)
{
    if (on) {
        if (!rt.power_ok)
            return "no 12 V";
        pend_set_mode(&pend, PEND_OFF);
        rt_coil_release_owner(RT_OWNER_PEND);
        film_start(&film, now_s());
    } else {
        film_stop(&film, now_s());
    }
    return NULL;
}

static const char *a_volume(float v)
{
    cfg.volume = v;
    return NULL;
}

static const char *a_clear(void)
{
    rt.clear_req++;
    return NULL;
}

static const char *a_save(void)
{
    lev_get_cal(&rt_lev, &cfg.lev);
    return settings_save(&cfg);
}

static void do_reboot(bool bootsel)
{
    lev_enable(&rt_lev, false);
    pend_set_mode(&pend, PEND_OFF);
    film_stop(&film, now_s());
    rt_coil_release_owner(RT_OWNER_PEND);
    rt_coil_release_owner(RT_OWNER_FILM);
    rt_coil_release_owner(RT_OWNER_CONSOLE);
    for (int p = 0; p < 2; p++)
        perch_set(p, false, 0.0f, 0.0f);
    /* core 1 lets everything go at its next tick; the UART gets the last lines out.  No
     * tud_task() here: this can run inside a TinyUSB callback (the 1200-baud habit). */
    uint32_t t0 = time_us_32();
    while (time_us_32() - t0 < 30000u)
        ulog_drain();
    board_bridges_off();
    if (bootsel)
        rom_reset_usb_boot_extra(-1, 0, false);
    watchdog_reboot(0, 0, 10);
    for (;;)
        tight_loop_contents();
}

static void a_reboot(bool bootsel) { do_reboot(bootsel); }

static const console_ops OPS = {
    .reply = out_line, .scene = a_scene, .led = a_led, .coil = a_coil, .sweep = a_sweep, .lev = a_lev,
    .pend = a_pend, .theremin = a_theremin, .film = a_film, .volume = a_volume, .clear = a_clear, .save = a_save,
    .status_json = status_json, .lev_json = lev_json, .i2c_scan_json = i2c_scan_json,
    .adc_dump_json = adc_dump_json, .reboot = a_reboot,
};

/* the console port at 1200 baud: the Arduino habit for "go to BOOTSEL" */
void tud_cdc_line_coding_cb(uint8_t itf, cdc_line_coding_t const *coding)
{
    if (itf == USB_CDC_CONSOLE && coding->bit_rate == 1200)
        do_reboot(true);
}

/* ---- the slots' work ----------------------------------------------------------------------- */
static void leds_frame(void)
{
    led_engine_set_ceiling(&leds, rt.power_ok ? 1.0f : LED_USB_ONLY_CEILING);
    float target[LED_COUNT];
    sin_.dt_s = 1.0f / (float)LED_FPS;
    sin_.lev_holding = rt_lev.state == LEV_HOLD;
    scenes_render(&show, &sin_, target);
    led_engine_frame(&leds, target);
    sin_.tap = sin_.double_tap = sin_.button = false;   /* consumed */
}

static void leds_write(int d)
{
    if (!drv[d].present)
        return;
    if (!lp5036_write_frame(&drv[d], leds.reg[d]) && drv[d].errors > 20 && drv[d].errors % 20 == 0)
        drv[d].present = false;          /* gone: looked for again later */
}

static void leds_look_for_drivers(void)
{
    for (int d = 0; d < LED_DRIVERS; d++)
        if (!drv[d].present && lp5036_init(&drv[d], LED_DRIVER_ADDR[d])) {
            led_engine_driver_reset(&leds, d);           /* it starts dark: fade in */
            event("{\"event\":\"led_driver\",\"addr\":\"0x%02X\",\"present\":true}", LED_DRIVER_ADDR[d]);
        }
}

static float pend_applied[PEND_COILS];

static void pendulum_sample(void)
{
    if (!tmag_read(&tmag))
        return;
    if (pend_cal_left > 0) {
        for (int k = 0; k < 3; k++)
            pend_cal_sum[k] += tmag.b_mT[k];
        if (--pend_cal_left == 0) {
            for (int k = 0; k < 3; k++)
                cfg.pend_offset_mT[k] = pend_cal_sum[k] / 200.0f;
            cfg.pend_offset_valid = 1;
            pend_set_offset(&pend, cfg.pend_offset_mT[0], cfg.pend_offset_mT[1], cfg.pend_offset_mT[2]);
            event("{\"event\":\"pend_cal\",\"offset_mT\":[%.3f,%.3f,%.3f]}", (double)cfg.pend_offset_mT[0],
                  (double)cfg.pend_offset_mT[1], (double)cfg.pend_offset_mT[2]);
        }
    }
    for (int c = 0; c < PEND_COILS; c++) {
        float r = rt.r_ohm[c] > 0.0f ? rt.r_ohm[c] : COIL_R20_OHM;
        pend_applied[c] = (float)PEND_POLARITY * rt.u[c] * rt.v12 / (r + DRV_RDSON_OHM);
    }
    pend_cmd cmd;
    pend_sample(&pend, tmag.t_us, tmag.b_mT[0], tmag.b_mT[1], tmag.b_mT[2], pend_applied, &cmd);
    if (pend.mode != PEND_OFF && !film_active(&film))
        for (int c = 0; c < PEND_COILS; c++)
            if (cmd.i_A[c] != 0.0f)
                rt_coil_request(c, (float)PEND_POLARITY * cmd.i_A[c], cmd.hold_ms, RT_OWNER_PEND);
    if (cmd.event == PEND_EV_CHOSE) {
        sin_.pendulum_choice = (int8_t)cmd.event_arg;
        event("{\"event\":\"pendulum\",\"chose\":%d}", cmd.event_arg);
    }
}

static void film_tick(void)
{
    if (!film_active(&film))
        return;
    const thermal_coil *th[FILM_COILS] = {&rt_thermal[0], &rt_thermal[1], &rt_thermal[2]};
    float i[FILM_COILS];
    film_step(&film, now_s(), th, i);
    for (int c = 0; c < FILM_COILS; c++)
        if (i[c] != 0.0f)
            rt_coil_request(c, i[c], 50, RT_OWNER_FILM);
    if (!film_active(&film))
        rt_coil_release_owner(RT_OWNER_FILM);
}

static void theremin_tick(void)
{
    float fp, fv;
    if (!theremin_hw_read(&fp, &fv)) {
        theremin_update(&thr, 0.0f, 0.0f, THEREMIN_WINDOW_MS * 1e-3f);
    } else {
        theremin_update(&thr, fp, fv, THEREMIN_WINDOW_MS * 1e-3f);
    }
    bool play = theremin_on && thr.ok && thr.active;
    audio_set(thr.pitch_hz, play ? thr.volume * cfg.volume : 0.0f);
    sin_.theremin_active = play;
    sin_.pitch01 = thr.near_pitch;
    sin_.volume01 = thr.near_vol;
}

static void familiars_tick(void)
{
    bool allowed = familiars_on && rt.power_ok && rt.v5 > V5_PRESENT_V;
    float t = now_s();
    for (int p = 0; p < 2; p++) {
        if (allowed != perch[p].enabled)
            fam_enable(&perch[p], allowed);
        fam_cmd cmd;
        fam_event ev = {0};
        fam_state before = perch[p].state;
        fam_step(&perch[p], t, rt.fam_isense[p], &perch_applied[p], &cmd, &ev);
        float f = perch_set(p, cmd.enable && allowed, cmd.freq_hz, cmd.duty);
        perch_applied[p] = (fam_cmd){cmd.enable && allowed, f, perch_duty(p)};
        if (ev.kind == FAM_EV_ARRIVED) {
            sin_.familiar[p] = (uint8_t)ev.who;
            event("{\"event\":\"familiar\",\"perch\":\"fam%d\",\"arrived\":\"%s\",\"f_hz\":%.0f}", p + 1,
                  fam_who_name(ev.who), (double)ev.freq_hz);
        } else if (ev.kind == FAM_EV_LEFT) {
            sin_.familiar[p] = FAMILIAR_NONE;
            event("{\"event\":\"familiar\",\"perch\":\"fam%d\",\"left\":true}", p + 1);
        }
        if (sweep_watch[p] == 1 && perch[p].state == FAM_ST_SWEEP)
            sweep_watch[p] = 2;
        if (sweep_watch[p] == 2 && before == FAM_ST_SWEEP && perch[p].state != FAM_ST_SWEEP) {
            static char buf[CONSOLE_REPLY_MAX];
            jsonbuf j = jb_start(buf, sizeof buf);
            jb_add(&j, "{\"event\":\"sweep\",\"perch\":\"fam%d\",\"f_kHz\":[", p + 1);
            for (int k = 0; k < FAM_SWEEP_N; k++)
                jb_add(&j, "%s%.1f", k ? "," : "", (double)(perch[p].f[k] * 1e-3f));
            jb_add(&j, "],\"y_mS\":[");
            for (int k = 0; k < FAM_SWEEP_N; k++)
                jb_add(&j, "%s%.3f", k ? "," : "", (double)(perch[p].y[k] * 1e3f));
            jb_add(&j, "],\"empty_mS\":[");
            for (int k = 0; k < FAM_SWEEP_N; k++)
                jb_add(&j, "%s%.3f", k ? "," : "", (double)(perch[p].base[k] * 1e3f));
            jb_add(&j, "]}");
            out_line(buf);
            sweep_watch[p] = 0;
        }
    }
}

static void imu_tick(void)
{
    static float single_at = -1.0f;
    if (!imu_read(&imu))
        return;
    for (int k = 0; k < 3; k++)
        sin_.gravity[k] = -imu.g[k];         /* the accelerometer reads up; the wisps want down */
    float t = now_s();
    /* a single tap waits out the double tap's window, so a double tap is not also a single */
    if (imu.double_tap) {
        sin_.double_tap = true;
        single_at = -1.0f;
    } else if (imu.tap) {
        single_at = t;
    }
    if (single_at >= 0.0f && t - single_at > 0.6f) {
        sin_.tap = true;
        single_at = -1.0f;
    }
    rt.ambient_C = imu.temp_C;
}

static void button_tick(void)
{
    static uint32_t stable_ms;
    static bool state, raw_prev;
    bool raw = board_button();
    stable_ms = raw == raw_prev ? stable_ms + 1u : 0u;
    raw_prev = raw;
    if (stable_ms == 30u && raw != state) {   /* 30 ms debounce */
        state = raw;
        if (state)
            sin_.button = true;
    }
}

/* events worth telling the console about without being asked */
static void watch_changes(void)
{
    static uint32_t faults;
    static lev_state lstate;
    static scene_id scene = SCENE_COUNT;
    if (rt.faults != faults) {
        uint32_t added = rt.faults & ~faults;
        faults = rt.faults;
        char buf[256];
        jsonbuf j = jb_start(buf, sizeof buf);
        jb_add(&j, "{\"event\":\"faults\",\"now\":");
        faults_json(&j, faults);
        jb_add(&j, ",\"new\":");
        faults_json(&j, added);
        jb_add(&j, "}");
        out_line(buf);
    }
    if (rt_lev.state != lstate) {
        lstate = rt_lev.state;
        lev_telemetry t;
        lev_get_telemetry(&rt_lev, &t);
        event("{\"event\":\"lev\",\"state\":\"%s\",\"reason\":\"%s\",\"gap_mm\":%.2f}", lev_state_name(lstate),
              t.reason ? t.reason : "", (double)t.gap_mm);
    }
    if (scenes_current(&show) != scene) {
        scene = scenes_current(&show);
        event("{\"event\":\"scene\",\"scene\":\"%s\"}", scene_name(scene));
    }
}

static void console_input(void)
{
    if (tud_cdc_available()) {
        char b[64];
        uint32_t n = tud_cdc_read(b, sizeof b);
        for (uint32_t i = 0; i < n; i++)
            console_feed(b[i]);
    }
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT)
        console_feed((char)c);
}

/* ---- start --------------------------------------------------------------------------------- */
int main(void)
{
    board_safe_init();                   /* before anything else: no coil can be driven */

    /* a reset by the watchdog running out (a hang), not by watchdog_reboot() (`reboot`); and
     * any watchdog reset at all, after which the coils may still be warm */
    bool wd = watchdog_enable_caused_reboot();
    bool warm = watchdog_caused_reboot();
    if (wd) {
        if (++watchdog_hw->scratch[0] >= CRASHES_TO_BOOTSEL) {
            watchdog_hw->scratch[0] = 0;
            rom_reset_usb_boot_extra(-1, 0, false);
        }
    } else {
        watchdog_hw->scratch[0] = 0;
    }
    stdio_init_all();                    /* printf: UART0 on GPIO16/17, the debug connector J5 */
    t0_us = time_us_64();
    tusb_init();
    console_init(&OPS);
    event("{\"event\":\"boot\",\"version\":\"%s\",\"board\":\"%s\",\"watchdog_reset\":%s}", OWL_FW_VERSION,
          OWL_BOARD, wd ? "true" : "false");

    settings_load(&cfg);
    theremin_on = cfg.theremin_on;
    familiars_on = cfg.familiars_on;

    i2c_bus_init();
    static char scan[512];
    i2c_scan_json(scan, sizeof scan);
    event("{\"event\":\"i2c_scan\",\"found\":%s}", scan);
    led_engine_init(&leds);
    led_engine_set_ceiling(&leds, LED_USB_ONLY_CEILING);
    for (int d = 0; d < LED_DRIVERS; d++) {
        bool ok = lp5036_init(&drv[d], LED_DRIVER_ADDR[d]);
        leds.driver_present[d] = ok;
        event("{\"event\":\"led_driver\",\"addr\":\"0x%02X\",\"present\":%s}", LED_DRIVER_ADDR[d],
              ok ? "true" : "false");
    }
    imu_init(&imu);
    als_init(&als);
    tmag_init(&tmag);
    event("{\"event\":\"sensors\",\"imu\":%s,\"als\":%s,\"tmag\":%s}", imu.present ? "true" : "false",
          als.present ? "true" : "false", tmag.present ? "true" : "false");

    scenes_init(&show, (uint32_t)time_us_32() ^ 0x0717u);
    memset(&sin_, 0, sizeof sin_);
    sin_.gravity[2] = -1.0f;
    sin_.lux = als.present ? SCENE_LUX_PENDING : -1.0f;
    sin_.pendulum_choice = -1;
    pend_params pp;
    pend_default_params(&pp);
    pend_init(&pend, &pp);
    if (cfg.pend_offset_valid)
        pend_set_offset(&pend, cfg.pend_offset_mT[0], cfg.pend_offset_mT[1], cfg.pend_offset_mT[2]);
    for (int p = 0; p < 2; p++)
        fam_init(&perch[p], p);
    film_init(&film);
    theremin_init(&thr);

    rt_start(!warm, &cfg.lev);           /* core 1: the tick, the ADC, the safety, the coils */
    if (wd)
        rt.faults |= RT_FAULT_WATCHDOG;
    perch_init();
    audio_init();
    theremin_hw_init();
    watchdog_enable(WATCHDOG_MS, true);

    uint32_t slot_at = time_us_32(), ms_at = slot_at, progress_at = slot_at, last_ticks = 0, slot = 0;
    uint64_t started = time_us_64();
    for (;;) {
        tud_task();
        ulog_drain();
        console_input();
        uint32_t now = time_us_32();
        if (now - ms_at >= 1000u) {      /* 1 kHz */
            ms_at += 1000u;
            if (now - ms_at > 20000u)
                ms_at = now;             /* fell far behind: catch up, do not race */
            familiars_tick();
            button_tick();
        }
        if (now - slot_at >= SLOT_US) {  /* 400 Hz: the I2C slots */
            slot_at += SLOT_US;
            if (now - slot_at > 20u * SLOT_US)
                slot_at = now;           /* fell far behind (a long console command): catch up */
            slot++;
            if (tmag.present && (pend.mode != PEND_OFF || pend_cal_left > 0 || (slot & 3u) == 0))
                pendulum_sample();
            if ((slot & 1u) == 0) {
                leds_frame();
                leds_write(LED_DRV_BASE);
            } else {
                leds_write(LED_DRV_TREE);
            }
            if ((slot & 3u) == 1)
                imu_tick();
            if ((slot & 3u) == 3) {
                theremin_tick();
                film_tick();
            }
            if (slot % 80u == 7u && als_read(&als))   /* a slot with no IMU read: under 1.6 ms of bus */
                sin_.lux = als.lux;
            if (slot % 2000u == 7u) {
                leds_look_for_drivers();     /* every 5 s: the tree plugged in late? */
                if (!als.present && als_init(&als))
                    sin_.lux = SCENE_LUX_PENDING;
                if (!imu.present)
                    imu_init(&imu);
                if (!tmag.present)
                    tmag_init(&tmag);
            }
            if (!imu.present && tmag.present)
                rt.ambient_C = tmag.temp_C;
            watch_changes();
        }
        /* the watchdog: only while core 1's tick advances */
        if (rt.ticks != last_ticks) {
            last_ticks = rt.ticks;
            progress_at = now;
        }
        if (now - progress_at < 50000u)
            watchdog_update();
        if (watchdog_hw->scratch[0] && time_us_64() - started > 10000000u)
            watchdog_hw->scratch[0] = 0;     /* ran ten seconds: this image is fine */
    }
}
