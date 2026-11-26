#pragma once
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace openshsm::experiment {
static_assert(std::atomic<uint64_t>::is_always_lock_free);
struct AudioCallbackStats {
    uint64_t calls, requested, supplied, missing, short_calls, errors;
};

class AudioCallback {
public:
    using Pull = size_t (*)(int16_t*, size_t);
    explicit AudioCallback(Pull source) : pull(source) {}

    static void render(void* userdata, uint8_t* stream, int length) noexcept {
        if (!userdata || !stream || length <= 0) {
            return;
        }
        auto& self = *static_cast<AudioCallback*>(userdata);
        std::memset(stream, 0, size_t(length));
        if ((length & 3) || !self.pull) {
            self.errors.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        const uint64_t frames = uint64_t(length) / 4;
        uint64_t supplied = 0;
        try {
            for (uint64_t offset = 0; offset < frames;) {
                int16_t samples[2048];
                const size_t requested = size_t(std::min<uint64_t>(1024, frames - offset));
                const size_t count = self.pull(samples, requested);
                if (count > requested) {
                    self.errors.fetch_add(1, std::memory_order_relaxed);
                    break;
                }
                std::memcpy(stream + offset * 4, samples, count * 4);
                supplied += count;
                offset += requested;
            }
        } catch (...) {
            self.errors.fetch_add(1, std::memory_order_relaxed);
        }
        self.calls.fetch_add(1, std::memory_order_relaxed);
        self.requested.fetch_add(frames, std::memory_order_relaxed);
        self.supplied.fetch_add(supplied, std::memory_order_relaxed);
        self.missing.fetch_add(frames - supplied, std::memory_order_relaxed);
        self.short_calls.fetch_add(supplied < frames, std::memory_order_relaxed);
    }

    AudioCallbackStats snapshot() const {
        return {calls.load(std::memory_order_relaxed), requested.load(std::memory_order_relaxed),
            supplied.load(std::memory_order_relaxed), missing.load(std::memory_order_relaxed),
            short_calls.load(std::memory_order_relaxed), errors.load(std::memory_order_relaxed)};
    }

    void report(bool final = false) {
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - origin).count();
        if (!final && elapsed < next_report) {
            return;
        }
        next_report = elapsed + 1000000;
        const auto stats = snapshot();
        std::printf("[AudioCallback] wallUs=%llu calls=%llu requested=%llu supplied=%llu missing=%llu short=%llu errors=%llu final=%u\n",
            static_cast<unsigned long long>(elapsed), static_cast<unsigned long long>(stats.calls),
            static_cast<unsigned long long>(stats.requested), static_cast<unsigned long long>(stats.supplied),
            static_cast<unsigned long long>(stats.missing), static_cast<unsigned long long>(stats.short_calls),
            static_cast<unsigned long long>(stats.errors), unsigned(final));
    }

private:
    Pull pull;
    std::atomic<uint64_t> calls{0}, requested{0}, supplied{0}, missing{0}, short_calls{0}, errors{0};
    std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now();
    int64_t next_report = 1000000;
};
}
