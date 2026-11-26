#pragma once
#include "reset_code_frontend.h"
namespace nwii::runtime {
inline bool experimentDcZero = false;
inline uint64_t experimentDcZeroLines = 0;
inline void experiment_dcbz_line(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (!experimentDcZero || instruction != 0x8021307c || context.msr != 0x2032 || memory_context(context).hid0 != 0xc200) {
        throw std::runtime_error("DCZeroRange cached dcbz profile unverified");
    }
    const auto mapping = bat_memory_range(context, address & ~31u, 32);
    if (mapping.wimg != 0 || !bat_memory_cached(context, mapping)) {
        throw std::runtime_error("DCZeroRange uncached/write-through dcbz unverified");
    }
    for (const auto& [start, image] : memory_context(context).instructionImages) {
        const uint32_t code = start & 0x3fffffffu;
        if (uint64_t(mapping.physical) < uint64_t(code) + image.size() && uint64_t(mapping.physical) + 32 > code) {
            throw std::runtime_error("DCZeroRange compiled-code zeroing forbidden");
        }
    }
    auto line = memory_line(context, mapping.physical, true);
    line->bytes.fill(0);
    line->dirty = true;
    ++experimentDcZeroLines;
}
}
