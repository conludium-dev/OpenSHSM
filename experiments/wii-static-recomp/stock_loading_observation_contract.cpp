#include <processor_adapter.h>
#include "stock_loading_observation.h"
#include <memory>
#include <iostream>

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[1] = 0x80700000; ctx.gpr[31] = 0x80600200; ctx.ctr = 0x800EF000;
    for (unsigned i = 3; i < 8; ++i) { ctx.gpr[i] = i * 16; }
    for (unsigned i = 0; i < 16; ++i) { ctx.mmu.write8(0x8048E078 + i, uint8_t(i)); }
    for (unsigned i = 0; i < 32; ++i) { ctx.mmu.write8(0x80600200 + i, uint8_t(i + 16)); }
    ctx.mmu.write8(0x8052A5E0, 0);
    const auto gpr = ctx.gpr;
    const auto gqr = ctx.gqr;
    const auto fpr = ctx.fpr;
    const auto ps1 = ctx.ps1;
    const auto pc = ctx.pc, lr = ctx.lr, ctr = ctx.ctr, xer = ctx.xer, msr = ctx.msr, fpscr = ctx.fpscr;
    const auto count = ctx.inst_count;
    const auto queue = stock_loading_observation::copy_ram(ctx, 0x8048E078, 16);
    const auto request = stock_loading_observation::copy_ram(ctx, 0x80600200, 32);
    const auto gate = stock_loading_observation::copy_ram(ctx, 0x8052A5E0, 1);
    for (uint32_t address : {0x8018FA50u, 0x801B51D4u, 0x801B51D8u, 0x8018FA5Cu}) {
        stock_loading_observation::observe(ctx, address);
        if (ctx.gpr != gpr || ctx.gqr != gqr || ctx.fpr != fpr || ctx.ps1 != ps1
            || ctx.pc != pc || ctx.lr != lr || ctx.ctr != ctr || ctx.xer != xer || ctx.msr != msr
            || ctx.fpscr != fpscr || ctx.inst_count != count
            || stock_loading_observation::copy_ram(ctx, 0x8048E078, 16) != queue
            || stock_loading_observation::copy_ram(ctx, 0x80600200, 32) != request
            || stock_loading_observation::copy_ram(ctx, 0x8052A5E0, 1) != gate) {
            return 1;
        }
    }
    if (!stock_loading_observation::copy_ram(ctx, 0xCC000000, 4).empty()
        || !stock_loading_observation::copy_ram(ctx, 0x817FFFFF, 16).empty()) {
        return 2;
    }
    std::cout << "LOADING_OBSERVER_STATE_PRESERVATION_PASS\n";
    return 0;
}
