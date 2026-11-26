#include "processor_adapter.h"
#include <cstring>
#include <stdexcept>

namespace nwii::runtime {
uint32_t experiment_read_dma(CPUContext& context, unsigned spr) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged locked-cache DMA access is unavailable in user mode");
    }
    auto& processor = static_cast<ProcessorContext&>(context);
    if (spr == 922) {
        return processor.dma_u;
    }
    if (spr == 923) {
        return processor.dma_l;
    }
    throw std::runtime_error("Invalid locked-cache DMA register");
}

void experiment_write_dma(CPUContext& context, unsigned spr, uint32_t value) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged locked-cache DMA access is unavailable in user mode");
    }
    auto& processor = static_cast<ProcessorContext&>(context);
    if (spr == 922) {
        processor.dma_u = value;
        return;
    }
    if (spr != 923 || (value & 1)) {
        throw std::runtime_error("Invalid DMA register or unsupported DMA queue flush");
    }
    if (!(value & 2)) {
        processor.dma_l = value;
        return;
    }
    if (!(processor.hid2 & 0x10000000)) {
        throw std::runtime_error("Locked-cache DMA requires original LCE initialization");
    }
    unsigned blocks = ((processor.dma_u & 31) << 2) | ((value >> 2) & 3);
    if (blocks == 0) {
        blocks = 128;
    }
    const uint32_t length = blocks * 32;
    const uint32_t memory_address = processor.dma_u & 0xFFFFFFE0;
    const uint32_t physical = memory_address & 0x3FFFFFFF;
    const uint32_t cache_offset = value & 0x3FFE0;
    const bool ram = (physical < 0x01800000 && length <= 0x01800000 - physical)
        || (physical >= 0x10000000 && physical < 0x14000000 && length <= 0x14000000 - physical);
    if (!ram || cache_offset > 0x40000 - length) {
        throw std::runtime_error("Locked-cache DMA outside supported RAM/cache range");
    }
    uint8_t* memory = context.mmu.get_ptr(memory_address);
    uint8_t* cache = context.mmu.get_ptr(0xE0000000 + cache_offset);
    if (!memory || !cache) {
        throw std::runtime_error("Locked-cache DMA backing memory is unavailable");
    }
    if (value & 0x10) {
        std::memcpy(cache, memory, length);
    } else {
        std::memcpy(memory, cache, length);
    }
    processor.dma_l = value & ~2u;
}
}
