#include "ipc_reset_backend.h"
#include "ipc_reset_adapter.h"
#include "loader-bat-seed.h"
#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <iostream>
#include <stdexcept>

int main() {
    using namespace nwii::runtime;
    hw::register_pi(MMIODispatcher::get());
    hw::register_ipc(MMIODispatcher::get());
    const uint32_t values[] = {0, 0x40000000, 0x80000000, 0xffffffff};
    for (unsigned index = 0; index < 32; ++index) {
        auto& dispatcher = MMIODispatcher::get();
        hw::experiment_ipc_quiescent_mask(0);
        dispatcher.write32(0xcd000004, ((index & 3) << 4) | 6);
        const auto before = hw::experiment_ipc_snapshot();
        hw::experiment_ipc_quiescent_mask(values[(index & 15) / 4]);
        const auto after = hw::experiment_ipc_snapshot();
        std::cout << "IPC_RESET_CASE " << index << ' ' << before.ppcControl << ' ' << after.ppcControl
                  << ' ' << before.armMessage << ' ' << after.armMessage << ' ' << after.ppcMask << '\n';
    }
    SeededBatContext context;
    context.msr = 0x2030;
    context.hid0 = 0xc200;
    for (unsigned index = 0; index < 8; ++index) {
        context.fpscr = index >= 4 ? 4 : 0;
        MMIODispatcher::get().write32(0xcd000004, (index & 3) << 4);
        experiment_ipc_reset_write(context, 0xcd000034, 0x40000000, 0x802175d4);
        if (hw::experiment_ipc_snapshot().ppcControl || context.fpscr != (index >= 4 ? 4u : 0u)) {
            return 10;
        }
    }
    unsigned guards = 0;
    auto refused = [&](uint32_t address, uint32_t value, uint32_t instruction) {
        const auto prior = hw::experiment_ipc_snapshot();
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto fpscr = context.fpscr;
        bool rejected = false;
        try {
            experiment_ipc_reset_write(context, address, value, instruction);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        const auto next = hw::experiment_ipc_snapshot();
        if (!rejected || prior.ppcMessage != next.ppcMessage || prior.armMessage != next.armMessage ||
            prior.ppcControl != next.ppcControl || prior.armControl != next.armControl || prior.ppcMask != next.ppcMask ||
            prior.delay != next.delay || context.gpr != gpr || context.fpr != fpr || context.ps1 != ps1 || context.fpscr != fpscr) {
            throw std::runtime_error("IPC frontend refusal changed state");
        }
        ++guards;
    };
    refused(0xcd000030, 0x40000000, 0x802175d4);
    refused(0xcd000034, 0x40000000, 0x802175d0);
    refused(0xcd000034, 0, 0x802175d4);
    context.msr = 0xa030;
    refused(0xcd000034, 0x40000000, 0x802175d4);
    context.msr = 0x2030;
    context.hid0 = 0x8200;
    refused(0xcd000034, 0x40000000, 0x802175d4);
    context.hid0 = 0xc200;
    context.dbat[1].lower ^= 8;
    refused(0xcd000034, 0x40000000, 0x802175d4);
    context.dbat[1].lower ^= 8;
    context.pending_cb_count = 1;
    refused(0xcd000034, 0x40000000, 0x802175d4);
    context.pending_cb_count = 0;
    hw::pi_intsr = 0x4000;
    refused(0xcd000034, 0x40000000, 0x802175d4);
    hw::pi_intsr = 0;
    std::cout << "IPC_RESET_FRONTEND cases=8 guards=" << guards << '\n';
    hw::ipc_post_reply(0x80510000);
    const auto before = hw::experiment_ipc_snapshot();
    bool caught = false;
    try {
        hw::experiment_ipc_quiescent_mask(0x40000000);
    } catch (const std::runtime_error&) {
        caught = true;
    }
    const auto after = hw::experiment_ipc_snapshot();
    if (!caught || before.ppcMessage != after.ppcMessage || before.armMessage != after.armMessage ||
        before.ppcControl != after.ppcControl || before.armControl != after.armControl ||
        before.ppcMask != after.ppcMask || before.delay != after.delay) {
        return 9;
    }
    std::cout << "IPC_RESET_INFLIGHT_GUARD 1\n";
    return 0;
}
