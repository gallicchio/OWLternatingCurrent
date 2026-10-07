#pragma once
#include "../sdk_stub.h"
typedef struct {
    bool phase_correct, inv_a, inv_b;
    uint16_t top;
} pwm_config;
pwm_config pwm_get_default_config(void);
void pwm_config_set_phase_correct(pwm_config *c, bool on);
void pwm_config_set_clkdiv_int(pwm_config *c, uint32_t div);
void pwm_config_set_wrap(pwm_config *c, uint16_t wrap);
void pwm_config_set_output_polarity(pwm_config *c, bool a, bool b);
void pwm_init(uint slice, pwm_config *c, bool start);
void pwm_set_both_levels(uint slice, uint16_t a, uint16_t b);
void pwm_set_wrap(uint slice, uint16_t wrap);
void pwm_set_counter(uint slice, uint16_t c);
void pwm_set_enabled(uint slice, bool on);
void pwm_set_mask_enabled(uint32_t mask);
void pwm_clear_irq(uint slice);
void pwm_irqn_set_slice_enabled(uint irq_index, uint slice, bool on);
/* the atomic set / clear aliases (hardware/address_mapped.h) */
static inline void hw_set_bits(volatile uint32_t *addr, uint32_t mask) { *addr |= mask; }
static inline void hw_clear_bits(volatile uint32_t *addr, uint32_t mask) { *addr &= ~mask; }
