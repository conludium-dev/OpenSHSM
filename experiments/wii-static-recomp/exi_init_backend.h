#pragma once
#include "exi_mask_backend.h"

namespace nwii::runtime::hw {
inline void experiment_register_exi_idle_controls(MMIODispatcher& dispatcher) {
    for (unsigned channel = 0; channel < 3; ++channel) {
        const auto base = 0xcd00680c + channel * 20;
        dispatcher.register_region(base, base + 3,
            [base](uint32_t address) -> uint32_t {
                if (address != base) {
                    throw std::runtime_error("EXI control alignment unverified");
                }
                return 0;
            },
            [](uint32_t, uint32_t) {
                throw std::runtime_error("EXI active transfer write unverified");
            },
            [](uint32_t) -> uint16_t {
                throw std::runtime_error("EXI control halfword read unverified");
            },
            [](uint32_t, uint16_t) {
                throw std::runtime_error("EXI control halfword write unverified");
            });
    }
}

inline void experiment_exi_init_csr_write(uint32_t address, uint32_t value) {
    unsigned channel = 3;
    for (unsigned index = 0; index < 3; ++index) {
        if (address == 0xcd006800 + index * 20) {
            channel = index;
        }
    }
    if (channel == 3 || (value != 0 && (channel != 0 || value != 0x2000)) || (pi_intsr.load() & ~0x10000u)) {
        throw std::runtime_error("EXI initialization write outside measured idle profile");
    }
    const auto before = experimentExiMaskState[channel];
    if ((channel == 0 && before != 0x1800 && before != 0x3800)
        || (channel == 1 && before != 0x0880 && before != 0x0800) || (channel == 2 && before != 0)) {
        throw std::runtime_error("EXI initialization channel state unverified");
    }
    experimentExiMaskState[channel] = channel == 0 ? 0x1800 | value : channel == 1 ? 0x800 : 0;
}
}
