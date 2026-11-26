#pragma once
#include "template_patch.h"
#include <iostream>

extern "C" void func_80211BA0(nwii::runtime::CPUContext&);

inline int experiment_template_stale_probe() {
    nwii::runtime::CPUContext context;
    nwii::runtime::g_trace_calls = false;
    context.msr = 0x2030;
    context.lr = 0x80000004;
    context.gpr.fill(0x12345678);
    context.fpr.fill(1.0);
    context.ps1.fill(2.0);
    unsigned guards = 0;
    for (uint32_t address = 0x80211ba0; address < 0x80211c38; address += 4) {
        context.pc = address;
        bool caught = false;
        try {
            func_80211BA0(context);
        } catch (const std::runtime_error& failure) {
            caught = std::string(failure.what()) == "Mutable exception template execution requires verified relocated dispatch";
        }
        if (!caught || context.pc != address || context.lr != 0x80000004 || context.msr != 0x2030) {
            return 9;
        }
        for (unsigned index = 0; index < 32; ++index) {
            if (context.gpr[index] != 0x12345678 || context.fpr[index] != 1.0 || context.ps1[index] != 2.0) {
                return 10;
            }
        }
        ++guards;
    }
    std::cout << "TEMPLATE_STALE_GUARDS " << guards << '\n';
    return 0;
}
