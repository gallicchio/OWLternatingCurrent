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
 * [ASSUMED] a chip on the top side at 0 degrees would have the board's axes (x right,
 * y toward the sky, z out of the face).  U15 is on the BOTTOM at 0 degrees: KiCad
 * mirrors a back-side footprint top-to-bottom (its pad 1 is at local (-1.26, -0.75) in
 * the library and lands at (-1.26, +0.75) on the board, checked in the board file), so
 * the chip's y runs along the board's -y and its z points into the board: Y and Z flip,
 * X keeps its sense.  Still to be confirmed by tilting the first board (the wisps roll
 * the wrong way if a sign is wrong; harmless).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define IMU_AXIS_X  (+1)    /* board x = IMU_AXIS_X * IMU x  [ASSUMED, see above] */
#define IMU_AXIS_Y  (-1)    /* mirrored by the bottom-side placement */
#define IMU_AXIS_Z  (-1)    /* the chip faces down */

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
