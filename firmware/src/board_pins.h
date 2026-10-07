/* board_pins.h: which RP2354A GPIO does what on OWLternating Current rev A.
 * WRITTEN BY gen/firmware_pins.py FROM gen/pins.py: edit that, not this. */
#pragma once

/* ---- every GPIO ---------------------------------------------------------- */
#define PIN_THEREMIN_PITCH    0   /* in: pitch oscillator (moon antenna), counted by PIO */
#define PIN_IMU_INT           1   /* in: LSM6DS3TR-C INT1: taps, tilt, free fall */
#define PIN_PEND2_IN1         2   /* out: pendulum coil 2 bridge (U6) IN1; PWM1 A */
#define PIN_PEND2_IN2         3   /* out: pendulum coil 2 bridge IN2; PWM1 B */
#define PIN_FAM1_A            4   /* out: owl perch bridge, leg A (UCC27524 U9, channel A); PWM2 A */
#define PIN_FAM1_B            5   /* out: owl perch bridge, leg B (U9, channel B); PWM2 B */
#define PIN_PEND1_IN1         6   /* out: pendulum coil 1 bridge (DRV8874 U5) IN1; PWM3 A */
#define PIN_PEND1_IN2         7   /* out: pendulum coil 1 bridge IN2; PWM3 B */
#define PIN_AUDIO             8   /* out: audio PWM to the class-D amplifier through an RC filter; PWM4 A */
#define PIN_THEREMIN_VOL      9   /* in: volume oscillator (pumpkin antenna), counted by PIO */
#define PIN_PEND3_IN1        10   /* out: pendulum coil 3 bridge (U7) IN1; PWM5 A */
#define PIN_PEND3_IN2        11   /* out: pendulum coil 3 bridge IN2; PWM5 B */
#define PIN_LEV_IN1          12   /* out: levitation coil bridge (U8) IN1; PWM6 A */
#define PIN_LEV_IN2          13   /* out: levitation coil bridge IN2; PWM6 B */
#define PIN_FAM2_A           14   /* out: cat perch bridge, leg A (UCC27524 U10, channel A); PWM7 A */
#define PIN_FAM2_B           15   /* out: cat perch bridge, leg B (U10, channel B); PWM7 B */
#define PIN_UART_TX          16   /* out: UART0 TX to the debug connector J5 (console, 115200) */
#define PIN_UART_RX          17   /* in: UART0 RX from J5 */
#define PIN_BUTTON           18   /* in: the SPELL button, low when pressed (internal pull-up: RP2350-E9 affects only pull-downs) */
#define PIN_DRV_nSLEEP       19   /* out: all four DRV8874s: low = asleep (4.7 k pull-down keeps them asleep in reset) */
#define PIN_SDA              20   /* io: I2C0 SDA: LED drivers, IMU, light sensor, 3-axis Hall; the tree's LED driver */
#define PIN_SCL              21   /* out: I2C0 SCL */
#define PIN_DRV_nFAULT       22   /* in: all four DRV8874s' nFAULT, wired-OR, 10 k pull-up */
#define PIN_FAM_EN           23   /* out: both UCC27524s' four enables (4.7 k pull-down beats their internal pull-ups: off in reset) */
#define PIN_MUX_S0           24   /* out: 74HC4051 select bit 0 */
#define PIN_MUX_S1           25   /* out: 74HC4051 select bit 1 */
#define PIN_MUX_S2           26   /* out: 74HC4051 select bit 2 */
#define PIN_HALL             27   /* adc: ADC1: the perch's DRV5055 Hall sensor (via the tree) */
#define PIN_LEV_IPROPI       28   /* adc: ADC2: levitation coil current (DRV8874 IPROPI) */
#define PIN_MUX_OUT          29   /* adc: ADC3: the 74HC4051's output (slow signals, below) */

