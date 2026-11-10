#pragma once
#include "../sdk_stub.h"
static inline uint32_t time_us_32(void) { return (uint32_t)stub_now_us; }
static inline uint64_t time_us_64(void) { return stub_now_us; }
