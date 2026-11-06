/* bringup_cmd.c: the bring-up image's console.  See bringup_cmd.h. */
#include "bringup_cmd.h"
#include "board_pins.h"
#include "coil_ids.h"
#include "config.h"
#include "jsonbuf.h"
#include "led_engine.h"
#include "led_map.h"
#include "sensors.h"
#include "version.h"
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const bringup_ops *ops;
static char reply[BRINGUP_REPLY_MAX];
static char line_buf[BRINGUP_LINE_MAX + 1];
static size_t line_len;
static bool line_overflow;
static uint64_t uptime_us;
static uint32_t uptime_last;

/* ---- small helpers ------------------------------------------------------------------- */
static uint64_t uptime(void)
{
    uint32_t now = ops->now_us();
    uptime_us += (uint32_t)(now - uptime_last);
    uptime_last = now;
    return uptime_us;
}

static bool ieq(const char *a, const char *b)
{
    if (!a || !b)
        return false;
    for (; *a && *b; a++, b++)
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b))
            return false;
    return *a == *b;
}

/* a whole token as a finite number */
static bool number(const char *s, float *v)
{
    if (!s || !*s)
        return false;
    char *end;
    float x = strtof(s, &end);
    if (*end || !isfinite(x))
        return false;
    *v = x;
    return true;
}

/* a whole token as an integer (0x.. for hex) */
static bool integer(const char *s, long lo, long hi, long *v)
{
    if (!s || !*s)
        return false;
    char *end;
    long x = strtol(s, &end, 0);
    if (*end || x < lo || x > hi)
        return false;
    *v = x;
    return true;
}

/* a JSON string's contents: quotes, backslashes and control characters escaped */
static void escape(char *out, size_t n, const char *s)
{
    size_t k = 0;
    for (; *s && k + 7 < n; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            out[k++] = '\\';
            out[k++] = (char)c;
        } else if (c < 0x20 || c >= 0x7f) {
            k += (size_t)snprintf(out + k, n - k, "\\u%04x", c);
        } else {
            out[k++] = (char)c;
        }
    }
    out[k] = 0;
}

/* a reply under construction: {"ok":..,"cmd":".." then fields, then } */
static jsonbuf start(bool ok, const char *cmd)
{
    char c[40];
    escape(c, sizeof c, cmd);
    jsonbuf j = jb_start(reply, sizeof reply);
    jb_add(&j, "{\"ok\":%s,\"cmd\":\"%s\"", ok ? "true" : "false", c);
    return j;
}

static void finish(jsonbuf *j)
{
    jb_add(j, "}");
    ops->out(reply);
}

/* a number, or null when it is not finite (JSON has no NaN) */
static void jf(jsonbuf *j, const char *key, float v, int decimals)
{
    if (isfinite(v))
        jb_add(j, ",\"%s\":%.*f", key, decimals, (double)v);
    else
        jb_add(j, ",\"%s\":null", key);
}

static void jbool(jsonbuf *j, const char *key, bool v) { jb_add(j, ",\"%s\":%s", key, v ? "true" : "false"); }

static void fail(const char *cmd, const char *msg)
{
    char m[200];
    escape(m, sizeof m, msg);
    jsonbuf j = start(false, cmd);
    jb_add(&j, ",\"error\":\"%s\"", m);
    finish(&j);
}

static void event_begin(jsonbuf *j, const char *name)
{
    *j = jb_start(reply, sizeof reply);
    jb_add(j, "{\"event\":\"%s\"", name);
}

/* wait, in slices, until ms have passed or a character arrives; true if interrupted */
static bool wait_ms_abortable(uint32_t ms)
{
    uint32_t t0 = ops->now_us();
    while ((uint32_t)(ops->now_us() - t0) < ms * 1000u) {
        if (ops->input_pending())
            return true;
        uint32_t left = ms * 1000u - (uint32_t)(ops->now_us() - t0);
        ops->wait_us(left < 5000u ? left : 5000u);
    }
    return false;
}

/* ---- the ADC --------------------------------------------------------------------------- */
static float counts_to_v(float counts) { return counts * (ADC_VREF_V / ADC_COUNTS); }

static float adc_avg(unsigned input, unsigned n)
{
    uint32_t s = 0;
    for (unsigned i = 0; i < n; i++)
        s += ops->adc_read(input);
    return (float)s / (float)n;
}

/* a multiplexer channel: select, settle (>= 30 us), average n conversions (counts) */
static float mux_counts(unsigned ch, unsigned n)
{
    ops->mux_select(ch);
    ops->wait_us(50);
    return adc_avg(ADC_CH_MUX_OUT, n);
}

static const char *const MUX_NAME[MUX_CHANNELS] = {
    [MUX_CH_PEND1_IPROPI] = "pend1_ipropi", [MUX_CH_PEND2_IPROPI] = "pend2_ipropi",
    [MUX_CH_PEND3_IPROPI] = "pend3_ipropi", [MUX_CH_FAM1_ISENSE] = "fam1_isense",
    [MUX_CH_FAM2_ISENSE] = "fam2_isense",   [MUX_CH_V12_SENSE] = "v12_sense",
    [MUX_CH_V5_SENSE] = "v5_sense",         [MUX_CH_VBUS_SENSE] = "vbus_sense",
};

/* a channel's scaled value and unit, from the volts at the ADC pin */
static float mux_scaled(unsigned ch, float v, const char **unit)
{
    switch (ch) {
    case MUX_CH_V12_SENSE: *unit = "V"; return v / V12_DIVIDER;
    case MUX_CH_V5_SENSE: *unit = "V"; return v / V5_DIVIDER;
    case MUX_CH_VBUS_SENSE: *unit = "V"; return v / VBUS_DIVIDER;
    case MUX_CH_FAM1_ISENSE:
    case MUX_CH_FAM2_ISENSE: *unit = "A"; return v / FAM_ISENSE_V_PER_A;
    default: *unit = "A"; return v / IPROPI_V_PER_A;     /* the three pendulum mirrors */
    }
}

typedef struct {
    float v12, v5, vbus;
    float raw12, raw5, rawbus;
} rails_t;

static rails_t read_rails(void)
{
    rails_t r;
    r.raw12 = mux_counts(MUX_CH_V12_SENSE, 16);
    r.raw5 = mux_counts(MUX_CH_V5_SENSE, 16);
    r.rawbus = mux_counts(MUX_CH_VBUS_SENSE, 16);
    r.v12 = counts_to_v(r.raw12) / V12_DIVIDER;
    r.v5 = counts_to_v(r.raw5) / V5_DIVIDER;
    r.vbus = counts_to_v(r.rawbus) / VBUS_DIVIDER;
    return r;
}

