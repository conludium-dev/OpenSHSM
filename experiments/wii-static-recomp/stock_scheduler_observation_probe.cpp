#include "stock_scheduler_observation.h"
#include "processor_adapter.h"
#include <cassert>
#include <iostream>
#include <memory>

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    constexpr uint32_t thread = 0x80568000;
    ctx.mmu.write32(0x800000DC, thread);
    ctx.mmu.write32(0x800000D4, thread);
    ctx.mmu.write32(thread + 0x2FC, thread);
    ctx.mmu.write32(thread + 0x2C8, 0x00010000);
    ctx.mmu.write32(thread + 0x2CC, 1);
    ctx.mmu.write32(thread + 0x2D0, 0);
    uint32_t value = 0;
    for (auto address : {0x817FFFFCu, 0x93FFFFFCu, 0x80568000u, 0xC0568000u}) {
        assert(stock_scheduler_observation::word(ctx, address, value));
    }
    for (auto address : {0x817FFFFDu, 0x81800000u, 0x94000000u, 0xCC000000u, 0xE0000000u, 0xFFFFFFFCu}) {
        value = 0x12345678;
        assert(!stock_scheduler_observation::word(ctx, address, value) && value == 0x12345678);
    }
    ctx.pc = 0x8021A8E8;
    ctx.lr = 0x8021A8DC;
    ctx.msr = 0x8032;
    ctx.gpr[13] = 0x8052E720;
    const auto before1 = ctx.mmu.mem1, before2 = ctx.mmu.mem2, before_cache = ctx.mmu.locked_cache;
    const auto gpr = ctx.gpr;
    for (unsigned i = 0; i < 20; ++i) {
        stock_scheduler_observation::observe(ctx);
    }
    ctx.pc = 0x8009BBD0;
    for (unsigned i = 0; i < 12; ++i) {
        stock_scheduler_observation::observe(ctx);
    }
    assert(ctx.gpr == gpr && ctx.pc == 0x8009BBD0 && ctx.lr == 0x8021A8DC && ctx.msr == 0x8032);
    assert(ctx.mmu.mem1 == before1 && ctx.mmu.mem2 == before2 && ctx.mmu.locked_cache == before_cache);
    std::cout << "SCHEDULER_OBSERVER_READ_ONLY_BOUNDS_CAPS_CYCLE_PASS\n";
}
