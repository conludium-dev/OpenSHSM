#pragma once
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>

namespace openshsm::experiment {

// Both observers run under the existing adma_mutex; there is no second audio queue.
class DspSupplyObserver {
public:
    void produced(uint64_t frames, uint64_t before, uint64_t after, uint64_t late,
        uint64_t period, bool admitted) {
        if (!enabled) {
            return;
        }
        const auto now = std::chrono::steady_clock::now();
        if (has_previous) {
            max_gap_us = std::max(max_gap_us, uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
                now - previous).count()));
        }
        previous = now;
        has_previous = true;
        ++events;
        produced_frames += admitted ? frames : 0;
        capped_frames += admitted ? 0 : frames;
        max_ring = std::max(max_ring, std::max(before, after));
        max_late = std::max(max_late, late);
        missed_periods += period ? late / period : 0;
        period_ticks = period;
        last_block_frames = frames;
    }

    void pulled(uint64_t requested, uint64_t supplied, uint64_t before) {
        if (!enabled) {
            return;
        }
        ++pulls;
        pulled_frames += supplied;
        requested_frames += requested;
        short_pulls += supplied < requested;
        max_ring = std::max(max_ring, before);
        const auto now = std::chrono::steady_clock::now();
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - origin).count();
        if (elapsed >= next_report_ms) {
            next_report_ms = elapsed + 1000;
            std::cout << "[DSPSupply] elapsedMs=" << elapsed << " events=" << events
                      << " producedFrames=" << produced_frames << " cappedFrames=" << capped_frames
                      << " blockFrames=" << last_block_frames << " periodTicks=" << period_ticks
                      << " maxLateTicks=" << max_late << " missedPeriods=" << missed_periods
                      << " maxGapUs=" << max_gap_us << " pulls=" << pulls
                      << " requestedFrames=" << requested_frames << " suppliedFrames=" << pulled_frames
                      << " short=" << short_pulls << " maxRingFrames=" << max_ring << '\n';
        }
    }

private:
    bool enabled = std::getenv("NWII_DSP_SUPPLY") != nullptr;
    bool has_previous = false;
    std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now(), previous;
    int64_t next_report_ms = 1000;
    uint64_t events = 0, produced_frames = 0, capped_frames = 0, max_ring = 0;
    uint64_t max_late = 0, missed_periods = 0, period_ticks = 0, last_block_frames = 0, max_gap_us = 0;
    uint64_t pulls = 0, requested_frames = 0, pulled_frames = 0, short_pulls = 0;
};

inline DspSupplyObserver dsp_supply_observer;

}
