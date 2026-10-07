/* theremin_hw.c: see theremin_hw.h. */
#include "theremin_hw.h"
#include "board_pins.h"
#include "edge_count.pio.h"
#include "hardware/pio.h"
#include "pico/time.h"

#define PIO_T pio0
static uint32_t last_x[2], last_us[2];
static bool started;

/* the freshest count: empty the FIFO, then wait (at most 20 us: ten edges) for the next */
static bool fresh(uint sm, uint32_t *x, uint32_t *t_us)
{
    while (!pio_sm_is_rx_fifo_empty(PIO_T, sm))
        (void)pio_sm_get(PIO_T, sm);
    uint32_t t0 = time_us_32();
    while (pio_sm_is_rx_fifo_empty(PIO_T, sm))
        if (time_us_32() - t0 > 20u)
            return false;
    *x = pio_sm_get(PIO_T, sm);
    *t_us = time_us_32();
    return true;
}

void theremin_hw_init(void)
{
    uint offset = pio_add_program(PIO_T, &edge_count_program);
    edge_count_program_init(PIO_T, 0, offset, PIN_THEREMIN_PITCH);
    edge_count_program_init(PIO_T, 1, offset, PIN_THEREMIN_VOL);
    started = false;
}

bool theremin_hw_read(float *fp, float *fv)
{
    float f[2] = {0.0f, 0.0f};
    bool ok = true;
    for (uint sm = 0; sm < 2; sm++) {
        uint32_t x, t;
        if (!fresh(sm, &x, &t)) {
            ok = false;
            continue;
        }
        if (started && t != last_us[sm])
            f[sm] = (float)(last_x[sm] - x) * 1e6f / (float)(t - last_us[sm]);   /* X counts down */
        last_x[sm] = x;
        last_us[sm] = t;
    }
    *fp = f[0];
    *fv = f[1];
    bool was = started;
    started = true;
    return ok && was;
}
