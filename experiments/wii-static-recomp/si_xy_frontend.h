#pragma once
#include "vi_clock_frontend.h"
#include "si_xy_backend.h"

namespace nwii::runtime {
inline void experiment_si_xy_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (address != 0xcd006430 || instruction != 0x8020feec) {
        experiment_vi_next_write32(context, address, value, instruction);
        return;
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, true);
    if (context.msr != 0x2030 || mapping.physical != 0x0d006430 || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("SI poll write outside measured mapping profile");
    }
    MMIODispatcher::get().write32(address, value);
}
}
