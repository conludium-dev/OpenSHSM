#pragma once
#include "timebase_adapter.h"
#include "runtime/event_scheduler.h"

namespace nwii::runtime {
inline uint32_t experiment_read_dec(CPUContext& base) {
    auto& context = static_cast<ClockContext&>(base);
    if (context.msr & 0x4001) {
        throw std::runtime_error("DEC privileged/endian profile unavailable");
    }
    if (!context.decCounterArmed) {
        return 0xffffffff;
    }
    const uint64_t now = experiment_read_timebase(context);
    if (now < context.dec_written_tb) {
        throw std::runtime_error("DEC clock moved backwards");
    }
    return uint32_t(context.dec_value - (now - context.dec_written_tb));
}
inline void experiment_dec_event(CPUContext& base) {
    auto& context = static_cast<ClockContext&>(base);
    if (!context.decCounterArmed || !context.decPollEvent) {
        throw std::runtime_error("DEC event without armed counter");
    }
    const uint64_t now = experiment_read_timebase(context);
    if (now < context.dec_written_tb) {
        throw std::runtime_error("DEC event clock moved backwards");
    }
    if (now - context.dec_written_tb >= context.dec_value) {
        context.dec_irq_pending = true;
        EventScheduler::get().cancel(context.decPollEvent);
        context.decPollEvent = 0;
    }
}
inline void experiment_write_dec(CPUContext& base,uint32_t value) {
    auto& context = static_cast<ClockContext&>(base);
    if ((context.msr & 0x4001) || !value || (value & 0x80000000) || context.dec_irq_pending) {
        throw std::runtime_error("DEC write/latched IRQ profile not verified");
    }
    const uint64_t now = experiment_read_timebase(context);
    if (context.decCounterArmed && now < context.dec_written_tb) {
        throw std::runtime_error("DEC reprogramming clock moved backwards");
    }
    if (context.decPollEvent) {
        if (!EventScheduler::get().cancel(context.decPollEvent)) {
            throw std::runtime_error("DEC scheduled owner missing");
        }
    }
    context.dec_value = value;
    context.dec_written_tb = now;
    context.decCounterArmed = true;
    context.decPollEvent = EventScheduler::get().schedule_recurring(1,[owner = &context](CPUContext& active,uint64_t) {
        if (&active != owner) {
            throw std::runtime_error("DEC event context owner mismatch");
        }
        experiment_dec_event(active);
    });
}
}
