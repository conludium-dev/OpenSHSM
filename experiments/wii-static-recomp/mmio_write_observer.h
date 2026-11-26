#pragma once
#include "template_reset.h"

namespace nwii::runtime {
inline void experiment_mmio_write_observer(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    try {
        bat_memory_write32(context, address, value);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction
                << " address=" << address << " value=" << value << " length=4";
        try {
            const auto& state = bat_context(context);
            const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
            message << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        } catch (const std::runtime_error&) {
            message << " translation=unavailable";
        }
        throw std::runtime_error(message.str());
    }
}
}
