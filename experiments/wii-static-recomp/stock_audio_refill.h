#pragma once
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>

namespace openshsm::experiment {

struct AudioRefillResult {
    uint32_t before = 0, after = 0;
    uint32_t pulls = 0, supplied = 0, queued = 0, empty = 0, errors = 0;
    bool limited = false;
};

// Refill the existing 64ms device target; never enqueue the pull's zero-filled tail.
template<class QueueSize, class Pull, class Enqueue, class Observe>
AudioRefillResult refill_audio(QueueSize queue_size, Pull pull, Enqueue enqueue, Observe observe) {
    constexpr uint32_t target_bytes = 8192;
    constexpr uint32_t frame_bytes = 4;
    AudioRefillResult result;
    result.before = queue_size();
    uint32_t queued_bytes = result.before;
    for (unsigned attempt = 0; attempt < 8 && result.queued < 4096; ++attempt) {
        if (queued_bytes >= target_bytes) {
            break;
        }
        const auto requested = std::min({1024u, (target_bytes - queued_bytes) / frame_bytes,
            4096u - result.queued});
        if (!requested) {
            break;
        }
        int16_t samples[2048];
        const auto supplied = pull(samples, requested);
        if (supplied > requested) {
            throw std::runtime_error("Audio pull exceeds requested frames");
        }
        ++result.pulls;
        result.supplied += uint32_t(supplied);
        if (!supplied) {
            ++result.empty;
            observe(queued_bytes, 0, true, false, requested);
            break;
        }
        const bool failed = enqueue(samples, uint32_t(supplied)) != 0;
        observe(queued_bytes, supplied, true, failed, requested);
        if (failed) {
            ++result.errors;
            break;
        }
        result.queued += uint32_t(supplied);
        queued_bytes = queue_size();
    }
    if (!result.pulls) {
        observe(queued_bytes, 0, false, false, 0);
    }
    result.after = queue_size();
    result.limited = result.after < target_bytes && (result.pulls == 8 || result.queued == 4096);
    return result;
}

class AudioRefillMonitor {
public:
    void record(const AudioRefillResult& result) {
        pulls += result.pulls;
        supplied += result.supplied;
        queued += result.queued;
        empty += result.empty;
        errors += result.errors;
        limited += result.limited;
        const auto now = std::chrono::steady_clock::now();
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(now - origin).count();
        if (elapsed >= next_report_us) {
            next_report_us = elapsed + 1000000;
            std::cout << "[AudioRefill] wallUs=" << elapsed << " pulls=" << pulls << " supplied=" << supplied
                      << " queued=" << queued << " empty=" << empty << " errors=" << errors
                      << " limited=" << limited << " before=" << result.before << " after=" << result.after << '\n';
        }
    }

private:
    std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now();
    int64_t next_report_us = 1000000;
    uint64_t pulls = 0, supplied = 0, queued = 0, empty = 0, errors = 0, limited = 0;
};

}
