#pragma once
#include <processor_adapter.h>
#include <iostream>
#include <sstream>

namespace openshsm::experiment {
inline bool observed_buffer_span(uint32_t address, uint32_t length) {
    const uint64_t end = uint64_t(address) + length;
    return (address >= 0x80004000 && end <= 0x81800000)
        || (address >= 0x90000000 && end <= 0x94000000);
}

inline void observe_buffer_flush(nwii::runtime::CPUContext& ctx, bool entry) {
    static unsigned ordinary[2] = {}, abnormal[2] = {};
    const auto owner = entry ? ctx.gpr[3] : ctx.gpr[29];
    const auto address = entry ? ctx.gpr[4] : ctx.gpr[3];
    const auto length = entry ? ctx.gpr[6] : ctx.gpr[4];
    const bool valid = length == 0 || observed_buffer_span(address, length);
    const unsigned phase = entry ? 0 : 1;
    auto& count = valid ? ordinary[phase] : abnormal[phase];
    if (count >= 16) {
        return;
    }
    ++count;
    std::ostringstream out;
    out << "[Buffer flush snapshot] phase=" << (entry ? "entry" : "call") << " valid=" << valid
        << std::hex << " pc=" << ctx.pc << " lr=" << ctx.lr << " msr=" << ctx.msr
        << " sp=" << ctx.gpr[1] << " owner=" << owner << " address=" << address << " length=" << length;
    out << " gpr3-9=";
    for (unsigned i = 3; i <= 9; ++i) {
        out << ' ' << ctx.gpr[i];
    }
    out << " saved=";
    if (!entry && observed_buffer_span(ctx.gpr[1], 40)) {
        out << ' ' << ctx.mmu.read32(ctx.gpr[1] + 36);
    }
    out << " owner-head=";
    if (observed_buffer_span(owner, 96)) {
        for (unsigned i = 0; i < 24; ++i) {
            out << ' ' << ctx.mmu.read32(owner + i * 4);
        }
    }
    out << " owner-fields=";
    if (observed_buffer_span(owner, 0x160)) {
        for (auto offset : {0x10u, 0x80u, 0x150u, 0x154u, 0x158u, 0x15Cu}) {
            out << ' ' << ctx.mmu.read32(owner + offset);
        }
    }
    std::cout << out.str() << '\n';
}
}
