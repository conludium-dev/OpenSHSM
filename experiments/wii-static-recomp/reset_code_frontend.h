#pragma once
#include "memory_protection_frontend.h"
namespace nwii::runtime {
inline bool experimentResetCode = false;
inline unsigned experimentResetCodeReads = 0;
inline uint32_t experiment_reset_code_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (address != 0xcc003024) { return experiment_si_query_read32(context, address, instruction); }
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
    if (!experimentResetCode || instruction != 0x80219504 || context.msr != 0x2032 || mapping.physical != 0x0c003024 ||
        mapping.slot != 1 || mapping.wimg != 5 || bat_memory_read32(context, 0x80492240) != 0) {
        throw std::runtime_error("Cold reset-code caller/mapping/profile unverified");
    }
    const auto value = MMIODispatcher::get().read32(address);
    if (value != 0) { throw std::runtime_error("Non-cold PI reset value unverified"); }
    ++experimentResetCodeReads;
    return value;
}
}
