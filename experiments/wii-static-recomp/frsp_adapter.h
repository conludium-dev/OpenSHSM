#pragma once
#include "ni_conversion.h"
#include "processor_adapter.h"

namespace nwii::runtime {
inline unsigned frsp_single_class(uint32_t value) {
    const bool negative = value & 0x80000000u;
    const unsigned exponent = (value >> 23) & 255;
    const uint32_t fraction = value & 0x7fffff;
    if (exponent == 255) {
        if (fraction) {
            return 17;
        }
        return negative ? 9 : 5;
    }
    if (!exponent) {
        if (fraction) {
            return negative ? 24 : 20;
        }
        return negative ? 18 : 2;
    }
    return negative ? 8 : 4;
}

inline void experiment_frsp(CPUContext& context, uint32_t opcode) {
    if (opcode >> 26 != 63 || ((opcode >> 1) & 1023) != 12 || (opcode & 1) || !(context.msr & 0x2000) ||
        (context.msr & 0x900) || (context.fpscr & 0x8fb)) {
        throw std::runtime_error("FRSP opcode/FP availability/rounding/exception profile unavailable");
    }
    const unsigned source = (opcode >> 11) & 31;
    const unsigned destination = (opcode >> 21) & 31;
    const uint64_t input = std::bit_cast<uint64_t>(context.fpr[source]);
    const uint32_t single = ni_single_nearest_bits(input, context.fpscr & 4);
    const uint64_t result = widen_single_bits(single);
    uint32_t next = context.fpscr & ~0x0007f000u;
    if (input != result) {
        if (!(next & 0x02000000u)) {
            next |= 0x80000000u;
        }
        next |= 0x02020000u;
        next &= ~0x60000000u;
        if (next & 0x01f80700u) {
            next |= 0x20000000u;
        }
    }
    if ((result & 0x7fffffffffffffffull) > (input & 0x7fffffffffffffffull)) {
        next |= 0x00040000u;
    }
    next |= frsp_single_class(single) << 12;
    context.fpr[destination] = std::bit_cast<double>(result);
    context.ps1[destination] = std::bit_cast<double>(result);
    context.fpscr = next;
    if (opcode & 1) {
        context.cr[1].lt = next & 0x80000000u;
        context.cr[1].gt = next & 0x40000000u;
        context.cr[1].eq = next & 0x20000000u;
        context.cr[1].so = next & 0x10000000u;
    }
}
}
