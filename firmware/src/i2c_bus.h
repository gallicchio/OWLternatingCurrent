/* i2c_bus.h: I2C0 (GPIO20/21), shared by the LED drivers, the IMU, the light sensor and
 * the 3-axis Hall sensor.  Core 0 owns it; every transfer has a timeout, and a
 * stuck bus is freed with nine clocks. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

void i2c_bus_init(void);
bool i2c_bus_recover(void);                    /* nine SCL pulses and a STOP; true if SDA is free */
bool i2c_probe(uint8_t addr);                  /* does anything acknowledge? */
bool i2c_write_reg(uint8_t addr, uint8_t reg, const uint8_t *data, size_t n);
bool i2c_write_reg8(uint8_t addr, uint8_t reg, uint8_t value);
bool i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *data, size_t n);
uint32_t i2c_errors(void);
/* the scan: a JSON array of the addresses that answered, with their names */
void i2c_scan_json(char *buf, size_t n);
const char *i2c_device_name(uint8_t addr);
