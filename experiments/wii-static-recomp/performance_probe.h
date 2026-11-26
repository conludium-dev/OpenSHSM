#pragma once
#include "performance_adapter.h"

extern "C" {
void func_80210720(nwii::runtime::CPUContext&);
void func_80210730(nwii::runtime::CPUContext&);
void func_80210740(nwii::runtime::CPUContext&);
void func_80210750(nwii::runtime::CPUContext&);
void func_80210760(nwii::runtime::CPUContext&);
void func_80210770(nwii::runtime::CPUContext&);
}

inline int experiment_performance_probe() {
    using namespace nwii::runtime;
    PerformanceContext context;
    g_trace_calls = false;
    const std::array<std::array<uint32_t, 3>, 8> rejected = {{{6, 0, 0x2030}, {999, 0, 0x2030},
        {0, 1, 0x2030}, {1, 0xffffffff, 0x2030}, {2, 0x80000000, 0x2030},
        {0, 0, 0x6030}, {0, 0, 0xa030}, {5, 0, 0xe030}}};
    context.performanceRegisters = {1, 2, 3, 4, 5, 6};
    for (const auto& test : rejected) {
        context.msr = test[2];
        const auto before = context.performanceRegisters;
        bool refused = false;
        try {
            experiment_reset_performance(context, test[0], test[1]);
        } catch (const std::runtime_error&) {
            refused = true;
        }
        if (!refused || before != context.performanceRegisters) {
            return 11;
        }
    }
    const std::array<void (*)(CPUContext&), 6> functions = {func_80210720, func_80210730, func_80210740,
        func_80210750, func_80210760, func_80210770};
    uint32_t seed, cr, xer, ctr;
    while (std::cin >> seed >> cr >> xer >> ctr) {
        for (auto& value : context.gpr) {
            if (!(std::cin >> value)) {
                return 8;
            }
        }
        for (unsigned index = 0; index < 8; ++index) {
            const unsigned field = (cr >> (28 - index * 4)) & 15;
            context.cr[index].lt = bool(field & 8);
            context.cr[index].gt = bool(field & 4);
            context.cr[index].eq = bool(field & 2);
            context.cr[index].so = bool(field & 1);
        }
        context.xer = xer;
        context.ctr = ctr;
        context.msr = 0x2030;
        context.performanceRegisters = {0x80000000, 0, seed, seed ^ 0x12345678, seed ^ 0xaaaaaaaa, seed ^ 0xffffffff};
        for (unsigned index = 0; index < 6; ++index) {
            context.gpr[3] = 0;
            context.pc = 0x80210720 + index * 16;
            context.lr = 0x802113B0 + index * 8;
            functions[index](context);
            if (context.pc != context.lr) {
                return 9;
            }
        }
        for (auto value : context.gpr) {
            std::cout << value << ' ';
        }
        std::cout << cr << ' ' << context.lr << ' ' << context.ctr << ' ' << context.xer << ' ' << context.msr;
        for (auto value : context.performanceRegisters) {
            std::cout << ' ' << value;
        }
        uint32_t actualCr = 0;
        for (const auto& field : context.cr) {
            actualCr = (actualCr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        if (actualCr != cr) {
            return 10;
        }
        std::cout << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
