/* i2c_bus.c: see i2c_bus.h. */
#include "i2c_bus.h"
#include "board_pins.h"
#include "config.h"
#include "jsonbuf.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "pico/time.h"
#include <stdio.h>
#include <string.h>

#define BUS i2c0
#define BYTE_US 40u                  /* a byte and its acknowledge at 400 kHz is 22.5 us */

static uint32_t errors;

uint32_t i2c_errors(void) { return errors; }

bool i2c_bus_recover(void)
{
    /* as the I2C specification's "bus clear": clock SCL until the target lets go of SDA */
    gpio_init(PIN_SDA);
    gpio_init(PIN_SCL);
    gpio_pull_up(PIN_SDA);
    gpio_pull_up(PIN_SCL);
    gpio_set_dir(PIN_SDA, GPIO_IN);
    gpio_set_dir(PIN_SCL, GPIO_IN);       /* released: the pull-ups hold it high */
    busy_wait_us_32(10);
    for (int i = 0; i < 9 && !gpio_get(PIN_SDA); i++) {
        gpio_put(PIN_SCL, 0);
        gpio_set_dir(PIN_SCL, GPIO_OUT);  /* open-drain style: drive low, release high */
        busy_wait_us_32(5);
        gpio_set_dir(PIN_SCL, GPIO_IN);
        busy_wait_us_32(5);
    }
    /* a STOP: SDA low then released while SCL is high */
    gpio_put(PIN_SDA, 0);
    gpio_set_dir(PIN_SDA, GPIO_OUT);
    busy_wait_us_32(5);
    gpio_set_dir(PIN_SDA, GPIO_IN);
    busy_wait_us_32(5);
    return gpio_get(PIN_SDA);
}

void i2c_bus_init(void)
{
    i2c_bus_recover();
    i2c_init(BUS, I2C_BAUD);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(PIN_SDA);                /* weak; the board has its own pull-ups */
    gpio_pull_up(PIN_SCL);
}

static uint32_t timeout_us(size_t bytes) { return 500u + (uint32_t)bytes * BYTE_US * 2u; }

static bool failed(int r)
{
    if (r < 0) {
        errors++;
        return true;
    }
    return false;
}

bool i2c_probe(uint8_t addr)
{
    uint8_t b;
    return i2c_read_timeout_us(BUS, addr, &b, 1, false, timeout_us(2)) == 1;
}

bool i2c_write_reg(uint8_t addr, uint8_t reg, const uint8_t *data, size_t n)
{
    uint8_t buf[64];
    if (n + 1 > sizeof buf)
        return false;
    buf[0] = reg;
    memcpy(buf + 1, data, n);
    int r = i2c_write_timeout_us(BUS, addr, buf, n + 1, false, timeout_us(n + 2));
    return !failed(r) && r == (int)(n + 1);
}

bool i2c_write_reg8(uint8_t addr, uint8_t reg, uint8_t value) { return i2c_write_reg(addr, reg, &value, 1); }

bool i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *data, size_t n)
{
    int r = i2c_write_timeout_us(BUS, addr, &reg, 1, true, timeout_us(2));
    if (failed(r) || r != 1)
        return false;
    r = i2c_read_timeout_us(BUS, addr, data, n, false, timeout_us(n + 1));
    return !failed(r) && r == (int)n;
}

const char *i2c_device_name(uint8_t addr)
{
    switch (addr) {
    case I2C_ADDR_LP5036_BASE: return "LP5036 base";
    case I2C_ADDR_LP5036_TREE: return "LP5036 tree";
    case I2C_ADDR_LSM6DS3TR_C: return "LSM6DS3TR-C";
    case I2C_ADDR_LTR_303ALS: return "LTR-303ALS";
    case I2C_ADDR_TMAG5273A2: return "TMAG5273A2";
    case 0x1C: return "LP5036 broadcast";
    default: return "?";
    }
}

void i2c_scan_json(char *buf, size_t n)
{
    jsonbuf j = jb_start(buf, n);
    jb_add(&j, "[");
    bool first = true;
    for (uint8_t a = 0x08; a < 0x78; a++) {
        if (!i2c_probe(a))
            continue;
        jb_add(&j, "%s{\"addr\":\"0x%02X\",\"name\":\"%s\"}", first ? "" : ",", a, i2c_device_name(a));
        first = false;
    }
    jb_add(&j, "]");
}
