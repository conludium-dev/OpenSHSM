#pragma once
#include <chrono>

namespace openshsm::experiment {
inline std::chrono::steady_clock::time_point host_sleep_deadline(
    std::chrono::steady_clock::time_point started, bool presented, bool headless) {
    const auto interval = presented || headless ? std::chrono::nanoseconds(16666667)
        : std::chrono::nanoseconds(1000000);
    return started + interval;
}
}
