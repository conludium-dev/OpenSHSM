#include "stock_thp_chain_observation.h"
#define main loading_fixture_main
#include "stock_loading_observation_contract.cpp"
#undef main

int main() {
    if (loading_fixture_main() != 0) {
        return 1;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[13] = 0x8052E720;
    ctx.mmu.write32(ctx.gpr[13] - 14704u, 0x8009BA88);
    const auto gpr = ctx.gpr;
    const auto fpr = ctx.fpr;
    const auto count = ctx.inst_count;
    const auto pc = ctx.pc, lr = ctx.lr, xer = ctx.xer, msr = ctx.msr, ctr = ctx.ctr;
    const auto bytes = stock_loading_observation::copy_ram(ctx, ctx.gpr[13] - 14756u, 56);
    for (uint32_t address : {0x8009BA88u, 0x8009BBF0u, 0x8009BC38u, 0x8009BC90u, 0x8009BE40u,
        0x8022CA84u, 0x8022CD80u, 0x8022CD90u, 0x8022CDB8u, 0x8022CDBCu, 0x8022CDC4u,
        0x8009BB2Cu, 0x8009BB30u, 0x8009BB48u, 0x8009BB4Cu, 0x8009BAECu, 0x8009BBBCu}) {
        stock_thp_queue_observation::observe_producer(ctx, address);
        if (ctx.gpr != gpr || ctx.fpr != fpr || ctx.inst_count != count || ctx.pc != pc || ctx.lr != lr
            || ctx.xer != xer || ctx.msr != msr || ctx.ctr != ctr
            || stock_loading_observation::copy_ram(ctx, ctx.gpr[13] - 14756u, 56) != bytes) {
            return 2;
        }
    }
    for (unsigned i = 0; i < 70; ++i) {
        stock_thp_queue_observation::observe_producer(ctx, 0x8009BBF0);
    }
    ctx.mmu.write8(0x8046BBE5, 2);
    stock_thp_queue_observation::observe_producer(ctx, 0x8009BBF0);
    if (ctx.gpr != gpr || ctx.fpr != fpr || ctx.inst_count != count) {
        return 3;
    }
    std::cout << "MOVIE_CHAIN_HELPER_STATE_PRESERVATION_PASS\n";
    return 0;
}
