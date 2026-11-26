#include "timebase_adapter.h"
#define main unused_frontend_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    assert(experiment_ticks_from_ns(0) == 0);
    assert(experiment_ticks_from_ns(1000) == 60);
    assert(experiment_ticks_from_ns(1000000000) == 60750000);
    assert(experiment_ticks_from_ns(1000000001) == 60750000);
    ClockContext context;
    uint64_t prior = experiment_read_timebase(context);
    for (unsigned index = 0; index < 1000; ++index) {
        uint64_t next = experiment_read_timebase(context);
        assert(next >= prior);
        prior = next;
    }
    unsigned refusals = 0;
    context.scriptedClock = true;
    try {
        experiment_read_timebase(context);
    } catch (const std::runtime_error&) {
        ++refusals;
    }
    context.scriptedClock = false;
    context.tb_freq = 40500000;
    try {
        experiment_read_timebase(context);
    } catch (const std::runtime_error&) {
        ++refusals;
    }
    context.tb_freq = 60750000;
    context.tb_start = std::chrono::steady_clock::now() + std::chrono::hours(1);
    try {
        experiment_read_timebase(context);
    } catch (const std::runtime_error&) {
        ++refusals;
    }
    assert(refusals == 3);
    std::cout << "TIMEBASE_CONTRACT conversion monotonic1000 guards3 PASS\n";
}
