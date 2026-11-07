/* bringup_board_sim.c: see bringup_board_sim.h. */
#define _DEFAULT_SOURCE                 /* usleep */
#include "bringup_board_sim.h"
#include "board_pins.h"
#include "coil_ids.h"
#include "config.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

board_sim sim;
void (*sim_line_out)(const char *line);
bool (*sim_stdin_pending)(void);

#define SIM_V12   12.0f
#define SIM_V5    4.80f
#define SIM_VBUS  5.0f
#define MIRROR_OFFSET_A 0.005f          /* a DRV8874 mirror's offset, as the bench may show */
static const float COIL_R[COIL_COUNT] = {2.40f, 2.38f, 2.43f, 2.62f};   /* a little warm, a little spread */

static bool is_lp5036(int a) { return a == I2C_ADDR_LP5036_BASE || a == I2C_ADDR_LP5036_TREE; }
static bool answers(int a)
{
    if (a == 0x1C)                      /* the LP5036s' broadcast address */
        return !sim.missing[0x1C] && (!sim.missing[I2C_ADDR_LP5036_BASE] || !sim.missing[I2C_ADDR_LP5036_TREE]);
    return (is_lp5036(a) || a == I2C_ADDR_LSM6DS3TR_C || a == I2C_ADDR_LTR_303ALS || a == I2C_ADDR_TMAG5273A2) &&
           !sim.missing[a];
}

static float noise(float amp)
{
    sim.noise = sim.noise * 1664525u + 1013904223u;
    return amp * ((float)(sim.noise >> 8) / 16777216.0f - 0.5f) * 2.0f;
}

static void power_on_regs(int a)
{
    memset(sim.reg[a], 0, sizeof sim.reg[a]);
    if (is_lp5036(a))
        sim.reg[a][0x01] = 0x3C;
    if (a == I2C_ADDR_LSM6DS3TR_C) {
        sim.reg[a][0x0F] = 0x6A;
        sim.reg[a][0x12] = 0x04;        /* CTRL3_C: IF_INC */
    }
    if (a == I2C_ADDR_LTR_303ALS) {
        sim.reg[a][0x86] = 0xA0;
        sim.reg[a][0x87] = 0x05;
    }
    if (a == I2C_ADDR_TMAG5273A2) {
        sim.reg[a][0x0D] = 0x02;        /* A2 */
        sim.reg[a][0x0E] = 0x49;
        sim.reg[a][0x0F] = 0x54;
    }
}

void sim_reset(void)
{
    sim.t_us = 1000;
    sim.mux = 0;
    sim.drv_awake = sim.fam_en = false;
    sim.coil = -1;
    sim.perch = -1;
    sim.rebooted = sim.bootsel = false;
    sim.noise = 12345u;
    for (int a = 0; a < 128; a++)
        power_on_regs(a);
}

static float v12(void) { return sim.no12v ? 0.0f : SIM_V12; }
static float v5(void) { return sim.no12v ? 0.0f : SIM_V5; }
static float vbus(void) { return sim.usb_off ? 0.0f : SIM_VBUS; }

static float coil_current(int c)
{
    if (!sim.drv_awake || sim.coil != c || v12() < 4.5f)
        return 0.0f;
    float i = fabsf(sim.coil_u) * v12() / (COIL_R[c] + DRV_RDSON_OHM);
    if (sim.short_coil == c)
        i *= 10.0f;
    return i > DRV_ITRIP_A ? DRV_ITRIP_A : i;
}

static float mirror_V(int c) { return (coil_current(c) + MIRROR_OFFSET_A) * IPROPI_V_PER_A; }

/* a perch bridge's supply current: the drivers' own draw, the coil's losses, and a
 * token's resonance (the coupled mode, ~15 % above its tuning) */
static float isense_V(int p)
{
    float i = 0.0008f;                                  /* the op-amp's offset, bridge off */
    if (sim.fam_en && sim.perch == p && v5() > 4.0f) {
        float f0 = sim.token == 1 ? 160000.0f : 350000.0f, q = 8.0f;
        float x = (sim.perch_f - f0) / (f0 / (2.0f * q));
        float bump = sim.token ? 1.5f / (1.0f + x * x) : 0.0f;
        i = 0.003f + 0.25f * sim.perch_duty * (1.0f + bump);
    }
    return i * FAM_ISENSE_V_PER_A;
}

static float mux_V(void)
{
    switch (sim.mux) {
    case MUX_CH_V12_SENSE: return v12() * V12_DIVIDER;
    case MUX_CH_V5_SENSE: return v5() * V5_DIVIDER;
    case MUX_CH_VBUS_SENSE: return vbus() * VBUS_DIVIDER;
    case MUX_CH_PEND1_IPROPI: return mirror_V(COIL_PEND1);
    case MUX_CH_PEND2_IPROPI: return mirror_V(COIL_PEND2);
    case MUX_CH_PEND3_IPROPI: return mirror_V(COIL_PEND3);
    case MUX_CH_FAM1_ISENSE: return isense_V(0);
    case MUX_CH_FAM2_ISENSE: return isense_V(1);
    default: return 0.0f;
    }
}

