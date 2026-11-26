#pragma once
#include "runtime/cpu_context.h"

namespace nwii::runtime {
struct ProcessorContext : CPUContext {
    uint32_t hid2 = 0;
    uint32_t hid0 = 0;
    uint64_t instructionCacheInvalidations = 0;
    std::vector<std::pair<uint32_t, std::vector<uint8_t>>> instructionImages;
};

uint32_t experiment_read_hid2(CPUContext& context);
void experiment_write_hid2(CPUContext& context, uint32_t value);
uint32_t experiment_read_hid0(CPUContext& context);
void experiment_write_hid0(CPUContext& context, uint32_t value);
}
