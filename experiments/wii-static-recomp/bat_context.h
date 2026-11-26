#pragma once
#include "performance_adapter.h"
#include "bat_translation.h"

namespace nwii::runtime {
struct BatContext : PerformanceContext {
    std::array<BatPair, 8> ibat{};
    std::array<BatPair, 8> dbat{};
    uint32_t hid4 = 0;
    bool fpuFirstUse = false;
    uint32_t exceptionVector = 0;
    uint32_t fpuResume = 0;
    uint64_t fpuEntries = 0;
    bool flushSyscall = false;
    uint32_t flushPhase = 0;
    uint64_t flushEntries = 0;
    uint64_t flushBarriers = 0;
};

inline BatContext& bat_context(CPUContext& context) {
    return static_cast<BatContext&>(context);
}

inline bool experiment_fpu_vector_active(CPUContext& context) {
    const auto& state = bat_context(context);
    return state.fpuFirstUse && state.exceptionVector == 7 && context.msr == 0 && state.fpuResume == 0x800060f4;
}

inline void bat_validate_images(BatContext& context, const std::array<BatPair, 8>& bank, uint32_t hid4) {
    for (const auto& [address, image] : context.instructionImages) {
        if (image.empty()) {
            continue;
        }
        for (uint64_t offset = 0; offset < image.size();) {
            const uint32_t virtualAddress = address + offset;
            const uint64_t span = std::min<uint64_t>(image.size() - offset, 0x20000 - (virtualAddress & 0x1ffff));
            const auto first = resolve_reference_bat(bank, hid4, context.msr, virtualAddress, true);
            const auto last = resolve_reference_bat(bank, hid4, context.msr, virtualAddress + span - 1, true);
            if (first.physical != (virtualAddress & 0x3fffffffu) || last.physical != first.physical + span - 1) {
                throw std::runtime_error("Remapped compiled code requires a verified fetch/recompilation path");
            }
            offset += span;
        }
    }
}

inline uint32_t experiment_read_bat(CPUContext& context, bool instruction, unsigned index, bool lower) {
    if ((context.msr & 0x4000) || index >= 8) {
        throw std::runtime_error("BAT privileged access contract unavailable");
    }
    const auto& pair = (instruction ? bat_context(context).ibat : bat_context(context).dbat)[index];
    return lower ? pair.lower : pair.upper;
}

inline void experiment_write_bat(CPUContext& context, bool instruction, unsigned index, bool lower, uint32_t value) {
    if ((context.msr & 0x4000) || index >= 8) {
        throw std::runtime_error("BAT privileged access contract unavailable");
    }
    auto& state = bat_context(context);
    auto& bank = instruction ? state.ibat : state.dbat;
    auto candidate = bank;
    (lower ? candidate[index].lower : candidate[index].upper) = value;
    if (instruction) {
        bat_validate_images(state, candidate, state.hid4);
    }
    bank = candidate;
}

inline uint32_t experiment_read_hid4(CPUContext& context) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("HID4 privileged access contract unavailable");
    }
    return bat_context(context).hid4;
}

inline void experiment_write_hid4(CPUContext& context, uint32_t value) {
    if ((context.msr & 0xc000) || (value != 0x80000000 && value != 0x82000000 && value != 0x83900000 && value != 0x81900000)) {
        throw std::runtime_error("HID4 value/interrupt/privilege effects outside measured reference profile");
    }
    auto& state = bat_context(context);
    bat_validate_images(state, state.ibat, value);
    state.hid4 = value;
}
}
