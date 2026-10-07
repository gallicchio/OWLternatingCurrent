/* settings.c: see settings.h.  The pattern is GPiBridge's (main.c there). */
#include "settings.h"
#include "config.h"
#include "rt.h"
#include "hardware/flash.h"
#include "pico/flash.h"
#include <string.h>

#define SETTINGS_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)
#define SETTINGS_MAGIC  0x4F574C31u      /* "OWL1" */

typedef struct {
    uint32_t magic;
    uint32_t size;
    settings_data d;
    uint32_t check;
} settings_record;

static uint32_t checksum(const settings_data *d)
{
    const uint8_t *p = (const uint8_t *)d;
    uint32_t h = 2166136261u;            /* FNV-1a */
    for (size_t i = 0; i < sizeof *d; i++)
        h = (h ^ p[i]) * 16777619u;
    return h;
}

void settings_defaults(settings_data *s)
{
    memset(s, 0, sizeof *s);
    s->volume = AUDIO_VOLUME_DEFAULT;
    s->theremin_on = 1;
    s->familiars_on = 1;
}

bool settings_load(settings_data *s)
{
    const settings_record *r = (const settings_record *)(XIP_BASE + SETTINGS_OFFSET);
    if (r->magic != SETTINGS_MAGIC || r->size != sizeof *r || r->check != checksum(&r->d)) {
        settings_defaults(s);
        return false;
    }
    *s = r->d;
    if (!(s->volume >= 0.0f && s->volume <= AUDIO_VOLUME_CEILING))
        s->volume = AUDIO_VOLUME_DEFAULT;
    return true;
}

static settings_record pending;

static void write_now(void *arg)
{
    (void)arg;
    static uint8_t page[FLASH_PAGE_SIZE * ((sizeof(settings_record) + FLASH_PAGE_SIZE - 1) / FLASH_PAGE_SIZE)];
    memset(page, 0xff, sizeof page);
    memcpy(page, &pending, sizeof pending);
    flash_range_erase(SETTINGS_OFFSET, FLASH_SECTOR_SIZE);
    flash_range_program(SETTINGS_OFFSET, page, sizeof page);
}

const char *settings_save(const settings_data *s)
{
    if (!rt_coils_idle())
        return "a coil is on (lev off, pend off, film off first): a flash write pauses core 1";
    const settings_record *r = (const settings_record *)(XIP_BASE + SETTINGS_OFFSET);
    pending = (settings_record){.magic = SETTINGS_MAGIC, .size = sizeof(settings_record), .d = *s};
    pending.check = checksum(&pending.d);
    if (!memcmp(r, &pending, sizeof pending))
        return NULL;                     /* already there: no wear */
    if (flash_safe_execute(write_now, NULL, 200) != PICO_OK)
        return "flash busy";
    return NULL;
}
