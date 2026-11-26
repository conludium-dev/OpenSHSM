#pragma once
#include "memory_protection_frontend.h"
namespace nwii::runtime {
inline uint32_t experiment_reset_code_observe(CPUContext& context, uint32_t address, uint32_t instruction) {
    try { return experiment_si_query_read32(context, address, instruction); }
    catch (const std::runtime_error&) {
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
        std::cout << "RESET_CODE_REFUSAL instruction=" << std::hex << instruction << " address=" << address
                  << " physical=" << mapping.physical << " msr=" << context.msr << " lr=" << context.lr
                  << " wimg=" << unsigned(mapping.wimg) << " slot=" << mapping.slot << " width=4" << std::dec << '\n';
        throw;
    }
}
}
