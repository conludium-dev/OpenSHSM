#pragma once
#include "table_write_observer.h"

namespace nwii::runtime {
inline void experiment_template_reset(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x80211b0cu || address != 0x80211c08u || value != 0x38600000u) {
        throw std::runtime_error("Template reset outside verified instruction/word/value");
    }
    // Reuse the verified cache commit after validating the distinct original reset caller.
    experiment_template_patch(context, address, value, 0x802119a8u);
}
}
