#pragma once
#include "pi_mask_adapter.h"
#include "ipc_reset_backend.h"

namespace nwii::runtime {
inline void experiment_ipc_reset_write(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x802175d4u || address != 0xcd000034u || value != 0x40000000u ||
        context.msr != 0x2030u || memory_context(context).hid0 != 0xc200u) {
        throw std::runtime_error("IPC reset outside verified caller/value/EE0 profile");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0d000034u || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("IPC reset outside verified uncached BAT mapping");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty() ||
        context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc ||
        context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load() ||
        !context.pending_callbacks.empty()) {
        throw std::runtime_error("IPC reset with pending delivery requires verified event ordering");
    }
    hw::experiment_ipc_quiescent_mask(value);
}
}
