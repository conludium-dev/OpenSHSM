#include "stock_thp_update_observation.h"
#define main loading_fixture_main
#include "stock_loading_observation_contract.cpp"
#undef main

int main() {
    if (loading_fixture_main() != 0) {
        return 1;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[28] = 0x80604000;
    ctx.mmu.write32(0x8046BC38, 0x80603000);
    const auto gpr = ctx.gpr;
    const auto fpr = ctx.fpr;
    const auto count = ctx.inst_count;
    const auto pc = ctx.pc, lr = ctx.lr, xer = ctx.xer, msr = ctx.msr;
    const auto bytes = stock_loading_observation::copy_ram(ctx, 0x8046BC30, 16);
    for (uint32_t address : {0x8009B72Cu, 0x8009B750u, 0x8009B760u, 0x8009B770u}) {
        stock_thp_queue_observation::observe_update(ctx, address);
        if (ctx.gpr != gpr || ctx.fpr != fpr || ctx.inst_count != count || ctx.pc != pc
            || ctx.lr != lr || ctx.xer != xer || ctx.msr != msr
            || stock_loading_observation::copy_ram(ctx, 0x8046BC30, 16) != bytes) {
            return 2;
        }
    }
    std::cout << "MOVIE_UPDATE_HELPER_STATE_PRESERVATION_PASS\n";
    return 0;
}
