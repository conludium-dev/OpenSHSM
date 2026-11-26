#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>

namespace stock_vi_timer_profile {
enum class Reason : unsigned { Masked, Callback, Pending, Busy, Raised };

template <class Context, class Mask, class Status>
Reason classify(Context& c, const Mask& mask, const Status& status) {
    if (!(mask & 0x100)) {
        return Reason::Masked;
    }
    if (c.in_callback) {
        return Reason::Callback;
    }
    if (status & 0x100) {
        return Reason::Pending;
    }
    if (c.dispatch_saved_ctx != 0 && c.mmu.read32(0x800000E4) != 0) {
        return Reason::Busy;
    }
    return Reason::Raised;
}

struct Observer {
    bool enabled = std::getenv("NWII_VI_TIMER_PROFILE") != nullptr;
    uint64_t period = 0;
    uint64_t registration_frequency = 0;
    uint64_t current_frequency = 0;
    uint64_t due = 0;
    uint64_t late = 0;
    uint64_t maximum_late = 0;
    uint64_t reasons[5] = {};

    void registration(uint64_t ticks, uint64_t frequency) {
        period = ticks;
        registration_frequency = frequency;
    }
    void record(Reason reason, uint64_t lateness, uint64_t frequency) {
        if (!enabled) {
            return;
        }
        ++due;
        ++reasons[static_cast<unsigned>(reason)];
        late += lateness;
        if (lateness > maximum_late) {
            maximum_late = lateness;
        }
        current_frequency = frequency;
        if (due % 60 == 0) {
            report();
        }
    }
    void report() const {
        std::fprintf(stderr, "[VI_TIMER] period=%llu registrationHz=%llu currentHz=%llu due=%llu lateTicks=%llu maxLate=%llu masked=%llu callback=%llu pending=%llu busy=%llu raised=%llu\n",
            (unsigned long long)period, (unsigned long long)registration_frequency,
            (unsigned long long)current_frequency, (unsigned long long)due,
            (unsigned long long)late, (unsigned long long)maximum_late,
            (unsigned long long)reasons[0], (unsigned long long)reasons[1],
            (unsigned long long)reasons[2], (unsigned long long)reasons[3],
            (unsigned long long)reasons[4]);
    }
    ~Observer() {
        if (enabled && due != 0) {
            report();
        }
    }
};
inline Observer& observer() {
    static Observer value;
    return value;
}
}
