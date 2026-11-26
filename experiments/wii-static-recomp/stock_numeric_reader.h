#pragma once
#include "stock_loading_observation.h"
#include <bit>

namespace stock_numeric_reader {
struct Pending {
    const void* context = nullptr;
    uint32_t sp = 0, caller = 0;
    bool active = false;
};
inline void observe(nwii::runtime::CPUContext& ctx, bool before) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) { return; }
    static std::array<Pending, 8192> pending{};
    static unsigned used = 0;
    static const auto start = std::chrono::steady_clock::now();
    unsigned id = 0;
    std::string input;
    uint32_t input_address = 0, reader = 0;
    if (before) {
        if (used == pending.size()) { return; }
        id = used++;
        pending[id] = {&ctx, ctx.gpr[1], ctx.lr, true};
        reader = ctx.gpr[4];
        if (reader == 0x8019D3AC) {
            const auto word = stock_loading_observation::copy_ram(ctx, ctx.gpr[5], 4);
            if (!word.empty()) {
                input_address = uint32_t(std::stoul(word, nullptr, 16));
                for (unsigned i = 0; i < 80; ++i) {
                    auto byte = stock_loading_observation::copy_ram(ctx, input_address + i, 1);
                    if (byte.empty() || byte == "00") { break; }
                    input += byte;
                }
            }
        }
    } else {
        bool found = false;
        for (unsigned i = used; i > 0; --i) {
            auto& state = pending[i - 1];
            if (state.active && state.context == &ctx && state.sp == ctx.gpr[1] && state.caller == ctx.lr) {
                id = i - 1; state.active = false; found = true; break;
            }
        }
        if (!found) { return; }
    }
    std::ofstream file(std::string(prefix) + "-numeric-reader.jsonl", std::ios::app);
    if (!file) { return; }
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    std::ostringstream result;
    result << std::hex << std::setw(16) << std::setfill('0') << std::bit_cast<uint64_t>(double(ctx.fpr[1]));
    file << "{\"before\":" << (before ? "true" : "false") << ",\"id\":" << id << ",\"hostMs\":" << ms
        << ",\"sp\":" << ctx.gpr[1] << ",\"caller\":" << ctx.lr << ",\"msr\":" << ctx.msr
        << ",\"reader\":" << reader << ",\"inputAddress\":" << input_address << ",\"inputHex\":\"" << input
        << "\",\"fpr1Hex\":\"" << result.str() << "\"}\n";
}
}
