#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include SHSM_PSQ_HEADER
#include <bit>
#include <memory>
#ifndef SHSM_PSQ_BASELINE
#include "psq-float-reference.h"
#endif

int main() {
    auto owned = std::make_unique<nwii::runtime::CPUContext>();
    auto& ctx = *owned;
    ctx.gpr[1] = 0x80005000;
    ctx.gpr[0] = 8;
    ctx.gqr[0] = 0;
    ctx.fpr[31] = 1.0 / 3.0;
    ctx.ps1[31] = -2;
    ctx.mmu.write32(0x80005008, 0x12345678);
#ifdef SHSM_PSQ_BASELINE
    try {
        shsm_psq_indexed(ctx, 0x13e1000e, 0x8034c2d4);
    } catch (const std::runtime_error&) {
        if (ctx.pc == 0x8034c2d4 && ctx.mmu.read32(0x80005008) == 0x12345678) {
            std::puts("BASELINE_NONREPRESENTABLE_PSQ_STORE_REFUSAL_REPRODUCED");
            return 0;
        }
    }
    return 2;
#else
    uint64_t cases = 0;
    uint64_t random = 0x5348534d52455630ull;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 7;
        random ^= random << 17;
        return random;
    };
    for (unsigned index = 0; index < 400000; ++index) {
        const uint64_t raw = next();
        const uint32_t single = static_cast<uint32_t>(next());
        if (shsm_psq_single_ftz(raw) != ConvertToSingleFTZ(raw) ||
                shsm_psq_double(single) != ConvertToDouble(single)) {
            return 3;
        }
        ++cases;
    }
    constexpr uint64_t values[] = {0, 0x8000000000000000ull, 1, 0x8000000000000001ull,
        0x3fd5555555555555ull, 0x3ff0000000000001ull, 0x380fffffffffffffull,
        0x3810000000000000ull, 0x3810000000000001ull, 0x7ff0000000000000ull,
        0xfff0000000000000ull, 0x7ff0000000000001ull, 0x7ff8000000000001ull,
        0x7fefffffffffffffull, 0x0010000000000000ull};
    constexpr uint32_t singles[] = {0, 0x80000000u, 1, 0x80000001u, 0x007fffffu,
        0x00800000u, 0x3f800000u, 0x7f7fffffu, 0x7f800000u, 0xff800000u,
        0x7f800001u, 0xff800001u, 0x7fc00001u, 0xffc00001u, 0xffffffffu};
    for (unsigned subop : {6u, 7u, 38u, 39u}) {
        for (unsigned reg = 0; reg < 32; ++reg) {
            for (unsigned gqr = 0; gqr < 8; ++gqr) {
                for (unsigned w : {0u, 1u}) {
                    for (uint32_t base : {0x80000000u, 0x90000000u, 0xc0000000u, 0xd0000000u}) {
                        const uint32_t ea = base + 0x4000;
                        const unsigned ra = (subop & 32) ? 5 : ((reg & 1) ? 5 : 0);
                        ctx.gpr[0] = 0xdeadbeef;
                        ctx.gpr[5] = ea - 16;
                        ctx.gpr[6] = ra ? 16 : ea;
                        ctx.gqr[gqr] = 0x3f003f00;
                        const uint64_t a = values[reg % 15];
                        const uint64_t b = values[(reg + 3) % 15];
                        const uint32_t input_a = singles[reg % 15];
                        const uint32_t input_b = singles[(reg + 3) % 15];
                        ctx.fpr[reg] = std::bit_cast<double>(a);
                        ctx.ps1[reg] = std::bit_cast<double>(b);
                        ctx.fpscr = 0xfffff7ff;
                        ctx.pc = 0x80006000;
                        ctx.inst_count = 17;
                        ctx.mmu.write32(ea - 4, 0x11111111);
                        ctx.mmu.write32(ea, input_a);
                        ctx.mmu.write32(ea + 4, input_b);
                        ctx.mmu.write32(ea + 8, 0x22222222);
                        const uint32_t word = (4u << 26) | (reg << 21) | (ra << 16) |
                            (6u << 11) | (w << 10) | (gqr << 7) | (subop << 1);
                        shsm_psq_indexed(ctx, word, 0x8034c2d4);
                        if (subop & 1) {
                            if (ctx.mmu.read32(ea) != ConvertToSingleFTZ(a) ||
                                    ctx.mmu.read32(ea + 4) != (w ? input_b : ConvertToSingleFTZ(b)) ||
                                    std::bit_cast<uint64_t>(ctx.fpr[reg]) != a ||
                                    std::bit_cast<uint64_t>(ctx.ps1[reg]) != b) {
                                return 4;
                            }
                        } else if (std::bit_cast<uint64_t>(ctx.fpr[reg]) != ConvertToDouble(input_a) ||
                                std::bit_cast<uint64_t>(ctx.ps1[reg]) != (w ? 0x3ff0000000000000ull : ConvertToDouble(input_b))) {
                            return 5;
                        }
                        if (ctx.mmu.read32(ea - 4) != 0x11111111 || ctx.mmu.read32(ea + 8) != 0x22222222 ||
                                ctx.gpr[0] != 0xdeadbeef || ctx.gpr[5] != ((subop & 32) ? ea : ea - 16) ||
                                ctx.fpscr != 0xfffff7ff || ctx.pc != 0x80006000 || ctx.inst_count != 17) {
                            return 6;
                        }
                        ++cases;
                    }
                }
            }
        }
    }
    unsigned refused = 0;
    ctx.gpr[1] = 0x80005000;
    ctx.gpr[0] = 8;
    ctx.gqr[0] = 4;
    ctx.mmu.write32(0x80005008, 0x12345678);
    try {
        shsm_psq_indexed(ctx, 0x13e1000e, 0x8034c2d4);
    } catch (const std::runtime_error&) {
        refused += ctx.mmu.read32(0x80005008) == 0x12345678;
    }
    ctx.gqr[0] = 0;
    for (uint32_t word : {0x13e0004eu, 0x13e1000fu}) {
        try {
            shsm_psq_indexed(ctx, word, 0x8034c2d4);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    ctx.gpr[1] = 0x80000000u | static_cast<uint32_t>(ctx.mmu.mem1.size() - 4);
    ctx.gpr[0] = 0;
    try {
        shsm_psq_indexed(ctx, 0x13e1000e, 0x8034c2d4);
    } catch (const std::runtime_error&) {
        ++refused;
    }
    if (refused != 4) {
        return 7;
    }
    std::printf("PSQ_FLOAT_BITS_COMPONENT_PASS %llu cases;4 invalid/unverified profiles refused\n",
        static_cast<unsigned long long>(cases));
#endif
}