static bool usb_only(const rails_t *r) { return r->vbus > VBUS_PRESENT_V && r->v12 < V12_ABSENT_V; }

static float hall_mT_of(float volts)
{
    return (float)HALL_POLARITY * (volts - HALL_VQ_FRACTION * ADC_VREF_V) / (HALL_MV_PER_MT * 1e-3f);
}

/* ---- commands ------------------------------------------------------------------------ */
static const char *const HELP[] = {
    "help", "id", "rails", "adc", "gpio", "i2c scan", "i2c rd <addr> <reg> <n>", "i2c wr <addr> <reg> <b0> [b1..]",
    "sensors", "led <name|all> <0..1>", "led <drv 0|1> <out 0..35> <0..1>", "led off", "led cap <0|1>",
    "ledwalk [ms]", "coil <pend1|pend2|pend3|lev> <duty -0.5..0.5> <ms 1..500>",
    "perch <1|2> <freq_hz> <duty 0..0.1> <ms 1..2000>", "sweep <1|2> [f0 f1 steps duty]",
    "tone <hz 100..4000> <ms 1..3000> [amp 0..0.25]", "osc [ms]", "reboot", "bootsel",
};

static void cmd_help(void)
{
    jsonbuf j = start(true, "help");
    jb_add(&j, ",\"commands\":[");
    for (size_t i = 0; i < sizeof HELP / sizeof HELP[0]; i++)
        jb_add(&j, "%s\"%s\"", i ? "," : "", HELP[i]);
    jb_add(&j, "]");
    finish(&j);
}

static void id_fields(jsonbuf *j)
{
    char id[40];
    ops->chip_id(id, sizeof id);
    char e[48];
    escape(e, sizeof e, id);
    jb_add(j, ",\"image\":\"bringup\",\"version\":\"%s\",\"board\":\"%s\",\"uptime_ms\":%lu,\"chip_id\":\"%s\"",
           OWL_FW_VERSION, OWL_BOARD, (unsigned long)(uptime() / 1000u), e);
}

static void cmd_id(void)
{
    jsonbuf j = start(true, "id");
    id_fields(&j);
    finish(&j);
}

static void rails_fields(jsonbuf *j, const rails_t *r)
{
    jf(j, "v12", r->v12, 3);
    jf(j, "v5", r->v5, 3);
    jf(j, "vbus", r->vbus, 3);
    jbool(j, "usb_only", usb_only(r));
    jb_add(j, ",\"raw\":{\"v12\":%.1f,\"v5\":%.1f,\"vbus\":%.1f}", (double)r->raw12, (double)r->raw5, (double)r->rawbus);
}

static void cmd_rails(void)
{
    rails_t r = read_rails();
    jsonbuf j = start(true, "rails");
    rails_fields(&j, &r);
    finish(&j);
}

static void cmd_adc(void)
{
    float hall = adc_avg(ADC_CH_HALL, 16), lev = adc_avg(ADC_CH_LEV_IPROPI, 16);
    float mux[MUX_CHANNELS];
    for (unsigned c = 0; c < MUX_CHANNELS; c++)
        mux[c] = mux_counts(c, 16);
    jsonbuf j = start(true, "adc");
    jf(&j, "hall_V", counts_to_v(hall), 4);
    jf(&j, "hall_mT", hall_mT_of(counts_to_v(hall)), 2);
    jf(&j, "hall_raw", hall, 1);
    jf(&j, "lev_ipropi_A", counts_to_v(lev) / IPROPI_V_PER_A, 4);
    jf(&j, "lev_ipropi_raw", lev, 1);
    jb_add(&j, ",\"mux\":{");
    for (unsigned c = 0; c < MUX_CHANNELS; c++) {
        const char *unit;
        float v = counts_to_v(mux[c]);
        float x = mux_scaled(c, v, &unit);
        jb_add(&j, "%s\"%s\":{\"ch\":%u,\"raw\":%.1f,\"V\":%.4f,\"value\":%.4f,\"unit\":\"%s\"}", c ? "," : "",
               MUX_NAME[c], c, (double)mux[c], (double)v, (double)x, unit);
    }
    jb_add(&j, "}");
    finish(&j);
}

static void cmd_gpio(void)
{
    jsonbuf j = start(true, "gpio");
    jbool(&j, "nfault", !ops->gpio_get(PIN_DRV_nFAULT));        /* asserted low */
    jbool(&j, "button", !ops->gpio_get(PIN_BUTTON));            /* pressed low */
    jbool(&j, "imu_int", ops->gpio_get(PIN_IMU_INT));
    jbool(&j, "nsleep", ops->gpio_get(PIN_DRV_nSLEEP));         /* outputs, as driven */
    jbool(&j, "fam_en", ops->gpio_get(PIN_FAM_EN));
    finish(&j);
}

/* ---- I2C ------------------------------------------------------------------------------- */
static const uint8_t EXPECTED[] = {I2C_ADDR_LP5036_BASE, I2C_ADDR_LP5036_TREE, I2C_ADDR_LSM6DS3TR_C,
                                   I2C_ADDR_LTR_303ALS, I2C_ADDR_TMAG5273A2};

static const char *dev_name(uint8_t a)
{
    switch (a) {
    case I2C_ADDR_LP5036_BASE: return "LP5036 base";
    case I2C_ADDR_LP5036_TREE: return "LP5036 tree";
    case I2C_ADDR_LSM6DS3TR_C: return "LSM6DS3TR-C";
    case I2C_ADDR_LTR_303ALS: return "LTR-303ALS";
    case I2C_ADDR_TMAG5273A2: return "TMAG5273A2";
    case 0x1C: return "LP5036 broadcast";
    default: return "?";
    }
}

