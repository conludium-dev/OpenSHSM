#include "stock_cache_irq_observation.h"
#include <cassert>
#include <memory>

extern "C" void func_80212FD0(nwii::runtime::CPUContext& ctx);

int main() {
    for (unsigned alignment = 0; alignment < 32; ++alignment) {
        for (auto length : {0u, 384u}) {
            auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
            auto& ctx = *owned;
            const uint32_t address = 0x80560000 + alignment;
            ctx.gpr[3] = address;
            ctx.gpr[4] = length;
            ctx.gpr[1] = 0x80700000;
            ctx.lr = 0x8009BBD0;
            ctx.pc = 0x80212FD0;
            ctx.msr = 0;
            ctx.ctr = 123;
            func_80212FD0(ctx);
            const unsigned lines = length ? (length + alignment + 31) / 32 : 0;
            assert(ctx.pc == ctx.lr && ctx.gpr[3] == address + lines * 32);
            assert(ctx.ctr == (length ? 0 : 123));
        }
    }
    std::cout << "CACHE_FLUSH_NATIVE_NO_IRQ_PASS64 zero-length/384bytes/all-alignments/return\n";
}
