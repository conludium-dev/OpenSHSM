#include "stock_movie_timing.h"
#include "processor_adapter.h"
#include <cassert>
#include <iostream>
#include <memory>

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.mmu.write32(0x800000D4, 0x80568000);
    ctx.mmu.write32(0x800000D8, 0x80569000);
    ctx.pc = 0x80209D80;
    ctx.lr = 0x8009C5E4;
    ctx.msr = 0x2032;
    for (unsigned i = 0; i < 32; ++i) {
        ctx.gpr[i] = 0x80560000 + i * 4;
        ctx.fpr[i] = i + 0.25;
        ctx.ps1[i] = i + 0.75;
    }
    const auto mem1 = ctx.mmu.mem1, mem2 = ctx.mmu.mem2, cache = ctx.mmu.locked_cache;
    const auto gpr = ctx.gpr;
    const auto fpr = ctx.fpr, ps1 = ctx.ps1;
    for (unsigned i = 0; i < 4100; ++i) {
        stock_movie_timing::observe(ctx, 0x80209D80);
    }
    assert(ctx.mmu.mem1 == mem1 && ctx.mmu.mem2 == mem2 && ctx.mmu.locked_cache == cache);
    assert(ctx.gpr == gpr && ctx.fpr == fpr && ctx.ps1 == ps1);
    assert(ctx.pc == 0x80209D80 && ctx.lr == 0x8009C5E4 && ctx.msr == 0x2032);
    std::cout << "MOVIE_TIMING_NONMUTATION_CAP_PASS\n";
}
