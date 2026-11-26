#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include "functions.h"
#include <SDL.h>
#include <array>
#include <cassert>
#include <iostream>
#include <memory>
#include <vector>

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
    ctx.gpr[1] = 0x816F0000;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_ai(mmio);
    hw::register_dsp(mmio);
    mmio.write32(0xCC006C00, 0x40);
    for (unsigned i = 0; i < 32; ++i) {
        ctx.mmu.write16(0x80560000 + i * 2, uint16_t(int16_t(int(i) * 71 - 900)));
        ctx.mmu.write16(0x80560100 + i * 2, uint16_t(int16_t(int(i) * 43 + 3000)));
    }
    auto invoke = [&](uint32_t pc, auto function) {
        ctx.pc = pc;
        ctx.lr = 0x807F0000;
        ctx.msr = 0;
        function(ctx);
        assert(ctx.pc == 0x807F0000 && ctx.gpr[1] == 0x816F0000);
    };
    ctx.gpr[3] = 0x560000;
    ctx.gpr[4] = 64;
    invoke(0x8022CAB0, func_8022CAB0);
    scheduler.reset();
    mmio.write16(0xCC00500A, 0x10);
    mmio.write16(0xCC005036, 0x8002);
    assert(mmio.read16(0xCC00503A) == 1);
    scheduler.advance(ctx, 16);
    assert(!(mmio.read16(0xCC00500A) & 8));
    scheduler.advance(ctx, 17);
    assert(mmio.read16(0xCC00500A) & 8);
    mmio.write16(0xCC00500A, 0x18);
    invoke(0x8022CB70, func_8022CB70);
    assert(ctx.gpr[3] == 32);
    scheduler.advance(ctx, 15186);
    std::array<int16_t, 2048> pcm{};
    assert(hw::dsp_audio_pull(pcm.data(), 8) == 0);
    scheduler.advance(ctx, 15187);
    assert(hw::dsp_audio_pull(pcm.data(), 8) == 8);
    for (unsigned i = 0; i < 16; ++i) {
        assert(pcm[i] == int(i) * 71 - 900);
    }
    invoke(0x8022CB70, func_8022CB70);
    assert(ctx.gpr[3] == 0 && !(mmio.read16(0xCC00500A) & 8));
    ctx.gpr[3] = 0x560100;
    ctx.gpr[4] = 32;
    invoke(0x8022CAB0, func_8022CAB0);
    scheduler.advance(ctx, 30375);
    assert(hw::dsp_audio_pull(pcm.data(), 8) == 8);
    for (unsigned i = 0; i < 16; ++i) {
        assert(pcm[i] == int(i + 16) * 71 - 900);
    }
    assert(mmio.read16(0xCC00500A) & 8);
    scheduler.advance(ctx, 45562);
    assert(hw::dsp_audio_pull(pcm.data(), 8) == 8);
    for (unsigned i = 0; i < 16; ++i) {
        assert(pcm[i] == int(i) * 43 + 3000);
    }
    invoke(0x8022CB50, func_8022CB50);
    scheduler.advance(ctx, 60750000);
    assert(hw::dsp_audio_pull(pcm.data(), 8) == 0);

    scheduler.reset();
    mmio.write32(0xCC006C00, 0);
    for (unsigned i = 0; i < 16; i += 2) {
        ctx.mmu.write16(0x80560100 + i * 2, 1000);
        ctx.mmu.write16(0x80560100 + i * 2 + 2, uint16_t(int16_t(-2000)));
    }
    mmio.write16(0xCC005036, 0x8001);
    std::vector<int16_t> converted;
    for (unsigned i = 1; i <= 6000; ++i) {
        scheduler.advance(ctx, uint64_t(i) * 10125);
        const auto supplied = hw::dsp_audio_pull(pcm.data(), 1024);
        converted.insert(converted.end(), pcm.begin(), pcm.begin() + supplied * 2);
    }
    mmio.write16(0xCC005036, 1);
    for (;;) {
        const auto supplied = hw::dsp_audio_pull(pcm.data(), 1024);
        if (!supplied) {
            break;
        }
        converted.insert(converted.end(), pcm.begin(), pcm.begin() + supplied * 2);
    }
    std::vector<int16_t> raw(48000 * 2), reference(32000 * 2 + 2048);
    for (unsigned i = 0; i < raw.size(); i += 2) {
        raw[i] = 1000;
        raw[i + 1] = -2000;
    }
    auto* stream = SDL_NewAudioStream(AUDIO_S16SYS, 2, 48000, AUDIO_S16SYS, 2, 32000);
    assert(stream);
    for (unsigned i = 0; i < 6000; ++i) {
        assert(SDL_AudioStreamPut(stream, raw.data() + i * 16, 32) == 0);
    }
    assert(SDL_AudioStreamFlush(stream) == 0);
    const int bytes = SDL_AudioStreamGet(stream, reference.data(), int(reference.size() * 2));
    assert(bytes >= 0 && bytes % 4 == 0);
    reference.resize(bytes / 2);
    SDL_FreeAudioStream(stream);
    if (converted != reference) {
        size_t first = 0, different = 0;
        int maximum = 0;
        for (size_t i = 0; i < std::min(converted.size(), reference.size()); ++i) {
            const int error = std::abs(int(converted[i]) - int(reference[i]));
            if (error) {
                if (!different) {
                    first = i;
                }
                ++different;
                maximum = std::max(maximum, error);
            }
        }
        std::cerr << "CONVERSION_DIFFERENCE actual=" << converted.size() << " reference=" << reference.size()
                  << " first=" << first << " different=" << different << " max=" << maximum << '\n';
    }
    assert(converted == reference);
    mmio.write16(0xCC005036, 0x8001);
    mmio.write16(0xCC00500A, 1);
    scheduler.advance(ctx, 2 * 60750000);
    assert(mmio.read16(0xCC005036) == 0 && hw::dsp_audio_pull(pcm.data(), 1024) == 0);
    std::cout << "ADMA_CHUNKS_SDK_PCM_IRQ_RATE_PASS convertedFrames=" << converted.size() / 2 << '\n';
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
