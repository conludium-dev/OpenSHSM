#pragma once
#include "bat_memory_frontend.h"

namespace nwii::runtime {
inline void experiment_write_hid0_spd(CPUContext& context, uint32_t value) {
    auto& state = memory_context(context);
    const uint32_t prior = state.hid0;
    state.hid0 = prior & ~0x200u;
    try {
        experiment_write_hid0_dcache(context, value & ~0x200u);
    } catch (...) {
        state.hid0 = prior;
        throw;
    }
    state.hid0 |= value & 0x200u;
}
}
