/* sensors.c: see sensors.h.  Registers from each datasheet's register map. */
#include "sensors.h"
#include "board_pins.h"
#include "i2c_bus.h"
#include "pico/time.h"
#include <string.h>

/* ---- LSM6DS3TR-C ---------------------------------------------------------------- */
#define LSM_WHO_AM_I    0x0F    /* 0x6A */
#define LSM_CTRL1_XL    0x10
#define LSM_CTRL2_G     0x11
#define LSM_CTRL3_C     0x12
#define LSM_TAP_SRC     0x1C
#define LSM_OUT_TEMP_L  0x20
#define LSM_OUTX_L_XL   0x28
#define LSM_TAP_CFG     0x58
#define LSM_TAP_THS_6D  0x59
#define LSM_INT_DUR2    0x5A
#define LSM_WAKE_UP_THS 0x5B
#define LSM_MD1_CFG     0x5E

bool imu_init(imu_state *s)
{
    memset(s, 0, sizeof *s);
    uint8_t who = 0;
    if (!i2c_read_reg(I2C_ADDR_LSM6DS3TR_C, LSM_WHO_AM_I, &who, 1) || who != 0x6A)
        return false;
    const uint8_t a = I2C_ADDR_LSM6DS3TR_C;
    bool ok = i2c_write_reg8(a, LSM_CTRL3_C, 0x01) &&          /* SW_RESET */
              (sleep_ms(2), true) &&
              i2c_write_reg8(a, LSM_CTRL3_C, 0x44) &&          /* BDU, IF_INC */
              i2c_write_reg8(a, LSM_CTRL1_XL, 0x60) &&         /* 416 Hz, +-2 g (taps need >= 416 Hz) */
              i2c_write_reg8(a, LSM_CTRL2_G, 0x00) &&          /* gyroscope off */
              i2c_write_reg8(a, LSM_TAP_CFG, 0x8F) &&          /* interrupts, taps on X Y Z, latched */
              i2c_write_reg8(a, LSM_TAP_THS_6D, 0x0C) &&       /* tap threshold 12 x FS/32 = 0.75 g */
              i2c_write_reg8(a, LSM_INT_DUR2, 0x7F) &&         /* DUR 7, QUIET 3, SHOCK 3 (ST's AN5130 values) */
              i2c_write_reg8(a, LSM_WAKE_UP_THS, 0x80) &&      /* single and double taps */
              i2c_write_reg8(a, LSM_MD1_CFG, 0x48);            /* both on INT1 */
    s->present = ok;
    return ok;
}

bool imu_read(imu_state *s)
{
    uint8_t d[6], tap = 0, t[2];
    if (!s->present)
        return false;
    if (!i2c_read_reg(I2C_ADDR_LSM6DS3TR_C, LSM_OUTX_L_XL, d, 6) ||
        !i2c_read_reg(I2C_ADDR_LSM6DS3TR_C, LSM_TAP_SRC, &tap, 1) ||
        !i2c_read_reg(I2C_ADDR_LSM6DS3TR_C, LSM_OUT_TEMP_L, t, 2)) {
        s->errors++;
        return false;
    }
    const float k = 0.061e-3f;                                 /* g per LSB at +-2 g */
    int16_t x = (int16_t)(d[0] | d[1] << 8), y = (int16_t)(d[2] | d[3] << 8), z = (int16_t)(d[4] | d[5] << 8);
    s->g[0] = IMU_AXIS_X * k * (float)x;
    s->g[1] = IMU_AXIS_Y * k * (float)y;
    s->g[2] = IMU_AXIS_Z * k * (float)z;
    s->temp_C = 25.0f + (float)(int16_t)(t[0] | t[1] << 8) / 256.0f;
    s->tap = (tap & 0x20) != 0;                                /* SINGLE_TAP */
    s->double_tap = (tap & 0x10) != 0;                         /* DOUBLE_TAP */
    s->taps += s->tap;
    s->double_taps += s->double_tap;
    return true;
}

/* ---- LTR-303ALS --------------------------------------------------------------------- */
#define LTR_CONTR     0x80
#define LTR_MEAS_RATE 0x85
#define LTR_PART_ID   0x86    /* 0xA0 */
#define LTR_MANUFAC   0x87    /* 0x05 */
#define LTR_DATA      0x88    /* CH1 low, CH1 high, CH0 low, CH0 high: read together */
#define LTR_GAIN      48.0f
#define LTR_INT       1.0f    /* integration time / 100 ms */

