/* sdk_stub.c: the modelled SDK for test/test_rt.c (see sdk_stub.h). */
#include "sdk_stub.h"
#include "hardware/adc.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include <setjmp.h>
#include <string.h>

int stub_gpio_func[32];
bool stub_gpio_out[32], stub_gpio_oe[32], stub_gpio_in[32];
pwm_hw_t stub_pwm;
bool stub_pwm_phase_correct[12], stub_pwm_inv_a[12], stub_pwm_inv_b[12];
adc_hw_t stub_adc;
bool stub_adc_running;
uint16_t *stub_dma_dest;
unsigned stub_dma_count;
bool stub_dma_busy;
irq_handler_t stub_irq_handler[64];
uint32_t stub_now_us;

/* GPIO: a pin's level is its output when driven, else what the test puts on it */
void gpio_init(uint p) { stub_gpio_func[p] = GPIO_FUNC_SIO; stub_gpio_oe[p] = false; stub_gpio_out[p] = false; }
void gpio_init_mask(uint32_t m) { for (uint p = 0; p < 32; p++) if (m & (1u << p)) gpio_init(p); }
void gpio_set_function(uint p, enum gpio_function f) { stub_gpio_func[p] = (int)f; }
void gpio_set_dir(uint p, bool out) { stub_gpio_oe[p] = out; }
void gpio_set_dir_out_masked(uint32_t m) { for (uint p = 0; p < 32; p++) if (m & (1u << p)) stub_gpio_oe[p] = true; }
void gpio_put(uint p, bool v) { stub_gpio_out[p] = v; }
void gpio_put_masked(uint32_t m, uint32_t v) { for (uint p = 0; p < 32; p++) if (m & (1u << p)) stub_gpio_out[p] = (v >> p) & 1u; }
void gpio_clr_mask(uint32_t m) { for (uint p = 0; p < 32; p++) if (m & (1u << p)) stub_gpio_out[p] = false; }
bool gpio_get(uint p) { return stub_gpio_oe[p] ? stub_gpio_out[p] : stub_gpio_in[p]; }
void gpio_pull_up(uint p) { (void)p; }
void gpio_disable_pulls(uint p) { (void)p; }

/* ADC */
void adc_init(void) {}
void adc_gpio_init(uint p) { stub_gpio_func[p] = GPIO_FUNC_NULL; }
void adc_select_input(uint i) { (void)i; }
void adc_set_round_robin(uint m) { (void)m; }
void adc_fifo_setup(bool a, bool b, uint16_t c, bool d, bool e) { (void)a; (void)b; (void)c; (void)d; (void)e; }
void adc_set_clkdiv(float d) { (void)d; }
void adc_run(bool r) { stub_adc_running = r; }
void adc_fifo_drain(void) {}

/* DMA */
int dma_claim_unused_channel(bool r) { (void)r; return 3; }
dma_channel_config dma_channel_get_default_config(uint ch) { (void)ch; return (dma_channel_config){0}; }
void channel_config_set_transfer_data_size(dma_channel_config *c, enum dma_channel_transfer_size s) { (void)c; (void)s; }
void channel_config_set_read_increment(dma_channel_config *c, bool i) { (void)c; (void)i; }
void channel_config_set_write_increment(dma_channel_config *c, bool i) { (void)c; (void)i; }
void channel_config_set_dreq(dma_channel_config *c, uint d) { (void)c; (void)d; }
void dma_channel_configure(uint ch, const dma_channel_config *c, volatile void *w, const volatile void *r, uint n, bool t)
{
    (void)ch; (void)c; (void)r; (void)t;
    stub_dma_dest = (uint16_t *)w;
    stub_dma_count = n;
}
void dma_irqn_set_channel_enabled(uint i, uint ch, bool e) { (void)i; (void)ch; (void)e; }
void dma_irqn_acknowledge_channel(uint i, uint ch) { (void)i; (void)ch; }
bool dma_channel_is_busy(uint ch) { (void)ch; return stub_dma_busy; }
void dma_channel_transfer_to_buffer_now(uint ch, volatile void *dst, uint32_t n)
{
    (void)ch;
    stub_dma_dest = (uint16_t *)dst;
    stub_dma_count = n;
    stub_dma_busy = true;
}

/* interrupts */
void irq_set_exclusive_handler(uint n, irq_handler_t h) { stub_irq_handler[n] = h; }
void irq_set_priority(uint n, uint8_t p) { (void)n; (void)p; }
void irq_set_enabled(uint n, bool on) { (void)n; (void)on; }

/* PWM: the registers, as the slices hold them */
pwm_config pwm_get_default_config(void) { return (pwm_config){false, false, false, 0xffff}; }
void pwm_config_set_phase_correct(pwm_config *c, bool on) { c->phase_correct = on; }
void pwm_config_set_clkdiv_int(pwm_config *c, uint32_t d) { (void)c; (void)d; }
void pwm_config_set_wrap(pwm_config *c, uint16_t w) { c->top = w; }
void pwm_config_set_output_polarity(pwm_config *c, bool a, bool b) { c->inv_a = a; c->inv_b = b; }
void pwm_init(uint s, pwm_config *c, bool start)
{
    stub_pwm_phase_correct[s] = c->phase_correct;
    stub_pwm_inv_a[s] = c->inv_a;
    stub_pwm_inv_b[s] = c->inv_b;
    stub_pwm.slice[s].top = c->top;
    stub_pwm.slice[s].cc = 0;
    stub_pwm.slice[s].ctr = 0;
    if (start)
        stub_pwm.en |= 1u << s;
    else
        stub_pwm.en &= ~(1u << s);
}
void pwm_set_both_levels(uint s, uint16_t a, uint16_t b) { stub_pwm.slice[s].cc = (uint32_t)a | (uint32_t)b << 16; }
void pwm_set_wrap(uint s, uint16_t w) { stub_pwm.slice[s].top = w; }
void pwm_set_counter(uint s, uint16_t c) { stub_pwm.slice[s].ctr = c; }
void pwm_set_enabled(uint s, bool on) { if (on) stub_pwm.en |= 1u << s; else stub_pwm.en &= ~(1u << s); }
void pwm_set_mask_enabled(uint32_t m) { stub_pwm.en = m; }
void pwm_clear_irq(uint s) { stub_pwm.intr &= ~(1u << s); }
void pwm_irqn_set_slice_enabled(uint i, uint s, bool on) { (void)i; (void)s; (void)on; }

/* core 1: run its set-up, and come back when it settles into waiting for interrupts */
static jmp_buf core1_waiting;
void __wfi(void) { longjmp(core1_waiting, 1); }
void multicore_launch_core1(void (*entry)(void))
{
    if (!setjmp(core1_waiting))
        entry();
}
