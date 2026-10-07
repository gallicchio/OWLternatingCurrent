/* audio.c: see audio.h. */
#include "audio.h"
#include "board_pins.h"
#include "config.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pwm.h"
#include <math.h>

#define AUDIO_BUF 256
static uint32_t buf[2][AUDIO_BUF];
static int ch[2];
static float dc;                              /* rises to mid-scale at start-up */
static float shaped_err;
voice audio_voice;

static void fill(uint32_t *b)
{
    static float s[AUDIO_BUF];
    const float mid = (float)(AUDIO_PWM_TOP + 1u) / 2.0f;
    voice_render(&audio_voice, s, AUDIO_BUF);
    for (int i = 0; i < AUDIO_BUF; i++) {
        if (dc < mid)
            dc += mid / (0.3f * (float)AUDIO_SAMPLE_HZ);    /* 0 -> mid over 0.3 s */
        float x = dc + s[i] * mid + shaped_err;
        float q = floorf(x + 0.5f);
        shaped_err = x - q;
        if (q < 0.0f)
            q = 0.0f;
        if (q > (float)AUDIO_PWM_TOP)
            q = (float)AUDIO_PWM_TOP;
        b[i] = (uint32_t)q;                    /* channel A's level; B (GPIO15) is the IMU's input */
    }
}

static void dma_isr(void)
{
    for (int k = 0; k < 2; k++)
        if (dma_irqn_get_channel_status(0, (uint)ch[k])) {
            dma_irqn_acknowledge_channel(0, (uint)ch[k]);
            fill(buf[k]);
            dma_channel_set_read_addr((uint)ch[k], buf[k], false);
        }
}

void audio_init(void)
{
    voice_init(&audio_voice, (float)AUDIO_SAMPLE_HZ);
    pwm_config c = pwm_get_default_config();
    pwm_config_set_wrap(&c, AUDIO_PWM_TOP);
    pwm_config_set_clkdiv_int(&c, 1);
    pwm_init(PWM_SLICE_AUDIO, &c, true);
    pwm_set_chan_level(PWM_SLICE_AUDIO, PWM_CHAN_A, 0);
    gpio_set_function(PIN_AUDIO, GPIO_FUNC_PWM);

    int timer = dma_claim_unused_timer(true);
    dma_timer_set_fraction((uint)timer, 1, (uint16_t)((AUDIO_PWM_TOP + 1u) * AUDIO_SAMPLE_DIV));
    ch[0] = dma_claim_unused_channel(true);
    ch[1] = dma_claim_unused_channel(true);
    fill(buf[0]);
    fill(buf[1]);
    for (int k = 0; k < 2; k++) {
        dma_channel_config d = dma_channel_get_default_config((uint)ch[k]);
        channel_config_set_transfer_data_size(&d, DMA_SIZE_32);
        channel_config_set_read_increment(&d, true);
        channel_config_set_write_increment(&d, false);
        channel_config_set_dreq(&d, dma_get_timer_dreq((uint)timer));
        channel_config_set_chain_to(&d, (uint)ch[k ^ 1]);
        dma_channel_configure((uint)ch[k], &d, &pwm_hw->slice[PWM_SLICE_AUDIO].cc, buf[k], AUDIO_BUF, false);
        dma_irqn_set_channel_enabled(0, (uint)ch[k], true);
    }
    irq_set_exclusive_handler(DMA_IRQ_0, dma_isr);
    irq_set_priority(DMA_IRQ_0, PICO_DEFAULT_IRQ_PRIORITY);
    irq_set_enabled(DMA_IRQ_0, true);
    dma_channel_start((uint)ch[0]);
}

void audio_set(float freq_hz, float amp)
{
    irq_set_enabled(DMA_IRQ_0, false);      /* the refill reads the voice */
    voice_set(&audio_voice, freq_hz, amp);
    irq_set_enabled(DMA_IRQ_0, true);
}
