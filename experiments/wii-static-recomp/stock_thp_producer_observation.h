#pragma once
#include "stock_thp_queue_observation.h"

namespace stock_thp_queue_observation {
inline void observe_producer(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    constexpr std::array<uint32_t, 11> sites = {0x8009BA88, 0x8009BBF0, 0x8009BC38, 0x8009BC90,
        0x8009BE40, 0x8022CA84, 0x8022CD80, 0x8022CD90, 0x8022CDB8, 0x8022CDBC, 0x8022CDC4};
    unsigned slot = 0;
    while (slot < sites.size() && sites[slot] != pc) {
        ++slot;
    }
    if (slot == sites.size()) {
        return;
    }
    static std::array<unsigned, 11> hits{};
    static unsigned events = 0;
    ++hits[slot];
    if (events >= 8192 || (hits[slot] > 16 && hits[slot] % 60 != 0)) {
        return;
    }
    static const auto start = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    std::ofstream file(std::string(prefix) + "-movie-producer.jsonl", std::ios::app);
    if (!file) {
        return;
    }
    file << "{\"serial\":" << events++ << ",\"hostMs\":" << ms << ",\"pc\":" << pc
        << ",\"hits\":" << hits[slot] << ",\"sp\":" << ctx.gpr[1] << ",\"lr\":" << ctx.lr
        << ",\"r13\":" << ctx.gpr[13] << ",\"gpr3\":" << ctx.gpr[3] << ",\"gpr4\":" << ctx.gpr[4]
        << ",\"gpr5\":" << ctx.gpr[5] << ",\"ctr\":" << ctx.ctr
        << ",\"cr0eq\":" << (ctx.cr[0].eq ? "true" : "false")
        << ",\"sdkStateHex\":\"" << stock_loading_observation::copy_ram(ctx, ctx.gpr[13] - 14756u, 56)
        << "\",\"movieA0Hex\":\"" << stock_loading_observation::copy_ram(ctx, 0x8046BBE0, 32)
        << "\",\"movieF0Hex\":\"" << stock_loading_observation::copy_ram(ctx, 0x8046BC30, 16) << "\"}\n";
}
}
