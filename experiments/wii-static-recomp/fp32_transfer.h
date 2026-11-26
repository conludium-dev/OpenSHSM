#pragma once
#include "code_write_observer.h"
#include <bit>

namespace nwii::runtime {
inline uint64_t experiment_fp32_expand(uint32_t bits) {
    const uint64_t sign = uint64_t(bits & 0x80000000u) << 32;
    const uint32_t exponent = (bits >> 23) & 255;
    const uint32_t fraction = bits & 0x7fffff;
    if (exponent == 255) {
        return sign | (uint64_t(2047) << 52) | (uint64_t(fraction) << 29);
    }
    if (exponent) {
        return sign | (uint64_t(exponent + 896) << 52) | (uint64_t(fraction) << 29);
    }
    if (!fraction) {
        return sign;
    }
    const unsigned leading = std::bit_width(fraction) - 1;
    return sign | (uint64_t(874 + leading) << 52) |
        (uint64_t(fraction - (1u << leading)) << (52 - leading));
}
inline uint32_t experiment_fp32_exact_narrow(uint64_t bits) {
    const uint32_t sign = uint32_t(bits >> 32) & 0x80000000u;
    const unsigned exponent = unsigned((bits >> 52) & 2047);
    const uint64_t fraction = bits & 0xfffffffffffffull;
    uint32_t result = sign;
    if (exponent == 2047) {
        result |= 0x7f800000u | uint32_t(fraction >> 29);
    } else if (exponent >= 897 && exponent <= 1150) {
        result |= (exponent - 896) << 23 | uint32_t(fraction >> 29);
    } else if (exponent >= 874 && exponent <= 896) {
        result |= uint32_t((fraction | (1ull << 52)) >> (926 - exponent));
    }
    if (experiment_fp32_expand(result) != bits) {
        throw std::runtime_error("FP32 store outside verified exact-single representation");
    }
    return result;
}
inline bool experiment_fp32_opcode(uint32_t opcode) {
    const unsigned primary = opcode >> 26;
    const unsigned extended = (opcode >> 1) & 1023;
    return primary == 48 || primary == 52 || (primary == 31 && !(opcode & 1) &&
        (extended == 535 || extended == 663));
}
inline void experiment_fp32_transfer(CPUContext& context, uint32_t opcode) {
    if (!experiment_fp32_opcode(opcode) || !(context.msr & 0x2000) || (context.msr & 0x901)) {
        throw std::runtime_error("FP32 opcode/FP availability/exception profile unavailable");
    }
    const unsigned reg = (opcode >> 21) & 31;
    const unsigned ra = (opcode >> 16) & 31;
    const uint32_t base = ra ? context.gpr[ra] : 0;
    const uint32_t offset = opcode >> 26 == 31 ? context.gpr[(opcode >> 11) & 31] :
        uint32_t(int32_t(int16_t(opcode)));
    const uint32_t address = base + offset;
    if (address & 3) {
        throw std::runtime_error("FP32 alignment exception delivery unavailable");
    }
    const bool load = opcode >> 26 == 48 || (opcode >> 26 == 31 && ((opcode >> 1) & 1023) == 535);
    if (load) {
        const uint64_t bits = experiment_fp32_expand(bat_memory_read32(context,address));
        context.fpr[reg] = std::bit_cast<double>(bits);
        context.ps1[reg] = std::bit_cast<double>(bits);
    } else {
        const uint32_t bits = experiment_fp32_exact_narrow(std::bit_cast<uint64_t>(context.fpr[reg]));
        bat_memory_write32(context,address,bits);
    }
}
}
