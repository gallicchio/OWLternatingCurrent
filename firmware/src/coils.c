/* coils.c: see coils.h. */
#include "coils.h"
#include "board.h"
#include "board_pins.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include <math.h>

static const uint8_t SLICE[COIL_COUNT] = {PWM_SLICE_PEND1, PWM_SLICE_PEND2, PWM_SLICE_PEND3, PWM_SLICE_LEV};
static const uint8_t PIN_A[COIL_COUNT] = {PIN_PEND1_IN1, PIN_PEND2_IN1, PIN_PEND3_IN1, PIN_LEV_IN1};
static const uint8_t PIN_B[COIL_COUNT] = {PIN_PEND1_IN2, PIN_PEND2_IN2, PIN_PEND3_IN2, PIN_LEV_IN2};
static uint16_t top[COIL_COUNT];

static void slice_setup(unsigned slice, uint16_t wrap)
{
    pwm_config c = pwm_get_default_config();
    pwm_config_set_phase_correct(&c, true);
    pwm_config_set_clkdiv_int(&c, 1);
    pwm_config_set_wrap(&c, wrap);
    pwm_config_set_output_polarity(&c, false, true);      /* B (IN2 / leg B) inverted */
    pwm_init(slice, &c, false);
}

void coils_init(void)
{
    for (int c = 0; c < COIL_COUNT; c++) {
        top[c] = (uint16_t)(c == COIL_LEV ? TOP_LEV : TOP_PEND);
        slice_setup(SLICE[c], top[c]);
        coil_coast(c);
    }
    uint32_t mask = 0;
    for (int c = 0; c < COIL_COUNT; c++)
        mask |= 1u << SLICE[c];
    pwm_set_mask_enabled(pwm_hw->en | mask);              /* running, outputs still plain pins */
}

void coils_connect(bool on)
{
    for (int c = 0; c < COIL_COUNT; c++) {
        coil_coast(c);
        if (on) {
            gpio_set_function(PIN_A[c], GPIO_FUNC_PWM);
            gpio_set_function(PIN_B[c], GPIO_FUNC_PWM);
        } else {
            gpio_put(PIN_A[c], 0);
            gpio_put(PIN_B[c], 0);
            gpio_set_function(PIN_A[c], GPIO_FUNC_SIO);
            gpio_set_function(PIN_B[c], GPIO_FUNC_SIO);
            gpio_set_dir(PIN_A[c], GPIO_OUT);
            gpio_set_dir(PIN_B[c], GPIO_OUT);
        }
    }
}

uint16_t coil_top(int coil) { return top[coil]; }

float coil_pwm_hz(int coil) { return (float)SYS_CLK_HZ / (2.0f * (float)(top[coil] + 1u)); }

void coil_coast(int coil)
{
    /* IN1 never high (ccA = 0); IN2 never high (B inverted, ccB = P) */
    pwm_set_both_levels(SLICE[coil], 0, (uint16_t)(top[coil] + 1u));
}

void coil_set_fractions(int coil, float f_fwd, float f_rev)
{
    if (!(f_fwd > 0.0f))
        f_fwd = 0.0f;
    if (!(f_rev > 0.0f))
        f_rev = 0.0f;
    float s = f_fwd + f_rev;
    if (s > 1.0f) {
        f_fwd /= s;
        f_rev /= s;
    }
    uint32_t P = top[coil] + 1u;
    uint32_t ccB = (uint32_t)lroundf(f_fwd * (float)P);
    uint32_t ccA = P - (uint32_t)lroundf(f_rev * (float)P);
    if (ccB > ccA)
        ccB = ccA;
    pwm_set_both_levels(SLICE[coil], (uint16_t)ccA, (uint16_t)ccB);
}

void coil_set_u(int coil, float u, float min_alt)
{
    if (!(min_alt > 0.0f))
        min_alt = 0.0f;
    if (min_alt > 0.5f)
        min_alt = 0.5f;
    float lim = 1.0f - 2.0f * min_alt;
    if (!(u == u))
        u = 0.0f;                                         /* NaN: nothing */
    if (u > lim)
        u = lim;
    if (u < -lim)
        u = -lim;
    coil_set_fractions(coil, (u > 0.0f ? u : 0.0f) + min_alt, (u < 0.0f ? -u : 0.0f) + min_alt);
}

void coil_lev_frequency(bool carrier)
{
    top[COIL_LEV] = (uint16_t)(carrier ? TOP_CARRIER : TOP_LEV);
    pwm_set_wrap(SLICE[COIL_LEV], top[COIL_LEV]);         /* latched at its next wrap */
}

/* ---- the familiar perches ----------------------------------------------------------- */
static const uint8_t FSLICE[2] = {PWM_SLICE_FAM1, PWM_SLICE_FAM2};
static const uint8_t FPIN_A[2] = {PIN_FAM1_A, PIN_FAM2_A};
static const uint8_t FPIN_B[2] = {PIN_FAM1_B, PIN_FAM2_B};
static float ffreq[2], fduty[2];
static bool fon[2];

void perch_init(void)
{
    for (int p = 0; p < 2; p++) {
        slice_setup(FSLICE[p], 749);
        pwm_set_both_levels(FSLICE[p], 0, 750);           /* both legs low */
        pwm_set_enabled(FSLICE[p], true);
        fon[p] = false;
    }
}

float perch_set(int perch, bool on, float freq_hz, float duty)
{
    if (perch < 0 || perch > 1)
        return 0.0f;
    unsigned s = FSLICE[perch];
    if (!on || !(freq_hz > 0.0f)) {
        uint16_t t = (uint16_t)pwm_hw->slice[s].top;
        pwm_set_both_levels(s, 0, (uint16_t)(t + 1u));
        fon[perch] = false;
        fduty[perch] = 0.0f;
        if (!fon[0] && !fon[1])
            board_fam_enable(false);
        return ffreq[perch];
    }
    if (freq_hz < FAM_F_MIN_HZ * 0.9f)
        freq_hz = FAM_F_MIN_HZ * 0.9f;
    if (freq_hz > FAM_F_MAX_HZ * 1.1f)
        freq_hz = FAM_F_MAX_HZ * 1.1f;
    uint32_t P = (uint32_t)lroundf((float)SYS_CLK_HZ / (2.0f * freq_hz));
    if (!(duty > 0.0f))
        duty = 0.0f;
    if (duty > 0.5f)
        duty = 0.5f;
    uint32_t cc = (uint32_t)lroundf(duty * (float)P);
    pwm_set_wrap(s, (uint16_t)(P - 1u));
    pwm_set_both_levels(s, (uint16_t)cc, (uint16_t)(P - cc));
    if (!fon[perch]) {
        gpio_set_function(FPIN_A[perch], GPIO_FUNC_PWM);
        gpio_set_function(FPIN_B[perch], GPIO_FUNC_PWM);
        fon[perch] = true;
        board_fam_enable(true);
    }
    ffreq[perch] = (float)SYS_CLK_HZ / (2.0f * (float)P);
    fduty[perch] = (float)cc / (float)P;
    return ffreq[perch];
}

float perch_freq(int perch) { return ffreq[perch & 1]; }
float perch_duty(int perch) { return fduty[perch & 1]; }
bool perch_on(int perch) { return fon[perch & 1]; }
