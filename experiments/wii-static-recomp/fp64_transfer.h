#pragma once
#include "code_write_observer.h"

namespace nwii::runtime {
inline bool experiment_fp64_opcode(uint32_t opcode) {
    const unsigned primary = opcode >> 26;
    return primary == 50 || primary == 51 || primary == 54 || primary == 55 ||
           (primary == 31 && !(opcode & 1) && (((opcode >> 1) & 1023) == 599 || ((opcode >> 1) & 1023) == 727));
}

inline void experiment_fp64_transfer(CPUContext& context, uint32_t opcode) {
    if (!experiment_fp64_opcode(opcode) || !(context.msr & 0x2000) || (context.msr & 0x901)) {
        throw std::runtime_error("FP64 opcode/FP availability/exception profile unavailable");
    }
    const unsigned primary = opcode >> 26;
    const unsigned reg = (opcode >> 21) & 31;
    const unsigned ra = (opcode >> 16) & 31;
    const bool update = primary == 51 || primary == 55;
    if (update && !ra) {
        throw std::runtime_error("FP64 update with zero RA unavailable");
    }
    const uint32_t base = ra ? context.gpr[ra] : 0;
    const uint32_t offset = primary == 31 ? context.gpr[(opcode >> 11) & 31] :
        static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(opcode & 65535)));
    const uint32_t address = base + offset;
    if (address & 3) {
        throw std::runtime_error("FP64 alignment exception delivery unavailable");
    }
    const bool load = primary == 50 || primary == 51 || (primary == 31 && ((opcode >> 1) & 1023) == 599);
    if (load) {
        const uint64_t bits = bat_memory_read64(context, address);
        context.fpr[reg] = std::bit_cast<double>(bits);
    } else {
        bat_memory_write64(context, address, std::bit_cast<uint64_t>(context.fpr[reg]));
    }
    if (update) {
        context.gpr[ra] = address;
    }
}
}
