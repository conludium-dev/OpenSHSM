#pragma once
#include "boot_poll.h"
#include "carry_adapter.h"

namespace nwii::runtime {
struct ClockContext : L2Context {
    bool scriptedClock = false;
    std::vector<uint64_t> clockSamples;
    size_t clockSampleIndex = 0;
    ClockContext() {
        tb_freq = 60750000;
    }
};

inline uint64_t experiment_ticks_from_ns(uint64_t nanoseconds) {
    return (nanoseconds / 1000000000) * 60750000 + (nanoseconds % 1000000000) * 60750000 / 1000000000;
}

inline uint64_t experiment_read_timebase(CPUContext& base) {
    auto& context = static_cast<ClockContext&>(base);
    if (context.tb_freq != 60750000) {
        throw std::runtime_error("Unverified timebase frequency");
    }
    if (context.scriptedClock) {
        if (context.clockSampleIndex >= context.clockSamples.size()) {
            throw std::runtime_error("Timebase fixture exhausted");
        }
        return context.clockSamples[context.clockSampleIndex++];
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - context.tb_start).count();
    if (elapsed < 0) {
        throw std::runtime_error("Monotonic timebase origin is in the future");
    }
    return experiment_ticks_from_ns(static_cast<uint64_t>(elapsed));
}
}
