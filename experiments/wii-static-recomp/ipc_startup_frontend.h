#pragma once
namespace nwii::runtime {
inline bool experimentIpcStartup = false;
inline unsigned experimentIpcStartupWrites = 0;
inline void experiment_ipc_startup_store(CPUContext& context, uint32_t address, uint32_t value) {
    if (address != 0xcd000004) {
        bat_memory_write32(context, address, value);
        return;
    }
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, true);
    const auto before = hw::experiment_ipc_snapshot();
    if (!experimentIpcStartup || context.pc != 0x80241c30 || context.lr != 0x80242140 || context.msr != 0xa032 ||
        memory_context(context).hid0 != 0xc200 || mapping.physical != 0x0d000004 || mapping.slot != 1 || mapping.wimg != 5 ||
        value != 0x38 || before.ppcMessage || before.armMessage || before.ppcControl || before.armControl ||
        before.ppcMask != 0x40000000 || before.delay || (hw::pi_intsr.load() & ~0x10000u) || hw::pi_intmr.load() != 0x40f8 ||
        context.in_callback || context.callback_depth || !context.backup_stack.empty() || context.dispatch_saved_ctx ||
        context.ext_resched_pending || context.exception_pc || context.vblank_pending.load() || context.dec_irq_pending ||
        context.pending_cb_count.load() || !context.pending_callbacks.empty()) {
        throw std::runtime_error("Cold IPC client control write profile unverified");
    }
    hw::experiment_ipc_control_no_request(value);
    ++experimentIpcStartupWrites;
}
}