static void scan_fields(jsonbuf *j)
{
    bool found[128] = {false};
    for (uint8_t a = 0x08; a < 0x78; a++)
        found[a] = ops->i2c_probe(a);
    jb_add(j, ",\"found\":[");
    bool first = true;
    for (int a = 0; a < 128; a++)
        if (found[a]) {
            jb_add(j, "%s\"0x%02X\"", first ? "" : ",", a);
            first = false;
        }
    jb_add(j, "],\"names\":{");
    first = true;
    for (int a = 0; a < 128; a++)
        if (found[a]) {
            jb_add(j, "%s\"0x%02X\":\"%s\"", first ? "" : ",", a, dev_name((uint8_t)a));
            first = false;
        }
    jb_add(j, "},\"missing\":[");
    first = true;
    for (size_t i = 0; i < sizeof EXPECTED; i++)
        if (!found[EXPECTED[i]]) {
            jb_add(j, "%s\"0x%02X\"", first ? "" : ",", EXPECTED[i]);
            first = false;
        }
    jb_add(j, "]");
}

static void cmd_i2c(int argc, char **argv)
{
    if (argc >= 2 && ieq(argv[1], "scan") && argc == 2) {
        jsonbuf j = start(true, "i2c scan");
        scan_fields(&j);
        finish(&j);
        return;
    }
    long addr, reg, n;
    if (argc == 5 && ieq(argv[1], "rd")) {
        if (!integer(argv[2], 0x08, 0x77, &addr) || !integer(argv[3], 0, 255, &reg) || !integer(argv[4], 1, 32, &n))
            return fail("i2c rd", "usage: i2c rd <addr 0x08..0x77> <reg 0..255> <n 1..32>");
        uint8_t d[32];
        if (!ops->i2c_read((uint8_t)addr, (uint8_t)reg, d, (size_t)n))
            return fail("i2c rd", "no acknowledge (or the read failed)");
        jsonbuf j = start(true, "i2c rd");
        jb_add(&j, ",\"addr\":\"0x%02lX\",\"reg\":\"0x%02lX\",\"bytes\":[", addr, reg);
        for (long i = 0; i < n; i++)
            jb_add(&j, "%s%u", i ? "," : "", d[i]);
        jb_add(&j, "]");
        finish(&j);
        return;
    }
    if (argc >= 5 && argc <= 4 + 16 && ieq(argv[1], "wr")) {
        if (!integer(argv[2], 0x08, 0x77, &addr) || !integer(argv[3], 0, 255, &reg))
            return fail("i2c wr", "usage: i2c wr <addr 0x08..0x77> <reg 0..255> <b0> [b1 .. b15]");
        uint8_t d[16];
        int nb = argc - 4;
        for (int i = 0; i < nb; i++) {
            long b;
            if (!integer(argv[4 + i], 0, 255, &b))
                return fail("i2c wr", "each byte 0..255 (0x.. for hex)");
            d[i] = (uint8_t)b;
        }
        if (!ops->i2c_write((uint8_t)addr, (uint8_t)reg, d, (size_t)nb))
            return fail("i2c wr", "no acknowledge (or the write failed)");
        jsonbuf j = start(true, "i2c wr");
        jb_add(&j, ",\"addr\":\"0x%02lX\",\"reg\":\"0x%02lX\",\"n\":%d", addr, reg, nb);
        finish(&j);
        return;
    }
    fail("i2c", "usage: i2c scan | i2c rd <addr> <reg> <n> | i2c wr <addr> <reg> <b0> [b1..]");
}

/* ---- the sensors ------------------------------------------------------------------------ */
/* registers: the same as sensors.c (each datasheet's register map) */
#define LSM_WHO_AM_I    0x0F
#define LSM_CTRL1_XL    0x10
#define LSM_CTRL2_G     0x11
#define LSM_CTRL3_C     0x12
#define LSM_OUT_TEMP_L  0x20
#define LSM_OUTX_L_XL   0x28
#define LTR_CONTR       0x80
#define LTR_MEAS_RATE   0x85
#define LTR_PART_ID     0x86
#define LTR_DATA        0x88
#define TMAG_DEVICE_CONFIG_1 0x00
#define TMAG_DEVICE_CONFIG_2 0x01
#define TMAG_SENSOR_CONFIG_1 0x02
#define TMAG_SENSOR_CONFIG_2 0x03
#define TMAG_T_CONFIG        0x07
#define TMAG_DEVICE_ID       0x0D
#define TMAG_T_MSB           0x10

static bool imu_ready, als_ready, tmag_ready;

static bool w8(uint8_t a, uint8_t reg, uint8_t v) { return ops->i2c_write(a, reg, &v, 1); }

static void sensor_imu(jsonbuf *j)
{
    const uint8_t a = I2C_ADDR_LSM6DS3TR_C;
    uint8_t who = 0;
    if (!ops->i2c_read(a, LSM_WHO_AM_I, &who, 1)) {
        imu_ready = false;
        jb_add(j, "\"imu\":{\"present\":false,\"error\":\"no acknowledge at 0x6A\"}");
        return;
    }
    if (who != 0x6A) {
        imu_ready = false;
        jb_add(j, "\"imu\":{\"present\":false,\"whoami\":\"0x%02X\",\"error\":\"WHO_AM_I is not 0x6A\"}", who);
        return;
    }
    if (!imu_ready) {
        imu_ready = w8(a, LSM_CTRL3_C, 0x01);                  /* SW_RESET */
        ops->wait_us(2000);
        imu_ready = imu_ready && w8(a, LSM_CTRL3_C, 0x44) &&   /* BDU, IF_INC */
                    w8(a, LSM_CTRL1_XL, 0x60) &&               /* 416 Hz, +-2 g */
                    w8(a, LSM_CTRL2_G, 0x00);                  /* gyroscope off */
        ops->wait_us(20000);                                   /* a few samples */
    }
    uint8_t d[6], t[2];
    if (!imu_ready || !ops->i2c_read(a, LSM_OUTX_L_XL, d, 6) || !ops->i2c_read(a, LSM_OUT_TEMP_L, t, 2)) {
        imu_ready = false;
        jb_add(j, "\"imu\":{\"present\":true,\"whoami\":\"0x%02X\",\"error\":\"configuration or read failed\"}", who);
        return;
    }
    const float k = 0.061e-3f;                                 /* g per LSB at +-2 g */
    float g[3];
    for (int i = 0; i < 3; i++)
        g[i] = k * (float)(int16_t)(d[2 * i] | d[2 * i + 1] << 8);
    float temp = 25.0f + (float)(int16_t)(t[0] | t[1] << 8) / 256.0f;
    /* accel_g: the chip's own axes; accel_board_g: with sensors.h's assumed signs (U15 on
     * the bottom), which tilting the board confirms */
    jb_add(j, "\"imu\":{\"present\":true,\"whoami\":\"0x%02X\",\"accel_g\":[%.3f,%.3f,%.3f],"
              "\"accel_board_g\":[%.3f,%.3f,%.3f],\"temp_C\":%.1f}",
           who, (double)g[0], (double)g[1], (double)g[2], (double)(IMU_AXIS_X * g[0]),
           (double)(IMU_AXIS_Y * g[1]), (double)(IMU_AXIS_Z * g[2]), (double)temp);
}

