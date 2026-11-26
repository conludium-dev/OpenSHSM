#pragma once
#include "si_xy_backend.h"
#include "runtime/hw/hw.h"

namespace nwii::runtime::hw {
inline uint32_t experimentSiControl = 0;
inline uint32_t experimentSiControlWritten = 0;
struct ExperimentSiQuery {
    bool enabled = false;
    bool payloadReady = false;
    bool loseCompletion = false;
    bool wrongResponse = false;
    bool interruptProfile = false;
    uint32_t status = 0;
    uint32_t buffer = 0;
    uint32_t callbackChannel = 0;
    uint32_t callbackStatus = 0;
    uint32_t callbackCount = 0;
};
inline ExperimentSiQuery experimentSiQuery;

inline bool experiment_si_query_control_valid() {
    const auto fields = experimentSiControl & ~7u;
    return experimentSiControl == 0 || fields == 0x00010300 || fields == 0x20010300 || fields == 0xa0010300 ||
        (experimentSiQuery.interruptProfile && (fields == 0x40010300 || fields == 0x60010300 || fields == 0xe0010300));
}

inline void experiment_register_si_idle(MMIODispatcher& dispatcher) {
    dispatcher.register_region(0xcd006434, 0xcd006437,
        [](uint32_t address) -> uint32_t {
            if (experimentSiQuery.enabled) {
                if (address != 0xcd006434 || !experiment_si_query_control_valid()) {
                    throw std::runtime_error("SI query control read profile unverified");
                }
                return experimentSiControl;
            }
            if (address != 0xcd006434 || experimentSiControl != 0) {
                throw std::runtime_error("SI control read outside measured idle profile");
            }
            return experimentSiControl;
        },
        [](uint32_t address, uint32_t value) {
            if (experimentSiQuery.enabled) {
                if (address != 0xcd006434 || !experiment_si_query_control_valid()) {
                    throw std::runtime_error("SI query control write profile unverified");
                }
                if (value == 0x80000000 && experimentSiControl == 0) {
                    experimentSiControlWritten = value;
                    return;
                }
                const auto channel = (value >> 1) & 3u;
                const auto command = (experimentSiControl & 0x20000000) | 0x80010301u | (channel << 1) |
                    (experimentSiQuery.interruptProfile ? 0x40000000u : 0u);
                if (value == command && experimentSiQuery.payloadReady && !(experimentSiControl & 1u)) {
                    if (experimentSiQuery.status & (8u << ((3u - channel) * 8u))) {
                        throw std::runtime_error("SI query channel status not acknowledged");
                    }
                    experimentSiControlWritten = value;
                    experimentSiQuery.payloadReady = false;
                    experimentSiControl = value & ~0x80000000u;
                    if (!experimentSiQuery.loseCompletion) {
                        experimentSiControl = (experimentSiControl & ~1u) | 0xa0000000u;
                        experimentSiQuery.status |= 8u << ((3u - channel) * 8u);
                        experimentSiQuery.buffer = experimentSiQuery.wrongResponse ? 0x01020300 : 0;
                        if (experimentSiQuery.interruptProfile) {
                            trigger_pi_interrupt(8);
                        }
                    }
                    return;
                }
                if ((experimentSiControl & 0x80000001u) == 0x80000000u && value == experimentSiControl) {
                    experimentSiControlWritten = value;
                    experimentSiControl &= ~0x80000000u;
                    if (experimentSiQuery.interruptProfile) {
                        clear_pi_interrupt(8);
                    }
                    return;
                }
                throw std::runtime_error("SI query control command unverified");
            }
            if (address != 0xcd006434 || experimentSiControl != 0 || value != 0x80000000) {
                throw std::runtime_error("SI control write outside measured idle profile");
            }
            experimentSiControlWritten = value;
        },
        [](uint32_t) -> uint16_t {
            throw std::runtime_error("SI control halfword read unverified");
        },
        [](uint32_t, uint16_t) {
            throw std::runtime_error("SI control halfword write unverified");
        });
}
}
