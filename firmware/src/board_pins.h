/* board_pins.h: which RP2354A GPIO does what on OWLternating Current rev A.
 * WRITTEN BY gen/firmware_pins.py FROM gen/pins.py: edit that, not this. */
#pragma once

/* ---- every GPIO ---------------------------------------------------------- */
#define PIN_PEND1_IN1         0   /* out: pendulum coil 1 bridge (DRV8874 U5) IN1; PWM0 A */
#define PIN_PEND1_IN2         1   /* out: pendulum coil 1 bridge IN2; PWM0 B */
#define PIN_PEND2_IN1         2   /* out: pendulum coil 2 bridge (U6) IN1; PWM1 A */
#define PIN_PEND2_IN2         3   /* out: pendulum coil 2 bridge IN2; PWM1 B */
#define PIN_PEND3_IN1         4   /* out: pendulum coil 3 bridge (U7) IN1; PWM2 A */
#define PIN_PEND3_IN2         5   /* out: pendulum coil 3 bridge IN2; PWM2 B */
#define PIN_LEV_IN1           6   /* out: levitation coil bridge (U8) IN1; PWM3 A */
#define PIN_LEV_IN2           7   /* out: levitation coil bridge IN2; PWM3 B */
#define PIN_FAM1_A            8   /* out: owl perch bridge, leg A (UCC27524 U9); PWM4 A */
#define PIN_FAM1_B            9   /* out: owl perch bridge, leg B (U10); PWM4 B */
#define PIN_FAM2_A           10   /* out: cat perch bridge, leg A (U11); PWM5 A */
#define PIN_FAM2_B           11   /* out: cat perch bridge, leg B (U12); PWM5 B */
#define PIN_UART_TX          12   /* out: UART0 TX to the debug connector J5 (console, 115200) */
#define PIN_UART_RX          13   /* in: UART0 RX from J5 */
#define PIN_AUDIO            14   /* out: audio PWM to the class-D amplifier through an RC filter; PWM7 A */
#define PIN_IMU_INT          15   /* in: LSM6DS3TR-C INT1: taps, tilt, free fall */
#define PIN_SDA              16   /* io: I2C0 SDA: LED drivers, IMU, light sensor, 3-axis Hall; the tree's LED driver */
#define PIN_SCL              17   /* out: I2C0 SCL */
#define PIN_THEREMIN_PITCH   18   /* in: pitch oscillator (moon antenna), counted by PIO */
#define PIN_THEREMIN_VOL     19   /* in: volume oscillator (pumpkin antenna), counted by PIO */
#define PIN_MUX_S0           20   /* out: 74HC4051 select bit 0 */
#define PIN_MUX_S1           21   /* out: 74HC4051 select bit 1 */
#define PIN_MUX_S2           22   /* out: 74HC4051 select bit 2 */
#define PIN_DRV_nSLEEP       23   /* out: all four DRV8874s: low = asleep (10 k pull-down keeps them asleep in reset) */
#define PIN_DRV_nFAULT       24   /* in: all four DRV8874s' nFAULT, wired-OR, 10 k pull-up */
#define PIN_FAM_EN           25   /* out: the four UCC27524s' enables (10 k pull-down: off in reset) */
#define PIN_HALL             26   /* adc: ADC0: the perch's DRV5055 Hall sensor (via the tree) */
#define PIN_LEV_IPROPI       27   /* adc: ADC1: levitation coil current (DRV8874 IPROPI) */
#define PIN_MUX_OUT          28   /* adc: ADC2: the 74HC4051's output (slow signals, below) */
#define PIN_BUTTON           29   /* in: the SPELL button (10 k pull-up, low when pressed) */

