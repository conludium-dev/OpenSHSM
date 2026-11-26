#pragma once
#include "runtime/cpu_context.h"
#include <bit>
#include <stdexcept>

namespace nwii::runtime {
inline void experiment_fcmp_ordered(CPUContext& context, uint32_t opcode) {
    if (opcode != 0xfc010040 || !(context.msr & 0x2000) ||
        (context.msr & 0x901) || (context.fpscr & 0x8fb)) {
        throw std::runtime_error("Ordered compare opcode/FP/exception profile unavailable");
    }
    const uint64_t a = std::bit_cast<uint64_t>(context.fpr[1]);
    const uint64_t b = std::bit_cast<uint64_t>(context.fpr[0]);
    const uint64_t ma = a & 0x7fffffffffffffffull;
    const uint64_t mb = b & 0x7fffffffffffffffull;
    const bool an = ma > 0x7ff0000000000000ull;
    const bool bn = mb > 0x7ff0000000000000ull;
    unsigned cc;
    uint32_t status = context.fpscr;
    if (an || bn) {
        cc = 1;
        const bool signaling = (an && !(a & 0x8000000000000ull)) || (bn && !(b & 0x8000000000000ull));
        status |= 0xa0080000u | (signaling ? 0x01000000u : 0);
    } else if (a == b || !(ma | mb)) {
        cc = 2;
    } else if ((a >> 63) != (b >> 63)) {
        cc = (a >> 63) ? 8 : 4;
    } else {
        const bool less = (a >> 63) ? ma > mb : ma < mb;
        cc = less ? 8 : 4;
    }
    context.cr[0].lt = cc == 8;
    context.cr[0].gt = cc == 4;
    context.cr[0].eq = cc == 2;
    context.cr[0].so = cc == 1;
    context.fpscr = (status & ~0xf000u) | (cc << 12);
}
}
