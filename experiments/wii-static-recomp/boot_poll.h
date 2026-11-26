#pragma once
#include "l2_adapter.h"
#ifdef SHSM_SI_EXTERNAL_DELIVERY
#include "si_external_delivery.h"
#endif

namespace nwii::runtime {
inline uint64_t bootPollChecks = 0;

inline bool experiment_boot_poll(CPUContext& context) {
    std::lock_guard<std::mutex> lock(context.cb_mutex);
    if (!context.is_running.load() || !context.pc || context.pc == 0xfffffffcu) {
        throw std::runtime_error("Idle/restore/stopped polling requires verified scheduler");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc) {
        throw std::runtime_error("Callback/dispatch/exception polling requires verified state transition");
    }
    if (context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("Pending producer state requires verified event delivery");
    }
    if (bootPollChecks >= 1000000) {
        throw std::runtime_error("Pre-service polling budget exceeded");
    }
    if (context.msr & 0x8000) {
#ifdef SHSM_SI_EXTERNAL_DELIVERY
        ++bootPollChecks;
        return experiment_si_external_entry(context);
#else
        throw std::runtime_error("Enabled interrupt polling requires verified event producers/delivery");
#endif
    }
    ++bootPollChecks;
    return false;
}
}
