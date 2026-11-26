#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/event_scheduler.h"
#include "functions.h"
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
    ctx.gpr[1] = 0x816F0000;
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_dsp(mmio);
    EventScheduler::get().reset();
    unsigned cases = 0;
    auto invoke = [&](uint32_t pc, auto function) {
        ctx.pc = pc;
        ctx.lr = 0x807F0000;
        ctx.msr = 0;
        function(ctx);
        assert(ctx.pc == 0x807F0000 && ctx.gpr[1] == 0x816F0000 && ctx.msr == 0);
    };
    for (uint32_t address : {0x00560000u, 0x00560120u, 0x1FFFFFE0u}) {
        for (uint32_t length : {0u, 32u, 384u, 0xFFFE0u}) {
            mmio.write16(0xCC005036, 0);
            ctx.gpr[3] = address;
            ctx.gpr[4] = length;
            invoke(0x8022CAB0, func_8022CAB0);
            assert(mmio.read16(0xCC005030) == (address >> 16));
            assert(mmio.read16(0xCC005032) == uint16_t(address));
            assert(mmio.read16(0xCC005036) == (length >> 5));
            invoke(0x8022CB30, func_8022CB30);
            assert(mmio.read16(0xCC005036) == ((length >> 5) | 0x8000));
            ctx.gpr[3] = address;
            ctx.gpr[4] = 384;
            invoke(0x8022CAB0, func_8022CAB0);
            assert(mmio.read16(0xCC005036) == 0x800C);
            invoke(0x8022CB50, func_8022CB50);
            assert(mmio.read16(0xCC005036) == 12);
            invoke(0x8022CB70, func_8022CB70);
            assert(ctx.gpr[3] == 0);
            ++cases;
        }
    }
    EventScheduler::get().reset();
    std::cout << "OWN_WII_ADMA_SDK_NATIVE_MMIO_PASS cases=" << cases
              << " calls=" << cases * 5 << " remaining=legacy-zero-unverified\n";
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
