#pragma once
#include "stock_loading_observation.h"

namespace stock_loading_observation {
inline uint32_t context_word(nwii::runtime::CPUContext& ctx, uint32_t address) {
    const uint64_t end = uint64_t(address) + 4;
    if (!((address >= 0x80000000 && end <= 0x81800000)
        || (address >= 0x90000000 && end <= 0x94000000))) {
        return 0;
    }
    const uint8_t* data = ctx.mmu.get_ptr(address);
    if (!data) {
        return 0;
    }
    return (uint32_t(data[0]) << 24) | (uint32_t(data[1]) << 16)
        | (uint32_t(data[2]) << 8) | uint32_t(data[3]);
}

inline void observe_context(nwii::runtime::CPUContext& ctx, unsigned stage, uint32_t subject) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix || stage > 3) {
        return;
    }
    static std::array<uint64_t, 4> hits{};
    static unsigned records = 0;
    const uint64_t hit = ++hits[stage];
    const uint32_t selected = context_word(ctx, 0x800000D4);
    const uint32_t current = context_word(ctx, 0x800000E4);
    const uint32_t target = stage == 0 ? subject : selected;
    const bool zero_resume = target != 0 && context_word(ctx, target + 0x198) == 0;
    if (records >= 4096 || (hit > 16 && hit % 64 != 0 && !zero_resume)) {
        return;
    }
    std::ofstream file(std::string(prefix) + "-contexts.jsonl", std::ios::app);
    if (!file) {
        return;
    }
    file << "{\"serial\":" << records++ << ",\"stage\":" << stage << ",\"hit\":" << hit
        << ",\"pc\":" << ctx.pc << ",\"lr\":" << ctx.lr << ",\"sp\":" << ctx.gpr[1]
        << ",\"msr\":" << ctx.msr << ",\"selected\":" << selected << ",\"current\":" << current
        << ",\"saved\":" << ctx.dispatch_saved_ctx << ",\"subject\":" << subject
        << ",\"inCallback\":" << (ctx.in_callback ? "true" : "false")
        << ",\"selectedHex\":\"" << copy_ram(ctx, selected, 0x1C8)
        << "\",\"currentHex\":\"" << copy_ram(ctx, current, 0x1C8)
        << "\",\"savedHex\":\"" << copy_ram(ctx, ctx.dispatch_saved_ctx, 0x1C8) << "\"}\n";
}
}
