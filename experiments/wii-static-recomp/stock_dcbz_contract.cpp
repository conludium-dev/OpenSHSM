#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include "dcbz-sites.h"

int main() {
    nwii::runtime::CPUContext ctx;
    unsigned cases = 0;
    for (unsigned site = 0; site < 12; ++site) {
        for (uint32_t base : {0x80010000u, 0x90010000u, 0xE0001000u}) {
            for (unsigned offset = 0; offset < 32; ++offset) {
                for (unsigned i = 0; i < 96; ++i) {
                    ctx.mmu.write8(base - 32 + i, uint8_t(i + 1));
                }
                ctx.gpr[0] = 0xDEADBEEF;
                ctx.gpr[4] = base + offset;
                if (dcbz_ra[site] != 0) {
                    ctx.gpr[4] = base;
                    ctx.gpr[0] = offset;
                }
                const auto registers = ctx.gpr;
                const uint32_t old_pc = ctx.pc, old_xer = ctx.xer;
                dcbz_site(ctx, site);
                for (unsigned i = 0; i < 96; ++i) {
                    const uint8_t expected = i >= 32 && i < 64 ? 0 : uint8_t(i + 1);
                    if (ctx.mmu.read8(base - 32 + i) != expected) {
                        return 2;
                    }
                }
                for (unsigned i = 0; i < 32; ++i) {
                    if (ctx.gpr[i] != registers[i]) {
                        return 3;
                    }
                }
                if (ctx.pc != old_pc || ctx.xer != old_xer) {
                    return 4;
                }
                ++cases;
            }
        }
    }
    ctx.gpr[0] = 0;
    ctx.gpr[4] = 0xCC000000;
    bool refused = false;
    try {
        dcbz_site(ctx, 0);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    if (!refused) {
        return 5;
    }
    std::printf("PASS %u lowered-original THP dcbz RAM cases; RA0/alignment/canaries/registers/MMIO-refusal\n", cases);
}