bool als_init(als_state *s)
{
    memset(s, 0, sizeof *s);
    s->lux = -1.0f;
    uint8_t id[2];
    if (!i2c_read_reg(I2C_ADDR_LTR_303ALS, LTR_PART_ID, id, 2) || id[0] != 0xA0 || id[1] != 0x05)
        return false;
    bool ok = i2c_write_reg8(I2C_ADDR_LTR_303ALS, LTR_MEAS_RATE, 0x02) &&   /* 100 ms, every 200 ms */
              i2c_write_reg8(I2C_ADDR_LTR_303ALS, LTR_CONTR, (0x6 << 2) | 1); /* 48x, active */
    s->present = ok;
    return ok;
}

bool als_read(als_state *s)
{
    uint8_t d[4];
    if (!s->present)
        return false;
    if (!i2c_read_reg(I2C_ADDR_LTR_303ALS, LTR_DATA, d, 4)) {
        s->errors++;
        return false;
    }
    s->ch1 = (uint16_t)(d[0] | d[1] << 8);
    s->ch0 = (uint16_t)(d[2] | d[3] << 8);
    /* Lite-On's lux formula for the LTR-303/329 (the datasheet's appendix A) */
    float c0 = s->ch0, c1 = s->ch1;
    float ratio = c0 + c1 > 0.0f ? c1 / (c0 + c1) : 0.0f;
    float lux;
    if (ratio < 0.45f)
        lux = (1.7743f * c0 + 1.1059f * c1) / LTR_GAIN / LTR_INT;
    else if (ratio < 0.64f)
        lux = (4.2785f * c0 - 1.9548f * c1) / LTR_GAIN / LTR_INT;
    else if (ratio < 0.85f)
        lux = (0.5926f * c0 + 0.1185f * c1) / LTR_GAIN / LTR_INT;
    else
        lux = 0.0f;
    s->lux = lux < 0.0f ? 0.0f : lux;
    return true;
}

/* ---- TMAG5273A2 ------------------------------------------------------------------- */
#define TMAG_DEVICE_CONFIG_1 0x00
#define TMAG_DEVICE_CONFIG_2 0x01
#define TMAG_SENSOR_CONFIG_1 0x02
#define TMAG_SENSOR_CONFIG_2 0x03
#define TMAG_T_CONFIG        0x07
#define TMAG_DEVICE_ID       0x0D
#define TMAG_MANUFACTURER    0x0E    /* 0x49, 0x54 */
#define TMAG_T_MSB           0x10    /* T, X, Y, Z (MSB first), CONV_STATUS */
#define TMAG_RANGE_MT        133.0f  /* A2, X_Y_RANGE = Z_RANGE = 0 */

bool tmag_init(tmag_state *s)
{
    memset(s, 0, sizeof *s);
    uint8_t id[3];
    const uint8_t a = I2C_ADDR_TMAG5273A2;
    if (!i2c_read_reg(a, TMAG_DEVICE_ID, id, 3) || id[1] != 0x49 || id[2] != 0x54)
        return false;
    bool ok = i2c_write_reg8(a, TMAG_DEVICE_CONFIG_1, 0x03 << 2) &&   /* 8x averaging (1.6 kSPS, 3 axes) */
              i2c_write_reg8(a, TMAG_SENSOR_CONFIG_1, 0x7 << 4) &&    /* X, Y, Z */
              i2c_write_reg8(a, TMAG_SENSOR_CONFIG_2, 0x00) &&        /* +-133 mT */
              i2c_write_reg8(a, TMAG_T_CONFIG, 0x01) &&               /* temperature too */
              i2c_write_reg8(a, TMAG_DEVICE_CONFIG_2, 0x12);          /* low noise, continuous */
    s->present = ok;
    return ok;
}

bool tmag_read(tmag_state *s)
{
    uint8_t d[9];
    if (!s->present)
        return false;
    if (!i2c_read_reg(I2C_ADDR_TMAG5273A2, TMAG_T_MSB, d, 9)) {
        s->errors++;
        return false;
    }
    s->t_us = time_us_32();
    int16_t t = (int16_t)(d[0] << 8 | d[1]);
    for (int k = 0; k < 3; k++)
        s->b_mT[k] = (float)(int16_t)(d[2 + 2 * k] << 8 | d[3 + 2 * k]) * (TMAG_RANGE_MT / 32768.0f);
    s->temp_C = 25.0f + ((float)t - 17508.0f) / 58.0f;        /* TADC_T0 17508 at 25 C, 58 LSB/C */
    s->readings++;
    return true;
}
