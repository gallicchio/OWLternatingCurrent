/* settings.h: what the board remembers across resets, in the flash's last sector.
 * Written only when asked (`save`), and only with every coil off: a flash write
 * pauses core 1 for ~45 ms (flash_safe_execute), and nothing may be driven then. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "lev_ctrl.h"

typedef struct {
    lev_cal_data lev;          /* the levitation's calibration (lev cal) */
    float pend_offset_mT[3];   /* the 3-axis Hall sensor's reading with no bat (pend cal) */
    float volume;              /* the theremin's loudness, 0..AUDIO_VOLUME_CEILING */
    uint8_t theremin_on;
    uint8_t familiars_on;
    uint8_t pend_offset_valid;
    uint8_t pad;
} settings_data;

void settings_defaults(settings_data *s);
bool settings_load(settings_data *s);          /* false: none saved (defaults filled in) */
const char *settings_save(const settings_data *s);   /* NULL when saved, else why not */