static void sensor_als(jsonbuf *j)
{
    const uint8_t a = I2C_ADDR_LTR_303ALS;
    uint8_t id[2] = {0, 0};
    if (!ops->i2c_read(a, LTR_PART_ID, id, 2)) {
        als_ready = false;
        jb_add(j, "\"als\":{\"present\":false,\"error\":\"no acknowledge at 0x29\"}");
        return;
    }
    if (id[0] != 0xA0 || id[1] != 0x05) {
        als_ready = false;
        jb_add(j, "\"als\":{\"present\":false,\"part_id\":\"0x%02X\",\"manufacturer\":\"0x%02X\","
                  "\"error\":\"not an LTR-303ALS (0xA0, 0x05)\"}", id[0], id[1]);
        return;
    }
    if (!als_ready) {
        als_ready = w8(a, LTR_MEAS_RATE, 0x02) &&              /* 100 ms, every 200 ms */
                    w8(a, LTR_CONTR, (0x6 << 2) | 1);          /* 48x, active */
        ops->wait_us(250000);                                  /* the first integration */
    }
    uint8_t d[4];
    if (!als_ready || !ops->i2c_read(a, LTR_DATA, d, 4)) {
        als_ready = false;
        jb_add(j, "\"als\":{\"present\":true,\"error\":\"configuration or read failed\"}");
        return;
    }
    float c1 = (float)(d[0] | d[1] << 8), c0 = (float)(d[2] | d[3] << 8);
    /* Lite-On's lux formula (the datasheet's appendix A), gain 48, 100 ms */
    float ratio = c0 + c1 > 0.0f ? c1 / (c0 + c1) : 0.0f, lux;
    if (ratio < 0.45f)
        lux = (1.7743f * c0 + 1.1059f * c1) / 48.0f;
    else if (ratio < 0.64f)
        lux = (4.2785f * c0 - 1.9548f * c1) / 48.0f;
    else if (ratio < 0.85f)
        lux = (0.5926f * c0 + 0.1185f * c1) / 48.0f;
    else
        lux = 0.0f;
    if (lux < 0.0f)
        lux = 0.0f;
    jb_add(j, "\"als\":{\"present\":true,\"lux\":%.2f,\"ch0\":%u,\"ch1\":%u}", (double)lux, (unsigned)c0, (unsigned)c1);
}

static void sensor_tmag(jsonbuf *j)
{
    const uint8_t a = I2C_ADDR_TMAG5273A2;
    uint8_t id[3] = {0, 0, 0};
    if (!ops->i2c_read(a, TMAG_DEVICE_ID, id, 3)) {
        tmag_ready = false;
        jb_add(j, "\"tmag\":{\"present\":false,\"error\":\"no acknowledge at 0x35\"}");
        return;
    }
    if (id[1] != 0x49 || id[2] != 0x54) {
        tmag_ready = false;
        jb_add(j, "\"tmag\":{\"present\":false,\"manufacturer\":\"0x%02X%02X\",\"error\":\"not a TMAG5273 (0x5449)\"}",
               id[2], id[1]);
        return;
    }
    if (!tmag_ready) {
        tmag_ready = w8(a, TMAG_DEVICE_CONFIG_1, 0x03 << 2) &&  /* 8x averaging */
                     w8(a, TMAG_SENSOR_CONFIG_1, 0x7 << 4) &&   /* X, Y, Z */
                     w8(a, TMAG_SENSOR_CONFIG_2, 0x00) &&       /* +-133 mT */
                     w8(a, TMAG_T_CONFIG, 0x01) &&              /* temperature too */
                     w8(a, TMAG_DEVICE_CONFIG_2, 0x12);         /* low noise, continuous */
        ops->wait_us(10000);
    }
    uint8_t d[9];
    if (!tmag_ready || !ops->i2c_read(a, TMAG_T_MSB, d, 9)) {
        tmag_ready = false;
        jb_add(j, "\"tmag\":{\"present\":true,\"error\":\"configuration or read failed\"}");
        return;
    }
    float b[3];
    for (int k = 0; k < 3; k++)
        b[k] = (float)(int16_t)(d[2 + 2 * k] << 8 | d[3 + 2 * k]) * (133.0f / 32768.0f);
    float t = 25.0f + ((float)(int16_t)(d[0] << 8 | d[1]) - 17508.0f) / 58.0f;
    jb_add(j, "\"tmag\":{\"present\":true,\"device_id\":\"0x%02X\",\"mT\":[%.2f,%.2f,%.2f],\"temp_C\":%.1f}", id[0],
           (double)b[0], (double)b[1], (double)b[2], (double)t);
}

static void cmd_sensors(void)
{
    jsonbuf j = start(true, "sensors");
    jb_add(&j, ",");
    sensor_imu(&j);
    jb_add(&j, ",");
    sensor_als(&j);
    jb_add(&j, ",");
    sensor_tmag(&j);
    float hv = counts_to_v(adc_avg(ADC_CH_HALL, 16));
    jf(&j, "hall_lev_V", hv, 4);
    jf(&j, "hall_lev_mT", hall_mT_of(hv), 2);
    finish(&j);
}

/* ---- the LEDs ------------------------------------------------------------------------- */
static bool drv_ready[LED_DRIVERS];
static float led_cap = BU_LED_CAP_DEFAULT;

