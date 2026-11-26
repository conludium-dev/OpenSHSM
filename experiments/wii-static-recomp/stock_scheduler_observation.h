#pragma once
#include "runtime/cpu_context.h"
#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace stock_scheduler_observation {
inline bool word(nwii::runtime::CPUContext& ctx, uint32_t address, uint32_t& value) {
    const uint32_t physical = address & 0x3FFFFFFF;
    const bool ram = physical <= 0x01800000 - 4 ||
        (physical >= 0x10000000 && physical <= 0x14000000 - 4);
    if (!ram || (address & 3) || !ctx.mmu.get_ptr(address) || !ctx.mmu.get_ptr(address + 3)) {
        return false;
    }
    const auto* bytes = ctx.mmu.get_ptr(address);
    value = (uint32_t(bytes[0]) << 24) | (uint32_t(bytes[1]) << 16) | (uint32_t(bytes[2]) << 8) | bytes[3];
    return true;
}

inline void observe(nwii::runtime::CPUContext& ctx) {
    static const char* prefix = std::getenv("NWII_SCHED_OBSERVE");
    if (!prefix || !*prefix) {
        return;
    }
    uint32_t current = 0;
    word(ctx, 0x800000E4, current);
    const bool idle = current == 0 && (ctx.pc == 0x8021A8E8 || ctx.pc == 0x8021A8F8);
    static std::array<unsigned, 2> counts{};
    auto& count = counts[idle ? 1 : 0];
    if (count >= (idle ? 16u : 8u)) {
        return;
    }
    ++count;
    static const auto started = std::chrono::steady_clock::now();
    std::ostringstream line;
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started).count();
    line << "{\"hostMs\":" << ms << ",\"idle\":" << (idle ? "true" : "false")
        << ",\"pc\":" << ctx.pc << ",\"lr\":" << ctx.lr << ",\"msr\":" << ctx.msr
        << ",\"r13\":" << ctx.gpr[13];
    const auto append_word = [&](const char* name, uint32_t address) {
        uint32_t value = 0;
        line << ",\"" << name << "\":";
        if (word(ctx, address, value)) {
            line << value;
        } else {
            line << "null";
        }
    };
    append_word("currentE4", 0x800000E4);
    append_word("selectedD4", 0x800000D4);
    append_word("rawD8", 0x800000D8);
    append_word("reschedule", 0x8052AB00);
    append_word("runHint", 0x8052AB04);
    append_word("runBits", 0x8052AB08);
    append_word("waitHead", 0x8052B288);
    append_word("waitTail", 0x8052B28C);
    line << ",\"runQueues\":[";
    for (unsigned i = 0; i < 64; ++i) {
        uint32_t value = 0;
        if (i) { line << ','; }
        if (word(ctx, 0x80492970 + i * 4, value)) { line << value; } else { line << "null"; }
    }
    line << "],\"threads\":[";
    uint32_t thread = 0;
    word(ctx, 0x800000DC, thread);
    std::array<uint32_t, 24> seen{};
    unsigned used = 0;
    while (thread && used < seen.size()) {
        bool duplicate = false;
        for (unsigned i = 0; i < used; ++i) {
            duplicate |= seen[i] == thread;
        }
        if (duplicate) { break; }
        uint32_t state_word = 0, next = 0;
        if (thread > 0xFFFFFFFFu - 0x300 || !word(ctx, thread + 0x2C8, state_word)
            || !word(ctx, thread + 0x2FC, next)) { break; }
        seen[used] = thread;
        if (used++) { line << ','; }
        line << "{\"address\":" << thread << ",\"state2C8\":" << (state_word >> 16);
        append_word("word2CC", thread + 0x2CC);
        append_word("priority2D0", thread + 0x2D0);
        append_word("wait2DC", thread + 0x2DC);
        append_word("next2E0", thread + 0x2E0);
        append_word("previous2E4", thread + 0x2E4);
        append_word("pc198", thread + 0x198);
        line << '}';
        thread = next;
    }
    line << "]}\n";
    std::ofstream file(std::string(prefix) + "-scheduler.jsonl", std::ios::app);
    file << line.str();
}
}
