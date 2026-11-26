#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>

namespace openshsm::experiment {
class HostPhases {
public:
    using Clock = std::chrono::steady_clock;
    void begin(uint64_t gx) {
        last = Clock::now();
        if (!started) {
            started = true;
            epoch = last;
            first_gx = gx;
        }
    }
    void mark(unsigned slot) {
        const auto now = Clock::now();
        if (slot < ns.size()) {
            ns[slot] += std::chrono::duration_cast<std::chrono::nanoseconds>(now - last).count();
        }
        last = now;
    }
    void publication(bool pending) {
        ++published;
        pending_samples += pending;
    }
    void end(uint64_t gx, bool final = false) {
        if (!started) { return; }
        if (!final) { ++loops; }
        const auto now = Clock::now();
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(now - epoch).count();
        if (!final && elapsed < 1000000) { return; }
        const auto host = std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count();
        std::printf("[HostPhases] hostUs=%llu elapsedUs=%llu loops=%llu gx=%llu publications=%llu pendingSamples=%llu inputNs=%llu xfbNs=%llu gxNs=%llu statsNs=%llu blitNs=%llu swapNs=%llu audioNs=%llu restNs=%llu sleepNs=%llu final=%u\n",
            (unsigned long long)host, (unsigned long long)elapsed, (unsigned long long)loops,
            (unsigned long long)(gx - first_gx), (unsigned long long)published, (unsigned long long)pending_samples,
            (unsigned long long)ns[0], (unsigned long long)ns[1], (unsigned long long)ns[2],
            (unsigned long long)ns[3], (unsigned long long)ns[4], (unsigned long long)ns[5],
            (unsigned long long)ns[6], (unsigned long long)ns[7], (unsigned long long)ns[8], unsigned(final));
        epoch = now;
        first_gx = gx;
        ns.fill(0);
        loops = published = pending_samples = 0;
    }
private:
    std::array<uint64_t, 9> ns{};
    Clock::time_point last{}, epoch{};
    uint64_t first_gx = 0, loops = 0, published = 0, pending_samples = 0;
    bool started = false;
};
}
