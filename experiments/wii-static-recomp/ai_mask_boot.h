#pragma once
#include "dsp_mask_boot.h"
#include "ai_mask_backend.h"

namespace nwii::runtime {
inline void experiment_ai_boot_guard(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (address != 0xcd006c00 || (instruction != 0x80217734 && instruction != 0x80217750)
        || context.msr != 0x2030 || memory_context(context).hid0 != 0xc200
        || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)) {
        throw std::runtime_error("AI mask outside verified boot profile");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("AI mask with pending delivery unverified");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0d006c00 || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("AI mask BAT mapping unverified");
    }
}

inline uint32_t experiment_ai_boot_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    experiment_ai_boot_guard(context, address, instruction);
    static const bool registered = [] {
        hw::experiment_register_ai_mask(MMIODispatcher::get());
        return true;
    }();
    (void)registered;
    const auto value = MMIODispatcher::get().read32(address);
    if (value != 0x42) {
        throw std::runtime_error("AI boot loader state unverified");
    }
    std::cout << "AI_MASK_BOOT_READ_ACCEPTED value=42 loader-seed\n";
    return value;
}

inline void experiment_ai_boot_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    experiment_ai_boot_guard(context, address, instruction);
    const auto cause = hw::pi_intsr.load();
    MMIODispatcher::get().write32(address, value);
    if (MMIODispatcher::get().read32(address) != value || hw::pi_intsr.load() != cause) {
        throw std::runtime_error("AI boot mask readback/PI mismatch");
    }
    std::cout << "AI_MASK_BOOT_WRITE_ACCEPTED value=" << std::hex << value << std::dec << '\n';
}
}