/* the LP5036 at driver d: reset, enabled, independent mode, every bank's brightness full */
static const char *led_driver_up(int d)
{
    if (drv_ready[d])
        return NULL;
    uint8_t a = LED_DRIVER_ADDR[d];
    if (!ops->i2c_probe(a))
        return d == LED_DRV_BASE ? "the base LP5036 (0x30) does not answer"
                                 : "the tree LP5036 (0x32) does not answer (is the tree plugged in?)";
    uint8_t cfg1 = 0, banks[LED_DRIVER_BANKS];
    memset(banks, 0xFF, sizeof banks);
    bool ok = w8(a, LP5036_RESET, 0xFF);
    ops->wait_us(500);
    ok = ok && ops->i2c_read(a, LP5036_DEVICE_CONFIG1, &cfg1, 1);
    if (ok && cfg1 != 0x3C)
        return "an LP5036 address answered, but DEVICE_CONFIG1 is not its reset value 0x3C";
    ok = ok && w8(a, LP5036_DEVICE_CONFIG0, LP5036_CHIP_EN) && w8(a, LP5036_DEVICE_CONFIG1, LP5036_CONFIG1_VALUE) &&
         w8(a, LP5036_LED_CONFIG0, 0x00) && w8(a, LP5036_LED_CONFIG1, 0x00) &&
         ops->i2c_write(a, LP5036_LED0_BRIGHTNESS, banks, sizeof banks);
    if (!ok)
        return "the LP5036 stopped acknowledging while being configured";
    drv_ready[d] = true;
    return NULL;
}

static uint8_t colour_of(float duty) { return (uint8_t)lroundf(duty * 255.0f); }

static const char *led_out(int d, int out, float duty)
{
    const char *e = led_driver_up(d);
    if (e)
        return e;
    if (!w8(LED_DRIVER_ADDR[d], (uint8_t)(LP5036_OUT0_COLOR + out), colour_of(duty))) {
        drv_ready[d] = false;
        return "the LP5036 did not acknowledge the write";
    }
    return NULL;
}

/* every mapped output of every driver that answers; returns how many LEDs it set */
static int led_all(float duty, char *drivers, size_t n)
{
    int lit = 0;
    jsonbuf j = jb_start(drivers, n);
    jb_add(&j, "[");
    bool first = true;
    for (int d = 0; d < LED_DRIVERS; d++) {
        if (led_driver_up(d))
            continue;
        uint8_t c[LED_DRIVER_CHANNELS];
        for (int o = 0; o < LED_DRIVER_CHANNELS; o++) {
            c[o] = LED_OF_CHANNEL[d][o] >= 0 ? colour_of(duty) : 0;
            lit += LED_OF_CHANNEL[d][o] >= 0;
        }
        if (!ops->i2c_write(LED_DRIVER_ADDR[d], LP5036_OUT0_COLOR, c, sizeof c)) {
            drv_ready[d] = false;
            continue;
        }
        jb_add(&j, "%s\"0x%02X\"", first ? "" : ",", LED_DRIVER_ADDR[d]);
        first = false;
    }
    jb_add(&j, "]");
    return lit;
}

static int led_lookup(const char *name)
{
    for (int i = 0; i < LED_COUNT; i++)
        if (ieq(name, LED_MAP[i].name))
            return i;
    return -1;
}

static void led_reply(int driver, int out, const char *name, float duty)
{
    jsonbuf j = start(true, "led");
    jb_add(&j, ",\"driver\":%d,\"out\":%d,\"name\":\"%s\"", driver, out, name);
    jf(&j, "duty", duty, 3);
    finish(&j);
}

static void cmd_led(int argc, char **argv)
{
    float duty;
    if (argc == 2 && ieq(argv[1], "off")) {
        char drivers[64];
        led_all(0.0f, drivers, sizeof drivers);
        jsonbuf j = start(true, "led");
        jb_add(&j, ",\"driver\":-1,\"out\":-1,\"name\":\"off\",\"duty\":0.000,\"drivers\":%s", drivers);
        finish(&j);
        return;
    }
    if (argc == 3 && ieq(argv[1], "cap")) {
        if (!number(argv[2], &duty) || (duty != 0.0f && duty != 1.0f))
            return fail("led cap", "led cap 1 (allow full duty) or led cap 0 (back to 0.5)");
        led_cap = duty == 1.0f ? 1.0f : BU_LED_CAP_DEFAULT;
        jsonbuf j = start(true, "led cap");
        jf(&j, "cap", led_cap, 2);
        finish(&j);
        return;
    }
    if (argc != 3 && argc != 4)
        return fail("led", "usage: led <name|all> <0..1> | led <drv 0|1> <out 0..35> <0..1> | led off | led cap <0|1>");
    if (!number(argv[argc - 1], &duty) || duty < 0.0f || duty > 1.0f)
        return fail("led", "the duty is a number 0..1");
    if (duty > led_cap) {
        char m[96];
        snprintf(m, sizeof m, "duty %.2f is over the cap %.2f (led cap 1 lifts it)", (double)duty, (double)led_cap);
        return fail("led", m);
    }
    if (argc == 4) {
        long d, o;
        if (!integer(argv[1], 0, 1, &d) || !integer(argv[2], 0, 35, &o))
            return fail("led", "led <drv 0|1> <out 0..35> <0..1>");
        const char *e = led_out((int)d, (int)o, duty);
        if (e)
            return fail("led", e);
        int k = LED_OF_CHANNEL[d][o];
        led_reply((int)d, (int)o, k >= 0 ? LED_MAP[k].name : "unconnected", duty);
        return;
    }
    if (ieq(argv[1], "all")) {
        char drivers[64];
        int lit = led_all(duty, drivers, sizeof drivers);
        if (!strcmp(drivers, "[]"))
            return fail("led", "no LED driver answers");
        jsonbuf j = start(true, "led");
        jb_add(&j, ",\"driver\":-1,\"out\":-1,\"name\":\"all\"");
        jf(&j, "duty", duty, 3);
        jb_add(&j, ",\"lit\":%d,\"drivers\":%s", lit, drivers);
        finish(&j);
        return;
    }
    int k = led_lookup(argv[1]);
    if (k < 0)
        return fail("led", "no LED by that name (names as in led_map.h: STAR3, PUMPKIN0, OWLA_L ...)");
    const char *e = led_out(LED_MAP[k].driver, LED_MAP[k].channel, duty);
    if (e)
        return fail("led", e);
    led_reply(LED_MAP[k].driver, LED_MAP[k].channel, LED_MAP[k].name, duty);
}