static uint16_t to_counts(float v)
{
    float c = v * (ADC_COUNTS / ADC_VREF_V) + noise(1.5f);
    if (c < 0.0f)
        c = 0.0f;
    if (c > 4095.0f)
        c = 4095.0f;
    return (uint16_t)lroundf(c);
}

/* ---- the ops ------------------------------------------------------------------------- */
static void s_out(const char *line)
{
    sim.lines++;
    if (!strncmp(line, "{\"event\"", 8))
        sim.events++;
    if (sim_line_out)
        sim_line_out(line);
}

static uint32_t s_now_us(void) { return (uint32_t)sim.t_us; }

static void s_wait_us(uint32_t us)
{
    sim.t_us += us;
    if (sim.realtime)
        usleep(us);
}

static void s_poll(void) {}

static bool s_input_pending(void)
{
    if (sim.pending_after_events >= 0 && sim.events >= sim.pending_after_events)
        return true;
    return sim_stdin_pending && sim_stdin_pending();
}

static uint16_t s_adc_read(unsigned input)
{
    sim.t_us += 2;                                      /* 500 ksps */
    switch (input) {
    case ADC_CH_HALL: return to_counts(HALL_VQ_FRACTION * ADC_VREF_V + 0.4f * HALL_MV_PER_MT * 1e-3f);
    case ADC_CH_LEV_IPROPI: return to_counts(mirror_V(COIL_LEV));
    case ADC_CH_MUX_OUT: return to_counts(mux_V());
    default: return 0;
    }
}

static void s_mux_select(unsigned ch) { sim.mux = ch & 7u; }

static bool s_gpio_get(unsigned pin)
{
    switch (pin) {
    case PIN_DRV_nFAULT: return !(sim.nfault_on_drive && sim.drv_awake && sim.coil >= 0);
    case PIN_BUTTON: return !sim.button;
    case PIN_DRV_nSLEEP: return sim.drv_awake;
    case PIN_FAM_EN: return sim.fam_en;
    default: return false;
    }
}

static bool s_i2c_init(bool *sda_low, bool *scl_low)
{
    *sda_low = sim.sda_stuck;
    *scl_low = false;
    return true;                                        /* the nine clocks free it */
}

static bool s_i2c_probe(uint8_t a)
{
    sim.t_us += 50;
    return a < 128 && answers(a);
}

/* the data registers, refreshed from the simulated world before a read */
static void refresh(int a)
{
    uint8_t *r = sim.reg[a];
    if (a == I2C_ADDR_LSM6DS3TR_C && r[0x10]) {         /* accelerometer running */
        int16_t g[3] = {(int16_t)lroundf(0.01f / 0.061e-3f), (int16_t)lroundf(-0.02f / 0.061e-3f),
                        (int16_t)lroundf(1.0f / 0.061e-3f)};   /* flat, chip facing down: +1 g on its z */
        for (int k = 0; k < 3; k++) {
            r[0x28 + 2 * k] = (uint8_t)(g[k] & 0xFF);
            r[0x29 + 2 * k] = (uint8_t)((uint16_t)g[k] >> 8);
        }
        int16_t t = (int16_t)(1.5f * 256.0f);           /* 26.5 C */
        r[0x20] = (uint8_t)(t & 0xFF);
        r[0x21] = (uint8_t)((uint16_t)t >> 8);
    }
    if (a == I2C_ADDR_LTR_303ALS && (r[0x80] & 1)) {    /* active */
        uint16_t ch1 = 60, ch0 = 240;
        r[0x88] = ch1 & 0xFF, r[0x89] = ch1 >> 8, r[0x8A] = ch0 & 0xFF, r[0x8B] = ch0 >> 8;
    }
    if (a == I2C_ADDR_TMAG5273A2 && r[0x02]) {          /* axes enabled */
        int16_t v[4] = {(int16_t)(17508 + 87), (int16_t)lroundf(0.6f * 32768.0f / 133.0f),
                        (int16_t)lroundf(-0.4f * 32768.0f / 133.0f), (int16_t)lroundf(1.8f * 32768.0f / 133.0f)};
        for (int k = 0; k < 4; k++) {
            r[0x10 + 2 * k] = (uint8_t)((uint16_t)v[k] >> 8);
            r[0x11 + 2 * k] = (uint8_t)(v[k] & 0xFF);
        }
    }
}

static bool s_i2c_read(uint8_t a, uint8_t reg, uint8_t *d, size_t n)
{
    sim.t_us += 30 + 25 * n;
    if (a >= 128 || !answers(a) || a == 0x1C)
        return false;
    refresh(a);
    for (size_t i = 0; i < n; i++)
        d[i] = sim.reg[a][(reg + i) & 0xFF];
    return true;
}

