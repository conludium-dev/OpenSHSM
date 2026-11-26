#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include "stock_audio_refill.h"
#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main(int argc, char** argv) {
    assert(argc == 3);
    const std::string mode(argv[1]);
    const uint64_t frequency = std::stoull(argv[2]);
    assert(mode == "steady" || mode == "slow" || mode == "stall");
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    g_ctx_ptr = &ctx;
    g_mmu = &ctx.mmu;
    ctx.tb_freq = frequency;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_ai(mmio);
    hw::register_dsp(mmio);
    mmio.write32(0xCC006C00, 0x40);
    for (unsigned i = 0; i < 192; ++i) {
        ctx.mmu.write16(0x80560000 + i * 2, uint16_t(int16_t(int(i) * 113 - 12000)));
    }
    mmio.write16(0xCC005030, 0x56);
    mmio.write16(0xCC005032, 0);
    mmio.write16(0xCC005036, 0x800C);
    uint64_t time_us = 64000;
    scheduler.advance(ctx, time_us * frequency / 1000000);
    uint32_t device_frames = 0;
    uint64_t missing_frames = 0;
    std::vector<int16_t> enqueued;
    auto refill = [&] {
        return openshsm::experiment::refill_audio(
            [&] { return device_frames * 4; },
            [&](int16_t* data, uint32_t count) { return hw::dsp_audio_pull(data, count); },
            [&](const int16_t* data, uint32_t count) {
                enqueued.insert(enqueued.end(), data, data + count * 2);
                device_frames += count;
                assert(device_frames <= 2048);
                return 0;
            }, [](uint32_t, size_t, bool, bool, size_t) {});
    };
    assert(refill().queued == 2048);
    const uint32_t interval_us = mode == "steady" ? 16000 : mode == "slow" ? 96000 : 1200000;
    const unsigned iterations = mode == "steady" ? 64 : mode == "slow" ? 16 : 1;
    for (unsigned i = 0; i < iterations; ++i) {
        const uint32_t demand = uint32_t(uint64_t(interval_us) * 32000 / 1000000);
        const uint32_t consumed = std::min(device_frames, demand);
        device_frames -= consumed;
        missing_frames += demand - consumed;
        time_us += interval_us;
        scheduler.advance(ctx, time_us * frequency / 1000000);
        const auto result = refill();
        assert(result.errors == 0 && result.supplied == result.queued);
    }
    mmio.write16(0xCC005036, 12);
    for (;;) {
        device_frames = 0;
        if (!refill().queued) {
            break;
        }
    }
    const uint64_t produced = time_us * 32000 / 1000000;
    const uint64_t lost = produced - enqueued.size() / 2;
    assert(lost == (mode == "stall" ? 6400 : 0));
    assert(missing_frames == (mode == "steady" ? 0 : mode == "slow" ? 16384 : 36352));
    for (size_t i = 0; i < enqueued.size(); ++i) {
        assert(enqueued[i] == int16_t(int(i % 192) * 113 - 12000));
    }
    std::cout << "AUDIO_CADENCE_PASS mode=" << mode << " produced=" << produced
              << " supplied=" << enqueued.size() / 2 << " lost=" << lost
              << " deviceMissing=" << missing_frames << '\n';
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
