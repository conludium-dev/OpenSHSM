#pragma once
#include "fp32_transfer.h"
#include "frsp_adapter.h"

namespace nwii::runtime {
inline void experiment_fsubs_integer_bias(CPUContext& context,uint32_t opcode) {
    if (std::getenv("SHSM_FP_INITIALIZER_DISABLED")) {
        experiment_ni_guard(context,opcode,0x8000c31c);
    }
    if (opcode >> 26 != 59 || ((opcode >> 1) & 31) != 20 || (opcode & 0x7c1) ||
        !(context.msr & 0x2000) || (context.msr & 0x901) || (context.fpscr & 0x8fb)) {
        throw std::runtime_error("Fsubs integer-bias opcode/FP/rounding profile unavailable");
    }
    const unsigned destination = (opcode >> 21) & 31;
    const unsigned left = (opcode >> 16) & 31;
    const unsigned right = (opcode >> 11) & 31;
    const uint64_t a = std::bit_cast<uint64_t>(context.fpr[left]);
    const uint64_t b = std::bit_cast<uint64_t>(context.fpr[right]);
    if ((a >> 32) != 0x43300000 || b != 0x4330000080000000ull) {
        throw std::runtime_error("Fsubs operands outside measured signed-int bias family");
    }
    const int64_t integer = int64_t(uint32_t(a)) - 0x80000000ll;
    const uint64_t magnitude = integer < 0 ? uint64_t(-integer) : uint64_t(integer);
    uint64_t exact = 0;
    if (magnitude) {
        const unsigned highest = std::bit_width(magnitude) - 1;
        exact = (integer < 0 ? 0x8000000000000000ull : 0) | (uint64_t(highest + 1023) << 52) |
            ((magnitude - (1ull << highest)) << (52 - highest));
    }
    const uint32_t single = ni_single_nearest_bits(exact,context.fpscr & 4);
    const uint64_t result = experiment_fp32_expand(single);
    const uint32_t status = (context.fpscr & ~0x1f000u) | (frsp_single_class(single) << 12);
    context.fpr[destination] = std::bit_cast<double>(result);
    context.ps1[destination] = std::bit_cast<double>(result);
    context.fpscr = status;
}
}
