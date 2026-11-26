#pragma once
#include "runtime/hw/mmio_dispatcher.h"
#include <stdexcept>

namespace nwii::runtime::hw {
inline uint16_t experimentMiMask = 0;
inline uint16_t experimentMiProtection = 0;
inline uint16_t experimentMiUnknown20 = 0;

inline void experiment_register_mi_protection(MMIODispatcher& dispatcher) {
    for (uint32_t address : {0xcc004010u, 0xcc004020u}) {
        dispatcher.register_region(address, address + 1,
            [](uint32_t) -> uint32_t { throw std::runtime_error("MI protection read32 unverified"); },
            [](uint32_t, uint32_t) { throw std::runtime_error("MI protection write32 unverified"); },
            [address](uint32_t actual) -> uint16_t {
                if (actual != address) { throw std::runtime_error("MI protection unaligned read"); }
                return address == 0xcc004010 ? experimentMiProtection : experimentMiUnknown20;
            },
            [address](uint32_t actual, uint16_t value) {
                if (actual != address || value != (address == 0xcc004010 ? 0xff : 0)) {
                    throw std::runtime_error("MI protection startup write unverified");
                }
                (address == 0xcc004010 ? experimentMiProtection : experimentMiUnknown20) = value;
            });
    }
}

inline void experiment_register_mi_mask(MMIODispatcher& dispatcher) {
    experimentMiMask = 0;
    dispatcher.register_region(0xcc00401c, 0xcc00401d,
        [](uint32_t) -> uint32_t { throw std::runtime_error("MI mask read32 unverified"); },
        [](uint32_t, uint32_t) { throw std::runtime_error("MI mask write32 unverified"); },
        [](uint32_t address) -> uint16_t {
            if (address != 0xcc00401c) {
                throw std::runtime_error("MI mask unaligned read");
            }
            return experimentMiMask;
        },
        [](uint32_t address, uint16_t value) {
            if (address != 0xcc00401c) {
                throw std::runtime_error("MI mask unaligned write");
            }
            experimentMiMask = value;
        });
}
}
