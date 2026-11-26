#pragma once
#include "fp64_transfer.h"

namespace nwii::runtime {
inline void experiment_fp64_boot_observe(CPUContext& context, uint32_t opcode, uint32_t instruction) {
    try {
        experiment_fp64_transfer(context, opcode);
    } catch (const std::runtime_error&) {
        const unsigned ra = (opcode >> 16) & 31;
        const uint32_t offset = opcode >> 26 == 31 ? context.gpr[(opcode >> 11) & 31] :
            static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(opcode)));
        std::cout << "FP64_REFUSAL instruction=" << std::hex << instruction << " opcode=" << opcode
                  << " msr=" << context.msr << " address=" << (ra ? context.gpr[ra] : 0) + offset
                  << " lr=" << context.lr << " fpscr=" << context.fpscr << std::dec << '\n';
        try {
            const uint32_t current = bat_memory_read32(context, 0x800000d4);
            std::cout << "FP64_OS current=" << std::hex << current
                      << " physical=" << bat_memory_read32(context, 0x800000c0)
                      << " owner=" << bat_memory_read32(context, 0x800000d8)
                      << " handler=" << bat_memory_read32(context, 0x8000301c)
                      << " flags=" << bat_memory_read16(context, current + 0x1a2)
                      << " savedMsr=" << bat_memory_read32(context, current + 0x19c)
                      << std::dec << '\n';
        } catch (const std::runtime_error&) {
            std::cout << "FP64_OS observation unavailable\n";
        }
        throw;
    }
}
}
