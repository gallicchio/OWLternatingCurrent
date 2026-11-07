/* test_bringup.c: the bring-up image's console (src/bringup_cmd.c) on the simulated
 * board (bringup_board_sim.c).
 *
 * Every command, its reply's fields and values against the simulated board; every
 * refusal and limit (no 12 V, too much current, the LED cap, ranges, malformed lines);
 * the sequences' safety (after every command every bridge is off and asleep; a short
 * or nFAULT stops a pulse); walks and sweeps that can be interrupted; the boot lines;
 * every line one well-formed JSON object, exactly one reply per command.
 */
#include "bringup_board_sim.h"
#include "board_pins.h"
#include "config.h"
#include "led_engine.h"
#include "led_map.h"
#include "sensors.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures, checks;
#define CHECK(cond, ...)                                  \
    do {                                                  \
        checks++;                                         \
        if (!(cond)) {                                    \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
            failures++;                                   \
        }                                                 \
    } while (0)

#define MAX_LINES 400
static char lines[MAX_LINES][BRINGUP_REPLY_MAX];
static int nlines;
static char last[BRINGUP_REPLY_MAX];     /* the last reply (not an event) */
static int replies, events, bad_json;

static bool json_ok(const char *s)
{
    size_t n = strlen(s);
    if (n < 2 || s[0] != '{' || s[n - 1] != '}')
        return false;
    int quotes = 0, depth = 0;
    for (size_t i = 0; i < n; i++) {
        if ((unsigned char)s[i] < 0x20)
            return false;
        if (s[i] == '\\') {
            i++;
            continue;
        }
        if (s[i] == '"')
            quotes++;
        else if (!(quotes & 1) && (s[i] == '{' || s[i] == '['))
            depth++;
        else if (!(quotes & 1) && (s[i] == '}' || s[i] == ']'))
            depth--;
        if (depth < 0)
            return false;
    }
    if (strstr(s, "nan") || strstr(s, "inf"))
        return false;                                      /* JSON has neither */
    return !(quotes & 1) && depth == 0;
}

static void capture(const char *line)
{
    if (!json_ok(line)) {
        printf("bad JSON: %s\n", line);
        bad_json++;
    }
    if (nlines < MAX_LINES)
        snprintf(lines[nlines++], sizeof lines[0], "%s", line);
    if (!strncmp(line, "{\"event\"", 8)) {
        events++;
    } else {
        replies++;
        snprintf(last, sizeof last, "%s", line);
    }
}

/* a number after "key": in s (NAN if absent or null) */
static double num(const char *s, const char *key)
{
    char k[64];
    snprintf(k, sizeof k, "\"%s\":", key);
    const char *p = strstr(s, k);
    if (!p)
        return NAN;
    p += strlen(k);
    if (!strncmp(p, "null", 4))
        return NAN;
    return strtod(p, NULL);
}

/* element i of the array after "key":[ */
static double arr(const char *s, const char *key, int i)
{
    char k[64];
    snprintf(k, sizeof k, "\"%s\":[", key);
    const char *p = strstr(s, k);
    if (!p)
        return NAN;
    p += strlen(k);
    for (; i > 0; i--) {
        p = strchr(p, ',');
        if (!p)
            return NAN;
        p++;
    }
    return strtod(p, NULL);
}

static bool has(const char *s, const char *frag) { return strstr(s, frag) != NULL; }

static bool all_off(void) { return sim.coil < 0 && sim.perch < 0 && !sim.drv_awake && !sim.fam_en; }

/* one command: exactly one reply, ok as expected, everything off afterwards */
static const char *run(const char *cmd, bool want_ok)
{
    char buf[512];
    snprintf(buf, sizeof buf, "%s\n", cmd);
    int r0 = replies;
    nlines = 0;
    for (char *c = buf; *c; c++)
        bringup_feed(*c);
    CHECK(replies == r0 + 1, "'%s': %d replies", cmd, replies - r0);
    bool ok = has(last, "\"ok\":true");
    CHECK(ok == want_ok, "'%s' -> %s", cmd, last);
    if (!ok)
        CHECK(has(last, "\"error\":\""), "'%s': a refusal without an error: %s", cmd, last);
    CHECK(all_off(), "'%s' left something on (coil %d, perch %d, awake %d, fam_en %d)", cmd, sim.coil, sim.perch,
          sim.drv_awake, sim.fam_en);
    return last;
}

