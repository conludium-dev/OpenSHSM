#pragma once
#include "stock_loading_observation.h"
#include <bit>

namespace stock_numeric_reader {
struct Pending {
    const void* context = nullptr;
    uint32_t sp = 0, caller = 0;
    bool active = false;
    unsigned id = 0;
    std::string input;
};
inline void observe(nwii::runtime::CPUContext& ctx, bool before) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) { return; }
    static std::array<Pending, 64> pending{};
    static unsigned used = 0, finished = 0, overwritten = 0;
    static const std::string saved_prefix(prefix);
    struct Finalizer {
        ~Finalizer() {
            std::ofstream file(saved_prefix + "-numeric-flight.json");
            file << "{\"started\":" << used << ",\"finished\":" << finished
                << ",\"overwrittenActive\":" << overwritten << ",\"pending\":[";
            bool first = true;
            for (const auto& state : pending) {
                if (!state.active) { continue; }
                file << (first ? "" : ",") << "{\"id\":" << state.id << ",\"sp\":" << state.sp
                    << ",\"caller\":" << state.caller << ",\"inputHex\":\"" << state.input << "\"}";
                first = false;
            }
            file << "]}\n";
        }
    };
    static Finalizer finalizer;
    static const auto start = std::chrono::steady_clock::now();
    unsigned id = 0;
    std::string input;
    uint32_t input_address = 0, reader = 0;
    if (before) {
        id = used++;
        auto& slot = pending[id % pending.size()];
        if (slot.active) { ++overwritten; }
        slot = {&ctx, ctx.gpr[1], ctx.lr, true, id, ""};
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
        pending[id % pending.size()].input = input;
    } else {
        bool found = false;
        for (unsigned i = pending.size(); i > 0; --i) {
            auto& state = pending[i - 1];
            if (state.active && state.context == &ctx && state.sp == ctx.gpr[1] && state.caller == ctx.lr) {
                id = state.id; state.active = false; ++finished; found = true; break;
            }
        }
        if (!found) { return; }
    }
    if (id >= 8192) { return; }
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
