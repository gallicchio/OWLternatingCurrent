/* sdk_stub.h: the little of the Pico SDK that src/rt.c, src/coils.c and src/board.c
 * use, modelled for test/test_rt.c: GPIO levels and functions, PWM slices' registers,
 * the ADC and one DMA channel, interrupt handlers, a clock the test advances. */
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef unsigned int uint;

/* GPIO */
enum { GPIO_IN = 0, GPIO_OUT = 1 };
enum gpio_function { GPIO_FUNC_SIO = 5, GPIO_FUNC_PIO0 = 6, GPIO_FUNC_PWM = 4, GPIO_FUNC_I2C = 3,
                     GPIO_FUNC_UART = 2, GPIO_FUNC_NULL = 0x1f };
extern int stub_gpio_func[32];
extern bool stub_gpio_out[32], stub_gpio_oe[32], stub_gpio_in[32];

/* PWM */
typedef struct {
    volatile uint32_t csr, div, ctr, cc, top;
} pwm_slice_hw_t;
typedef struct {
    pwm_slice_hw_t slice[12];
    volatile uint32_t en, intr, inte0, intf0, ints0, inte1, intf1, ints1;
} pwm_hw_t;
extern pwm_hw_t stub_pwm;
#define pwm_hw (&stub_pwm)
extern bool stub_pwm_phase_correct[12], stub_pwm_inv_a[12], stub_pwm_inv_b[12];

/* ADC */
typedef struct {
    volatile uint32_t cs, result, fcs, fifo, div, intr, inte, intf, ints;
} adc_hw_t;
extern adc_hw_t stub_adc;
#define adc_hw (&stub_adc)
extern bool stub_adc_running;
extern int stub_drain_while_running;

/* DMA (one channel is enough) */
extern uint16_t *stub_dma_dest;
extern unsigned stub_dma_count;
extern bool stub_dma_busy;
extern bool stub_dma_irq_pending;

/* interrupts */
typedef void (*irq_handler_t)(void);
extern irq_handler_t stub_irq_handler[64];

/* time */
extern uint64_t stub_now_us;          /* 64-bit, as the RP2350 timer; time_us_32 is its low word */
