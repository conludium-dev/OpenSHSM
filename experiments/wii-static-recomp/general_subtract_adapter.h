#pragma once
#include "single_arithmetic_adapter.h"

namespace nwii::runtime {
inline ArithmeticWide subtract_align(ArithmeticWide value, unsigned shift) {
    if (!shift) {
        return value;
    }
    if (shift >= 128) {
        return value != 0;
    }
    return (value >> shift) | ((value & ((ArithmeticWide(1) << shift) - 1)) != 0);
}

inline uint64_t subtract_finite64(uint64_t a, uint64_t b) {
    b ^= 0x8000000000000000ull;
    const uint64_t ma = arithmetic_mantissa(a);
    const uint64_t mb = arithmetic_mantissa(b);
    if (!ma && !mb) {
        return a & b & 0x8000000000000000ull;
    }
    if (!ma) {
        return b;
    }
    if (!mb) {
        return a;
    }
    const unsigned ha = std::bit_width(ma) - 1;
    const unsigned hb = std::bit_width(mb) - 1;
    const int ea = arithmetic_scale(a) + int(ha);
    const int eb = arithmetic_scale(b) + int(hb);
    const int common = ea > eb ? ea : eb;
    const ArithmeticWide va = subtract_align(ArithmeticWide(ma) << (124 - ha), unsigned(common - ea));
    const ArithmeticWide vb = subtract_align(ArithmeticWide(mb) << (124 - hb), unsigned(common - eb));
    const bool sa = a >> 63;
    const bool sb = b >> 63;
    ArithmeticWide magnitude;
    bool negative;
    if (sa == sb) {
        magnitude = va + vb;
        negative = sa;
    } else {
        magnitude = va >= vb ? va - vb : vb - va;
        negative = va >= vb ? sa : sb;
    }
    if (!magnitude) {
        return 0;
    }
    const int highest = arithmetic_highest(magnitude);
    const int scale = common - 124;
    const int exponent = highest + scale;
    const bool subnormal = exponent < -1022;
    const int shift = subnormal ? -1074 - scale : highest - 52;
    return arithmetic_pack64(negative, exponent, uint64_t(arithmetic_round_shift(magnitude, shift)), subnormal);
}

inline void experiment_general_subtract(CPUContext& context, uint32_t opcode) {
    if (opcode != 0xec020028 || !(context.msr & 0x2000) || (context.msr & 0x901) || (context.fpscr & 0x8fb)) {
        throw std::runtime_error("General subtraction opcode/FP/rounding/exception profile unavailable");
    }
    const uint64_t a = std::bit_cast<uint64_t>(context.fpr[2]);
    const uint64_t b = std::bit_cast<uint64_t>(context.fpr[0]);
    const uint64_t ma = a & 0x7fffffffffffffffull;
    const uint64_t mb = b & 0x7fffffffffffffffull;
    const bool an = ma > 0x7ff0000000000000ull;
    const bool bn = mb > 0x7ff0000000000000ull;
    const bool ai = ma == 0x7ff0000000000000ull;
    const bool bi = mb == 0x7ff0000000000000ull;
    uint32_t status = context.fpscr;
    uint64_t result;
    if (an || bn) {
        if ((an && !(a & 0x8000000000000ull)) || (bn && !(b & 0x8000000000000ull))) {
            arithmetic_exception(status, 0x01000000u);
        }
        result = (an ? a : b) | 0x8000000000000ull;
        status &= ~0x60000u;
    } else if (ai && bi && !((a ^ b) >> 63)) {
        arithmetic_exception(status, 0x00800000u);
        result = 0x7ff8000000000000ull;
        status &= ~0x60000u;
    } else if (ai || bi) {
        result = ai ? a : b ^ 0x8000000000000000ull;
        status &= ~0x60000u;
    } else {
        result = subtract_finite64(a, b);
    }
    const bool nan = (result & 0x7fffffffffffffffull) > 0x7ff0000000000000ull;
    const uint32_t single = nan ? (uint32_t(result >> 32) & 0x80000000u) | 0x7fc00000u | uint32_t((result >> 29) & 0x7fffffu)
        : ni_single_nearest_bits(result, status & 4);
    const uint64_t expanded = widen_single_bits(single);
    context.fpr[0] = std::bit_cast<double>(expanded);
    context.ps1[0] = std::bit_cast<double>(expanded);
    context.fpscr = (status & ~0x1f000u) | (frsp_single_class(single) << 12);
}
}
