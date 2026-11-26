#pragma once
#include "stock_loading_observation.h"

namespace stock_subtitle_progress {
inline void observe(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) { return; }
    static unsigned events = 0, scripts = 0, cues = 0;
    static const auto start = std::chrono::steady_clock::now();
    if (events >= 32768) { return; }
    if (pc == 0x800D806C) { ++scripts; }
    if (pc == 0x800D80E4) { ++cues; }
    const char* event = pc == 0x800D806C ? "script" : pc == 0x800D80E4 ? "cue" :
        pc == 0x800D8114 ? "time-before" : pc == 0x800D8120 ? "time-after" :
        pc == 0x800D8280 ? "cue-after" : "load-after";
    std::string input;
    if (pc == 0x800D8114) {
        for (unsigned i = 0; i < 80; ++i) {
            auto byte = stock_loading_observation::copy_ram(ctx, ctx.gpr[3] + i, 1);
            if (byte.empty() || byte == "00") { break; }
            input += byte;
        }
    }
    std::ofstream file(std::string(prefix) + "-subtitle-progress.jsonl", std::ios::app);
    if (!file) { return; }
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    file << "{\"event\":\"" << event << "\",\"serial\":" << events++ << ",\"hostMs\":" << ms
        << ",\"pc\":" << pc << ",\"scripts\":" << scripts << ",\"cues\":" << cues
        << ",\"sp\":" << ctx.gpr[1] << ",\"scriptNode\":" << ctx.gpr[29] << ",\"cueNode\":" << ctx.gpr[28]
        << ",\"cueData\":" << ctx.gpr[30] << ",\"gpr3\":" << ctx.gpr[3] << ",\"inputHex\":\"" << input
        << "\",\"timeHex\":\"" << stock_loading_observation::copy_ram(ctx, ctx.gpr[30], 4) << "\"}\n";
}
}
