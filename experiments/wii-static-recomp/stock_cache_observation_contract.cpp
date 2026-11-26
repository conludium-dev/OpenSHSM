#include <processor_adapter.h>
#include <stock_context_observation.h>
#include <iostream>
#include <memory>

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.mmu.write32(0x800000D4, 0x80540000);
    ctx.mmu.write32(0x80540198, 0x80212FC4);
    ctx.pc = 0x80212FC4;
    ctx.lr = 0x8009BB9C;
    ctx.ctr = 12;
    auto observe = [&](unsigned stage) {
        const auto gpr = ctx.gpr;
        const auto fpr = ctx.fpr;
        const auto pc = ctx.pc, lr = ctx.lr, msr = ctx.msr, ctr = ctx.ctr, xer = ctx.xer;
        const auto count = ctx.inst_count;
        const auto ram = stock_loading_observation::copy_ram(ctx, 0x80540000, 0x1C8);
        stock_loading_observation::observe_context(ctx, stage, 0x80540000);
        return gpr == ctx.gpr && fpr == ctx.fpr && pc == ctx.pc && lr == ctx.lr && msr == ctx.msr
            && ctr == ctx.ctr && xer == ctx.xer && count == ctx.inst_count
            && ram == stock_loading_observation::copy_ram(ctx, 0x80540000, 0x1C8);
    };
    for (unsigned i = 0; i < 600; ++i) {
        if (!observe(0)) {
            return 1;
        }
    }
    ctx.lr = 0x8009BBBB;
    for (unsigned stage = 4; stage <= 7; ++stage) {
        for (unsigned i = 0; i < 300; ++i) {
            if (!observe(stage)) {
                return 5;
            }
        }
    }
    ctx.lr = 0x8009BB9C;
    for (unsigned stage = 4; stage <= 8; ++stage) {
        if (!observe(stage)) {
            return 2;
        }
    }
    ctx.mmu.write32(0x80540198, 0);
    for (unsigned i = 0; i < 20; ++i) {
        ctx.pc = i % 2 == 0 ? 0x80212FC4 : 0;
        if (!observe(i % 2 == 0 ? 2 : 3)) {
            return 3;
        }
    }
    if (stock_loading_observation::context_word(ctx, 0xCC000000) != 0
        || stock_loading_observation::context_word(ctx, 0xFFFFFFFE) != 0) {
        return 4;
    }
    std::cout << "CACHE_OBSERVER_STATE_BUDGET_CRITICAL_RESERVE_PASS\n";
    return 0;
}
