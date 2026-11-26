// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "runtime/cpu_context.h"
#include "Common/FloatUtils.h"
#include <bit>
#include <cfenv>
#include <cmath>
#include <stdexcept>

namespace nwii::runtime {
inline void stock_estimate_exception(CPUContext& ctx, uint32_t mask) {
    if ((ctx.fpscr & mask) != mask) {
        ctx.fpscr |= 0x80000000u;
    }
    ctx.fpscr |= mask;
    ctx.fpscr &= ~0x60000000u;
    if (ctx.fpscr & 0x01f80700u) {
        ctx.fpscr |= 0x20000000u;
    }
    if ((ctx.fpscr >> 22) & (ctx.fpscr & 0xf8u)) {
        ctx.fpscr |= 0x40000000u;
    }
    if ((ctx.fpscr & 0x40000000u) && (ctx.msr & 0x900u)) {
        throw std::runtime_error("Paired estimate FP program exception delivery is unverified");
    }
}

inline float stock_estimate_single(uint32_t fpscr, double value) {
    const uint64_t raw = std::bit_cast<uint64_t>(value);
    if ((fpscr & 4u) && (raw & 0x7fffffffffffffffu) < 0x3810000000000000ull) {
        return std::bit_cast<float>(static_cast<uint32_t>((raw & 0x8000000000000000ull) >> 32));
    }
    constexpr int modes[] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
    const int previous = std::fegetround();
    const int requested = modes[fpscr & 3u];
    if (previous < 0 || (previous != requested && std::fesetround(requested) != 0)) {
        throw std::runtime_error("Host rounding mode unavailable for paired estimate");
    }
    volatile float converted = static_cast<float>(value);
    const float result = converted;
    if (previous != requested && std::fesetround(previous) != 0) {
        throw std::runtime_error("Host rounding mode restoration failed");
    }
    return (fpscr & 4u) ? Common::FlushToZero(result) : result;
}

inline void stock_paired_estimate(CPUContext& ctx, uint32_t opcode) {
    const uint32_t xo = (opcode >> 1) & 1023u;
    if ((opcode >> 26) != 4u || (xo != 24u && xo != 26u) || (opcode & 0x001f0000u)) {
        throw std::runtime_error("Invalid paired estimate encoding");
    }
    const unsigned destination = (opcode >> 21) & 31u;
    const unsigned source = (opcode >> 11) & 31u;
    const double a = ctx.fpr[source];
    const double b = ctx.ps1[source];
    if (a == 0.0 || b == 0.0) {
        stock_estimate_exception(ctx, 0x04000000u);
        ctx.fpscr &= ~0x00060000u;
    }
    if (xo == 26u && (a < 0.0 || b < 0.0)) {
        stock_estimate_exception(ctx, 0x00000200u);
        ctx.fpscr &= ~0x00060000u;
    }
    if (std::isnan(a) || std::isinf(a) || std::isnan(b) || std::isinf(b)) {
        ctx.fpscr &= ~0x00060000u;
    }
    if (Common::IsSNAN(a) || Common::IsSNAN(b)) {
        stock_estimate_exception(ctx, 0x01000000u);
    }
    const double first = xo == 24u ? Common::ApproximateReciprocal(a) :
        stock_estimate_single(ctx.fpscr, Common::ApproximateReciprocalSquareRoot(a));
    const double second = xo == 24u ? Common::ApproximateReciprocal(b) :
        stock_estimate_single(ctx.fpscr, Common::ApproximateReciprocalSquareRoot(b));
    ctx.fpr[destination] = first;
    ctx.ps1[destination] = second;
    ctx.fpscr = (ctx.fpscr & ~0x0001f000u) |
        (Common::ClassifyFloat(stock_estimate_single(0, first)) << 12);
    if (opcode & 1u) {
        ctx.cr[1].lt = (ctx.fpscr & 0x80000000u) != 0;
        ctx.cr[1].gt = (ctx.fpscr & 0x40000000u) != 0;
        ctx.cr[1].eq = (ctx.fpscr & 0x20000000u) != 0;
        ctx.cr[1].so = (ctx.fpscr & 0x10000000u) != 0;
    }
}
}
