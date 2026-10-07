/* audio.h: the theremin's voice out of GPIO14 (PWM slice 7, A).
 *
 * The PWM runs at 150 MHz / (AUDIO_PWM_TOP + 1) = 146 kHz, 10 bits, into the RC
 * filter and the NS4150B class-D amplifier (its slide switch, not the firmware, turns
 * the sound on).  Two DMA channels in a ping-pong write one level a sample into the
 * slice's compare register, paced by a DMA timer at AUDIO_SAMPLE_HZ (36.6 kHz); the
 * DMA_IRQ_0 handler (core 0) refills the finished buffer from the voice (voice.h)
 * with first-order noise shaping.  The output rises slowly to mid-scale at start-up
 * (no pop) and stays there in silence.
 */
#pragma once
#include "voice.h"

void audio_init(void);
void audio_set(float freq_hz, float amp);    /* amp 0..1 of full scale; the voice caps it */
extern voice audio_voice;
