#pragma once
#include "runtime/hw/mmio_dispatcher.h"
#include <stdexcept>

namespace nwii::runtime::hw {
inline uint32_t experimentSiPoll = 0;

inline void experiment_register_si_xy(MMIODispatcher& dispatcher) {
    dispatcher.register_region(0xcd006430, 0xcd006433,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd006430) {
                throw std::runtime_error("SI poll read address unverified");
            }
            return experimentSiPoll;
        },
        [](uint32_t address, uint32_t value) {
            bool measured = false;
            for (unsigned index = 0; index < 8; ++index) {
                const auto retained = index * 0x04000001u;
                measured |= value == (0x01ec0200u | retained) || value == (0x001c1300u | retained);
            }
            if (address != 0xcd006430 || !measured) {
                throw std::runtime_error("SI poll write outside measured values");
            }
            experimentSiPoll = value;
        },
        [](uint32_t) -> uint16_t {
            throw std::runtime_error("SI poll halfword read unverified");
        },
        [](uint32_t, uint16_t) {
            throw std::runtime_error("SI poll halfword write unverified");
        });
}
}
