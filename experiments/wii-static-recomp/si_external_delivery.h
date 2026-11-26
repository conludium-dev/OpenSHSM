#pragma once
#include "bat_memory_frontend.h"
#include "si_idle_backend.h"

namespace nwii::runtime {
inline uint32_t bat_memory_read32(CPUContext& context, uint32_t address);
inline bool experiment_fpu_vector_active(CPUContext& context);
inline uint64_t siExternalEntries = 0;
inline void experiment_si_vector_execution_guard(CPUContext& context, uint32_t address) {
    const bool fpu = experiment_fpu_vector_active(context);
    if (address < 0x80211ba0 || address >= 0x80211c38 || context.pc != 0x80211ba0 ||
        (!fpu && (context.msr != 0x2000 || !siExternalEntries))) {
        throw std::runtime_error("SI relocated vector dispatch unverified");
    }
}

inline bool experiment_si_external_entry(CPUContext& context) {
    if (context.msr != 0xa032 || !hw::experimentSiQuery.interruptProfile) {
        throw std::runtime_error("SI external delivery CPU/profile unverified");
    }
    const auto pending = hw::pi_intsr.load() & hw::pi_intmr.load();
    if (pending == 0) {
        return false;
    }
    if (pending != 8 || hw::pi_intmr.load() != 8 || (hw::experimentSiControl & 0xc0000001u) != 0xc0000000u) {
        throw std::runtime_error("SI external delivery producer/mask unverified");
    }
    const auto found = std::find_if(memory_context(context).instructionImages.begin(), memory_context(context).instructionImages.end(),
        [](const auto& image) { return image.first <= 0x80211ba0 && uint64_t(image.first) + image.second.size() >= 0x80211c38; });
    if (found == memory_context(context).instructionImages.end()) {
        throw std::runtime_error("SI external vector original image missing");
    }
    for (unsigned index = 0; index < 38; ++index) {
        const auto offset = 0x80211ba0 - found->first + index * 4;
        uint32_t expected = 0;
        for (unsigned byte = 0; byte < 4; ++byte) {
            expected = (expected << 8) | found->second[offset + byte];
        }
        if (index == 26) {
            if (expected != 0x38600000) {
                throw std::runtime_error("SI original vector ID unverified");
            }
            expected = 0x38600004;
        }
        if (bat_memory_read32(context, 0x80000500 + index * 4) != expected) {
            throw std::runtime_error("SI relocated vector mismatch");
        }
    }
    if (bat_memory_read32(context, 0x800000c0) != 0x00501000 || bat_memory_read32(context, 0x800000d4) != 0x80501000
        || bat_memory_read32(context, 0x80003010) != 0x80217c60 || bat_memory_read32(context, 0x8052aad8) != 0x80003040
        || bat_memory_read32(context, 0x80003090) != 0x8020f850 || bat_memory_read32(context, 0x800000c4) != 0xfffff7ff
        || bat_memory_read32(context, 0x800000c8) || bat_memory_read32(context, 0x8052ab00) || bat_memory_read32(context, 0x8052ab04)) {
        throw std::runtime_error("SI external delivery OS state unverified");
    }
    context.srr0 = context.pc;
    context.srr1 = context.msr;
    context.msr &= ~0x8032u;
    context.pc = 0x80211ba0;
    ++siExternalEntries;
    return true;
}
}
