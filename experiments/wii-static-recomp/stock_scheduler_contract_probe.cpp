#include "runtime/event_scheduler.h"
#include "runtime/cpu_context.h"
#include <cstdio>
#include <memory>
#include <stdexcept>

int main() {
    auto ctx = std::make_unique<nwii::runtime::CPUContext>();
    auto& scheduler = nwii::runtime::EventScheduler::get();
    auto record = [&](unsigned tag) {
        return [&, tag](auto& context, uint64_t late) {
            context.gpr[3] += tag;
            std::printf("EVENT %u %llu %llu %u\n", tag,
                static_cast<unsigned long long>(late), static_cast<unsigned long long>(scheduler.now()), context.gpr[3]);
        };
    };
    scheduler.reset();
    scheduler.schedule_at(10, record(1));
    scheduler.schedule_after(10, record(2));
    scheduler.advance(*ctx, 9);
    if (ctx->gpr[3] != 0) { return 1; }
    scheduler.advance(*ctx, 10);
    scheduler.advance(*ctx, 5);
    if (scheduler.now() != 10 || ctx->gpr[3] != 3) { return 2; }
    scheduler.schedule_at(5, record(3));
    scheduler.schedule_after(0, record(4));
    scheduler.advance(*ctx, 10);
    if (ctx->gpr[3] != 10) { return 3; }
    scheduler.reset();
    auto recurring = scheduler.schedule_recurring(10, record(5));
    scheduler.advance(*ctx, 35);
    scheduler.advance(*ctx, 44);
    scheduler.advance(*ctx, 45);
    if (!scheduler.cancel(recurring) || scheduler.cancel(recurring)) { return 4; }
    scheduler.advance(*ctx, 100);
    if (ctx->gpr[3] != 20) { return 5; }
    scheduler.reset();
    nwii::runtime::EventScheduler::EventId self = 0;
    self = scheduler.schedule_recurring(0, [&](auto& context, uint64_t late) {
        record(6)(context, late);
        if (!scheduler.cancel(self)) { throw std::runtime_error("self cancel"); }
    });
    scheduler.advance(*ctx, 1);
    scheduler.advance(*ctx, 2);
    if (ctx->gpr[3] != 26) { return 6; }
    scheduler.reset();
    scheduler.schedule_after(10, [&](auto& context, uint64_t late) {
        record(7)(context, late);
        scheduler.schedule_at(15, record(8));
        scheduler.advance(context, 20);
        scheduler.schedule_after(0, record(9));
    });
    scheduler.advance(*ctx, 10);
    if (ctx->gpr[3] != 50 || scheduler.now() != 20) { return 7; }
    scheduler.reset();
    nwii::runtime::EventScheduler::EventId ids[100]{};
    unsigned total = 50;
    for (unsigned i = 0; i < 100; ++i) {
        ids[i] = scheduler.schedule_at((i * 37) % 101, record(100 + i));
        if (i % 2) { total += 100 + i; }
    }
    for (unsigned i = 0; i < 100; i += 2) {
        if (!scheduler.cancel(ids[i])) { return 8; }
    }
    scheduler.advance(*ctx, 1000);
    if (ctx->gpr[3] != total || scheduler.cancel(0)) { return 9; }
    scheduler.reset();
    scheduler.schedule_at(1, [](auto&, auto) { throw std::runtime_error("contract"); });
    try {
        scheduler.advance(*ctx, 1);
        return 10;
    } catch (const std::runtime_error&) {
    }
    scheduler.schedule_at(2, record(10));
    scheduler.advance(*ctx, 3);
    if (ctx->gpr[3] != total || scheduler.now() != 3) { return 11; }
    scheduler.reset();
    scheduler.schedule_after(0, record(11));
    scheduler.advance(*ctx, 0);
    if (ctx->gpr[3] != total + 11) { return 12; }
    std::puts("SCHEDULER_ORDER_CANCEL_LATE_REENTRANT_EXCEPTION_RESET_PASS");
}
