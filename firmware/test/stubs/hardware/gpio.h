#pragma once
#include "../sdk_stub.h"
void gpio_init(uint pin);
void gpio_init_mask(uint32_t mask);
void gpio_set_function(uint pin, enum gpio_function f);
void gpio_set_dir(uint pin, bool out);
void gpio_set_dir_out_masked(uint32_t mask);
void gpio_put(uint pin, bool v);
void gpio_put_masked(uint32_t mask, uint32_t value);
void gpio_clr_mask(uint32_t mask);
bool gpio_get(uint pin);
void gpio_pull_up(uint pin);
void gpio_disable_pulls(uint pin);
