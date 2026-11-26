#include <processor_adapter.h>
#include "runtime/config.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <iostream>
#include <memory>

bool probe_arm_sc = false;
extern "C" void probe_cache_flush(nwii::runtime::CPUContext&);

int main(int argc, char**) {
    const bool baseline = argc > 1;
    nwii::runtime::Config::get().game_profile.ext_interrupt_dispatch = 0;
    for (unsigned alignment : {0u, 1u, 31u}) {
        auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
        auto& ctx = *owned;
        constexpr uint32_t context = 0x80568000, target = 0x80004000;
        ctx.mmu.write32(0x800000D4, context);
        ctx.mmu.write32(0x800000E4, 0);
        nwii::runtime::hw::pi_intmr = 0;
        nwii::runtime::hw::pi_intsr = 0;
        ctx.gpr[1] = 0x80700000;
        ctx.gpr[3] = 0x80560000 + alignment;
        ctx.gpr[4] = 384;
        ctx.pc = 0x80212FD0;
        ctx.lr = 0x8009BBD0;
        ctx.msr = 0;
        probe_arm_sc = true;
        if (setjmp(ctx.exception_jmp_buf) == 0) {
            probe_cache_flush(ctx);
            assert(false && "Expected callback exactly at SC boundary");
        }
        assert(!probe_arm_sc && ctx.pc == target && ctx.ctr == 0);
        const auto saved = ctx.mmu.read32(context + 0x198);
        assert(saved == (baseline ? 0x80212FF4 : 0x80212FF8));
        assert(ctx.mmu.read32(context + 0x88) == 0);
        ctx.pc = 0xFFFFFFFC;
        ctx.in_callback = false;
        assert(nwii::runtime::process_pending_callbacks(ctx));
        assert(ctx.pc == saved && ctx.ctr == 0);
        if (!baseline) {
            probe_cache_flush(ctx);
            assert(ctx.pc == 0x8009BBD0 && ctx.ctr == 0);
            assert(ctx.gpr[3] == 0x80560000 + alignment + ((384 + alignment + 31) / 32) * 32);
        }
        std::cout << "SC_RESUME " << alignment << ' ' << std::hex << saved << std::dec << '\n';
    }
    std::cout << (baseline ? "STALE_SC_PC_RESUME_REPRODUCED" : "SYNCHRONIZED_SC_PC_RETURN_PASS") << '\n';
}