static void cmd_ledwalk(int argc, char **argv)
{
    long ms = 400;
    if (argc > 2 || (argc == 2 && !integer(argv[1], 20, 5000, &ms)))
        return fail("ledwalk", "usage: ledwalk [ms 20..5000]");
    const float level = 0.2f;
    int lit = 0, skipped = 0;
    bool aborted = false;
    for (int i = 0; i < LED_COUNT && !aborted; i++) {
        const led_info *L = &LED_MAP[i];
        jsonbuf j;
        if (ops->input_pending()) {
            aborted = true;
            break;
        }
        const char *e = led_out(L->driver, L->channel, level);
        event_begin(&j, "ledwalk");
        jb_add(&j, ",\"i\":%d,\"name\":\"%s\",\"driver\":%u,\"out\":%u", i, L->name, L->driver, L->channel);
        if (e) {
            char m[120];
            escape(m, sizeof m, e);
            jb_add(&j, ",\"skipped\":true,\"error\":\"%s\"}", m);
            ops->out(reply);
            skipped++;
            continue;
        }
        jf(&j, "duty", level, 2);
        jb_add(&j, "}");
        ops->out(reply);
        lit++;
        aborted = wait_ms_abortable((uint32_t)ms);
        led_out(L->driver, L->channel, 0.0f);
    }
    char drivers[64];
    led_all(0.0f, drivers, sizeof drivers);
    jsonbuf j = start(true, "ledwalk");
    jb_add(&j, ",\"count\":%d,\"skipped\":%d", lit, skipped);
    jbool(&j, "aborted", aborted);
    finish(&j);
}

/* ---- the coils ------------------------------------------------------------------------- */
static const char *const COIL_NAME[COIL_COUNT] = {"pend1", "pend2", "pend3", "lev"};
static const unsigned COIL_MUX[PEND_COILS] = {MUX_CH_PEND1_IPROPI, MUX_CH_PEND2_IPROPI, MUX_CH_PEND3_IPROPI};

/* the coil's current mirror, averaged over n conversions (A) */
static float mirror_A(int coil, unsigned n)
{
    unsigned input = coil == COIL_LEV ? ADC_CH_LEV_IPROPI : ADC_CH_MUX_OUT;
    return counts_to_v(adc_avg(input, n)) / IPROPI_V_PER_A;
}

static void cmd_coil(int argc, char **argv)
{
    int c = -1;
    float duty;
    long ms;
    if (argc != 4)
        return fail("coil", "usage: coil <pend1|pend2|pend3|lev> <duty -0.5..0.5> <ms 1..500>");
    for (int k = 0; k < COIL_COUNT; k++)
        if (ieq(argv[1], COIL_NAME[k]))
            c = k;
    if (c < 0)
        return fail("coil", "the coils are pend1 pend2 pend3 lev");
    if (!number(argv[2], &duty) || fabsf(duty) > BU_COIL_DUTY_MAX)
        return fail("coil", "the duty is a number -0.5..0.5 (a fraction of 12 V)");
    if (!integer(argv[3], 1, BU_COIL_MS_MAX, &ms))
        return fail("coil", "ms is 1..500");
    rails_t r = read_rails();
    if (r.v12 < V12_PRESENT_V) {
        char m[64];
        snprintf(m, sizeof m, "no 12 V (V12 reads %.2f V)", (double)r.v12);
        return fail("coil", m);
    }
    float r20 = c == COIL_LEV ? LEV_COIL_R20_OHM : COIL_R20_OHM;
    float expect = fabsf(duty) * r.v12 / r20;
    if (expect > BU_COIL_I_MAX_A) {
        char m[96];
        snprintf(m, sizeof m, "%.2f A expected: over the bring-up limit of %.1f A", (double)expect,
                 (double)BU_COIL_I_MAX_A);
        return fail("coil", m);
    }
    float abort_A = fmaxf(1.5f * expect, expect + 0.3f);
    if (abort_A > BU_COIL_ABORT_A)
        abort_A = BU_COIL_ABORT_A;

    if (c != COIL_LEV) {
        ops->mux_select(COIL_MUX[c]);
        ops->wait_us(50);
    }
    float i_before = mirror_A(c, 64);
    ops->drv_sleep(false);
    ops->wait_us(DRV_WAKE_US + 200u);
    bool nfault = !ops->gpio_get(PIN_DRV_nFAULT);
    const char *err = nfault ? "nFAULT asserted when the bridges woke: nothing driven" : NULL;
    float sum = 0.0f, peak = 0.0f;
    unsigned n = 0;
    uint32_t ran_us = 0;
    if (!err) {
        ops->coil_drive(c, duty);
        uint32_t t0 = ops->now_us(), polled = t0;
        for (;;) {
            uint32_t t = (uint32_t)(ops->now_us() - t0);
            if (t >= (uint32_t)ms * 1000u)
                break;
            float i = mirror_A(c, 8);
            if (i > peak)
                peak = i;
            if (t >= 300u) {                              /* L/R is ~13 us; the mirror settles */
                sum += i;
                n++;
            }
            if (!ops->gpio_get(PIN_DRV_nFAULT)) {
                nfault = true;
                err = "nFAULT asserted during the pulse: stopped";
                break;
            }
            if (i > abort_A) {
                err = "the current mirror read more than expected (a short?): stopped";
                break;
            }
            if ((uint32_t)(ops->now_us() - polled) > 2000u) {
                ops->poll();
                polled = ops->now_us();
            }
        }
        ran_us = (uint32_t)(ops->now_us() - t0);
    }
    ops->bridges_off();                                   /* every bridge low, asleep */
    ops->wait_us(2000);
    float i_off = mirror_A(c, 64);
    float mean = n ? sum / (float)n : NAN;
    float net = mean - i_off;
    float r_loop = net > 0.02f ? fabsf(duty) * r.v12 / net : NAN;

    jsonbuf j = start(err == NULL, "coil");
    if (err) {
        char m[120];
        escape(m, sizeof m, err);
        jb_add(&j, ",\"error\":\"%s\"", m);
    }
    jb_add(&j, ",\"coil\":\"%s\"", COIL_NAME[c]);
    jf(&j, "duty", duty, 3);
    jb_add(&j, ",\"ms\":%ld,\"ran_ms\":%.1f", ms, (double)ran_us / 1000.0);
    jf(&j, "v12", r.v12, 3);
    jf(&j, "i_expected_A", expect, 4);
    jf(&j, "i_mean_A", mean, 4);
    jf(&j, "i_peak_A", peak, 4);
    jf(&j, "i_off_A", i_off, 4);
    jf(&j, "i_before_A", i_before, 4);
    jf(&j, "i_net_A", net, 4);
    jf(&j, "r_loop_ohm", r_loop, 3);                      /* the coil and the bridge */
    jf(&j, "r_est_ohm", r_loop - DRV_RDSON_OHM, 3);       /* the coil alone */
    jbool(&j, "nfault", nfault);
    jb_add(&j, ",\"pwm\":\"forward/brake, phase-correct, %u Hz\"", c == COIL_LEV ? LEV_PWM_HZ : PEND_PWM_HZ);
    finish(&j);
}

