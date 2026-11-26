#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include <array>
#include <cassert>
#include <iostream>
#include <memory>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    g_ctx_ptr = &ctx;
    g_mmu = &ctx.mmu;
    ctx.tb_freq = 60750000;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_dsp(mmio);
    constexpr uint32_t address = 0x80560000;
    std::array<int16_t, 192> expected{};
    for (unsigned i = 0; i < expected.size(); ++i) {
        expected[i] = int16_t(int(i) * 113 - 16000);
        ctx.mmu.write16(address + i * 2, uint16_t(expected[i]));
    }
    std::array<int16_t, 256> pcm{};
    assert(hw::dsp_audio_pull(pcm.data(), 128) == 0);
    for (auto value : pcm) {
        assert(value == 0);
    }
    mmio.write16(0xCC005030, 0x56);
    mmio.write16(0xCC005032, 0);
    mmio.write16(0xCC005036, 0x800C);
    const uint64_t period = ctx.tb_freq / 200;
    scheduler.advance(ctx, period - 1);
    assert(hw::dsp_audio_pull(pcm.data(), 128) == 0);
    scheduler.advance(ctx, period);
    assert(hw::dsp_audio_pull(pcm.data(), 64) == 64);
    for (unsigned i = 0; i < 128; ++i) {
        assert(pcm[i] == expected[i]);
    }
    assert(hw::dsp_audio_pull(pcm.data(), 64) == 32);
    for (unsigned i = 0; i < 64; ++i) {
        assert(pcm[i] == expected[i + 128] && pcm[i + 64] == 0);
    }
    scheduler.advance(ctx, period * 10);
    mmio.write16(0xCC005036, 0);
    scheduler.advance(ctx, period * 20);
    assert(hw::dsp_audio_pull(pcm.data(), 128) == 96);
    for (unsigned i = 0; i < pcm.size(); ++i) {
        assert(pcm[i] == (i < expected.size() ? expected[i] : 0));
    }
    for (unsigned i = 0; i < expected.size(); ++i) {
        assert(ctx.mmu.read16(address + i * 2) == uint16_t(expected[i]));
    }
    std::cout << "DSP_SUPPLY_PCM_SCHEDULE_NONMUTATION_PASS\n";
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
