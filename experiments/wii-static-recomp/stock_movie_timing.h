#pragma once
#include "runtime/cpu_context.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>

namespace stock_movie_timing {

inline void observe(nwii::runtime::CPUContext& ctx, uint32_t site) {
    static FILE* stream = []() -> FILE* {
        const char* path = std::getenv("NWII_MOVIE_TIMING");
        if (!path || !*path) {
            return nullptr;
        }
        FILE* result = std::fopen(path, "a");
        if (result) {
            std::setvbuf(result, nullptr, _IOLBF, 0);
        }
        return result;
    }();
    static unsigned serial = 0;
    if (!stream || serial >= 4096) {
        return;
    }
    const auto now = std::chrono::steady_clock::now().time_since_epoch();
    const auto us = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    std::fprintf(stream, "{\"serial\":%u,\"hostUs\":%lld,\"site\":%u,\"thread\":%u,\"owner\":%u,"
        "\"sp\":%u,\"lr\":%u,\"msr\":%u,\"r3\":%u,\"r4\":%u,\"r5\":%u,\"r6\":%u}\n",
        serial++, static_cast<long long>(us), site, ctx.mmu.read32(0x800000D4),
        ctx.mmu.read32(0x800000D8), ctx.gpr[1], ctx.lr, ctx.msr,
        ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6]);
}

}
