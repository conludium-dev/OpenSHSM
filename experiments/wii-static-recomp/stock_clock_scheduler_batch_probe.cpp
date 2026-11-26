#include "runtime/cpu_context.h"
#include "runtime/event_scheduler.h"
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <time.h>

using nwii::runtime::CPUContext;
using nwii::runtime::EventScheduler;

static uint64_t clock_ns(clockid_t clock) {
    timespec value{};
    if (clock_gettime(clock, &value) != 0) { std::abort(); }
    return uint64_t(value.tv_sec) * 1000000000 + uint64_t(value.tv_nsec);
}

__attribute__((noinline)) static uint64_t empty(CPUContext&, EventScheduler&, uint64_t i) {
    return i;
}
__attribute__((noinline)) static uint64_t timebase(CPUContext& ctx, EventScheduler&, uint64_t) {
    return ctx.read_timebase();
}
__attribute__((noinline)) static uint64_t advance(CPUContext& ctx, EventScheduler& scheduler, uint64_t i) {
    scheduler.advance(ctx, i);
    return scheduler.now();
}
__attribute__((noinline)) static uint64_t combined(CPUContext& ctx, EventScheduler& scheduler, uint64_t) {
    scheduler.advance(ctx, ctx.read_timebase());
    return scheduler.now();
}
__attribute__((noinline)) static uint64_t callbacks(CPUContext& ctx, EventScheduler&, uint64_t) {
    ++ctx.inst_count;
    if (nwii::runtime::process_pending_callbacks(ctx)) { std::abort(); }
    return ctx.pc;
}

int main() {
    std::setvbuf(stdout, nullptr, _IOLBF, 0);
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    auto& scheduler = EventScheduler::get();
    ctx.tb_freq = 60750000;
    ctx.pc = 0x80209D80;
    ctx.lr = 0x8009C5E4;
    ctx.is_running = true;
    ctx.inst_count = 12345;
    constexpr uint64_t calls = 262144;
    struct Case {
        const char* name;
        uint64_t (*function)(CPUContext&, EventScheduler&, uint64_t);
        unsigned policy;
    };
    const Case cases[] = {
        {"empty", empty, 0}, {"timebase", timebase, 0},
        {"advance-empty", advance, 0}, {"advance-notdue", advance, 1},
        {"combined-empty", combined, 0}, {"combined-notdue", combined, 1},
        {"combined-vi-period", combined, 2},
        {"callbacks-ee0", callbacks, 3}, {"callbacks-ee1", callbacks, 4},
        {"callbacks-ee0-dec-pending", callbacks, 5}, {"callbacks-ee1-dec-pending", callbacks, 6}
    };
    volatile uint64_t sink = 0;
    for (unsigned repeat = 0; repeat < 5; ++repeat) {
        for (unsigned step = 0; step < sizeof(cases) / sizeof(cases[0]); ++step) {
            const unsigned index = repeat % 2 ? unsigned(sizeof(cases) / sizeof(cases[0]) - 1 - step) : step;
            const auto& item = cases[index];
            scheduler.reset();
            uint64_t firings = 0;
            ctx.msr = item.policy == 4 || item.policy == 6 ? 0xA032 : 0x2032;
            ctx.dec_irq_pending = item.policy >= 5;
            ctx.dec_value = UINT32_MAX;
            ctx.dec_written_tb = ctx.read_timebase();
            if (item.policy == 1) {
                scheduler.schedule_at(UINT64_MAX, [&](auto&, auto) { std::abort(); });
            } else if (item.policy == 2) {
                scheduler.schedule_recurring(ctx.tb_freq / 60, [&](auto&, auto) { ++firings; });
            }
            for (uint64_t i = 0; i < 1024; ++i) {
                sink = sink + item.function(ctx, scheduler, i);
            }
            const auto wall_start = clock_ns(CLOCK_MONOTONIC_RAW);
            const auto cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
            for (uint64_t i = 1024; i < 1024 + calls; ++i) {
                sink = sink + item.function(ctx, scheduler, i);
            }
            const auto cpu_end = clock_ns(CLOCK_THREAD_CPUTIME_ID);
            const auto wall_end = clock_ns(CLOCK_MONOTONIC_RAW);
            if (ctx.pc != 0x80209D80 || ctx.lr != 0x8009C5E4 || ctx.pending_cb_count.load() ||
                ctx.in_callback || ctx.callback_depth || ctx.dispatch_saved_ctx) { return 1; }
            std::printf("BATCH %u %s %llu %llu %llu %llu\n", repeat, item.name,
                static_cast<unsigned long long>(calls), static_cast<unsigned long long>(wall_end - wall_start),
                static_cast<unsigned long long>(cpu_end - cpu_start), static_cast<unsigned long long>(firings));
        }
    }
    std::printf("CLOCK_SCHEDULER_NATIVE_BATCH_PASS %llu\n", static_cast<unsigned long long>(sink));
}
