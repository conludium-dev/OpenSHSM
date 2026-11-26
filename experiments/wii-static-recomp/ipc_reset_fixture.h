#pragma once
#include "ipc_reset_adapter.h"

namespace nwii::runtime {
inline bool isolatedIpcResetFixture = false;
inline void experiment_isolated_ipc_store(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (!isolatedIpcResetFixture) {
        experiment_mmio_write_observer(context, address, value, instruction);
        return;
    }
    experiment_ipc_reset_write(context, address, value, instruction);
    throw std::runtime_error("Isolated IPC reset fixture exit after original store");
}
}
