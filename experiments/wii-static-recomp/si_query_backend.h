#pragma once
#include "si_idle_backend.h"

namespace nwii::runtime::hw {
inline void experiment_register_si_query(MMIODispatcher& dispatcher) {
    experiment_register_si_idle(dispatcher);
    experimentSiQuery.enabled = true;
    dispatcher.register_region(0xcd006438, 0xcd00643b,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd006438) {
                throw std::runtime_error("SI query status address unverified");
            }
            return experimentSiQuery.status;
        },
        [](uint32_t address, uint32_t value) {
            if (address != 0xcd006438 || (value != 0 && value != 0x08000000 && value != 0x00080000 && value != 0x800 && value != 8)) {
                throw std::runtime_error("SI query status write unverified");
            }
            experimentSiQuery.status &= ~value;
        },
        [](uint32_t) -> uint16_t { throw std::runtime_error("SI query status halfword read unverified"); },
        [](uint32_t, uint16_t) { throw std::runtime_error("SI query status halfword write unverified"); });
    dispatcher.register_region(0xcd006480, 0xcd006483,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd006480) {
                throw std::runtime_error("SI query buffer address unverified");
            }
            return experimentSiQuery.buffer;
        },
        [](uint32_t address, uint32_t value) {
            if (address != 0xcd006480 || value != 0 || (experimentSiControl & 1u)) {
                throw std::runtime_error("SI query payload unverified");
            }
            experimentSiQuery.buffer = value;
            experimentSiQuery.payloadReady = true;
        },
        [](uint32_t) -> uint16_t { throw std::runtime_error("SI query buffer halfword read unverified"); },
        [](uint32_t, uint16_t) { throw std::runtime_error("SI query buffer halfword write unverified"); });
}
}
