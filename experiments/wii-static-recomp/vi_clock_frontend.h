#pragma once
#include "exi_getid_frontend.h"

namespace nwii::runtime {
inline void experiment_vi_next_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    try {
        experiment_getid_write32(context, address, value);
    } catch (const std::runtime_error& failure) {
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, true);
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction << " address=" << address
                << " length=4 write value=" << value << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}

inline uint16_t experiment_uart_next_read16(CPUContext& context, uint32_t address, uint32_t instruction) {
    try {
        if (address == 0xcc00206c && instruction == 0x80210620) {
            const auto& state = bat_context(context);
            const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
            if (context.msr != 0x2030 || mapping.physical != 0x0c00206c || mapping.wimg != 5 || mapping.slot != 1) {
                throw std::runtime_error("VI clock read outside measured mapping profile");
            }
            const auto value = MMIODispatcher::get().read16(address);
            if (value != 1) {
                throw std::runtime_error("VI clock backend differs from measured loader profile");
            }
            std::cout << "VI_CLOCK_PROVEN_READ instruction=80210620 address=cc00206c value=1\n";
            return value;
        }
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
