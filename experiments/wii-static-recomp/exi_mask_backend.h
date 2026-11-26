#pragma once
#include "runtime/hw/hw.h"
#include <array>
#include <stdexcept>

namespace nwii::runtime::hw {
inline std::array<uint32_t, 3> experimentExiMaskState{0x1800, 0x0880, 0};
inline constexpr std::array<uint32_t, 3> experimentExiWriteBase{0x1000, 0x0080, 0};
inline constexpr std::array<uint32_t, 3> experimentExiMaskBits{0x405, 0x405, 5};

inline void experiment_register_exi_masks(MMIODispatcher& dispatcher) {
    experimentExiMaskState = {0x1800, 0x0880, 0};
    for (unsigned channel = 0; channel < 3; ++channel) {
        const uint32_t base = 0xcd006800 + channel * 20;
        dispatcher.register_region(base, base + 3,
            [channel, base](uint32_t address) -> uint32_t {
                if (address != base) {
                    throw std::runtime_error("EXI unaligned read unverified");
                }
                return experimentExiMaskState[channel];
            },
            [channel, base](uint32_t address, uint32_t value) {
                if (address != base || (value & ~experimentExiMaskBits[channel]) != experimentExiWriteBase[channel]) {
                    throw std::runtime_error("EXI write outside measured mask profile");
                }
                experimentExiMaskState[channel] = (experimentExiMaskState[channel] & ~experimentExiMaskBits[channel])
                    | (value & experimentExiMaskBits[channel]);
                const bool asserted = (experimentExiMaskState[0] & 0x400u) || (experimentExiMaskState[1] & 0x400u);
                if (asserted) {
                    pi_intsr.fetch_or(0x10u);
                } else {
                    pi_intsr.fetch_and(~0x10u);
                }
            },
            [](uint32_t) -> uint16_t {
                throw std::runtime_error("EXI halfword read unverified");
            },
            [](uint32_t, uint16_t) {
                throw std::runtime_error("EXI halfword write unverified");
            });
    }
}
}
