#pragma once
#include "runtime/cpu_context.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <time.h>
#include "stock_movie_input.h"
#include "stock_movie_capture_gate.h"

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
    static stock_movie_capture_gate::Gate gate(std::getenv("NWII_MOVIE_CAPTURE_AFTER_MS"));
    if (!gate.valid) {
        return;
    }
    if (gate.delay_us) {
        const auto gate_now = std::chrono::steady_clock::now().time_since_epoch();
        const auto gate_us = std::chrono::duration_cast<std::chrono::microseconds>(gate_now).count();
        if (gate_us < 0 || !gate.accept(static_cast<uint64_t>(gate_us))) {
            return;
        }
    }
    stock_movie_input::observe(ctx, site, serial);
    timespec cpu_time{};
    const int cpu_result = clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_time);
    const long long cpu_us = cpu_result == 0 ? (long long)cpu_time.tv_sec * 1000000 + cpu_time.tv_nsec / 1000 : -1;
    const auto now = std::chrono::steady_clock::now().time_since_epoch();
    const auto us = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    std::fprintf(stream, "{\"serial\":%u,\"hostUs\":%lld,\"hostThreadCpuUs\":%lld,\"site\":%u,\"thread\":%u,\"owner\":%u,"
        "\"sp\":%u,\"lr\":%u,\"msr\":%u,\"r3\":%u,\"r4\":%u,\"r5\":%u,\"r6\":%u}\n",
        serial++, static_cast<long long>(us), cpu_us, site, ctx.mmu.read32(0x800000D4),
        ctx.mmu.read32(0x800000D8), ctx.gpr[1], ctx.lr, ctx.msr,
        ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6]);
}

}
