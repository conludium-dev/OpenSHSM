#pragma once
#include "exi_getid_frontend.h"

namespace nwii::runtime {
inline uint16_t experiment_uart_next_read16(CPUContext& context, uint32_t address, uint32_t instruction) {
    try {
        return bat_memory_read16(context, address);
    } catch (const std::runtime_error& failure) {
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction << " address=" << address
                << " length=2 read physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}
}
