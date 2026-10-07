#pragma once
#include "../sdk_stub.h"
enum dma_channel_transfer_size { DMA_SIZE_8 = 0, DMA_SIZE_16 = 1, DMA_SIZE_32 = 2 };
typedef struct {
    uint32_t ctrl;
} dma_channel_config;
#define DREQ_ADC 48
int dma_claim_unused_channel(bool required);
dma_channel_config dma_channel_get_default_config(uint ch);
void channel_config_set_transfer_data_size(dma_channel_config *c, enum dma_channel_transfer_size s);
void channel_config_set_read_increment(dma_channel_config *c, bool inc);
void channel_config_set_write_increment(dma_channel_config *c, bool inc);
void channel_config_set_dreq(dma_channel_config *c, uint dreq);
void dma_channel_configure(uint ch, const dma_channel_config *c, volatile void *write, const volatile void *read,
                           uint count, bool trigger);
void dma_irqn_set_channel_enabled(uint irq_index, uint ch, bool enabled);
void dma_irqn_acknowledge_channel(uint irq_index, uint ch);
bool dma_channel_is_busy(uint ch);
void dma_channel_transfer_to_buffer_now(uint ch, volatile void *dst, uint32_t count);
