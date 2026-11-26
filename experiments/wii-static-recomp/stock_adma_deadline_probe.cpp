#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main(int argc, char** argv) {
    assert(argc == 6);
    const std::string mode(argv[1]);
    const unsigned chunks = unsigned(std::stoul(argv[2]));
    const uint64_t frequency = std::stoull(argv[3]);
    const unsigned rate = unsigned(std::stoul(argv[4]));
    assert(chunks > 0 && chunks <= 6000 && (rate == 32000 || rate == 48000));
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    g_ctx_ptr = &ctx;
    g_mmu = &ctx.mmu;
    ctx.tb_freq = frequency;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    std::vector<unsigned> legacy_order;
    scheduler.schedule_after(0, [&](CPUContext&, uint64_t) { legacy_order.push_back(0); });
    const auto recurring = scheduler.schedule_recurring(5, [&](CPUContext&, uint64_t) { legacy_order.push_back(5); });
    scheduler.schedule_after(10, [&](CPUContext&, uint64_t) {
        legacy_order.push_back(10);
        scheduler.schedule_after(0, [&](CPUContext&, uint64_t) { legacy_order.push_back(20); });
    });
    scheduler.advance(ctx, 20);
    assert((legacy_order == std::vector<unsigned>{0, 5, 10, 20}));
    assert(scheduler.cancel(recurring));
    scheduler.advance(ctx, 25);
    assert(legacy_order.size() == 4);
    scheduler.reset();
    std::cout << "LEGACY_EVENT_API_ORDER_CANCEL_PASS size=" << sizeof(EventScheduler) << '\n';
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_ai(mmio);
    hw::register_dsp(mmio);
    mmio.write32(0xCC006C00, rate == 32000 ? 0x40 : 0);
    for (unsigned i = 0; i < 192; ++i) {
        ctx.mmu.write16(0x80560000 + i * 2, uint16_t(int16_t(int(i) * 113 - 12000)));
    }
    mmio.write16(0xCC005030, 0x56);
    mmio.write16(0xCC005032, 0);
    mmio.write16(0xCC005036, 0x800C);
    if (mode == "stop-regular" || mode == "stop-batched") {
        scheduler.schedule_after(frequency * 8 * 3 / rate + 1, [&](CPUContext&, uint64_t) {
            mmio.write16(0xCC005036, 12);
        });
    }
    const bool stopped = mode == "stop-regular" || mode == "stop-batched";
    if (mode == "regular" || mode == "stop-regular") {
        for (unsigned i = 1; i <= chunks; ++i) {
            scheduler.advance(ctx, uint64_t(i) * frequency * 8 / rate);
        }
    } else {
        scheduler.advance(ctx, uint64_t(chunks) * frequency * 8 / rate);
    }
    const unsigned left = mmio.read16(0xCC00503A);
    const unsigned interrupt = mmio.read16(0xCC00500A) & 8;
    if (mode == "baseline-loss") {
        assert(rate == 32000 && chunks == 10 && left == 9);
    } else {
        assert(left == (stopped ? 8 : 11 - chunks % 12));
    }
    mmio.write16(0xCC005036, 12);
    std::vector<int16_t> pcm;
    for (;;) {
        int16_t samples[2048];
        const auto supplied = hw::dsp_audio_pull(samples, 1024);
        if (!supplied) {
            break;
        }
        pcm.insert(pcm.end(), samples, samples + supplied * 2);
    }
    if (rate == 32000) {
        const unsigned expected = mode == "baseline-loss" ? 16 : (stopped ? 24 : chunks * 8);
        assert(pcm.size() == expected * 2);
        for (unsigned i = 0; i < pcm.size(); ++i) {
            assert(pcm[i] == int16_t(int(i % 192) * 113 - 12000));
        }
    }
    auto* file = std::fopen(argv[5], "wb");
    assert(file && std::fwrite(pcm.data(), sizeof(int16_t), pcm.size(), file) == pcm.size());
    assert(std::fclose(file) == 0);
    std::cout << "ADMA_DEADLINE_CASE mode=" << mode << " chunks=" << chunks << " frames=" << pcm.size() / 2
              << " left=" << left << " interrupt=" << interrupt << '\n';
    scheduler.advance(ctx, frequency * 2);
    int16_t empty[16];
    assert(hw::dsp_audio_pull(empty, 8) == 0);
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
