#pragma once
#include "dsp_startup_frontend.h"

namespace nwii::runtime {
inline void experiment_memory_protection_observe(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    try { bat_memory_write16(context, address, value); }
    catch (const std::runtime_error&) {
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
        std::cout << "MI_INIT_REFUSAL instruction=" << std::hex << instruction << " address=" << address
                  << " physical=" << mapping.physical << " value=" << value << " msr=" << context.msr
                  << " lr=" << context.lr << " wimg=" << unsigned(mapping.wimg) << " slot=" << mapping.slot
                  << " width=2" << std::dec << '\n';
        throw;
    }
}
}
