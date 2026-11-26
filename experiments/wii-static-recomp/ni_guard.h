#pragma once
#include "frsp_adapter.h"
#include <sstream>

namespace nwii::runtime {
inline bool experiment_fp_opcode(uint32_t opcode) {
    const unsigned primary = opcode >> 26;
    if (primary == 4 || (primary >= 48 && primary <= 57) || primary == 59 ||
        primary == 60 || primary == 61 || primary == 63) {
        return true;
    }
    if (primary == 31) {
        const unsigned extended = (opcode >> 1) & 1023;
        return extended == 535 || extended == 567 || extended == 599 || extended == 631 ||
               extended == 663 || extended == 695 || extended == 727 || extended == 759 || extended == 983;
    }
    return false;
}

inline void experiment_ni_set(CPUContext& context, uint32_t opcode) {
    const uint32_t summary = (context.fpscr & 0x01f80700u) ? 0x20000000u : 0;
    if (opcode != 0xffa0004cu || !(context.msr & 0x2000) || (context.msr & 0x900) ||
        (context.fpscr & 0x8fb) || (context.fpscr & 0x60000000u) != summary) {
        throw std::runtime_error("NI setter opcode/FP/rounding/exception profile unavailable");
    }
    context.fpscr |= 4;
}

inline void experiment_ni_guard(CPUContext& context, uint32_t opcode, uint32_t address) {
    if (!(context.fpscr & 4) || !experiment_fp_opcode(opcode) || opcode == 0xffa0004cu ||
        (opcode >> 26 == 63 && ((opcode >> 1) & 1023) == 12 && !(opcode & 1))) {
        return;
    }
    std::ostringstream message;
    message << "NI unsupported FP before instruction address=" << std::hex << address << " opcode=" << opcode;
    throw std::runtime_error(message.str());
}
}
