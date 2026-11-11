/* test_console.c: the JSON console (src/console.c) with the board's actions stubbed.
 *
 * Every command parses to the right action with the right arguments; malformed
 * ones are refused with a message; the coil limits refuse too much current, too
 * long, no 12 V; the volume is capped; replies are one well-formed JSON object
 * (quotes balanced and escaped, even when the input has quotes in it).
 */
#include "config.h"
#include "console.h"
#include "led_engine.h"
#include "scenes.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...)                                  \
    do {                                                  \
        if (!(cond)) {                                    \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
            failures++;                                   \
        }                                                 \
    } while (0)

static char last[2048];
static char call[256];
static int replies;

static bool json_ok(const char *s)
{
    size_t n = strlen(s);
    if (n < 2 || s[0] != '{' || s[n - 1] != '}')
        return false;
    int quotes = 0, depth = 0;
    for (size_t i = 0; i < n; i++) {
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
        if ((unsigned char)s[i] < 0x20)
            return false;
    }
    return !(quotes & 1) && depth == 0;
}

static void reply(const char *json)
{
    snprintf(last, sizeof last, "%s", json);
    replies++;
    if (!json_ok(json))
        printf("bad JSON: %s\n", json), failures++;
}

static const char *a_scene(int id) { snprintf(call, sizeof call, "scene %d", id); return NULL; }
static const char *a_led(int led, float level) { snprintf(call, sizeof call, "led %d %.3f", led, (double)level); return NULL; }
static const char *a_coil(int c, float duty, uint32_t ms)
{
    snprintf(call, sizeof call, "coil %d %.3f %u", c, (double)duty, (unsigned)ms);
    return console_coil_limits(duty, ms, 12.0f, COIL_R20_OHM);     /* as the board does */
}
static const char *a_sweep(int p) { snprintf(call, sizeof call, "sweep %d", p); return NULL; }
static const char *a_lev(int op, const char *param, float v)
{
    snprintf(call, sizeof call, "lev %d %s %.3f", op, param ? param : "-", (double)v);
    return NULL;
}
static const char *a_pend(int m) { snprintf(call, sizeof call, "pend %d", m); return NULL; }
static const char *a_theremin(int op) { snprintf(call, sizeof call, "theremin %d", op); return NULL; }
static const char *a_fam(int live) { snprintf(call, sizeof call, "fam %d", live); return NULL; }
static const char *a_fam_scan(int p, float f) { snprintf(call, sizeof call, "fam scan %d %.2f", p, (double)f); return NULL; }
static const char *a_film(bool on) { snprintf(call, sizeof call, "film %d", on); return NULL; }
static const char *a_volume(float v) { snprintf(call, sizeof call, "volume %.3f", (double)v); return NULL; }
static const char *a_clear(void) { snprintf(call, sizeof call, "clear"); return NULL; }
static const char *a_save(void) { snprintf(call, sizeof call, "save"); return "a coil is on"; }
static void a_status(char *b, size_t n) { snprintf(b, n, "{\"v12\":12.0,\"faults\":[]}"); }
static void a_levj(char *b, size_t n) { snprintf(b, n, "{\"state\":\"off\"}"); }
static void a_i2c(char *b, size_t n) { snprintf(b, n, "[\"0x30\"]"); }
static void a_adc(char *b, size_t n) { snprintf(b, n, "{\"hall\":2048}"); }
static void a_reboot(bool b) { snprintf(call, sizeof call, "reboot %d", b); }

static const console_ops OPS = {
    .reply = reply, .scene = a_scene, .led = a_led, .coil = a_coil, .sweep = a_sweep, .lev = a_lev,
    .pend = a_pend, .theremin = a_theremin, .fam = a_fam, .fam_scan = a_fam_scan, .film = a_film, .volume = a_volume, .clear = a_clear,
    .save = a_save, .status_json = a_status, .lev_json = a_levj, .i2c_scan_json = a_i2c,
    .adc_dump_json = a_adc, .reboot = a_reboot,
};

/* run a command; expect ok or not, and (if given) the action called */
static void expect(const char *line, bool ok, const char *want_call)
{
    char buf[256];
    snprintf(buf, sizeof buf, "%s", line);
    call[0] = 0;
    int before = replies;
    console_command(buf);
    CHECK(replies == before + 1, "'%s': %d replies", line, replies - before);
    bool got_ok = strstr(last, "\"ok\":true") != NULL;
    CHECK(got_ok == ok, "'%s' -> %s", line, last);
    if (want_call)
        CHECK(!strcmp(call, want_call), "'%s' called '%s', wanted '%s'", line, call, want_call);
}

