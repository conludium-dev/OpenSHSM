#pragma once
#include "stock_thp_queue_observation.h"

namespace stock_thp_queue_observation {
inline void observe_update(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    const unsigned slot = pc == 0x8009B72C ? 0 : pc == 0x8009B750 ? 1 : pc == 0x8009B760 ? 2 : 3;
    static std::array<unsigned, 4> hits{};
    static unsigned events = 0;
    ++hits[slot];
    if (events >= 4096 || (hits[slot] > 16 && hits[slot] % 60 != 0)) {
        return;
    }
    uint32_t active = 0;
    const bool valid = word(ctx, 0x8046BC38, active);
    static const auto start = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    std::ofstream file(std::string(prefix) + "-movie-update.jsonl", std::ios::app);
    if (!file) {
        return;
    }
    file << "{\"serial\":" << events++ << ",\"hostMs\":" << ms << ",\"pc\":" << pc
        << ",\"hits\":" << hits[slot] << ",\"sp\":" << ctx.gpr[1] << ",\"lr\":" << ctx.lr
        << ",\"candidate\":" << ctx.gpr[28] << ",\"gpr3\":" << ctx.gpr[3] << ",\"gpr4\":" << ctx.gpr[4]
        << ",\"activeValid\":" << (valid ? "true" : "false") << ",\"active\":" << active
        << ",\"candidateHex\":\"" << stock_loading_observation::copy_ram(ctx, ctx.gpr[28], 16)
        << "\",\"activeHex\":\"" << (valid ? stock_loading_observation::copy_ram(ctx, active, 16) : "")
        << "\",\"stateA0Hex\":\"" << stock_loading_observation::copy_ram(ctx, 0x8046BBE0, 32)
        << "\",\"stateF0Hex\":\"" << stock_loading_observation::copy_ram(ctx, 0x8046BC30, 16) << "\"}\n";
}
}
