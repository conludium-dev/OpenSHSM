#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
using namespace nwii::runtime;
#include "context-helpers.h"

int main() {
    CPUContext ctx;
    const uint32_t address = 0x80010000;
    unsigned baseline_mismatches = 0, corrected_mismatches = 0;
    for (unsigned fixture = 0; fixture < 64; ++fixture) {
        for (unsigned i = 0; i < 32; ++i) {
            ctx.fpr[i] = std::ldexp(double(i + 1) + 0.1, int(fixture % 21) - 10);
            ctx.ps1[i] = std::ldexp(-double(i + 1) - 0.3, int(fixture % 17) - 8);
        }
        ctx.gqr[0] = 0;
        const auto primary = ctx.fpr, secondary = ctx.ps1;
        std::array<uint64_t, 32> sdk_pairs;
        for (unsigned i = 0; i < 32; ++i) {
            ctx.psq_store(i, address + 0x1C8 + i * 8, 0, 0);
            sdk_pairs[i] = ctx.mmu.read64(address + 0x1C8 + i * 8);
        }
        baseline_save(ctx, address);
        for (unsigned i = 0; i < 32; ++i) {
            baseline_mismatches += ctx.mmu.read64(address + 0x1C8 + i * 8) != sdk_pairs[i];
        }
        corrected_save(ctx, address);
        for (unsigned i = 0; i < 32; ++i) {
            corrected_mismatches += ctx.mmu.read64(address + 0x1C8 + i * 8) != sdk_pairs[i];
            ctx.psq_load(i, address + 0x1C8 + i * 8, 0, 0);
            corrected_mismatches += ctx.fpr[i] != double(float(primary[i])) || ctx.ps1[i] != double(float(secondary[i]));
        }
        ctx.mmu.write32(0x800000D4, address);
        for (unsigned i = 0; i < 32; ++i) {
            ctx.fpr[i] = 0;
            ctx.ps1[i] = 0;
        }
        if (!corrected_load(ctx)) {
            return 3;
        }
        for (unsigned i = 0; i < 32; ++i) {
            corrected_mismatches += ctx.fpr[i] != primary[i] || ctx.ps1[i] != double(float(secondary[i]));
        }
    }
    std::printf("fixtures=64 registers=32 baselinePairMismatches=%u correctedMismatches=%u\n", baseline_mismatches, corrected_mismatches);
    return baseline_mismatches && !corrected_mismatches ? 0 : 2;
}
