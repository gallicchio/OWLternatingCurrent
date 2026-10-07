/* sensors.h: the I2C sensors.
 *
 *   LSM6DS3TR-C (0x6A)  accelerometer at 416 Hz, +-2 g: gravity for the wisps, single
 *                       and double taps (latched in TAP_SRC, also on INT1), its
 *                       temperature (the board's, near the coils)
 *   LTR-303ALS (0x29)   ambient light: gain 48x (0.02-1300 lux), 100 ms integration,
 *                       every 200 ms
 *   TMAG5273A2 (0x35)   3-axis Hall under the pendulum: X, Y, Z at +-133 mT and its
 *                       temperature, continuous conversion, 8x averaging (pendulum.h's noise)
 *
 * [ASSUMED] the IMU's axes are the board's (x right, y toward the sky, z out of the
 * face); IMU_AXIS_* below fix it once the placement is known.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define IMU_AXIS_X  (+1)    /* board x = IMU_AXIS_X * IMU x  [ASSUMED] */
#define IMU_AXIS_Y  (+1)
#define IMU_AXIS_Z  (+1)

typedef struct {
    bool present;
    float g[3];              /* board frame, in g (gravity reads -1 g on z, flat) */
    float temp_C;
    bool tap, double_tap;    /* since the last read */
    uint32_t taps, double_taps, errors;
} imu_state;

typedef struct {
    bool present;
    float lux;               /* < 0 until the first reading */
    uint16_t ch0, ch1;
    uint32_t errors;
} als_state;

typedef struct {
    bool present;
    float b_mT[3];
    float temp_C;
    uint32_t t_us;           /* when the reading was taken */
    uint32_t readings, errors;
} tmag_state;

bool imu_init(imu_state *s);
bool imu_read(imu_state *s);        /* acceleration, taps; temperature every call too */
bool als_init(als_state *s);
bool als_read(als_state *s);
bool tmag_init(tmag_state *s);
bool tmag_read(tmag_state *s);
