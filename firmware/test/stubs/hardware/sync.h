#pragma once
#include "../sdk_stub.h"
static inline void __dmb(void) {}
void __wfi(void);
static inline uint32_t save_and_disable_interrupts(void) { return 0u; }
static inline void restore_interrupts(uint32_t s) { (void)s; }
