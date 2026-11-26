#define main loading_fixture_main
#include "stock_loading_observation_contract.cpp"
#undef main
#include "stock_subtitle_progress.h"

int main() {
    if (loading_fixture_main() != 0) { return 1; }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[3] = 0x80600000; ctx.gpr[28] = 0x80600200; ctx.gpr[29] = 0x80600300; ctx.gpr[30] = 0x80600400;
    const char input[] = "1.25";
    for (unsigned i = 0; i < sizeof(input); ++i) { ctx.mmu.write8(ctx.gpr[3] + i, input[i]); }
    ctx.mmu.write32(ctx.gpr[30], 0x3FA00000);
    const auto gpr = ctx.gpr;
    const auto fpr = ctx.fpr;
    const auto inst = ctx.inst_count;
    for (uint32_t pc : {0x800D806Cu, 0x800D80E4u, 0x800D8114u, 0x800D8120u, 0x800D8280u, 0x800D82B0u}) {
        stock_subtitle_progress::observe(ctx, pc);
        if (ctx.gpr != gpr || ctx.fpr != fpr || ctx.inst_count != inst || ctx.mmu.read32(ctx.gpr[30]) != 0x3FA00000) {
            return 2;
        }
    }
    std::cout << "SUBTITLE_PROGRESS_HELPER_PRESERVATION_PASS\n";
    return 0;
}
