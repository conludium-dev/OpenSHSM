#pragma once
#include "ipc_reset_boot.h"
#include "mi_mask_backend.h"

namespace nwii::runtime {
inline uint16_t experiment_mi_boot_read16(CPUContext& context, uint32_t address, uint32_t instruction) {
    try {
        return bat_memory_read16(context, address);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction
                << " address=" << address << " length=2 read";
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        message << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}

inline void experiment_mi_mask_boot_write16(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    if (instruction != 0x802176e4 || address != 0xcc00401c || value || context.msr != 0x2030
        || memory_context(context).hid0 != 0xc200 || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)) {
        std::ostringstream message;
        message << "MI mask write outside verified reset-only boot profile; PI=" << std::hex << hw::pi_intsr.load()
                << " MSR=" << context.msr << " HID0=" << memory_context(context).hid0;
        throw std::runtime_error(message.str());
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("MI mask with pending delivery unverified");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0c00401c || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("MI mask BAT mapping unverified");
    }
    static const bool registered = [] {
        hw::experiment_register_mi_mask(MMIODispatcher::get());
        return true;
    }();
    (void)registered;
    MMIODispatcher::get().write16(address, value);
    if (MMIODispatcher::get().read16(address) != value) {
        throw std::runtime_error("MI mask backend failed readback");
    }
    std::cout << "MI_MASK_BOOT_ACCEPTED instruction=802176e4 address=cc00401c value=0\n";
}
}
