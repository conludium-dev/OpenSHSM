#pragma once
#include "timebase_adapter.h"
#include <charconv>
#include <sstream>

extern "C" void func_8021C000(nwii::runtime::CPUContext& context);

inline int experiment_clock_probe() {
    using namespace nwii::runtime;
    ClockContext context;
    g_trace_calls = false;
    context.scriptedClock = true;
    context.msr = 0x2030;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream input(line);
        std::string token;
        uint64_t count;
        if (!(input >> token)) {
            return 8;
        }
        auto parsed = std::from_chars(token.data(), token.data() + token.size(), count);
        if (parsed.ec != std::errc() || parsed.ptr != token.data() + token.size() || !count || count > 128) {
            return 8;
        }
        context.clockSamples.clear();
        for (unsigned index = 0; index < count; ++index) {
            uint64_t value;
            if (!(input >> token)) {
                return 8;
            }
            parsed = std::from_chars(token.data(), token.data() + token.size(), value);
            if (parsed.ec != std::errc() || parsed.ptr != token.data() + token.size()) {
                return 8;
            }
            context.clockSamples.push_back(value);
        }
        if (input >> token) {
            return 8;
        }
        context.clockSampleIndex = 0;
        context.gpr.fill(0);
        context.cr.fill({});
        context.xer = 0x20000000;
        context.pc = 0x8021c000;
        context.lr = 0x807f0000;
        bootPollChecks = 0;
        try {
            func_8021C000(context);
        } catch (const std::runtime_error&) {
            return 3;
        }
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.gpr[5] << ' '
                  << context.pc << ' ' << context.lr << ' ' << context.clockSampleIndex << ' '
                  << bootPollChecks << ' ' << context.xer << ' ' << cr << '\n';
    }
    return 0;
}
