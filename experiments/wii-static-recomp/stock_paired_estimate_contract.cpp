#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include "stock_paired_estimates.h"
#include "paired-reference.h"
#include <bit>
#include <cfenv>
#include <fstream>
#include <memory>

static uint64_t bits(double value) {
    return std::bit_cast<uint64_t>(value);
}

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    auto owned = std::make_unique<nwii::runtime::CPUContext>();
    auto& ctx = *owned;
    Interpreter reference;
    uint64_t cases = 0;
    constexpr int modes[] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
    const auto check = [&](uint64_t first, uint64_t second, uint32_t initial, unsigned xo,
            bool rc, bool overlap) {
        ctx.fpr.fill(123.25);
        ctx.ps1.fill(-321.5);
        const unsigned destination = overlap ? 1 : 2;
        ctx.fpr[1] = std::bit_cast<double>(first);
        ctx.ps1[1] = std::bit_cast<double>(second);
        ctx.fpscr = initial;
        ctx.msr = 0xa032;
        ctx.pc = 0x80071110;
        ctx.inst_count = 71;
        ctx.cr[1].lt = false;
        ctx.cr[1].gt = true;
        ctx.cr[1].eq = false;
        ctx.cr[1].so = true;
        auto& expected = reference.m_ppc_state;
        expected.fpscr.Hex = initial;
        expected.msr.Hex = ctx.msr;
        expected.cr.field = 5;
        expected.ps[1].SetBoth(ctx.fpr[1], ctx.ps1[1]);
        const UGeckoInstruction instruction{destination, 1, rc};
        if (std::fesetround(modes[initial & 3]) != 0) {
            return false;
        }
        if (xo == 24) {
            Interpreter::ps_res(reference, instruction);
        } else {
            Interpreter::ps_rsqrte(reference, instruction);
        }
        if (std::fesetround(FE_DOWNWARD) != 0) {
            return false;
        }
        const uint32_t opcode = (4u << 26) | (destination << 21) | (1u << 11) | (xo << 1) | rc;
        nwii::runtime::stock_paired_estimate(ctx, opcode);
        const unsigned cr = (ctx.cr[1].lt << 3) | (ctx.cr[1].gt << 2) |
            (ctx.cr[1].eq << 1) | ctx.cr[1].so;
        const bool match = bits(ctx.fpr[destination]) == bits(expected.ps[destination].PS0AsDouble()) &&
            bits(ctx.ps1[destination]) == bits(expected.ps[destination].PS1AsDouble()) &&
            ctx.fpscr == expected.fpscr.Hex && cr == expected.cr.field &&
            ctx.pc == 0x80071110 && ctx.inst_count == 71 && std::fegetround() == FE_DOWNWARD &&
            ctx.fpr[31] == 123.25 && ctx.ps1[31] == -321.5;
        if (!match) {
            std::fprintf(stderr, "MISMATCH %016llx %016llx fpscr=%08x xo=%u rc=%u overlap=%u got=%016llx/%016llx/%08x/%u expected=%016llx/%016llx/%08x/%u\n",
                static_cast<unsigned long long>(first), static_cast<unsigned long long>(second),
                initial, xo, rc, overlap, static_cast<unsigned long long>(bits(ctx.fpr[destination])),
                static_cast<unsigned long long>(bits(ctx.ps1[destination])), ctx.fpscr, cr,
                static_cast<unsigned long long>(bits(expected.ps[destination].PS0AsDouble())),
                static_cast<unsigned long long>(bits(expected.ps[destination].PS1AsDouble())),
                expected.fpscr.Hex, expected.cr.field);
        }
        ++cases;
        return match;
    };
    std::ifstream input(argv[1]);
    uint64_t first, reciprocal, square_root;
    while (input >> std::hex >> first >> reciprocal >> square_root) {
        for (unsigned xo : {24u, 26u}) {
            if (!check(first, first ^ 0x8000000000000000ull, 0x00060000u, xo, true, false)) {
                return 3;
            }
        }
    }
    if (!input.eof()) {
        return 4;
    }
    constexpr uint64_t edge[] = {0, 0x8000000000000000ull, 1, 0x8000000000000001ull,
        0x3ff0000000000000ull, 0x4000000000000000ull, 0x4010000000000000ull,
        0xbff0000000000000ull, 0x7ff0000000000000ull, 0xfff0000000000000ull,
        0x7ff0000000000001ull, 0xfff0000000000001ull, 0x7ff8000000000001ull,
        0x7fefffffffffffffull, 0x0010000000000000ull, 0x47cfffffffffffffull,
        0x47d0000000000000ull, 0x47d0000000000001ull};
    for (uint64_t a : edge) {
        for (uint64_t b : edge) {
            for (unsigned flags : {0u, 0x00060000u, 0x84060010u, 0x21060280u}) {
                for (unsigned rn = 0; rn < 4; ++rn) {
                    for (unsigned ni : {0u, 4u}) {
                        for (unsigned xo : {24u, 26u}) {
                            for (bool rc : {false, true}) {
                                for (bool overlap : {false, true}) {
                                    if (!check(a, b, flags | rn | ni, xo, rc, overlap)) {
                                        return 5;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    unsigned refused = 0;
    ctx.msr = 0xa032 | 0x900;
    ctx.fpscr = 0x10;
    ctx.fpr[1] = 0;
    ctx.ps1[1] = 1;
    ctx.fpr[2] = 456;
    try {
        nwii::runtime::stock_paired_estimate(ctx, 0x10400830);
    } catch (const std::runtime_error&) {
        refused += ctx.fpr[2] == 456 && (ctx.fpscr & 0xc4000000u) == 0xc4000000u;
    }
    for (uint32_t invalid : {0x10410830u, 0x10400832u, 0xfc000030u}) {
        const uint32_t previous = ctx.fpscr;
        try {
            nwii::runtime::stock_paired_estimate(ctx, invalid);
        } catch (const std::runtime_error&) {
            refused += previous == ctx.fpscr && ctx.fpr[2] == 456;
        }
    }
    if (refused != 4 || cases < 1000000) {
        return 6;
    }
    std::printf("PAIRED_ESTIMATE_COMPONENT_PASS %llu cases; 4 unverified/invalid profiles refused\n",
        static_cast<unsigned long long>(cases));
}
