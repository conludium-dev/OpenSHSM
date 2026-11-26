#pragma once
#include "exi_mask_boot.h"

namespace nwii::runtime {
inline void experiment_set_mask_pi_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x802178a4 || address != 0xcc003004 || value != 0xf0 || hw::pi_intmr.load() != 0xf0
        || context.msr != 0x2030 || memory_context(context).hid0 != 0xc200
        || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)) {
        throw std::runtime_error("Final PI mask outside verified boot profile");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("Final PI mask with pending delivery unverified");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0c003004 || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("Final PI mask BAT mapping unverified");
    }
    const auto cause = hw::pi_intsr.load();
    MMIODispatcher::get().write32(address, value);
    if (MMIODispatcher::get().read32(address) != value || hw::pi_intsr.load() != cause) {
        throw std::runtime_error("Final PI mask readback/PI mismatch");
    }
    std::cout << "PI_FINAL_BOOT_ACCEPTED instruction=802178a4 value=f0\n";
}
}
