#pragma once
#include "stock_loading_observation.h"

namespace stock_thp_queue_observation {
struct Sample {
    uint32_t function = 0, queue = 0, caller = 0;
    unsigned hits = 0;
};

inline bool word(nwii::runtime::CPUContext& ctx, uint32_t address, uint32_t& value) {
    auto hex = stock_loading_observation::copy_ram(ctx, address, 4);
    if (hex.empty()) {
        return false;
    }
    value = uint32_t(std::stoul(hex, nullptr, 16));
    return true;
}

inline void observe(nwii::runtime::CPUContext& ctx, uint32_t function) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix || ctx.lr < 0x80090000 || ctx.lr >= 0x800A0000
        || (function != 0x80217D30 && function != 0x80217E00)) {
        return;
    }
    static std::array<Sample, 128> samples{};
    static unsigned used = 0, events = 0;
    Sample* sample = nullptr;
    for (unsigned i = 0; i < used; ++i) {
        if (samples[i].function == function && samples[i].queue == ctx.gpr[3] && samples[i].caller == ctx.lr) {
            sample = &samples[i];
            break;
        }
    }
    if (!sample) {
        if (used == samples.size()) {
            return;
        }
        sample = &samples[used++];
        *sample = {function, ctx.gpr[3], ctx.lr, 0};
    }
    ++sample->hits;
    if (events >= 20000 || (sample->hits > 16 && sample->hits % 60 != 0)) {
        return;
    }
    const uint32_t queue = ctx.gpr[3];
    uint32_t array = 0, capacity = 0, first = 0, count = 0, head = 0;
    const bool valid = queue <= 0xFFFFFFDFu && word(ctx, queue + 16, array)
        && word(ctx, queue + 20, capacity) && word(ctx, queue + 24, first) && word(ctx, queue + 28, count);
    bool head_valid = false;
    if (valid && capacity > 0 && capacity <= 128 && first < capacity && count > 0 && count <= capacity
        && uint64_t(array) + uint64_t(first) * 4 <= 0xFFFFFFFCu) {
        head_valid = word(ctx, array + first * 4, head);
    }
    static const auto start = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    std::ofstream file(std::string(prefix) + "-movie-queues.jsonl", std::ios::app);
    if (!file) {
        return;
    }
    file << "{\"serial\":" << events++ << ",\"hostMs\":" << ms << ",\"function\":" << function
        << ",\"caller\":" << ctx.lr << ",\"sp\":" << ctx.gpr[1] << ",\"hits\":" << sample->hits
        << ",\"queue\":" << queue << ",\"argument4\":" << ctx.gpr[4] << ",\"flags\":" << ctx.gpr[5]
        << ",\"queueHex\":\"" << stock_loading_observation::copy_ram(ctx, queue, 32)
        << "\",\"fieldsValid\":" << (valid ? "true" : "false")
        << ",\"capacity\":" << capacity << ",\"first\":" << first << ",\"count\":" << count
        << ",\"headValid\":" << (head_valid ? "true" : "false") << ",\"head\":" << head
        << ",\"headHex\":\"" << (head_valid ? stock_loading_observation::copy_ram(ctx, head, 16) : "")
        << "\",\"argumentHex\":\"" << stock_loading_observation::copy_ram(ctx, ctx.gpr[4], 16) << "\"}\n";
}
}