static void fresh(void)
{
    sim_from_env();                                        /* the environment's knobs: none in make */
    sim_line_out = capture;
    nlines = 0;
    bringup_init(&SIM_OPS);
}

static bool near(double a, double b, double tol) { return fabs(a - b) <= tol; }

int main(void)
{
    const char *r;

    /* ---- boot ---- */
    fresh();
    CHECK(nlines == 4, "boot: %d lines", nlines);
    CHECK(has(lines[0], "\"event\":\"boot\"") && has(lines[0], "\"image\":\"bringup\""), "boot: %s", lines[0]);
    CHECK(has(lines[1], "\"event\":\"i2c\"") && has(lines[1], "\"sda_stuck\":false"), "i2c: %s", lines[1]);
    CHECK(has(lines[2], "\"event\":\"rails\"") && near(num(lines[2], "v12"), 12.0, 0.05), "rails: %s", lines[2]);
    CHECK(has(lines[3], "\"event\":\"i2c_scan\"") && has(lines[3], "\"missing\":[]"), "scan: %s", lines[3]);
    sim.sda_stuck = true;
    bringup_init(&SIM_OPS);
    CHECK(has(lines[nlines - 3], "\"sda_stuck\":true"), "stuck SDA reported: %s", lines[nlines - 3]);
    fresh();

    /* ---- help, id, rails, adc, gpio ---- */
    r = run("help", true);
    CHECK(has(r, "\"commands\":[") && has(r, "ledwalk"), "%s", r);
    r = run("HELP", true);                                 /* case-insensitive */
    r = run("id", true);
    CHECK(has(r, "\"image\":\"bringup\"") && has(r, "\"chip_id\":\"E6614C311B5D2A37\"") && has(r, "\"version\":\""),
          "%s", r);
    CHECK(num(r, "uptime_ms") >= 0, "%s", r);
    r = run("rails", true);
    CHECK(near(num(r, "v12"), 12.0, 0.05) && near(num(r, "v5"), 4.80, 0.02) && near(num(r, "vbus"), 5.0, 0.02),
          "%s", r);
    CHECK(has(r, "\"usb_only\":false") && has(r, "\"raw\":{\"v12\":"), "%s", r);
    CHECK(near(num(r, "v12") * V12_DIVIDER * 4096.0 / 3.3, num(strstr(r, "\"raw\""), "v12"), 2.0), "raw: %s", r);
    sim.no12v = true;
    r = run("rails", true);
    CHECK(has(r, "\"usb_only\":true") && num(r, "v12") < 0.1, "USB only: %s", r);
    sim.no12v = false;
    r = run("adc", true);
    static const char *const mux_names[] = {"fam1_isense", "vbus_sense", "pend3_ipropi", "fam2_isense",
                                            "v5_sense", "pend2_ipropi", "v12_sense", "pend1_ipropi"};
    for (int i = 0; i < 8; i++) {
        char k[48];
        snprintf(k, sizeof k, "\"%s\":{\"ch\":%d,", mux_names[i], i);
        CHECK(has(r, k), "adc: %s missing: %s", k, r);
    }
    CHECK(near(num(r, "hall_V"), 1.653, 0.01) && near(num(r, "hall_mT"), 0.4, 0.3), "%s", r);
    CHECK(near(num(r, "lev_ipropi_A"), 0.005, 0.003), "%s", r);
    CHECK(near(num(strstr(r, "\"v12_sense\""), "value"), 12.0, 0.05), "%s", r);
    r = run("gpio", true);
    CHECK(has(r, "\"nfault\":false") && has(r, "\"button\":false") && has(r, "\"nsleep\":false") &&
              has(r, "\"fam_en\":false"), "%s", r);
    sim.button = true;
    r = run("gpio", true);
    CHECK(has(r, "\"button\":true"), "%s", r);
    sim.button = false;

    /* ---- I2C ---- */
    r = run("i2c scan", true);
    CHECK(has(r, "\"found\":[\"0x1C\",\"0x29\",\"0x30\",\"0x32\",\"0x35\",\"0x6A\"]"), "%s", r);
    CHECK(has(r, "\"0x30\":\"LP5036 base\"") && has(r, "\"missing\":[]"), "%s", r);
    sim.missing[0x32] = true;
    r = run("i2c scan", true);
    CHECK(has(r, "\"missing\":[\"0x32\"]"), "%s", r);
    sim.missing[0x32] = false;
    r = run("i2c rd 0x6A 0x0F 1", true);
    CHECK(has(r, "\"bytes\":[106]"), "%s", r);
    r = run("i2c rd 0x35 13 3", true);
    CHECK(has(r, "\"bytes\":[2,73,84]"), "%s", r);
    run("i2c rd 0x50 0 1", false);                         /* nobody there */
    run("i2c rd 0x6A 0x0F 0", false);
    run("i2c rd 0x6A 0x0F 33", false);
    run("i2c rd 0x07 0 1", false);
    run("i2c rd zz 0 1", false);
    run("i2c rd 0x6A", false);
    r = run("i2c wr 0x30 0x14 5 6 7", true);
    CHECK(sim.reg[0x30][0x14] == 5 && sim.reg[0x30][0x16] == 7 && has(r, "\"n\":3"), "%s", r);
    run("i2c wr 0x30 0x14 256", false);
    run("i2c wr 0x30", false);
    run("i2c wr 0x50 0 1", false);
    run("i2c bogus", false);
    run("i2c", false);

    /* ---- sensors ---- */
    r = run("sensors", true);
    CHECK(has(r, "\"imu\":{\"present\":true,\"whoami\":\"0x6A\""), "%s", r);
    CHECK(near(arr(r, "accel_g", 2), 1.0, 0.01) && near(arr(r, "accel_g", 0), 0.01, 0.005), "accel: %s", r);
    CHECK(near(arr(r, "accel_board_g", 2), IMU_AXIS_Z * 1.0, 0.01), "board frame: %s", r);
    CHECK(near(num(strstr(r, "\"imu\""), "temp_C"), 26.5, 0.1), "%s", r);
    CHECK(near(num(r, "lux"), 10.25, 0.05), "lux: %s", r);
    CHECK(near(arr(r, "mT", 0), 0.6, 0.01) && near(arr(r, "mT", 1), -0.4, 0.01) && near(arr(r, "mT", 2), 1.8, 0.01),
          "tmag: %s", r);
    CHECK(near(num(strstr(r, "\"tmag\""), "temp_C"), 26.5, 0.1), "%s", r);
    CHECK(near(num(r, "hall_lev_mT"), 0.4, 0.3), "%s", r);
    sim.missing[0x29] = true;
    sim.missing[0x35] = true;
    r = run("sensors", true);                              /* still ok: it reports what is absent */
    CHECK(has(r, "\"als\":{\"present\":false") && has(r, "\"tmag\":{\"present\":false"), "%s", r);
    sim.missing[0x29] = sim.missing[0x35] = false;
    sim.reg[0x6A][0x0F] = 0x69;                            /* a wrong part */
    r = run("sensors", true);
    CHECK(has(r, "\"imu\":{\"present\":false,\"whoami\":\"0x69\""), "%s", r);
    sim.reg[0x6A][0x0F] = 0x6A;

    /* ---- LEDs ---- */
    fresh();
    r = run("led STAR3 0.2", true);
    CHECK(num(r, "driver") == 0 && num(r, "out") == 6 && has(r, "\"name\":\"STAR3\""), "%s", r);
    CHECK(sim.reg[0x30][LP5036_OUT0_COLOR + 6] == 51, "STAR3's colour register %u", sim.reg[0x30][0x14 + 6]);
    CHECK(sim.reg[0x30][LP5036_DEVICE_CONFIG0] == LP5036_CHIP_EN && sim.reg[0x30][LP5036_DEVICE_CONFIG1] ==
          LP5036_CONFIG1_VALUE, "the driver configured");
    CHECK(sim.reg[0x30][LP5036_LED0_BRIGHTNESS] == 0xFF && sim.reg[0x30][LP5036_LED0_BRIGHTNESS + 11] == 0xFF,
          "banks at full brightness");
    r = run("led owla_l 0.5", true);                       /* names case-insensitive, on the tree */
    CHECK(num(r, "driver") == 1 && num(r, "out") == 10 && sim.reg[0x32][0x14 + 10] == 128, "%s", r);
    run("led star3 0.6", false);                           /* over the cap */
    CHECK(has(last, "over the cap"), "%s", last);
    r = run("led cap 1", true);
    CHECK(near(num(r, "cap"), 1.0, 1e-6), "%s", r);
    run("led star3 0.6", true);
    run("led star3 1.0", true);
    CHECK(sim.reg[0x30][0x14 + 6] == 255, "full: %u", sim.reg[0x30][0x14 + 6]);
    run("led cap 0", true);
    run("led star3 0.6", false);
    run("led cap 2", false);
    run("led star3 1.5", false);
    run("led star3 -0.1", false);
    run("led star3 nan", false);
    run("led bogus 0.2", false);
    run("led star3", false);
    run("led", false);
    r = run("led 0 14 0.2", true);                         /* raw: an unconnected output */
    CHECK(has(r, "\"name\":\"unconnected\"") && sim.reg[0x30][0x14 + 14] == 51, "%s", r);
    r = run("led 1 35 0.1", true);
    CHECK(has(r, "\"name\":\"OWLC_R\""), "%s", r);
    run("led 2 0 0.1", false);
    run("led 0 36 0.1", false);
    r = run("led all 0.3", true);
    CHECK(num(r, "lit") == LED_COUNT && has(r, "\"drivers\":[\"0x30\",\"0x32\"]"), "%s", r);
    CHECK(sim.reg[0x30][0x14 + 0] == 77 && sim.reg[0x30][0x14 + 14] == 0 && sim.reg[0x32][0x14 + 35] == 77,
          "all: mapped outputs only");
    r = run("led off", true);
    bool dark = true;
    for (int d = 0; d < 2; d++)
        for (int o = 0; o < 36; o++)
            dark = dark && sim.reg[d ? 0x32 : 0x30][0x14 + o] == 0;
    CHECK(dark && has(r, "\"name\":\"off\""), "off: %s", r);
    fresh();
    sim.missing[0x32] = true;
    run("led owla_l 0.2", false);
    CHECK(has(last, "tree"), "%s", last);
    r = run("led all 0.2", true);
    CHECK(num(r, "lit") == 31 && has(r, "\"drivers\":[\"0x30\"]"), "%s", r);
    sim.missing[0x30] = true;
    run("led all 0.2", false);
    sim.missing[0x30] = sim.missing[0x32] = false;

    /* ---- ledwalk ---- */
    fresh();
    int e0 = events;
    r = run("ledwalk 50", true);
    CHECK(events - e0 == LED_COUNT && num(r, "count") == LED_COUNT && has(r, "\"aborted\":false"), "%s", r);
    CHECK(has(lines[0], "\"event\":\"ledwalk\",\"i\":0,\"name\":\"PUMPKIN1\",\"driver\":0,\"out\":0"), "%s", lines[0]);
    dark = true;
    for (int d = 0; d < 2; d++)
        for (int o = 0; o < 36; o++)
            dark = dark && sim.reg[d ? 0x32 : 0x30][0x14 + o] == 0;
    CHECK(dark, "dark after the walk");
    sim.missing[0x32] = true;
    r = run("ledwalk 20", true);
    CHECK(num(r, "count") == 31 && num(r, "skipped") == 18, "%s", r);
    sim.missing[0x32] = false;
    sim.pending_after_events = sim.events + 3;                 /* a key pressed during the third LED */
    r = run("ledwalk 400", true);
    CHECK(has(r, "\"aborted\":true") && num(r, "count") == 3, "%s", r);
    sim.pending_after_events = -1;
    run("ledwalk 5", false);
    run("ledwalk 9000", false);
    run("ledwalk 1 2", false);

    /* ---- coils ---- */
    fresh();
    r = run("coil pend1 0.1 100", true);
    double want = 0.1 * 12.0 / (2.40 + DRV_RDSON_OHM);
    CHECK(near(num(r, "i_mean_A"), want + 0.005, 0.01), "pend1 mean: %s", r);
    CHECK(near(num(r, "i_off_A"), 0.005, 0.003) && near(num(r, "i_before_A"), 0.005, 0.003), "%s", r);
    CHECK(near(num(r, "r_est_ohm"), 2.40, 0.1) && near(num(r, "i_expected_A"), 0.1 * 12.0 / COIL_R20_OHM, 0.01),
          "%s", r);
    CHECK(has(r, "\"nfault\":false") && near(num(r, "ran_ms"), 100, 1) && has(r, "30000 Hz"), "%s", r);
    r = run("coil lev -0.1 50", true);
    CHECK(near(num(r, "i_mean_A"), 0.1 * 12.0 / (2.62 + DRV_RDSON_OHM) + 0.005, 0.01) && has(r, "100000 Hz"), "%s", r);
    r = run("COIL Pend3 0.05 1", true);
    run("coil pend2 0.3 100", false);                      /* 1.57 A expected */
    CHECK(has(last, "over the bring-up limit"), "%s", last);
    run("coil pend2 0.6 100", false);
    run("coil pend2 0.1 600", false);
    run("coil pend2 0.1 0", false);
    run("coil pend4 0.1 10", false);
    run("coil pend2 x 10", false);
    run("coil pend2 0.1", false);
    sim.no12v = true;
    run("coil pend1 0.05 10", false);
    CHECK(has(last, "no 12 V"), "%s", last);
    sim.no12v = false;
    sim.short_coil = 1;                                    /* pend2 shorted: the mirror reads 10x */
    r = run("coil pend2 0.05 200", false);
    CHECK(has(r, "a short?") && num(r, "ran_ms") < 1.0, "short: %s", r);
    sim.short_coil = -1;
    sim.nfault_on_drive = true;
    r = run("coil pend1 0.05 200", false);
    CHECK(has(r, "\"nfault\":true") && num(r, "ran_ms") < 1.0, "nFAULT: %s", r);
    sim.nfault_on_drive = false;

    /* ---- perches ---- */
    fresh();
    sim.token = 1;
    r = run("perch 1 160000 0.03 100", true);
    CHECK(num(r, "isense_on_A") > num(r, "isense_base_A") + 0.005 && near(num(r, "freq_hz"), 160000, 300), "%s", r);
    CHECK(near(num(r, "v5"), 4.8, 0.02) && near(num(r, "isense_base_A"), 0.0008, 0.0005), "%s", r);
    r = run("perch 2 300000 0.02 3", true);                /* short: the filter has not settled, still ok */
    r = run("perch 1 160000 0.2 100", true);                /* up to a square wave, to light a token ... */
    CHECK(has(r, "\"tripped\":false") && has(r, "\"held_ms\":100"), "%s", r);
    run("perch 1 160000 0.6 100", false);
    run("perch 1 30000 0.03 100", false);
    run("perch 1 500000 0.03 100", true);                   /* the clamp in coils.c decides, not the parser */
    run("perch 1 500001 0.03 100", false);
    run("perch 3 160000 0.03 100", false);
    run("perch 1 160000 0.03 3000", true);                  /* ... and for up to 10 s */
    run("perch 1 160000 0.03 10001", false);
    run("perch 1 160000 0.03", false);
    sim.no12v = true;
    run("perch 1 160000 0.03 100", false);
    CHECK(has(last, "4.8 V"), "%s", last);
    sim.no12v = false;

    /* ---- sweeps ---- */
    e0 = events;
    r = run("sweep 1", true);
    CHECK(events - e0 == 48 && num(r, "points") == 48 && has(r, "\"aborted\":false"), "%s", r);
    CHECK(num(r, "peak_f") > 140000 && num(r, "peak_f") < 180000, "owl's peak: %s", r);
    CHECK(has(lines[0], "\"event\":\"sweep_pt\",\"perch\":1,\"f\":100000"), "%s", lines[0]);
    sim.token = 2;
    r = run("sweep 2 200000 440000 25 0.02", true);
    CHECK(num(r, "points") == 25 && num(r, "peak_f") > 330000 && num(r, "peak_f") < 370000, "cat's peak: %s", r);
    sim.token = 0;
    sim.pending_after_events = sim.events + 5;
    r = run("sweep 1", true);
    CHECK(has(r, "\"aborted\":true") && num(r, "points") == 5, "%s", r);
    sim.pending_after_events = -1;
    run("sweep 1 400000 100000 10 0.03", false);
    run("sweep 1 100000 400000 1 0.03", false);
    run("sweep 1 100000 400000 10 0.5", false);
    run("sweep 1 100000 400000", false);
    run("sweep", false);
    sim.no12v = true;
    run("sweep 2", false);
    sim.no12v = false;

    /* ---- tone, osc ---- */
    r = run("tone 440 200", true);
    CHECK(sim.tone_hz == 440.0f && sim.tone_ms == 200 && near(sim.tone_amp, 0.1, 1e-6) && has(r, "SOUND"), "%s", r);
    run("tone 440 200 0.2", true);
    CHECK(near(sim.tone_amp, 0.2, 1e-6), "amp");
    run("tone 50 200", false);
    run("tone 440 200 0.3", true);                          /* the bench wants it loud: up to full scale ... */
    run("tone 440 200 1.0", true);
    run("tone 440 200 1.1", false);
    run("tone 440 4000", true);                             /* ... and for up to 20 s */
    run("tone 440 20001", false);
    run("tone", false);
    r = run("osc", true);
    CHECK(near(num(r, "pitch_hz"), 700000, 500) && near(num(r, "volume_hz"), 650000, 500), "%s", r);
    r = run("osc 20", true);
    sim.osc_dead = true;
    r = run("osc", true);
    CHECK(num(r, "pitch_hz") == 0 && has(r, "no edges"), "%s", r);
    sim.osc_dead = false;
    run("osc 0", false);
    run("osc 2000", false);

    /* ---- malformed lines, reboot ---- */
    run("bogus", false);
    CHECK(has(last, "unknown command"), "%s", last);
    run("\"quoted\\\" input", false);                      /* escaped in the reply */
    {
        int r0 = replies;
        bringup_feed('\n');                                /* an empty line: no reply */
        bringup_feed(' ');
        bringup_feed('\r');
        CHECK(replies == r0, "empty lines answered");
        char big[400];
        memset(big, 'x', sizeof big - 1);
        big[sizeof big - 1] = 0;
        for (char *c = big; *c; c++)
            bringup_feed(*c);
        bringup_feed('\n');
        CHECK(replies == r0 + 1 && has(last, "line too long"), "%s", last);
        bringup_feed('h');                                 /* the next line works */
        bringup_feed('e');
        bringup_feed('l');
        bringup_feed('p');
        bringup_feed('\n');
        CHECK(has(last, "\"cmd\":\"help\""), "%s", last);
    }
    run("led star3 0.2", true);
    run("reboot", true);
    CHECK(sim.rebooted && !sim.bootsel, "reboot");
    CHECK(sim.reg[0x30][LP5036_DEVICE_CONFIG1] & 1, "LEDs globally off before the reboot");
    sim_reset();
    run("bootsel", true);
    CHECK(sim.bootsel, "bootsel");
    sim_reset();
    run("reboot bootsel", true);
    CHECK(sim.bootsel, "reboot bootsel");
    run("reboot now", false);

    CHECK(bad_json == 0, "%d lines were not well-formed JSON", bad_json);
    if (failures) {
        printf("test_bringup: %d of %d checks FAILED\n", failures, checks);
        return 1;
    }
    printf("test_bringup: %d checks, %d replies, %d events; all passed\n", checks, replies, events);
    return 0;
}
