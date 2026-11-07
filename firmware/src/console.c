/* console.c: the console's parser and limits.  See console.h. */
#include "console.h"
#include "config.h"
#include "led_engine.h"
#include "scenes.h"
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const console_ops *ops;
static char reply[CONSOLE_REPLY_MAX];
static char inner[CONSOLE_REPLY_MAX - 64];

static const char *const COIL_NAMES[COIL_COUNT] = {"pend1", "pend2", "pend3", "lev"};
static const char *const PEND_NAMES[] = {"off", "sustain", "circle", "chaos", "cal"};

const char *coil_name(int coil) { return coil >= 0 && coil < COIL_COUNT ? COIL_NAMES[coil] : "?"; }

void console_init(const console_ops *o) { ops = o; }

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

static void ok(const char *cmd, const char *extra)
{
    snprintf(reply, sizeof reply, "{\"ok\":true,\"cmd\":\"%s\"%s%s}", cmd, extra && *extra ? "," : "", extra ? extra : "");
    ops->reply(reply);
}

static void fail(const char *cmd, const char *msg)
{
    char c[48], m[160];
    escape(c, sizeof c, cmd);
    escape(m, sizeof m, msg);
    snprintf(reply, sizeof reply, "{\"ok\":false,\"cmd\":\"%s\",\"error\":\"%s\"}", c, m);
    ops->reply(reply);
}