int main(void)
{
    console_init(&OPS);
    char want[64];

    expect("help", true, NULL);
    expect("status", true, NULL);
    CHECK(strstr(last, "\"status\":{\"v12\"") != NULL, "status: %s", last);
    expect("STATUS", true, NULL);                         /* case-insensitive command word */

    snprintf(want, sizeof want, "scene %d", SCENE_NIGHT);
    expect("scene night", true, want);
    expect("scene auto", true, "scene -1");
    expect("scene disco", false, "");
    expect("scene", false, "");

    snprintf(want, sizeof want, "led %d 0.500", LED_STAR3);
    expect("led STAR3 0.5", true, want);
    expect("led star3 0.5", true, want);                  /* names case-insensitive */
    expect("led all off", true, "led -1 -1.000");
    expect("led all 0.25", true, "led -1 0.250");
    expect("led bogus 0.5", false, "");
    expect("led star3 1.5", false, "");
    expect("led star3 nan", false, "");
    expect("led star3", false, "");

    expect("coil pend1 0.1 500", true, "coil 0 0.100 500");
    expect("coil lev -0.05 20", true, "coil 3 -0.050 20");
    expect("coil pend2 0.5 500", false, "coil 1 0.500 500");   /* 2.5 A: refused by the limits */
    CHECK(strstr(last, "over the console") != NULL, "%s", last);
    expect("coil pend3 0.1 3000", false, NULL);               /* too long */
    expect("coil pend3 1.5 100", false, NULL);
    expect("coil pend4 0.1 100", false, "");
    expect("coil pend1 0.1", false, "");
    expect("coil pend1 0.1 1e20", false, "");                 /* no float -> int overflow */
    CHECK(console_coil_limits(0.1f, 100, 5.0f, 2.2f) != NULL, "no 12 V must refuse");
    CHECK(console_coil_limits(0.1f, 100, 12.0f, 2.2f) == NULL, "0.5 A for 100 ms must be allowed");
    CHECK(console_coil_limits(0.2f, 2000, 12.0f, 2.2f) == NULL, "1.0 A for 2 s is the limit");
    CHECK(console_coil_limits(0.21f, 2000, 12.0f, 2.2f) != NULL, "1.05 A must be refused");
    CHECK(console_coil_limits(0.1f, 0, 12.0f, 2.2f) != NULL, "0 ms must be refused");

    expect("sweep fam1", true, "sweep 0");
    expect("sweep fam2", true, "sweep 1");
    expect("sweep fam3", false, "");

    expect("lev on", true, "lev 0 - 0.000");
    expect("lev off", true, "lev 1 - 0.000");
    expect("lev cal", true, "lev 2 coil 0.000");
    expect("lev cal zero", true, "lev 2 zero 0.000");
    expect("lev cal bogus", false, "");
    expect("lev eyes 0.5", true, "lev 5 - 0.500");
    expect("lev eyes 2", false, "");
    expect("pend cal", true, "pend 4");
    expect("lev status", true, NULL);
    CHECK(strstr(last, "\"lev\":{\"state\"") != NULL, "%s", last);
    expect("lev tune bw_hz 12", true, "lev 4 bw_hz 12.000");
    expect("lev tune bw_hz", false, "");
    expect("lev fly", false, "");

    expect("pend sustain", true, "pend 1");
    expect("pend circle", true, "pend 2");
    expect("pend chaos", true, "pend 3");
    expect("pend off", true, "pend 0");
    expect("pend loop", false, "");

    expect("theremin on", true, "theremin 0");
    expect("theremin cal", true, "theremin 2");
    expect("fam live", true, "fam 1");
    expect("fam sweep", true, "fam 0");
    expect("fam maybe", false, "");
    expect("fam scan fam2 0.5", true, "fam scan 1 0.50");
    expect("fam scan fam3 0.5", false, "");
    expect("fam scan fam1 2", false, "");
    expect("film on", true, "film 1");
    expect("film off", true, "film 0");
    expect("film maybe", false, "");

    snprintf(want, sizeof want, "volume %.3f", (double)AUDIO_VOLUME_CEILING);
    expect("volume 1.0", true, want);                     /* at the ceiling (1.0 since 2026-11-07) */
    expect("volume 0.9", true, "volume 0.900");
    expect("volume 0.1", true, "volume 0.100");
    expect("volume -1", false, "");

    expect("i2c scan", true, NULL);
    expect("adc dump", true, NULL);
    expect("clear", true, "clear");
    expect("save", false, "save");                        /* the board refused */
    expect("reboot", true, "reboot 0");
    expect("reboot bootsel", true, "reboot 1");
    expect("bootsel", true, "reboot 1");

    expect("frob\"nicate", false, "");                    /* a quote in the echo is escaped */
    CHECK(strstr(last, "frob\\\"nicate") != NULL, "%s", last);

    /* characters one at a time; an over-long line is refused, not cut and run */
    int before = replies;
    for (int i = 0; i < 400; i++)
        console_feed('x');
    console_feed('\n');
    CHECK(replies == before + 1 && strstr(last, "too long"), "overflow: %s", last);
    const char *s = "scene dusk\r\n";
    for (; *s; s++)
        console_feed(*s);
    snprintf(want, sizeof want, "scene %d", SCENE_DUSK);
    CHECK(!strcmp(call, want), "fed 'scene dusk' -> '%s'", call);

    if (failures) {
        printf("test_console: %d FAILED\n", failures);
        return 1;
    }
    printf("test_console: %d replies, all well-formed; all passed\n", replies);
    return 0;
}
