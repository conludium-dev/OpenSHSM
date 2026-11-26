#pragma once
#include "si_idle_frontend.h"
#include "si_query_backend.h"

namespace nwii::runtime {
inline bool experiment_si_query_mapping(CPUContext& context, uint32_t address, uint32_t instruction, bool write) {
    if (address != 0xcd006434 && address != 0xcd006438 && address != 0xcd006480) {
        return false;
    }
    const bool irq_allowed = hw::experimentSiQuery.interruptProfile &&
        ((write && address == 0xcd006438 && instruction == 0x8020f99c) ||
        (!write && ((address == 0xcd006434 && instruction == 0x8020f86c) || (address == 0xcd006438 && instruction == 0x8020f98c))));
    const bool allowed = irq_allowed || (write ?
        (address == 0xcd006438 && instruction == 0x8020fd68) || (address == 0xcd006480 && instruction == 0x8020fe30) ||
        (address == 0xcd006434 && (instruction == 0x8020fe8c || instruction == 0x8020f580)) :
        (address == 0xcd006438 && (instruction == 0x8020fd58 || instruction == 0x8020f570)) ||
        (address == 0xcd006480 && instruction == 0x8020f694) ||
        (address == 0xcd006434 && (instruction == 0x8020fe60 || instruction == 0x8020f574 || instruction == 0x8020f794)));
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, write);
    if (!allowed || context.msr != 0x2030 || mapping.physical != (address & 0x1fffffffu) || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("SI query MMIO caller/mapping unverified");
    }
    return true;
}
inline uint32_t experiment_si_query_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
#ifdef SHSM_SI_EXTERNAL_DELIVERY
    if ((address == 0xcc003000 && instruction == 0x802179d0) || (address == 0xcc003004 && instruction == 0x802179d4)) {
        const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
        if (context.msr != 0x2030 || !hw::experimentSiQuery.interruptProfile || mapping.physical != (address & 0x1fffffffu)
            || mapping.wimg != 5 || mapping.slot != 1) {
            throw std::runtime_error("SI external dispatcher PI mapping unverified");
        }
        return MMIODispatcher::get().read32(address);
    }
#endif
    if (experiment_si_query_mapping(context, address, instruction, false)) {
        return MMIODispatcher::get().read32(address);
    }
    return experiment_getid_read32(context, address, instruction);
}
inline void experiment_si_query_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (experiment_si_query_mapping(context, address, instruction, true)) {
        MMIODispatcher::get().write32(address, value);
        return;
    }
    experiment_getid_write32(context, address, value, instruction);
}
}
