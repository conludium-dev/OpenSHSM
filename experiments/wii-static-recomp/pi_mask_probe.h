#pragma once
#include "pi_mask_adapter.h"
#include "loader-bat-seed.h"
#include <iostream>

extern "C" void func_80217580(nwii::runtime::CPUContext&);

inline int experiment_pi_mask_probe() {
    using namespace nwii::runtime;
    const uint32_t values[] = {0, 0xf0, 0xffffffff, 0x100, 0x10000, 0x10100, 0x80000000, 0x12345678,
                               1, 2, 4, 8, 0x10, 0x20, 0x40, 0x4000};
    SeededBatContext context;
    g_trace_calls = false;
    for (unsigned index = 0; index < 32; ++index) {
        context.msr = 0x2030;
        context.hid0 = 0xc200;
        context.fpscr = index >= 16 ? 4 : 0;
        context.pc = 0x802175d0;
        context.gpr[4] = 0xcc000000;
        context.gpr[5] = values[index & 15];
        context.gpr[3] = 0xcd000000;
        context.gpr[0] = 0x40000000;
        hw::pi_intmr = index & 1 ? 0x10203040 : 0;
        hw::pi_intsr = 0x10000;
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto cause = hw::pi_intsr.load();
        const auto instructionCount = context.inst_count;
        bool nextGuard = false;
        try {
            func_80217580(context);
        } catch (const std::runtime_error& failure) {
            nextGuard = std::string(failure.what()).find("memory instruction=802175d4 address=cd000034") != std::string::npos;
        }
        if (!nextGuard || context.gpr != gpr || context.fpr != fpr || context.ps1 != ps1 ||
            hw::pi_intsr.load() != cause || context.fpscr != (index >= 16 ? 4u : 0u) ||
            hw::pi_intmr.load() != values[index & 15] || context.inst_count != instructionCount + 1) {
            return 9;
        }
        std::cout << "PI_MASK_CASE " << index << ' ' << hw::pi_intmr.load() << ' ' << context.fpscr << ' ' << hw::pi_intsr.load() << '\n';
    }
    unsigned guards = 0;
    auto refused = [&](uint32_t address, uint32_t instruction) {
        const auto mask = hw::pi_intmr.load();
        const auto cause = hw::pi_intsr.load();
        const auto gpr = context.gpr;
        bool caught = false;
        try {
            experiment_pi_mask_write(context, address, 0x12345678, instruction);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || hw::pi_intmr.load() != mask || hw::pi_intsr.load() != cause || context.gpr != gpr) {
            throw std::runtime_error("PI mask refusal changed state");
        }
        ++guards;
    };
    refused(0xcc003000, 0x802175d0);
    refused(0xcc003005, 0x802175d0);
    refused(0x0c003004, 0x802175d0);
    refused(0xcc003004, 0x802175d4);
    context.msr = 0xa030;
    refused(0xcc003004, 0x802175d0);
    context.msr = 0x2030;
    context.hid0 = 0x8200;
    refused(0xcc003004, 0x802175d0);
    context.hid0 = 0xc200;
    context.dbat[1].lower ^= 8;
    refused(0xcc003004, 0x802175d0);
    std::cout << "PI_MASK_GUARDS " << guards << '\n';
    return 0;
}