/* ---- the familiar perches ---------------------------------------------------------------- */
static const unsigned PERCH_MUX[2] = {MUX_CH_FAM1_ISENSE, MUX_CH_FAM2_ISENSE};

/* the selected perch's supply current (A) */
static float isense_A(unsigned n) { return counts_to_v(adc_avg(ADC_CH_MUX_OUT, n)) / FAM_ISENSE_V_PER_A; }

/* the perch's ISENSE channel selected and its 1 ms filter settled with the bridge off */
static float perch_baseline(int p)
{
    ops->mux_select(PERCH_MUX[p]);
    ops->wait_us(5000);
    return isense_A(64);
}

static const char *perch_rails(rails_t *r, char *m, size_t n)
{
    *r = read_rails();
    if (r->v5 < BU_PERCH_V5_MIN_V) {
        snprintf(m, n, "no 4.8 V rail (V5 reads %.2f V; the perches need > %.1f V)", (double)r->v5,
                 (double)BU_PERCH_V5_MIN_V);
        return m;
    }
    return NULL;
}

static void cmd_perch(int argc, char **argv)
{
    long p, ms;
    float f, duty;
    if (argc != 5 || !integer(argv[1], 1, 2, &p) || !number(argv[2], &f) || !number(argv[3], &duty) ||
        !integer(argv[4], 1, BU_PERCH_MS_MAX, &ms))
        return fail("perch", "usage: perch <1|2> <freq_hz 50000..450000> <duty 0..0.1> <ms 1..2000>");
    if (f < BU_PERCH_F_MIN_HZ || f > BU_PERCH_F_MAX_HZ)
        return fail("perch", "the frequency is 50000..450000 Hz");
    if (duty < 0.0f || duty > BU_PERCH_DUTY_MAX)
        return fail("perch", "the duty is 0..0.1 in bring-up");
    rails_t r;
    char m[96];
    if (perch_rails(&r, m, sizeof m))
        return fail("perch", m);
    int k = (int)p - 1;
    float base = perch_baseline(k);
    float fset = ops->perch_drive(k, f, duty);
    uint32_t t0 = ops->now_us(), from = (uint32_t)ms * 500u;   /* average the second half ... */
    if (ms >= 6 && from < 3000u)
        from = 3000u;                                     /* ... after the 1 ms filter has settled */
    float sum = 0.0f;
    unsigned n = 0;
    uint32_t polled = t0;
    for (;;) {
        uint32_t t = (uint32_t)(ops->now_us() - t0);
        if (t >= (uint32_t)ms * 1000u)
            break;
        float i = isense_A(8);
        if (t >= from) {
            sum += i;
            n++;
        }
        if ((uint32_t)(ops->now_us() - polled) > 2000u) {
            ops->poll();
            polled = ops->now_us();
        }
    }
    ops->bridges_off();
    float on = n ? sum / (float)n : NAN;
    jsonbuf j = start(true, "perch");
    jb_add(&j, ",\"perch\":%ld", p);
    jf(&j, "freq_hz", fset, 0);
    jf(&j, "freq_asked_hz", f, 0);
    jf(&j, "duty", duty, 4);
    jb_add(&j, ",\"ms\":%ld", ms);
    jf(&j, "isense_base_A", base, 4);
    jf(&j, "isense_on_A", on, 4);
    jf(&j, "isense_net_A", on - base, 4);
    jf(&j, "v5", r.v5, 3);
    finish(&j);
}

static void cmd_sweep(int argc, char **argv)
{
    long p, steps = 48;
    float f0 = 100000.0f, f1 = 400000.0f, duty = 0.03f;
    if (argc != 2 && argc != 6)
        return fail("sweep", "usage: sweep <1|2> [f0 f1 steps duty]");
    if (!integer(argv[1], 1, 2, &p))
        return fail("sweep", "the perch is 1 (owl) or 2 (cat)");
    if (argc == 6 && (!number(argv[2], &f0) || !number(argv[3], &f1) || !integer(argv[4], 2, 200, &steps) ||
                      !number(argv[5], &duty)))
        return fail("sweep", "usage: sweep <1|2> [f0 f1 steps 2..200 duty]");
    if (f0 < BU_PERCH_F_MIN_HZ || f1 > BU_PERCH_F_MAX_HZ || !(f1 > f0))
        return fail("sweep", "50000 <= f0 < f1 <= 450000 Hz");
    if (duty < 0.0f || duty > BU_PERCH_DUTY_MAX)
        return fail("sweep", "the duty is 0..0.1 in bring-up");
    rails_t r;
    char m[96];
    if (perch_rails(&r, m, sizeof m))
        return fail("sweep", m);
    int k = (int)p - 1;
    float base = perch_baseline(k), peak_i = -1.0f, peak_f = NAN;
    bool aborted = false;
    long done = 0;
    for (long s = 0; s < steps; s++) {
        if (ops->input_pending()) {
            aborted = true;
            break;
        }
        float f = f0 + (f1 - f0) * (float)s / (float)(steps - 1);
        float fset = ops->perch_drive(k, f, duty);
        ops->wait_us(12000);                              /* the 1 ms filter settles */
        float sum = 0.0f;
        unsigned n = 0;
        uint32_t t0 = ops->now_us();
        while ((uint32_t)(ops->now_us() - t0) < 8000u) {
            sum += isense_A(8);
            n++;
        }
        float i = n ? sum / (float)n : NAN;
        if (i > peak_i) {
            peak_i = i;
            peak_f = fset;
        }
        jsonbuf j;
        event_begin(&j, "sweep_pt");
        jb_add(&j, ",\"perch\":%ld", p);
        jf(&j, "f", fset, 0);
        jf(&j, "i_A", i, 5);
        jb_add(&j, "}");
        ops->out(reply);
        ops->poll();
        done++;
    }
    ops->bridges_off();
    jsonbuf j = start(true, "sweep");
    jb_add(&j, ",\"perch\":%ld,\"points\":%ld", p, done);
    jf(&j, "duty", duty, 4);
    jf(&j, "base_A", base, 5);
    jf(&j, "peak_f", peak_f, 0);
    jf(&j, "peak_i_A", done ? peak_i : NAN, 5);
    jf(&j, "v5", r.v5, 3);
    jbool(&j, "aborted", aborted);
    finish(&j);
}

