#include "dec_clock_adapter.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    context.msr = 0x32;
    context.scriptedClock = true;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    if (experiment_read_dec(context) != 0xffffffff || context.dec_irq_pending) {
        return 1;
    }
    context.clockSamples = {1000,1001,1064,1123,1192,1251,1319};
    experiment_write_dec(context,0x7fffffff);
    if (context.dec_irq_pending || !context.decPollEvent) {
        return 2;
    }
    std::cout << "DEC_COUNTDOWN";
    for (unsigned index = 0; index < 6; ++index) {
        std::cout << ' ' << experiment_read_dec(context);
    }
    std::cout << '\n';
    context.clockSamples = {2000,2001,2002,2003,2006,2007,2008};
    context.clockSampleIndex = 0;
    experiment_write_dec(context,3);
    scheduler.advance(context,1);
    if (context.dec_irq_pending || experiment_read_dec(context) != 1) {
        return 3;
    }
    experiment_write_dec(context,4);
    scheduler.advance(context,2);
    if (context.dec_irq_pending) {
        return 4;
    }
    scheduler.advance(context,3);
    if (!context.dec_irq_pending || context.decPollEvent || experiment_read_dec(context) != 0xffffffff) {
        return 5;
    }
    unsigned refused = 0;
    auto refusal = [&](uint32_t value) {
        const auto oldValue = context.dec_value;
        const auto oldTime = context.dec_written_tb;
        const auto oldEvent = context.decPollEvent;
        const auto oldArmed = context.decCounterArmed;
        const auto oldPending = context.dec_irq_pending;
        try {
            experiment_write_dec(context,value);
            throw std::logic_error("DEC write unexpectedly accepted");
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (context.dec_value != oldValue || context.dec_written_tb != oldTime || context.decPollEvent != oldEvent ||
            context.decCounterArmed != oldArmed || context.dec_irq_pending != oldPending) {
            throw std::logic_error("DEC refusal changed counter state");
        }
    };
    refusal(1);
    context.dec_irq_pending = false;
    for (uint32_t value : {0u,0x80000000u,0xffffffffu}) {
        refusal(value);
    }
    for (uint32_t msr : {0x4032u,0x33u}) {
        context.msr = msr;
        refusal(1);
    }
    context.msr = 0x32;
    context.clockSamples = {2002};
    context.clockSampleIndex = 0;
    refusal(1);
    scheduler.reset();
    std::cout << "DEC_CONTRACT reprogram-expiry-latch-wrap guards=" << refused << '\n';
}
