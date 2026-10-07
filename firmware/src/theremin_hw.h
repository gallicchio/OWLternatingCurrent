/* theremin_hw.h: the two theremin oscillators, counted by PIO0 (state machines 0 and 1). */
#pragma once
#include <stdbool.h>
#include <stdint.h>

void theremin_hw_init(void);
/* the frequencies since the last call (Hz); false if an oscillator gave no edges */
bool theremin_hw_read(float *f_pitch_hz, float *f_vol_hz);