/* ---- the coil bridges: one PWM slice each, IN1/leg A = channel A -------------- */
#define PWM_SLICE_PEND1  3   /* GPIO6 (IN1) = A, GPIO7 (IN2) = B */
#define PWM_SLICE_PEND2  1   /* GPIO2 (IN1) = A, GPIO3 (IN2) = B */
#define PWM_SLICE_PEND3  5   /* GPIO10 (IN1) = A, GPIO11 (IN2) = B */
#define PWM_SLICE_LEV    6   /* GPIO12 (IN1) = A, GPIO13 (IN2) = B */
#define PWM_SLICE_FAM1   2   /* GPIO4 (leg A) = A, GPIO5 (leg B) = B */
#define PWM_SLICE_FAM2   7   /* GPIO14 (leg A) = A, GPIO15 (leg B) = B */
#define PWM_SLICE_AUDIO  4   /* GPIO8 = A */
#define PWM_SLICE_TICK   0   /* no PWM output: GPIO0 and GPIO1 carry THEREMIN_PITCH and IMU_INT */

/* ---- the ADC inputs ---------------------------------------------------- */
#define ADC_CH_HALL         1   /* GPIO27 */
#define ADC_CH_LEV_IPROPI   2   /* GPIO28 */
#define ADC_CH_MUX_OUT      3   /* GPIO29 */
/* the round robin (from ADC_RR_FIRST, ascending): a burst's samples in this order */
#define ADC_RR_MASK      0xeu
#define ADC_RR_FIRST     1
#define ADC_SLOT_HALL       0   /* ADC1 */
#define ADC_SLOT_LEV_IPROPI 1   /* ADC2 */
#define ADC_SLOT_MUX_OUT    2   /* ADC3 */

/* ---- the 74HC4051 (S0-S2 on PIN_MUX_S0..S2) ------------------------------ */
#define MUX_SEL_SHIFT    24
#define MUX_SEL_MASK     (7u << MUX_SEL_SHIFT)
#define MUX_CH_FAM1_ISENSE    0   /* owl perch bridge's supply current, 1 ms average, x20.6 on 0.5 R: 10.3 V/A; rises when the owl sits on it */
#define MUX_CH_VBUS_SENSE     1   /* USB VBUS through 10 k / 10 k: plugged into USB? */
#define MUX_CH_PEND3_IPROPI   2   /* pendulum coil 3 current */
#define MUX_CH_FAM2_ISENSE    3   /* cat perch bridge's supply current, 1 ms average, x20.6 on 0.5 R: 10.3 V/A; rises when the cat sits on it */
#define MUX_CH_V5_SENSE       4   /* +5V through 10 k / 10 k (5 V reads 2.5 V) */
#define MUX_CH_PEND2_IPROPI   5   /* pendulum coil 2 current */
#define MUX_CH_V12_SENSE      6   /* +12V through 100 k / 22 k (12 V reads 2.16 V) */
#define MUX_CH_PEND1_IPROPI   7   /* pendulum coil 1 current */
#define MUX_CHANNELS     8
#define VBUS_DIVIDER         0.500000f   /* sense voltage / rail: 10 k over 10 k */
#define V5_DIVIDER           0.500000f   /* sense voltage / rail: 10 k over 10 k */
#define V12_DIVIDER          0.180328f   /* sense voltage / rail: 100 k over 22 k */

/* ---- I2C0 (7-bit addresses) ------------------------------------------------- */
#define I2C_ADDR_LP5036_BASE  0x30
#define I2C_ADDR_LP5036_TREE  0x32
#define I2C_ADDR_LSM6DS3TR_C  0x6A
#define I2C_ADDR_LTR_303ALS   0x29
#define I2C_ADDR_TMAG5273A2   0x35

/* ---- what the board's own resistors hold while the RP2354A is in reset ---- */
#define BOARD_PULL_UP_MASK    ((1u << PIN_DRV_nFAULT))
#define BOARD_PULL_DOWN_MASK  ((1u << PIN_DRV_nSLEEP) | (1u << PIN_FAM_EN))
/* the pins that rely on the pad's own pull-up (pull-ups are not hit by RP2350-E9) */
#define MCU_PULL_UP_MASK      ((1u << PIN_BUTTON))

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
