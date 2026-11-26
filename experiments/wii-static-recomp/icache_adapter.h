#pragma once
#include "fpscr_adapter.h"
#include <algorithm>

namespace nwii::runtime {
inline void experiment_write_hid0_icache(CPUContext& context, uint32_t value) {
    const uint32_t prior = experiment_read_hid0(context);
    if ((value ^ prior) & ~0x8800u) {
        throw std::runtime_error("HID0 effects beyond immutable instruction-cache ICE/ICFI are unavailable");
    }
    auto& processor = static_cast<ProcessorContext&>(context);
    if (processor.instructionImages.empty()) {
        throw std::runtime_error("Instruction cache image is not registered");
    }
    for (const auto& [address, image] : processor.instructionImages) {
        if (image.empty() || image.size() > UINT32_MAX || address > UINT32_MAX - (image.size() - 1)) {
            throw std::runtime_error("Invalid instruction cache image range");
        }
        auto actual = processor.mmu.get_ptr(address);
        if (!actual || !processor.mmu.get_ptr(address + image.size() - 1) || !std::equal(image.begin(), image.end(), actual)) {
            throw std::runtime_error("Modified guest code requires recompilation before instruction cache control");
        }
    }
    experiment_write_hid0(context, (value & ~0x8000u) | (prior & 0x8000u));
    processor.hid0 = (processor.hid0 & ~0x8000u) | (value & 0x8000u);
}
}
