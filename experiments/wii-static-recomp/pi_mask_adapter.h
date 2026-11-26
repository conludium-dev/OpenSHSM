#pragma once
#include "mmio_write_observer.h"
#include "runtime/hw/hw.h"

namespace nwii::runtime {
inline void experiment_pi_mask_write(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x802175d0u || address != 0xcc003004u || context.msr != 0x2030u ||
        memory_context(context).hid0 != 0xc200u) {
        throw std::runtime_error("PI mask store outside verified caller/address/EE0 profile");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0c003004u || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("PI mask store outside verified uncached BAT mapping");
    }
    static std::once_flag registered;
    std::call_once(registered, [] { hw::register_pi(MMIODispatcher::get()); });
    MMIODispatcher::get().write32(address, value);
}
}
