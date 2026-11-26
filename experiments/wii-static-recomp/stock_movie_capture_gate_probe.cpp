#include "stock_movie_capture_gate.h"
#include <cstdio>
#include <initializer_list>

int main() {
    using stock_movie_capture_gate::Gate;
    for (const char* text : {"", "-1", "+1", " 1", "1x", "180001", "999999999999999999999999999"}) {
        Gate gate(text);
        if (gate.valid || gate.accept(0) || gate.accept(UINT64_MAX)) {
            return 1;
        }
    }
    Gate disabled(nullptr);
    Gate zero("0");
    if (!disabled.accept(0) || !disabled.accept(UINT64_MAX) || !zero.accept(0)) {
        return 2;
    }
    Gate delayed("70000");
    if (delayed.accept(100) || delayed.accept(70000099) || !delayed.accept(70000100) ||
        !delayed.accept(70000101) || delayed.accept(99)) {
        return 3;
    }
    Gate maximum("180000");
    if (!maximum.valid || maximum.delay_us != 180000000) {
        return 4;
    }
    Gate overflow_clock("1");
    if (overflow_clock.accept(UINT64_MAX - 500) || overflow_clock.accept(500)) {
        return 5;
    }
    std::puts("MOVIE_CAPTURE_DELAY_BOUNDARY_INVALID_CLOCK_PASS");
}
