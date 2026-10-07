/* board.c: see board.h. */
#include "board.h"
#include "board_pins.h"
#include "config.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"

void board_safe_init(void)
{
    /* the coil bridges first: plain outputs, low */
    gpio_init_mask(BRIDGE_PIN_MASK);
    gpio_clr_mask(BRIDGE_PIN_MASK);
    gpio_set_dir_out_masked(BRIDGE_PIN_MASK);
    /* the DRV8874s asleep, the UCC27524s disabled */
    gpio_init(PIN_DRV_nSLEEP);
    gpio_put(PIN_DRV_nSLEEP, 0);
    gpio_set_dir(PIN_DRV_nSLEEP, GPIO_OUT);
    gpio_init(PIN_FAM_EN);
    gpio_put(PIN_FAM_EN, 0);
    gpio_set_dir(PIN_FAM_EN, GPIO_OUT);
    /* the audio output low until the audio starts (no pop) */
    gpio_init(PIN_AUDIO);
    gpio_put(PIN_AUDIO, 0);
    gpio_set_dir(PIN_AUDIO, GPIO_OUT);
    /* the multiplexer on channel 0 */
    gpio_init_mask(MUX_SEL_MASK);
    gpio_clr_mask(MUX_SEL_MASK);
    gpio_set_dir_out_masked(MUX_SEL_MASK);
    /* inputs: the board's pull-ups hold nFAULT and the button; the IMU and the
     * theremin oscillators drive theirs */
    gpio_init(PIN_DRV_nFAULT);
    gpio_set_dir(PIN_DRV_nFAULT, GPIO_IN);
    gpio_pull_up(PIN_DRV_nFAULT);       /* belt and braces: pull-ups are not hit by E9 */
    gpio_init(PIN_BUTTON);
    gpio_set_dir(PIN_BUTTON, GPIO_IN);
    for (unsigned pin = 0; pin < 32; pin++)
        if (MCU_PULL_UP_MASK & (1u << pin))
            gpio_pull_up(pin);          /* gen/pins.py: "internal pull-up" (the SPELL button) */
    gpio_init(PIN_IMU_INT);
    gpio_set_dir(PIN_IMU_INT, GPIO_IN);
    gpio_disable_pulls(PIN_IMU_INT);
    gpio_init(PIN_THEREMIN_PITCH);
    gpio_set_dir(PIN_THEREMIN_PITCH, GPIO_IN);
    gpio_disable_pulls(PIN_THEREMIN_PITCH);
    gpio_init(PIN_THEREMIN_VOL);
    gpio_set_dir(PIN_THEREMIN_VOL, GPIO_IN);
    gpio_disable_pulls(PIN_THEREMIN_VOL);
    /* the analogue inputs: digital input off, no pulls */
    adc_init();
    adc_gpio_init(PIN_HALL);
    adc_gpio_init(PIN_LEV_IPROPI);
    adc_gpio_init(PIN_MUX_OUT);
}

void board_bridges_off(void)
{
    /* the pins back to plain outputs driven low, whatever PWM was doing */
    gpio_clr_mask(BRIDGE_PIN_MASK);
    for (unsigned pin = 0; pin < 32; pin++)
        if (BRIDGE_PIN_MASK & (1u << pin))
            gpio_set_function(pin, GPIO_FUNC_SIO);
    gpio_set_dir_out_masked(BRIDGE_PIN_MASK);
    gpio_put(PIN_DRV_nSLEEP, 0);
    gpio_put(PIN_FAM_EN, 0);
}

void board_drv_sleep(bool asleep) { gpio_put(PIN_DRV_nSLEEP, !asleep); }

bool board_drv_fault(void) { return !gpio_get(PIN_DRV_nFAULT); }

void board_fam_enable(bool on) { gpio_put(PIN_FAM_EN, on); }

bool board_button(void) { return !gpio_get(PIN_BUTTON); }

void board_mux_select(unsigned ch) { gpio_put_masked(MUX_SEL_MASK, (ch & 7u) << MUX_SEL_SHIFT); }
