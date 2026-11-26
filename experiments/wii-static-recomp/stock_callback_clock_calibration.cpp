#include "stock_callback_profile.h"
#include <cstdio>

struct CalibrationContext {
    volatile uint32_t msr = 0x8000;
    volatile bool in_callback = false;
};

int main() {
    CalibrationContext ctx;
    if (!stock_callback_profile::enabled()) { return 1; }
    constexpr uint64_t calls = 2097152;
    for (uint64_t i = 0; i < calls; ++i) {
        const auto ticket = stock_callback_profile::enter(ctx);
        if (stock_callback_profile::leave(ticket, false)) { return 2; }
    }
    const auto values = stock_callback_profile::stats();
    if (values[0] != calls || values[1] != calls || values[2] || values[3] || values[4] ||
        values[5] != 2048 || values[6] != 2048 || values[8] || values[9]) { return 3; }
    std::printf("EMPTY_CALLBACK_CLOCK_CALIBRATION_PASS %llu %llu\n",
        static_cast<unsigned long long>(values[6]), static_cast<unsigned long long>(values[7]));
}
