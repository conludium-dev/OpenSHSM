#pragma once
#include "si_query_frontend.h"

namespace nwii::runtime::hw {
struct ExperimentPcClockProfile {
    bool enabled = false;
    unsigned mode = 0;
    unsigned phase = 0;
    std::vector<std::array<uint32_t, 3>> writes;
    std::vector<uint64_t> timestamps;
    bool audioStartupFp = false;
};
inline ExperimentPcClockProfile experimentPcClock;

inline void experiment_register_ipc_clock_profile(MMIODispatcher& dispatcher) {
    for (uint32_t address : {0xcd800180u, 0xcd8001ccu, 0xcd8001d0u}) {
        dispatcher.register_region(address, address + 3,
            [address](uint32_t actual) -> uint32_t {
                if (!experimentPcClock.enabled || actual != address) {
                    throw std::runtime_error("PC clock profile read disabled or unaligned");
                }
                return 0;
            },
            [address](uint32_t actual, uint32_t value) {
                auto& profile = experimentPcClock;
                if (!profile.enabled || actual != address || profile.phase >= 6) {
                    throw std::runtime_error("PC clock profile write disabled or out of sequence");
                }
                const unsigned mode = profile.phase == 0 ? (value == 0x100 ? 1 : 0) : profile.mode;
                const std::array<uint32_t, 6> addresses{0xcd800180, 0xcd8001d0, 0xcd8001cc, 0xcd8001d0, 0xcd8001d0, 0xcd8001d0};
                const std::array<uint32_t, 6> values{mode << 8, 0, mode == 0 ? 0x04640fc0u : 0x04b0ffceu, 0, 0x40000000, 0x80000000};
                if (address != addresses[profile.phase] || value != values[profile.phase]) {
                    throw std::runtime_error("PC clock profile command differs from measured modes");
                }
                profile.mode = mode;
                profile.writes.push_back({address, value, 0});
                ++profile.phase;
            },
            [](uint32_t) -> uint16_t { throw std::runtime_error("PC clock halfword read unverified"); },
            [](uint32_t, uint16_t) { throw std::runtime_error("PC clock halfword write unverified"); });
    }
}
}

namespace nwii::runtime {
inline bool experiment_ai_clock_mapping(CPUContext& context, uint32_t address, uint32_t instruction, bool write) {
    if (address != 0xcd800180 && address != 0xcd8001cc && address != 0xcd8001d0) {
        return false;
    }
    const bool caller = write ?
        ((address == 0xcd800180 && instruction == 0x80212af8) ||
        (address == 0xcd8001cc && (instruction == 0x80212b6c || instruction == 0x80212b94)) ||
        (address == 0xcd8001d0 && (instruction == 0x80212b04 || instruction == 0x80212be0 || instruction == 0x80212c30 || instruction == 0x80212c80))) :
        ((address == 0xcd800180 && instruction == 0x80212ae8) ||
        (address == 0xcd8001cc && (instruction == 0x80212b54 || instruction == 0x80212b78)) ||
        (address == 0xcd8001d0 && (instruction == 0x80212afc || instruction == 0x80212bd8 || instruction == 0x80212c24 || instruction == 0x80212c74)));
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    const bool verifiedMsr = context.msr == 0x32 || (hw::experimentPcClock.audioStartupFp && context.msr == 0x2032);
    if (!hw::experimentPcClock.enabled || !caller || !verifiedMsr || mapping.physical != (address & 0x1fffffffu)
        || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("PC clock profile caller/mapping unverified");
    }
    return true;
}
inline uint32_t experiment_ai_clock_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (experiment_ai_clock_mapping(context, address, instruction, false)) {
        return MMIODispatcher::get().read32(address);
    }
    return experiment_si_query_read32(context, address, instruction);
}
inline void experiment_ai_clock_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (experiment_ai_clock_mapping(context, address, instruction, true)) {
        MMIODispatcher::get().write32(address, value);
        hw::experimentPcClock.timestamps.push_back(experiment_read_timebase(context));
        return;
    }
    experiment_si_query_write32(context, address, value, instruction);
}
}
