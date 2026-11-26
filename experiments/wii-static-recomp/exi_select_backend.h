#pragma once
#include "exi_init_backend.h"

namespace nwii::runtime::hw {
inline void experiment_exi_select_csr_write(uint32_t address, uint32_t value) {
    const bool selected = value == 0x80 || value == 0x100 || value == 0x200
        || value == 0x90 || value == 0x110 || value == 0x210;
    const auto before = experimentExiMaskState[0];
    const auto fields = before & ~0x1800u;
    const bool prior = before == 0x3800 || fields == 0x80 || fields == 0x100 || fields == 0x200
        || fields == 0x90 || fields == 0x110 || fields == 0x210;
    if (address != 0xcd006800 || !selected || !prior || (before & 0x1800u) != 0x1800u
        || (pi_intsr.load() & ~0x10000u)) {
        throw std::runtime_error("EXI selection outside measured channel0 idle profile");
    }
    experimentExiMaskState[0] = (before & 0x1800u) | value;
}
}
