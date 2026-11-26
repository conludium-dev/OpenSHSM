#pragma once
#include "si_xy_frontend.h"
#include "si_idle_backend.h"

namespace nwii::runtime {
inline void experiment_si_idle_mapping(CPUContext& context, uint32_t address, bool write) {
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, write);
    if (address != 0xcd006434 || context.msr != 0x2030 || mapping.physical != 0x0d006434 || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("SI idle access outside measured mapping profile");
    }
}

inline uint32_t experiment_si_idle_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (instruction != 0x8020fc98) {
        throw std::runtime_error("SI idle read caller unverified");
    }
    experiment_si_idle_mapping(context, address, false);
    return MMIODispatcher::get().read32(address);
}

inline void experiment_si_idle_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x8020fcb0) {
        throw std::runtime_error("SI idle write caller unverified");
    }
    experiment_si_idle_mapping(context, address, true);
    MMIODispatcher::get().write32(address, value);
}
}
