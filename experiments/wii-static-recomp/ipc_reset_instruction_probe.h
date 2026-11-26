#pragma once
#include "ipc_reset_fixture.h"
#include "loader-bat-seed.h"
#include <iostream>

extern "C" void func_80217580(nwii::runtime::CPUContext&);

inline int experiment_ipc_reset_instruction_probe() {
    using namespace nwii::runtime;
    hw::register_pi(MMIODispatcher::get());
    hw::register_ipc(MMIODispatcher::get());
    SeededBatContext context;
    g_trace_calls = false;
    isolatedIpcResetFixture = true;
    for (unsigned index = 0; index < 8; ++index) {
        context.msr = 0x2030;
        context.hid0 = 0xc200;
        context.fpscr = index >= 4 ? 4 : 0;
        context.pc = 0x802175d4;
        context.gpr[3] = 0xcd000000;
        context.gpr[0] = 0x40000000;
        hw::pi_intsr = 0x10000;
        MMIODispatcher::get().write32(0xcd000004, (index & 3) << 4);
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        bool fixtureExit = false;
        try {
            func_80217580(context);
        } catch (const std::runtime_error& failure) {
            fixtureExit = std::string(failure.what()) == "Isolated IPC reset fixture exit after original store";
        }
        const auto state = hw::experiment_ipc_snapshot();
        if (!fixtureExit || context.gpr != gpr || context.fpr != fpr || context.ps1 != ps1 || state.ppcControl ||
            state.armMessage || context.fpscr != (index >= 4 ? 4u : 0u)) {
            return 9;
        }
        std::cout << "IPC_INSTRUCTION_CASE " << index << ' ' << state.ppcControl << ' ' << state.armMessage
                  << ' ' << context.fpscr << ' ' << hw::pi_intsr.load() << '\n';
    }
    isolatedIpcResetFixture = false;
    return 0;
}
