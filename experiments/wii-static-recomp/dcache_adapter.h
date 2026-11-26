#pragma once
#include "memory_frontend.h"

namespace nwii::runtime {
inline void experiment_write_hid0_dcache(CPUContext& context, uint32_t value) {
    auto& processor = memory_context(context);
    const uint32_t prior = processor.hid0;
    if ((value ^ prior) & ~0xc800u) {
        throw std::runtime_error("HID0 effects beyond verified ICE/ICFI/DCE enable unavailable");
    }
    if ((context.msr & 0x4000) || !(context.msr & 0x10)) {
        throw std::runtime_error("DCE contract requires privileged translated memory fixture");
    }
    if ((prior & 0x4000) && !(value & 0x4000)) {
        throw std::runtime_error("Data-cache disable/dirty drain requires independent verification");
    }
    if (!(prior & 0x4000) && (value & 0x4000)) {
        for (const auto& set : processor.dataLines) {
            for (const auto& line : set) {
                if (line.valid) {
                    throw std::runtime_error("DCE activation with populated cache requires verification");
                }
            }
        }
    }
    processor.hid0 = prior & ~0x4000u;
    try {
        experiment_write_hid0_icache(context, value & ~0x4000u);
    } catch (...) {
        processor.hid0 = prior;
        throw;
    }
    processor.hid0 |= value & 0x4000u;
}
}
