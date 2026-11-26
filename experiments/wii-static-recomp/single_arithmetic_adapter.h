#pragma once
#include "frsp_adapter.h"
#include <bit>

namespace nwii::runtime {
using ArithmeticWide = unsigned __int128;

inline unsigned arithmetic_highest(ArithmeticWide value) {
    const uint64_t high = uint64_t(value >> 64);
    return high ? 63 + std::bit_width(high) : std::bit_width(uint64_t(value)) - 1;
}

inline ArithmeticWide arithmetic_round_shift(ArithmeticWide value, int shift) {
    if (shift <= 0) {
        return value << -shift;
    }
    if (shift > 128) {
        return 0;
    }
    if (shift == 128) {
        return value > (ArithmeticWide(1) << 127);
    }
    const ArithmeticWide quotient = value >> shift;
    const ArithmeticWide remainder = value & ((ArithmeticWide(1) << shift) - 1);
    const ArithmeticWide half = ArithmeticWide(1) << (shift - 1);
    return quotient + (remainder > half || (remainder == half && (quotient & 1)));
}

inline uint64_t arithmetic_pack64(bool negative, int exponent, uint64_t rounded, bool subnormal) {
    const uint64_t sign = negative ? 0x8000000000000000ull : 0;
    if (subnormal) {
        return sign | rounded;
    }
    if (rounded == (1ull << 53)) {
        rounded >>= 1;
        ++exponent;
    }
    if (exponent > 1023) {
        return sign | 0x7ff0000000000000ull;
    }
    return sign | (uint64_t(exponent + 1023) << 52) | (rounded & 0xfffffffffffffull);
}

inline uint64_t arithmetic_mantissa(uint64_t value) {
    return (value & 0xfffffffffffffull) | (((value >> 52) & 2047) ? 1ull << 52 : 0);
}

inline int arithmetic_scale(uint64_t value) {
    const unsigned exponent = (value >> 52) & 2047;
    return exponent ? int(exponent) - 1075 : -1074;
}

inline uint64_t arithmetic_divide64(uint64_t a, uint64_t b) {
    const bool negative = (a ^ b) >> 63;
    const uint64_t ma = arithmetic_mantissa(a), mb = arithmetic_mantissa(b);
    int k = int(std::bit_width(ma)) - int(std::bit_width(mb));
    if ((k >= 0 && ArithmeticWide(ma) < (ArithmeticWide(mb) << k)) ||
        (k < 0 && (ArithmeticWide(ma) << -k) < mb)) {
        --k;
    }
    const int scale = arithmetic_scale(a) - arithmetic_scale(b);
    const int exponent = scale + k;
    const uint64_t sign = negative ? 0x8000000000000000ull : 0;
    if (exponent > 1023) {
        return sign | 0x7ff0000000000000ull;
    }
    if (exponent < -1075) {
        return sign;
    }
    const bool subnormal = exponent < -1022;
    const int shift = subnormal ? scale + 1074 : 52 - k;
    ArithmeticWide numerator = ma, denominator = mb;
    if (shift >= 0) {
        numerator <<= shift;
    } else {
        denominator <<= -shift;
    }
    ArithmeticWide quotient = numerator / denominator;
    const ArithmeticWide remainder = numerator % denominator;
    if (remainder * 2 > denominator || (remainder * 2 == denominator && (quotient & 1))) {
        ++quotient;
    }
    return arithmetic_pack64(negative, exponent, uint64_t(quotient), subnormal);
}

inline uint64_t arithmetic_multiply64(uint64_t a, uint64_t b) {
    const bool negative = (a ^ b) >> 63;
    const ArithmeticWide product = ArithmeticWide(arithmetic_mantissa(a)) * arithmetic_mantissa(b);
    const int highest = arithmetic_highest(product);
    const int scale = arithmetic_scale(a) + arithmetic_scale(b);
    const int exponent = highest + scale;
    const uint64_t sign = negative ? 0x8000000000000000ull : 0;
    if (exponent > 1023) {
        return sign | 0x7ff0000000000000ull;
    }
    if (exponent < -1075) {
        return sign;
    }
    const bool subnormal = exponent < -1022;
    const int shift = subnormal ? -1074 - scale : highest - 52;
    return arithmetic_pack64(negative, exponent, uint64_t(arithmetic_round_shift(product, shift)), subnormal);
}

inline uint64_t arithmetic_operand25(uint64_t value) {
    unsigned highest = 52;
    if (!(value & 0x7ff0000000000000ull)) {
        const uint64_t fraction = value & 0xfffffffffffffull;
        if (!fraction) {
            return value;
        }
        highest = std::bit_width(fraction) - 1;
    }
    if (highest <= 24) {
        return value;
    }
    const unsigned shift = highest - 24;
    return (value & ~((1ull << shift) - 1)) + (((value >> (shift - 1)) & 1) << shift);
}

inline void arithmetic_exception(uint32_t& status, uint32_t flag) {
    if ((status & flag) != flag) {
        status |= 0x80000000u;
    }
    status |= flag;
    status = (status & ~0x60000000u) | ((status & 0x01f80700u) ? 0x20000000u : 0);
}

inline void experiment_single_arithmetic(CPUContext& context, uint32_t opcode) {
    if ((opcode != 0xec220824 && opcode != 0xec000072) || !(context.msr & 0x2000) ||
        (context.msr & 0x901) || (context.fpscr & 0x8fb)) {
        throw std::runtime_error("Single arithmetic opcode/FP/rounding/exception profile unavailable");
    }
    const bool divide = opcode == 0xec220824;
    const unsigned destination = (opcode >> 21) & 31;
    const unsigned left = (opcode >> 16) & 31;
    const unsigned right = divide ? (opcode >> 11) & 31 : (opcode >> 6) & 31;
    const uint64_t a = std::bit_cast<uint64_t>(context.fpr[left]);
    const uint64_t b = divide ? std::bit_cast<uint64_t>(context.fpr[right]) : arithmetic_operand25(std::bit_cast<uint64_t>(context.fpr[right]));
    const uint64_t ma = a & 0x7fffffffffffffffull, mb = b & 0x7fffffffffffffffull;
    const bool an = ma > 0x7ff0000000000000ull, bn = mb > 0x7ff0000000000000ull;
    const bool ai = ma == 0x7ff0000000000000ull, bi = mb == 0x7ff0000000000000ull;
    const uint64_t sign = (a ^ b) & 0x8000000000000000ull;
    uint64_t result;
    uint32_t status = context.fpscr;
    if (an || bn) {
        if ((an && !(a & 0x8000000000000ull)) || (bn && !(b & 0x8000000000000ull))) {
            arithmetic_exception(status, 0x01000000u);
        }
        result = (an ? a : b) | 0x8000000000000ull;
        status &= ~0x60000u;
    } else if ((divide && ((!ma && !mb) || (ai && bi))) || (!divide && ((!ma && bi) || (ai && !mb)))) {
        arithmetic_exception(status, divide ? (!mb ? 0x00200000u : 0x00400000u) : 0x00100000u);
        result = 0x7ff8000000000000ull;
        status &= ~0x60000u;
    } else if (divide && !mb) {
        arithmetic_exception(status, 0x04000000u);
        result = sign | 0x7ff0000000000000ull;
    } else if (divide ? ai : (ai || bi)) {
        result = sign | 0x7ff0000000000000ull;
    } else if (divide ? (!ma || bi) : (!ma || !mb)) {
        result = sign;
    } else {
        result = divide ? arithmetic_divide64(a, b) : arithmetic_multiply64(a, b);
    }
    if (!divide) {
        status &= ~0x60000u;
    }
    const bool nan = (result & 0x7fffffffffffffffull) > 0x7ff0000000000000ull;
    const uint32_t single = nan ? (uint32_t(result >> 32) & 0x80000000u) | 0x7fc00000u | uint32_t((result >> 29) & 0x7fffffu)
        : ni_single_nearest_bits(result, status & 4);
    const uint64_t expanded = widen_single_bits(single);
    context.fpr[destination] = std::bit_cast<double>(expanded);
    context.ps1[destination] = std::bit_cast<double>(expanded);
    context.fpscr = (status & ~0x1f000u) | (frsp_single_class(single) << 12);
}
}
