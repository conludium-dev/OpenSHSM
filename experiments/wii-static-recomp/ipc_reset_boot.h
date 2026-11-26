#pragma once
#include "ipc_reset_fixture.h"
#include <sstream>

namespace nwii::runtime {
inline void experiment_boot_mmio_write16(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    try {
        bat_memory_write16(context, address, value);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction
                << " address=" << address << " value=" << value << " length=2";
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        message << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}

inline void experiment_boot_ipc_store(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (isolatedIpcResetFixture) {
        experiment_isolated_ipc_store(context, address, value, instruction);
        return;
    }
    experiment_ipc_reset_write(context, address, value, instruction);
    std::cout << "IPC_RESET_BOOT_ACCEPTED instruction=802175d4 address=cd000034 value=40000000\n";
}
}
