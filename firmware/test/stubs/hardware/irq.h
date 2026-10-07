#pragma once
#include "../sdk_stub.h"
#define PWM_IRQ_WRAP_1 9
#define DMA_IRQ_1 11
#define PICO_HIGHEST_IRQ_PRIORITY 0
void irq_set_exclusive_handler(uint num, irq_handler_t h);
void irq_set_priority(uint num, uint8_t p);
void irq_set_enabled(uint num, bool on);
