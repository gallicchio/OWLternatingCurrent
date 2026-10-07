/* lp5036.c: see lp5036.h.  Register map: the LP5036 datasheet, section 8.6. */
#include "lp5036.h"
#include "i2c_bus.h"
#include "pico/time.h"
#include <string.h>

bool lp5036_init(lp5036 *d, uint8_t addr)
{
    memset(d, 0, sizeof *d);
    d->addr = addr;
    if (!i2c_probe(addr))
        return false;
    /* RESET (0xFF to 0x38) puts every register back to its default: all colours 0, so
     * nothing lights while we configure */
    if (!i2c_write_reg8(addr, LP5036_RESET, 0xFF))
        return false;
    sleep_us(500);
    uint8_t cfg1 = 0;
    if (!i2c_read_reg(addr, LP5036_DEVICE_CONFIG1, &cfg1, 1) || cfg1 != 0x3C)
        return false;                     /* the reset value of DEVICE_CONFIG1: it is an LP503x */
    bool ok = i2c_write_reg8(addr, LP5036_DEVICE_CONFIG0, LP5036_CHIP_EN) &&
              i2c_write_reg8(addr, LP5036_DEVICE_CONFIG1, LP5036_CONFIG1_VALUE) &&
              i2c_write_reg8(addr, LP5036_LED_CONFIG0, 0x00) &&      /* independent control */
              i2c_write_reg8(addr, LP5036_LED_CONFIG1, 0x00);
    if (!ok)
        return false;
    /* the frame's registers to a known dark state */
    uint8_t dark[LP5036_FRAME_BYTES];
    memset(dark, 0, sizeof dark);
    for (int b = 0; b < 12; b++)
        dark[b] = 16;
    if (!i2c_write_reg(addr, LP5036_FRAME_REG, dark, sizeof dark))
        return false;
    memcpy(d->shadow, dark, sizeof dark);
    d->shadow_valid = true;
    d->present = true;
    return true;
}

bool lp5036_write_frame(lp5036 *d, const uint8_t image[LP5036_FRAME_BYTES])
{
    if (!d->present)
        return false;
    int first = -1, last = -1;
    for (int i = 0; i < LP5036_FRAME_BYTES; i++)
        if (!d->shadow_valid || d->shadow[i] != image[i]) {
            if (first < 0)
                first = i;
            last = i;
        }
    if (first < 0)
        return true;                      /* nothing changed */
    int n = last - first + 1;
    if (!i2c_write_reg(d->addr, (uint8_t)(LP5036_FRAME_REG + first), image + first, (size_t)n)) {
        d->errors++;
        d->shadow_valid = false;          /* send it all next time */
        return false;
    }
    memcpy(d->shadow + first, image + first, (size_t)n);
    d->shadow_valid = true;
    d->frames++;
    d->bytes += (uint32_t)n;
    return true;
}

void lp5036_all_off(lp5036 *d)
{
    if (d->present)
        i2c_write_reg8(d->addr, LP5036_DEVICE_CONFIG1, LP5036_CONFIG1_VALUE | 1u);
}
