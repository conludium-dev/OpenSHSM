#pragma once
#include "si_query_frontend.h"

namespace nwii::runtime {
inline uint32_t experiment_ai_clock_observe_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    try {
        return experiment_si_query_read32(context, address, instruction);
    } catch (const std::runtime_error& failure) {
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        std::ostringstream message;
        message << failure.what() << "; read instruction=" << std::hex << instruction << " address=" << address
                << " length=4 physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}
}
