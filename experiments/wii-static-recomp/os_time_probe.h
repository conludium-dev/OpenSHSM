#pragma once
#include "timebase_adapter.h"

extern "C" void func_8021C030(nwii::runtime::CPUContext& context);

inline int experiment_os_time_probe() {
    using namespace nwii::runtime;
    ClockContext context;
    g_trace_calls = false;
    context.scriptedClock = true;
    context.msr = 0x2030;
    uint64_t tick, adjustment;
    while (std::cin >> tick >> adjustment) {
        context.gpr.fill(0);
        for (unsigned index = 14; index < 32; ++index) {
            context.gpr[index] = 0x12340000 + index * 0x100;
        }
        const auto registers = context.gpr;
        context.gpr[1] = 0x80540000;
        context.cr.fill({});
        context.xer = 0x20000000;
        context.pc = 0x8021c030;
        context.lr = 0x807f0000;
        context.clockSamples = {tick, tick, tick};
        context.clockSampleIndex = 0;
        bootPollChecks = 0;
        memory_write32(context, 0x800030d8, adjustment >> 32);
        memory_write32(context, 0x800030dc, adjustment);
        try {
            func_8021C030(context);
        } catch (const std::runtime_error&) {
            return 3;
        }
        bool abi = context.gpr[1] == 0x80540000 && context.lr == 0x807f0000 && context.pc == 0x807f0000;
        for (unsigned index = 14; index < 32; ++index) {
            abi &= context.gpr[index] == registers[index];
        }
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << context.gpr[3] << ' ' << context.gpr[4] << ' ' << abi << ' ' << context.msr << ' '
                  << context.xer << ' ' << cr << ' ' << context.clockSampleIndex << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
