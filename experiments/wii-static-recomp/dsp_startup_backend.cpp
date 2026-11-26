#include "dsp_startup_backend.h"
#include "timebase_adapter.h"
#include <stdexcept>

namespace nwii::runtime {
class ExperimentDspScheduler {
public:
    static ExperimentDspScheduler& get() {
        static ExperimentDspScheduler instance;
        return instance;
    }
    EventScheduler::EventId schedule_after(uint64_t delay, EventScheduler::Callback callback);
    EventScheduler::EventId schedule_recurring(uint64_t period, EventScheduler::Callback callback) {
        return EventScheduler::get().schedule_recurring(period, std::move(callback));
    }
    bool cancel(EventScheduler::EventId id) { return EventScheduler::get().cancel(id); }
};
}

#define EventScheduler ExperimentDspScheduler
#include "hw_dsp.cpp"
#undef EventScheduler

namespace nwii::runtime {
EventScheduler::EventId ExperimentDspScheduler::schedule_after(uint64_t delay, EventScheduler::Callback callback) {
    if (!hw::experimentDspStartup.enabled) {
        return EventScheduler::get().schedule_after(delay, std::move(callback));
    }
    if (!hw::experimentDspStartup.schedulingDma || hw::ar_cnt != 32) {
        throw std::runtime_error("Unverified DSP event producer");
    }
    return EventScheduler::get().schedule_after(delay, [callback](CPUContext& context, uint64_t late) {
        if (hw::experimentDspStartup.lostDma) { return; }
        callback(context, late);
        hw::ar_mmaddr += 32;
        hw::ar_araddr += 32;
        ++hw::experimentDspStartup.completedDmas;
    });
}
}

namespace nwii::runtime::hw {
ExperimentDspStartup experimentDspStartup;

void experiment_dsp_startup_reset() {
    experimentDspStartup = {};
    dsp_control = 4;
    dsp_mbox_cpu_hi = dsp_mbox_cpu_lo = dsp_mbox_dsp_hi = dsp_mbox_dsp_lo = 0;
    ar_mmaddr = ar_araddr = ar_cnt = 0;
    ar_size = 0;
}

static void advance(CPUContext& context) {
    if (!experimentDspStartup.enabled || context.msr != 0x2032 || context.tb_freq != 60750000) {
        throw std::runtime_error("DSP startup CPU/profile unverified");
    }
    EventScheduler::get().advance(context, experiment_read_timebase(context));
}

uint32_t experiment_dsp_startup_read(CPUContext& context, uint32_t address, unsigned width) {
    if (width != 2 || (address != 0xcc00500a && address != 0xcc005004 && address != 0xcc005006 && address != 0xcc005012
        && address != 0xcc005020 && address != 0xcc005022 && address != 0xcc005024 && address != 0xcc005026
        && address != 0xcc005028 && address != 0xcc00502a)) {
        throw std::runtime_error("DSP startup read unverified");
    }
    advance(context);
    return MMIODispatcher::get().read16(address);
}

void experiment_dsp_startup_write(CPUContext& context, uint32_t address, uint32_t value, unsigned width) {
    static constexpr std::array<std::array<uint32_t, 3>, 17> commands{{
        {0xcc005012, 0x43, 2}, {0xcc00500a, 0x8ac, 2}, {0xcc00500a, 0x805, 2}, {0xcc005000, 0, 2},
        {0xcc005020, 0x01000000, 4}, {0xcc005024, 0, 4}, {0xcc005028, 32, 4}, {0xcc00500a, 0x824, 2},
        {0xcc005020, 0x01000000, 4}, {0xcc005024, 0, 4}, {0xcc005028, 32, 4}, {0xcc00500a, 0x824, 2},
        {0xcc00500a, 4, 2}, {0xcc00500a, 0, 2}, {0xcc00500a, 4, 2}, {0xcc00500a, 0x8ac, 2}, {0xcc00500a, 0x805, 2}
    }};
    if (!experimentDspStartup.enabled || experimentDspStartup.command >= commands.size() ||
        commands[experimentDspStartup.command] != std::array<uint32_t, 3>{address, value, width}) {
        throw std::runtime_error("DSP startup command/width/order unverified");
    }
    advance(context);
    if (address == 0xcc00500a) {
        if (value == 0x824 && !(dsp_control & 0x20)) {
            throw std::runtime_error("DSP DMA acknowledgement without completion");
        }
        const uint16_t prior = dsp_control;
        const bool releaseHalt = (prior & 4) && !(value & 4);
        if (releaseHalt && (experimentDspStartup.completedDmas != 2 || ar_cnt || context.mmu.mem2.size() < 32 ||
            !context.mmu.get_ptr(0x8042bca0) || !context.mmu.get_ptr(0x8042bcbf) ||
            !std::equal(context.mmu.mem2.begin(), context.mmu.mem2.begin() + 32, context.mmu.get_ptr(0x8042bca0)))) {
            throw std::runtime_error("DSP boot image/transfer contract unverified");
        }
        dsp_control = (prior & CSR_INT_BITS & ~value) | (value & ~CSR_INT_BITS);
        dsp_update_pi();
        if (value & 1) {
            EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) { dsp_control &= ~1u; dsp_update_pi(); });
        }
        if (releaseHalt) {
            if (!experimentDspStartup.lostMail) {
                EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) {
                    dsp_mbox_dsp_hi = 0x8054;
                    dsp_mbox_dsp_lo = experimentDspStartup.wrongMail ? 0x4349 : 0x4348;
                });
            }
        }
    } else if (address == 0xcc005028) {
        if (ar_mmaddr != 0x01000000 || ar_araddr || ar_cnt || g_mmu || g_ctx_ptr ||
            context.mmu.mem1.size() < 0x01000020 || context.mmu.mem2.size() < 32) {
            throw std::runtime_error("DSP DMA range/owner unverified");
        }
        ar_cnt = value;
        MMU* previous = g_mmu;
        g_mmu = &context.mmu;
        experimentDspStartup.schedulingDma = true;
        try { ar_dma_execute(); } catch (...) {
            experimentDspStartup.schedulingDma = false;
            g_mmu = previous;
            throw;
        }
        experimentDspStartup.schedulingDma = false;
        g_mmu = previous;
    } else {
        if (width == 2) { MMIODispatcher::get().write16(address, value); }
        else { MMIODispatcher::get().write32(address, value); }
    }
    ++experimentDspStartup.command;
}
}
