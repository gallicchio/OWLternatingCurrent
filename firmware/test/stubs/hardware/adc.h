#pragma once
#include "../sdk_stub.h"
void adc_init(void);
void adc_gpio_init(uint pin);
void adc_select_input(uint input);
void adc_set_round_robin(uint mask);
void adc_fifo_setup(bool en, bool dreq_en, uint16_t dreq_thresh, bool err_in_fifo, bool byte_shift);
void adc_set_clkdiv(float div);
void adc_run(bool run);
void adc_fifo_drain(void);
