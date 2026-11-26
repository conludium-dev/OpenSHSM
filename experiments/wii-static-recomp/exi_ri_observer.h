#pragma once
#include "memory_protection_frontend.h"

namespace nwii::runtime {
inline uint32_t experiment_exi_ri_observe(CPUContext& context, uint32_t address, uint32_t instruction) {
    try { return experiment_si_query_read32(context, address, instruction); }
    catch (const std::runtime_error&) {
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
        std::cout << "EXI_RI_REFUSAL instruction=" << std::hex << instruction << " address=" << address
                  << " physical=" << mapping.physical << " msr=" << context.msr << " lr=" << context.lr
                  << " channel=" << context.gpr[27] << " device=" << context.gpr[28] << " clock=" << context.gpr[29]
                  << " csr=" << hw::experimentExiMaskState[0] << " wimg=" << unsigned(mapping.wimg)
                  << " slot=" << mapping.slot << " width=4" << std::dec << '\n';
        throw;
    }
}
}