static void done(const char *cmd, const char *err, const char *extra)
{
    if (err)
        fail(cmd, err);
    else
        ok(cmd, extra);
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

static int lookup(const char *s, const char *const *names, int n)
{
    for (int i = 0; i < n; i++)
        if (s && !strcmp(s, names[i]))
            return i;
    return -1;
}

const char *console_coil_limits(float duty, uint32_t ms, float v12, float r_ohm)
{
    static char msg[96];
    if (!(duty >= -1.0f && duty <= 1.0f))
        return "duty must be -1..1";
    if (ms == 0 || ms > CONSOLE_ON_MAX_MS) {
        snprintf(msg, sizeof msg, "ms must be 1..%u", (unsigned)CONSOLE_ON_MAX_MS);
        return msg;
    }
    if (!(v12 >= V12_PRESENT_V))
        return "no 12 V: the coils stay off";
    float i = fabsf(duty) * v12 / (r_ohm + DRV_RDSON_OHM);
    if (i > CONSOLE_I_MAX_A) {
        snprintf(msg, sizeof msg, "%.2f A expected: over the console's %.1f A (try |duty| <= %.3f)", (double)i,
                 (double)CONSOLE_I_MAX_A, (double)(CONSOLE_I_MAX_A * (r_ohm + DRV_RDSON_OHM) / v12));
        return msg;
    }
    return NULL;
}

static const char HELP[] =
    "\"commands\":[\"status\",\"scene <asleep|dusk|night|firefly|quantum|familiar|dawn|theremin|auto>\","
    "\"led <name|all> <0..1|off>\",\"coil <pend1|pend2|pend3|lev> <duty -1..1> <ms>\",\"sweep <fam1|fam2>\","
    "\"lev <on|off|status>\",\"lev cal [coil|zero]\",\"lev tune <param> <value>\",\"lev eyes <0..1>\","
    "\"pend <off|sustain|circle|chaos|cal>\","
    "\"theremin <on|off|cal>\",\"fam <live|sweep>\",\"film <on|off>\",\"volume <0..1>\",\"i2c scan\",\"adc dump\",\"clear\",\"save\","
    "\"reboot\",\"reboot bootsel\",\"help\"]";

void console_command(char *line)
{
    char *tok[5] = {0};
    int n = 0;
    for (char *p = strtok(line, " \t\r\n"); p && n < 5; p = strtok(NULL, " \t\r\n"))
        tok[n++] = p;
    if (!n)
        return;
    for (char *p = tok[0]; *p; p++)
        *p = (char)tolower((unsigned char)*p);
    const char *cmd = tok[0];
    char extra[160];
    float v;

    if (!strcmp(cmd, "help")) {
        ok("help", HELP);
    } else if (!strcmp(cmd, "status")) {
        ops->status_json(inner, sizeof inner);
        snprintf(reply, sizeof reply, "{\"ok\":true,\"cmd\":\"status\",\"status\":%s}", inner);
        ops->reply(reply);
    } else if (!strcmp(cmd, "scene")) {
        int id = -2;
        if (tok[1] && !strcmp(tok[1], "auto"))
            id = -1;
        else if (tok[1] && scene_by_name(tok[1]) >= 0)
            id = scene_by_name(tok[1]);
        if (id == -2) {
            fail(cmd, "scene <asleep|dusk|night|firefly|quantum|familiar|dawn|theremin|auto>");
            return;
        }
        snprintf(extra, sizeof extra, "\"scene\":\"%s\"", id < 0 ? "auto" : scene_name((scene_id)id));
        done(cmd, ops->scene(id), extra);
    } else if (!strcmp(cmd, "led")) {
        if (n != 3) {
            fail(cmd, "led <name|all> <0..1|off>");
            return;
        }
        int led = !strcmp(tok[1], "all") ? -1 : led_engine_find(tok[1]);
        if (led == -1 && strcmp(tok[1], "all")) {
            fail(cmd, "no such LED (status lists them? see firmware/src/led_map.h)");
            return;
        }
        float level;
        if (!strcmp(tok[2], "off"))
            level = -1.0f;
        else if (!number(tok[2], &level) || level < 0.0f || level > 1.0f) {
            fail(cmd, "level must be 0..1 or off");
            return;
        }
        if (level < 0.0f)
            snprintf(extra, sizeof extra, "\"led\":\"%s\",\"level\":\"scene\"", led < 0 ? "all" : LED_MAP[led].name);
        else
            snprintf(extra, sizeof extra, "\"led\":\"%s\",\"level\":%.3f", led < 0 ? "all" : LED_MAP[led].name,
                     (double)level);
        done(cmd, ops->led(led, level), extra);
    } else if (!strcmp(cmd, "coil")) {
        float duty, ms;
        int c = lookup(tok[1], COIL_NAMES, COIL_COUNT);
        if (n != 4 || c < 0 || !number(tok[2], &duty) || !number(tok[3], &ms) || ms < 0.0f || ms > 1e6f) {
            fail(cmd, "coil <pend1|pend2|pend3|lev> <duty -1..1> <ms>");
            return;
        }
        snprintf(extra, sizeof extra, "\"coil\":\"%s\",\"duty\":%.3f,\"ms\":%u", COIL_NAMES[c], (double)duty,
                 (unsigned)ms);
        done(cmd, ops->coil(c, duty, (uint32_t)ms), extra);
    } else if (!strcmp(cmd, "sweep")) {
        int p = tok[1] && !strcmp(tok[1], "fam1") ? 0 : tok[1] && !strcmp(tok[1], "fam2") ? 1 : -1;
        if (p < 0) {
            fail(cmd, "sweep <fam1|fam2>");
            return;
        }
        snprintf(extra, sizeof extra, "\"perch\":\"fam%d\",\"result\":\"event\"", p + 1);
        done(cmd, ops->sweep(p), extra);
    } else if (!strcmp(cmd, "lev")) {
        static const char *const OPS[] = {"on", "off", "cal", "status", "tune", "eyes"};
        int op = lookup(tok[1], OPS, 6);
        if (op < 0) {
            fail(cmd, "lev <on|off|status> | lev cal [coil|zero] | lev tune <param> <value> | lev eyes <0..1>");
            return;
        }
        if (op == LEV_OP_EYES) {
            if (n != 3 || !number(tok[2], &v) || v < 0.0f || v > 1.0f) {
                fail(cmd, "lev eyes <0..1>");
                return;
            }
            snprintf(extra, sizeof extra, "\"eyes\":%.2f", (double)v);
            done(cmd, ops->lev(op, NULL, v), extra);
            return;
        }
        if (op == LEV_OP_CAL) {
            const char *kind = tok[2] ? tok[2] : "coil";
            if (strcmp(kind, "coil") && strcmp(kind, "zero")) {
                fail(cmd, "lev cal [coil|zero]");
                return;
            }
            snprintf(extra, sizeof extra, "\"cal\":\"%s\"", kind);
            done(cmd, ops->lev(op, kind, 0.0f), extra);
            return;
        }
        if (op == LEV_OP_STATUS) {
            ops->lev_json(inner, sizeof inner);
            snprintf(reply, sizeof reply, "{\"ok\":true,\"cmd\":\"lev\",\"lev\":%s}", inner);
            ops->reply(reply);
            return;
        }
        if (op == LEV_OP_TUNE) {
            if (n != 4 || !number(tok[3], &v)) {
                fail(cmd, "lev tune <param> <value>");
                return;
            }
            char p[40];
            escape(p, sizeof p, tok[2]);
            snprintf(extra, sizeof extra, "\"tune\":\"%s\",\"value\":%g", p, (double)v);
            done(cmd, ops->lev(op, tok[2], v), extra);
            return;
        }
        snprintf(extra, sizeof extra, "\"lev\":\"%s\"", OPS[op]);
        done(cmd, ops->lev(op, NULL, 0.0f), extra);
    } else if (!strcmp(cmd, "pend")) {
        int m = lookup(tok[1], PEND_NAMES, 5);
        if (m < 0) {
            fail(cmd, "pend <off|sustain|circle|chaos|cal>");
            return;
        }
        snprintf(extra, sizeof extra, "\"pend\":\"%s\"", PEND_NAMES[m]);
        done(cmd, ops->pend(m), extra);
    } else if (!strcmp(cmd, "theremin")) {
        static const char *const OPS[] = {"on", "off", "cal"};
        int op = lookup(tok[1], OPS, 3);
        if (op < 0) {
            fail(cmd, "theremin <on|off|cal>");
            return;
        }
        snprintf(extra, sizeof extra, "\"theremin\":\"%s\"", OPS[op]);
        done(cmd, ops->theremin(op), extra);
    } else if (!strcmp(cmd, "fam")) {
        int live = tok[1] && !strcmp(tok[1], "live") ? 1 : tok[1] && !strcmp(tok[1], "sweep") ? 0 : -1;
        if (live < 0) {
            fail(cmd, "fam <live|sweep>");
            return;
        }
        snprintf(extra, sizeof extra, "\"fam\":\"%s\"", live ? "live" : "sweep");
        done(cmd, ops->fam(live), extra);
    } else if (!strcmp(cmd, "film")) {
        int on = tok[1] && !strcmp(tok[1], "on") ? 1 : tok[1] && !strcmp(tok[1], "off") ? 0 : -1;
        if (on < 0) {
            fail(cmd, "film <on|off>");
            return;
        }
        snprintf(extra, sizeof extra, "\"film\":%s", on ? "true" : "false");
        done(cmd, ops->film(on == 1), extra);
    } else if (!strcmp(cmd, "volume")) {
        if (n != 2 || !number(tok[1], &v) || v < 0.0f || v > 1.0f) {
            fail(cmd, "volume <0..1>");
            return;
        }
        float capped = v > AUDIO_VOLUME_CEILING ? AUDIO_VOLUME_CEILING : v;
        snprintf(extra, sizeof extra, "\"volume\":%.3f%s", (double)capped, capped < v ? ",\"capped\":true" : "");
        done(cmd, ops->volume(capped), extra);
    } else if (!strcmp(cmd, "i2c") && tok[1] && !strcmp(tok[1], "scan")) {
        ops->i2c_scan_json(inner, sizeof inner);
        snprintf(reply, sizeof reply, "{\"ok\":true,\"cmd\":\"i2c scan\",\"i2c\":%s}", inner);
        ops->reply(reply);
    } else if (!strcmp(cmd, "adc") && tok[1] && !strcmp(tok[1], "dump")) {
        ops->adc_dump_json(inner, sizeof inner);
        snprintf(reply, sizeof reply, "{\"ok\":true,\"cmd\":\"adc dump\",\"adc\":%s}", inner);
        ops->reply(reply);
    } else if (!strcmp(cmd, "clear")) {
        done(cmd, ops->clear(), NULL);
    } else if (!strcmp(cmd, "save")) {
        done(cmd, ops->save(), NULL);
    } else if (!strcmp(cmd, "reboot") || !strcmp(cmd, "bootsel")) {
        bool bootsel = !strcmp(cmd, "bootsel") || (tok[1] && !strcmp(tok[1], "bootsel"));
        ok(cmd, bootsel ? "\"to\":\"bootsel\"" : NULL);
        ops->reboot(bootsel);
    } else {
        char c[40];
        escape(c, sizeof c, cmd);
        snprintf(extra, sizeof extra, "unknown command '%s' (help lists them)", c);
        fail(cmd, extra);
    }
}

void console_feed(char c)
{
    static char line[CONSOLE_LINE_MAX];
    static size_t n;
    static bool overflow;
    if (c == '\r' || c == '\n') {
        if (overflow)
            fail("?", "line too long");
        else if (n) {
            line[n] = 0;
            console_command(line);
        }
        n = 0;
        overflow = false;
    } else if (n < sizeof line - 1) {
        line[n++] = c;
    } else {
        overflow = true;
    }
}
