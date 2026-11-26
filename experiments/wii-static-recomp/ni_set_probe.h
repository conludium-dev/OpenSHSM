#pragma once
#include "ni_guard.h"
#include <iostream>

extern "C" void func_80210830(nwii::runtime::CPUContext&);

inline int experiment_ni_set_probe() {
    uint32_t fpscr;
    nwii::runtime::g_trace_calls = false;
    nwii::runtime::CPUContext context;
    while (std::cin >> fpscr) {
        context.fpscr = fpscr;
        context.msr = 0x2030;
        context.pc = 0x80210830;
        context.lr = 0x80000004;
        context.gpr.fill(0x12345678);
        context.fpr.fill(1.0);
        context.ps1.fill(2.0);
        func_80210830(context);
        if (context.pc != context.lr || context.lr != 0x80000004 || context.msr != 0x2030) {
            return 9;
        }
        for (unsigned index = 0; index < 32; ++index) {
            if (context.gpr[index] != 0x12345678 || context.fpr[index] != 1.0 || context.ps1[index] != 2.0) {
                return 10;
            }
        }
        std::cout << context.fpscr << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