/* ---- the coil bridges: one PWM slice each, IN1/leg A = channel A -------------- */
#define PWM_SLICE_PEND1  0   /* GPIO0 (IN1) = A, GPIO1 (IN2) = B */
#define PWM_SLICE_PEND2  1   /* GPIO2 (IN1) = A, GPIO3 (IN2) = B */
#define PWM_SLICE_PEND3  2   /* GPIO4 (IN1) = A, GPIO5 (IN2) = B */
#define PWM_SLICE_LEV    3   /* GPIO6 (IN1) = A, GPIO7 (IN2) = B */
#define PWM_SLICE_FAM1   4   /* GPIO8 (leg A) = A, GPIO9 (leg B) = B */
#define PWM_SLICE_FAM2   5   /* GPIO10 (leg A) = A, GPIO11 (leg B) = B */
#define PWM_SLICE_AUDIO  7   /* GPIO14 = A */
#define PWM_SLICE_TICK   6   /* no PWM output: GPIO12 and GPIO13 carry UART_TX and UART_RX */

/* ---- the ADC inputs ---------------------------------------------------- */
#define ADC_CH_HALL         0   /* GPIO26 */
#define ADC_CH_LEV_IPROPI   1   /* GPIO27 */
#define ADC_CH_MUX_OUT      2   /* GPIO28 */

/* ---- the 74HC4051 (S0-S2 on PIN_MUX_S0..S2) ------------------------------ */
#define MUX_SEL_SHIFT    20
#define MUX_SEL_MASK     (7u << MUX_SEL_SHIFT)
#define MUX_CH_PEND1_IPROPI   0   /* pendulum coil 1 current */
#define MUX_CH_PEND2_IPROPI   1   /* pendulum coil 2 current */
#define MUX_CH_PEND3_IPROPI   2   /* pendulum coil 3 current */
#define MUX_CH_FAM1_ISENSE    3   /* owl perch current (rectified, filtered) */
#define MUX_CH_FAM2_ISENSE    4   /* cat perch current (rectified, filtered) */
#define MUX_CH_V12_SENSE      5   /* +12V through 100 k / 22 k (12 V reads 2.16 V) */
#define MUX_CH_V5_SENSE       6   /* +5V through 10 k / 10 k (5 V reads 2.5 V) */
#define MUX_CH_VBUS_SENSE     7   /* USB VBUS through 10 k / 10 k: plugged into USB? */
#define MUX_CHANNELS     8
#define V12_DIVIDER          0.180328f   /* sense voltage / rail: 100 k over 22 k */
#define V5_DIVIDER           0.500000f   /* sense voltage / rail: 10 k over 10 k */
#define VBUS_DIVIDER         0.500000f   /* sense voltage / rail: 10 k over 10 k */

/* ---- I2C0 (7-bit addresses) ------------------------------------------------- */
#define I2C_ADDR_LP5036_BASE  0x30
#define I2C_ADDR_LP5036_TREE  0x31
#define I2C_ADDR_LSM6DS3TR_C  0x6A
#define I2C_ADDR_LTR_303ALS   0x29
#define I2C_ADDR_TMAG5273A2   0x35

/* ---- what the board's own 10 k resistors hold while the RP2354A is in reset ---- */
#define BOARD_PULL_UP_MASK    ((1u << PIN_DRV_nFAULT) | (1u << PIN_BUTTON))
#define BOARD_PULL_DOWN_MASK  ((1u << PIN_DRV_nSLEEP) | (1u << PIN_FAM_EN))

/* every pin that drives a coil bridge: low = off (DRV8874 coast, UCC27524 output low) */
#define BRIDGE_PIN_MASK  ((1u << PIN_PEND1_IN1) | \
                          (1u << PIN_PEND2_IN1) | \
                          (1u << PIN_PEND3_IN1) | \
                          (1u << PIN_LEV_IN1) | \
                          (1u << PIN_PEND1_IN2) | \
                          (1u << PIN_PEND2_IN2) | \
                          (1u << PIN_PEND3_IN2) | \
                          (1u << PIN_LEV_IN2) | \
                          (1u << PIN_FAM1_A) | \
                          (1u << PIN_FAM2_A) | \
                          (1u << PIN_FAM1_B) | \
                          (1u << PIN_FAM2_B))
