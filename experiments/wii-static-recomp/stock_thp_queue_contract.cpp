#include "stock_thp_queue_observation.h"
#define main loading_fixture_main
#include "stock_loading_observation_contract.cpp"
#undef main

int main() {
    if (loading_fixture_main() != 0) {
        return 1;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[3] = 0x80601000;
    ctx.gpr[4] = 0x80603000;
    ctx.gpr[5] = 1;
    ctx.lr = 0x8009C628;
    ctx.mmu.write32(ctx.gpr[3] + 16, 0x80602000);
    ctx.mmu.write32(ctx.gpr[3] + 20, 4);
    ctx.mmu.write32(ctx.gpr[3] + 24, 1);
    ctx.mmu.write32(ctx.gpr[3] + 28, 2);
    ctx.mmu.write32(0x80602004, 0x80603000);
    const auto gpr = ctx.gpr;
    const auto fpr = ctx.fpr;
    const auto count = ctx.inst_count;
    const auto xer = ctx.xer, msr = ctx.msr, pc = ctx.pc, lr = ctx.lr;
    const auto bytes = stock_loading_observation::copy_ram(ctx, 0x80601000, 32);
    for (uint32_t function : {0x80217D30u, 0x80217E00u}) {
        stock_thp_queue_observation::observe(ctx, function);
        if (ctx.gpr != gpr || ctx.fpr != fpr || ctx.inst_count != count || ctx.xer != xer
            || ctx.msr != msr || ctx.pc != pc || ctx.lr != lr
            || stock_loading_observation::copy_ram(ctx, 0x80601000, 32) != bytes) {
            return 2;
        }
    }
    uint32_t ignored = 0;
    if (stock_thp_queue_observation::word(ctx, 0xCC000000, ignored)
        || stock_thp_queue_observation::word(ctx, 0xFFFFFFFF, ignored)) {
        return 3;
    }
    std::cout << "MOVIE_QUEUE_HELPER_STATE_PRESERVATION_PASS\n";
    return 0;
}
