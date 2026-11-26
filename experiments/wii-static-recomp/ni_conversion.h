#pragma once
#include <bit>
#include <cstdint>
#include <stdexcept>

namespace nwii::runtime {
inline uint64_t round_shift_even(uint64_t value, unsigned shift) {
    if (!shift) {
        return value;
    }
    if (shift > 64) {
        return 0;
    }
    if (shift == 64) {
        return value > 0x8000000000000000ull ? 1 : 0;
    }
    uint64_t result = value >> shift;
    const uint64_t remainder = value & ((uint64_t(1) << shift) - 1);
    const uint64_t half = uint64_t(1) << (shift - 1);
    if (remainder > half || (remainder == half && (result & 1))) {
        ++result;
    }
    return result;
}

inline uint32_t ni_single_nearest_bits(uint64_t value, bool ni) {
    const uint32_t sign = (value >> 32) & 0x80000000u;
    const uint64_t magnitude = value & 0x7fffffffffffffffull;
    const unsigned exponent = (value >> 52) & 2047;
    const uint64_t fraction = value & 0x000fffffffffffffull;
    if (exponent == 2047) {
        if (fraction) {
            throw std::runtime_error("NaN payload/exception conversion requires verification");
        }
        return sign | 0x7f800000u;
    }
    if (ni && magnitude < 0x3810000000000000ull) {
        return sign;
    }
    int unbiased = exponent ? int(exponent) - 1023 : -1022;
    const uint64_t mantissa = fraction | (exponent ? uint64_t(1) << 52 : 0);
    if (unbiased < -126) {
        return sign | uint32_t(round_shift_even(mantissa, unsigned(-unbiased - 97)));
    }
    uint64_t rounded = round_shift_even(mantissa, 29);
    if (rounded == (uint64_t(1) << 24)) {
        rounded >>= 1;
        ++unbiased;
    }
    if (unbiased > 127) {
        return sign | 0x7f800000u;
    }
    return sign | (uint32_t(unbiased + 127) << 23) | uint32_t(rounded & 0x7fffff);
}

inline uint64_t widen_single_bits(uint32_t value) {
    const uint64_t sign = uint64_t(value & 0x80000000u) << 32;
    const unsigned exponent = (value >> 23) & 255;
    const uint32_t fraction = value & 0x7fffff;
    if (exponent == 255) {
        return sign | 0x7ff0000000000000ull | (uint64_t(fraction) << 29);
    }
    if (!exponent) {
        if (!fraction) {
            return sign;
        }
        const unsigned highest = 31 - std::countl_zero(fraction);
        return sign | (uint64_t(int(highest) - 149 + 1023) << 52) |
               ((uint64_t(fraction) << (52 - highest)) & 0x000fffffffffffffull);
    }
    return sign | (uint64_t(int(exponent) - 127 + 1023) << 52) | (uint64_t(fraction) << 29);
}
}
