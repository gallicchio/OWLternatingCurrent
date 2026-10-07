/* thermal.h: how hot each coil is, so that nothing a hand can reach passes
 * COIL_SURFACE_LIMIT_C (45 degC, PLAN.md section 7).
 *
 * One model per coil (the glue keeps four: PEND1, PEND2, PEND3, LEV), two
 * thermal nodes to ambient:
 *
 *        P = I^2 R(T)
 *          |
 *     [copper + surface] --R_cu_board-- [the board under the coil] --R_board_amb-- ambient
 *          C_cu                              C_board
 *
 * The copper node is the surface: the top layer's spiral lies under nothing but
 * solder mask.  The copper is also its own thermometer: its resistance rises
 * 0.39 %/degC, so a valid V/I measurement corrects the model (thermal_measure_r).
 * Because the DRV8874's IPROPI gain may be off by up to 6 %, an absolute
 * resistance reading can be 15 K wrong; so the first readings taken while the
 * model says the coil is cold calibrate the reference resistance (that cancels
 * the gain error), and until then a reading may only raise the estimate, never
 * lower it.
 *
 * Portable C (no SDK): the host test (test/test_thermal.c) runs it.
 *
 * How the glue uses it (core 1):
 *   thermal_update()     at ~1 kHz, with the mean I^2 over the interval and the
 *                        board temperature (IMU or TMAG5273) as ambient;
 *   thermal_measure_r()  whenever it has a DC-ish V/I measurement (|I| above
 *                        THERMAL_MEAS_MIN_A, the drive steady for a few ms);
 *   thermal_derate()     multiplies every current limit for that coil;
 *   thermal_r_ohm()      for converting a current target into a duty;
 *   thermal_max_on_s() / thermal_max_current_A()  for film mode's planning.
 */
#pragma once
#include <stdbool.h>

/* ---- model parameters, per coil [ASSUMED]: derivation in thermal.c ---------------- */
#define THERMAL_C_CU_J_PER_K         0.3f    /* the spiral (0.5 g of copper) and the FR4 just round it */
#define THERMAL_C_BOARD_J_PER_K      2.5f    /* the FR4 under and around the coil (r ~ 15 mm) */
#define THERMAL_R_CU_BOARD_K_PER_W   3.0f    /* copper into the board: tau ~ 1 s */
#define THERMAL_R_BOARD_AMB_K_PER_W  40.0f   /* the coil's patch of board to the room */

/* ---- the resistance thermometer [CHOICE] -------------------------------------------- */
#define THERMAL_MEAS_MIN_A           0.3f    /* below this, IPROPI's +-30 mA offset spoils V/I */
#define THERMAL_CORR_TAU_S           1.0f    /* how fast a reading pulls the model (both nodes) */
#define THERMAL_COLD_BAND_K          0.3f    /* "cold": the copper within this of ambient ... */
#define THERMAL_COLD_S               60.0f   /* ... for this long: a reading then calibrates R */
#define THERMAL_CAL_READINGS         5       /* readings averaged into the calibration */

typedef struct {
    float c_cu_J_per_K, c_board_J_per_K;
    float r_cu_board_K_per_W, r_board_amb_K_per_W;
    float r20_ohm;                 /* nominal resistance at 20 degC (COIL_R20_OHM) */
    float limit_C;                 /* COIL_SURFACE_LIMIT_C */
    float derate_from_C;           /* COIL_DERATE_FROM_C */
} thermal_params;

typedef struct {
    thermal_params p;
    float t_cu_C, t_board_C, t_amb_C;
    float comp_cu, comp_board;     /* Kahan compensation: at 1 kHz a step's increment is below
                                      float's resolution near equilibrium (it stalled 0.4 K short) */
    float r_ref_ohm, t_ref_C;      /* R(T) = r_ref (1 + alpha (T - t_ref)) */
    bool r_calibrated;
    float cold_s;                  /* how long the copper has been within the cold band */
    float cal_sum_ohm;             /* readings taken while cold, being averaged */
    int cal_n;
    float t_meas_C;                /* the last resistance-thermometer reading (or -273 if none) */
    float p_W;                     /* the heating power in the last update */
    float peak_C;                  /* the hottest surface estimate since init */
} thermal_coil;

void thermal_default_params(thermal_params *p);
void thermal_init(thermal_coil *c, const thermal_params *p, float ambient_C);
/* the coil is known to be at ambient now (a power-on boot after the board was off, not a
 * watchdog reset): its first resistance readings may calibrate at once, instead of after
 * THERMAL_COLD_S of the model sitting at ambient */
void thermal_assume_cold(thermal_coil *c);

/* advance by dt_s with the mean of I^2 over that interval (A^2); ambient_C is the
 * board's temperature (pass the previous value if no sensor has answered) */
void thermal_update(thermal_coil *c, float dt_s, float i2_mean_A2, float ambient_C);

/* a resistance measurement r = V / I of the coil alone (bridge resistance taken off),
 * made over dt_s; ignored if implausible */
void thermal_measure_r(thermal_coil *c, float r_meas_ohm, float dt_s);

float thermal_surface_C(const thermal_coil *c);   /* the estimate of the hottest touchable point */
float thermal_r_ohm(const thermal_coil *c);       /* the coil's resistance now */
float thermal_derate(const thermal_coil *c);      /* 1 below derate_from_C .. 0 at limit_C */

/* the longest time current i_A can flow, starting now, before the surface reaches
 * limit_C (horizon_s if never within it; 0 if already there) */
float thermal_max_on_s(const thermal_coil *c, float i_A, float limit_C, float horizon_s);
/* the largest current that can flow for on_s without the surface reaching limit_C */
float thermal_max_current_A(const thermal_coil *c, float on_s, float limit_C);
