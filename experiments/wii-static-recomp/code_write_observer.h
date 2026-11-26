#pragma once
#include "spd_adapter.h"
#include "ni_guard.h"
#include <sstream>

namespace nwii::runtime {
inline void experiment_observed_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    try {
        bat_memory_write32(context, address, value);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; write instruction=" << std::hex << instruction
                << " address=" << address << " value=" << value << " length=4";
        throw std::runtime_error(message.str());
    }
}
}
