#pragma once
#include "runtime/cpu_context.h"
#include <bit>
#include <stdexcept>

namespace nwii::runtime {
inline void experiment_mtfsf(CPUContext& context, uint32_t opcode) {
    if (!(context.msr & 0x2000)) {
        throw std::runtime_error("Floating-point unavailable exception delivery is unimplemented");
    }
    uint32_t mask = 0;
    const uint32_t fields = (opcode >> 17) & 255;
    for (unsigned index = 0; index < 8; ++index) {
        if (fields & (1u << index)) {
            mask |= 15u << (index * 4);
        }
    }
    const uint32_t value = static_cast<uint32_t>(std::bit_cast<uint64_t>(context.fpr[(opcode >> 11) & 31]));
    uint32_t next = ((context.fpscr & ~mask) | (value & mask)) & 0xfffff7ffu;
    next &= ~0x60000000u;
    if (next & 0x01f80700u) {
        next |= 0x20000000u;
    }
    if ((next >> 22) & (next & 0xf8)) {
        next |= 0x40000000u;
    }
    if ((next & 0x40000000u) && (context.msr & 0x900)) {
        throw std::runtime_error("Floating-point program exception delivery is unimplemented");
    }
    context.fpscr = next;
    if (opcode & 1) {
        context.cr[1].lt = next & 0x80000000u;
        context.cr[1].gt = next & 0x40000000u;
        context.cr[1].eq = next & 0x20000000u;
        context.cr[1].so = next & 0x10000000u;
    }
}
}