/* ---- sound and the theremin ------------------------------------------------------------- */
static void cmd_tone(int argc, char **argv)
{
    float hz, amp = 0.1f;
    long ms;
    if ((argc != 3 && argc != 4) || !number(argv[1], &hz) || !integer(argv[2], 1, 3000, &ms) ||
        (argc == 4 && !number(argv[3], &amp)))
        return fail("tone", "usage: tone <hz 100..4000> <ms 1..3000> [amp 0..0.25]");
    if (hz < 100.0f || hz > 4000.0f)
        return fail("tone", "the frequency is 100..4000 Hz");
    if (amp < 0.0f || amp > BU_TONE_AMP_MAX)
        return fail("tone", "the amplitude is 0..0.25 of full scale");
    ops->tone(hz, (uint32_t)ms, amp);
    jsonbuf j = start(true, "tone");
    jf(&j, "hz", hz, 1);
    jb_add(&j, ",\"ms\":%ld", ms);
    jf(&j, "amp", amp, 3);
    jb_add(&j, ",\"note\":\"a sine on the audio PWM; silent if the SOUND slide switch is off\"");
    finish(&j);
}

static void cmd_osc(int argc, char **argv)
{
    long ms = 100;
    if (argc > 2 || (argc == 2 && !integer(argv[1], 1, 1000, &ms)))
        return fail("osc", "usage: osc [ms 1..1000]");
    float fp = 0.0f, fv = 0.0f;
    bool ok = ops->osc((uint32_t)ms, &fp, &fv);
    jsonbuf j = start(true, "osc");
    jf(&j, "pitch_hz", fp, 0);
    jf(&j, "volume_hz", fv, 0);
    jb_add(&j, ",\"ms\":%ld", ms);
    if (!ok)
        jb_add(&j, ",\"note\":\"an oscillator gave no edges (0 Hz)\"");
    finish(&j);
}

/* ---- reboot ------------------------------------------------------------------------------ */
static void everything_off(void)
{
    ops->bridges_off();
    for (int d = 0; d < LED_DRIVERS; d++)
        if (drv_ready[d])
            w8(LED_DRIVER_ADDR[d], LP5036_DEVICE_CONFIG1, LP5036_CONFIG1_VALUE | 1u);   /* LED_Global_Off */
}

static void cmd_reboot(bool bootsel)
{
    everything_off();
    jsonbuf j = start(true, bootsel ? "bootsel" : "reboot");
    finish(&j);
    ops->reboot(bootsel);
}

/* ---- the dispatcher --------------------------------------------------------------------- */
void bringup_command(char *line)
{
    char *argv[24];
    int argc = 0;
    for (char *t = strtok(line, " \t\r\n"); t && argc < 24; t = strtok(NULL, " \t\r\n"))
        argv[argc++] = t;
    if (argc == 0)
        return;
    const char *c = argv[0];
    if (ieq(c, "help"))
        cmd_help();
    else if (ieq(c, "id"))
        cmd_id();
    else if (ieq(c, "rails"))
        cmd_rails();
    else if (ieq(c, "adc"))
        cmd_adc();
    else if (ieq(c, "gpio"))
        cmd_gpio();
    else if (ieq(c, "i2c"))
        cmd_i2c(argc, argv);
    else if (ieq(c, "sensors"))
        cmd_sensors();
    else if (ieq(c, "led"))
        cmd_led(argc, argv);
    else if (ieq(c, "ledwalk"))
        cmd_ledwalk(argc, argv);
    else if (ieq(c, "coil"))
        cmd_coil(argc, argv);
    else if (ieq(c, "perch"))
        cmd_perch(argc, argv);
    else if (ieq(c, "sweep"))
        cmd_sweep(argc, argv);
    else if (ieq(c, "tone"))
        cmd_tone(argc, argv);
    else if (ieq(c, "osc"))
        cmd_osc(argc, argv);
    else if (ieq(c, "reboot") && argc == 1)
        cmd_reboot(false);
    else if ((ieq(c, "bootsel") && argc == 1) || (ieq(c, "reboot") && argc == 2 && ieq(argv[1], "bootsel")))
        cmd_reboot(true);
    else
        fail(c, "unknown command");
    ops->bridges_off();                                   /* belt and braces: nothing left on */
}

void bringup_feed(char ch)
{
    if (ch == '\r' || ch == '\n') {
        if (line_overflow) {
            fail("?", "line too long");
        } else if (line_len) {
            line_buf[line_len] = 0;
            bringup_command(line_buf);
        }
        line_len = 0;
        line_overflow = false;
        return;
    }
    if (line_len >= BRINGUP_LINE_MAX) {
        line_overflow = true;
        return;
    }
    line_buf[line_len++] = ch;
}

/* ---- boot ---------------------------------------------------------------------------------- */
void bringup_hello(void)
{
    jsonbuf j;
    event_begin(&j, "boot");
    id_fields(&j);
    jb_add(&j, "}");
    ops->out(reply);
}

void bringup_init(const bringup_ops *o)
{
    ops = o;
    uptime_last = ops->now_us();
    uptime_us = 0;
    line_len = 0;
    line_overflow = false;
    imu_ready = als_ready = tmag_ready = false;
    led_cap = BU_LED_CAP_DEFAULT;
    for (int d = 0; d < LED_DRIVERS; d++)
        drv_ready[d] = false;
    ops->bridges_off();
    bringup_hello();

    bool sda_low = false, scl_low = false;
    bool freed = ops->i2c_init(&sda_low, &scl_low);
    jsonbuf j;
    event_begin(&j, "i2c");
    jbool(&j, "sda_stuck", sda_low);
    jbool(&j, "scl_stuck", scl_low);
    jbool(&j, "free", freed);
    jb_add(&j, "}");
    ops->out(reply);

    /* the LED drivers dark, whatever an earlier image left them showing */
    for (int d = 0; d < LED_DRIVERS; d++)
        if (ops->i2c_probe(LED_DRIVER_ADDR[d]))
            w8(LED_DRIVER_ADDR[d], LP5036_RESET, 0xFF);

    rails_t r = read_rails();
    event_begin(&j, "rails");
    rails_fields(&j, &r);
    jb_add(&j, "}");
    ops->out(reply);

    event_begin(&j, "i2c_scan");
    scan_fields(&j);
    jb_add(&j, "}");
    ops->out(reply);
}