static bool s_i2c_write(uint8_t a, uint8_t reg, const uint8_t *d, size_t n)
{
    sim.t_us += 30 + 25 * n;
    if (a >= 128 || !answers(a))
        return false;
    if (a == 0x1C)
        return true;
    for (size_t i = 0; i < n; i++) {
        unsigned r = (reg + i) & 0xFF;
        if (is_lp5036(a) && r == 0x38 && d[i] == 0xFF) {
            power_on_regs(a);
            continue;
        }
        if (a == I2C_ADDR_LSM6DS3TR_C && r == 0x12 && (d[i] & 1)) {
            power_on_regs(a);
            continue;
        }
        sim.reg[a][r] = d[i];
    }
    return true;
}

static void s_drv_sleep(bool asleep) { sim.drv_awake = !asleep; }

static void s_coil_drive(int c, float u)
{
    sim.coil = c;
    sim.coil_u = u;
}

static void s_bridges_off(void)
{
    sim.coil = -1;
    sim.perch = -1;
    sim.drv_awake = false;
    sim.fam_en = false;
}

static float s_perch_drive(int p, float f, float duty)
{
    /* as coils.c perch_set: clamped, whole counts of the 150 MHz clock */
    if (f < FAM_F_MIN_HZ * 0.9f)
        f = FAM_F_MIN_HZ * 0.9f;
    if (f > FAM_F_MAX_HZ * 1.1f)
        f = FAM_F_MAX_HZ * 1.1f;
    long P = lroundf((float)SYS_CLK_HZ / (2.0f * f));
    long cc = lroundf(duty * (float)P);
    sim.perch = p;
    sim.perch_f = (float)SYS_CLK_HZ / (2.0f * (float)P);
    sim.perch_duty = (float)cc / (float)P;
    sim.fam_en = true;
    return sim.perch_f;
}

static float sim_audio_dc = -1.0f;
static void s_audio_dc(float level) { sim_audio_dc = level; }
static void s_tone(float hz, uint32_t ms, float amp)
{
    sim.tone_hz = hz;
    sim.tone_ms = ms;
    sim.tone_amp = amp;
    s_wait_us(ms * 1000u);
}

static bool s_osc(uint32_t ms, float *fp, float *fv)
{
    s_wait_us(ms * 1000u);
    if (sim.osc_dead) {
        *fp = *fv = 0.0f;
        return false;
    }
    *fp = 700000.0f + noise(200.0f);
    *fv = 650000.0f + noise(200.0f);
    return true;
}

static void s_chip_id(char *buf, size_t n) { snprintf(buf, n, "E6614C311B5D2A37"); }

static void s_reboot(bool bootsel)
{
    sim.rebooted = true;
    sim.bootsel = bootsel;
}

const bringup_ops SIM_OPS = {
    .out = s_out, .now_us = s_now_us, .wait_us = s_wait_us, .poll = s_poll, .input_pending = s_input_pending,
    .adc_read = s_adc_read, .mux_select = s_mux_select, .gpio_get = s_gpio_get, .i2c_init = s_i2c_init,
    .i2c_probe = s_i2c_probe, .i2c_read = s_i2c_read, .i2c_write = s_i2c_write, .drv_sleep = s_drv_sleep,
    .coil_drive = s_coil_drive, .bridges_off = s_bridges_off, .perch_drive = s_perch_drive, .tone = s_tone,
    .audio_dc = s_audio_dc,
    .osc = s_osc, .chip_id = s_chip_id, .reboot = s_reboot,
};

static bool env_on(const char *k)
{
    const char *v = getenv(k);
    return v && *v && strcmp(v, "0");
}

void sim_from_env(void)
{
    memset(&sim, 0, sizeof sim);
    sim.short_coil = -1;
    sim.pending_after_events = -1;
    sim.no12v = env_on("OWL_SIM_NO12V");
    sim.usb_off = env_on("OWL_SIM_USB_OFF");
    sim.nfault_on_drive = env_on("OWL_SIM_NFAULT");
    sim.osc_dead = env_on("OWL_SIM_OSC_DEAD");
    sim.sda_stuck = env_on("OWL_SIM_SDA_STUCK");
    sim.realtime = env_on("OWL_SIM_REALTIME");
    sim.button = env_on("OWL_SIM_BUTTON");
    const char *t = getenv("OWL_SIM_TOKEN");
    if (t && !strcmp(t, "owl"))
        sim.token = 1;
    if (t && !strcmp(t, "cat"))
        sim.token = 2;
    const char *s = getenv("OWL_SIM_SHORT");
    static const char *const names[COIL_COUNT] = {"pend1", "pend2", "pend3", "lev"};
    for (int c = 0; s && c < COIL_COUNT; c++)
        if (!strcmp(s, names[c]))
            sim.short_coil = c;
    const char *m = getenv("OWL_SIM_MISSING");
    if (m) {
        char buf[256];
        snprintf(buf, sizeof buf, "%s", m);
        for (char *tok = strtok(buf, ", "); tok; tok = strtok(NULL, ", ")) {
            long a = strtol(tok, NULL, 0);
            if (a > 0 && a < 128)
                sim.missing[a] = true;
        }
    }
    sim_reset();
}
