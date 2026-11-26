#include "boot_poll.h"
#define main unused_frontend_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    L2Context context;
    context.msr = 0x2030;
    context.pc = 0x8000656c;
    context.lr = 0x8000632c;
    const auto registers = context.gpr;
    assert(!experiment_boot_poll(context) && bootPollChecks == 1);
    assert(context.gpr == registers && context.pc == 0x8000656c && context.lr == 0x8000632c && context.msr == 0x2030);
    unsigned refused = 0;
    for (unsigned mode = 0; mode < 14; ++mode) {
        context.msr = mode == 0 ? 0xa030 : 0x2030;
        context.pc = mode == 1 ? 0 : mode == 2 ? 0xfffffffcu : 0x8000656c;
        context.is_running = mode != 3;
        context.in_callback = mode == 4;
        context.callback_depth = mode == 5 ? 1 : 0;
        context.dispatch_saved_ctx = mode == 6 ? 1 : 0;
        context.ext_resched_pending = mode == 7;
        context.exception_pc = mode == 8 ? 1 : 0;
        context.vblank_pending = mode == 9;
        context.dec_irq_pending = mode == 10;
        context.pending_cb_count = mode == 11 ? 1 : 0;
        if (mode == 12) {
            context.pending_callbacks.push({1, 2, 3, false});
        }
        if (mode == 13) {
            context.backup_stack.emplace();
        }
        try {
            experiment_boot_poll(context);
            return 2;
        } catch (const std::runtime_error&) {
            assert(bootPollChecks == 1 && context.gpr == registers);
            ++refused;
        }
        if (mode == 12) {
            context.pending_callbacks.pop();
        }
    }
    assert(refused == 14);
    std::cout << "BOOT_POLL_CONTRACT cleanState 14refusals PASS\n";
}
