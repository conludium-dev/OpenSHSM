#include <processor_adapter.h>
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include <array>
#include <memory>
#include <cstdio>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<ProcessorContext>();
    auto& ctx = *owned;
    g_mmu = &ctx.mmu;
    g_ctx_ptr = &ctx;
    ctx.tb_freq = 60750000;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_dsp(mmio);
    mmio.write16(0xcc00500a, 0x0100);
    const auto mail = [&](uint32_t value) {
        mmio.write16(0xcc005000, uint16_t(value >> 16));
        mmio.write16(0xcc005002, uint16_t(value));
    };
    constexpr uint32_t base = 0x80560000;
    std::array<uint32_t, 128> before{};
    for (unsigned i = 0; i < before.size(); ++i) {
        before[i] = 0x13579bdfu ^ (i * 0x1020304u);
        ctx.mmu.write32(base + i * 4, before[i]);
    }
    unsigned replies = 0;
    uint64_t ticks = 0;
    for (uint32_t pointer : {base, base + 64, 0xfffffffcu}) {
        mail(0xbabe0080);
        mail(pointer);
        ticks += ctx.tb_freq / 1000 + 1;
        scheduler.advance(ctx, ticks);
        const uint32_t reply = uint32_t(mmio.read16(0xcc005004)) << 16 | mmio.read16(0xcc005006);
        if (reply != 0xdcd10002) {
            std::fprintf(stderr, "unexpected reply %08x\n", reply);
            return 2;
        }
        ++replies;
        for (unsigned i = 0; i < before.size(); ++i) {
            if (ctx.mmu.read32(base + i * 4) != before[i]) {
                return 3;
            }
        }
        std::array<int16_t, 64> samples{};
        if (hw::dsp_audio_pull(samples.data(), samples.size() / 2) != 0) {
            return 4;
        }
    }
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
    std::printf("CURRENT_DSP_MAIL_ACK_WITHOUT_LIST_EXECUTION_REPRODUCED %u replies; invalid pointer also acknowledged; RAM unchanged; PCM empty\n", replies);
}
