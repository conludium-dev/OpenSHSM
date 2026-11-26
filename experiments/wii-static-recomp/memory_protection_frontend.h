#pragma once
#include "dsp_startup_frontend.h"
#include "mi_mask_boot.h"

namespace nwii::runtime {
struct ExperimentMemoryProtection {
    bool enabled = false;
    unsigned phase = 0;
    std::vector<std::array<uint32_t, 3>> writes;
    CPUContext* realOwner = nullptr;
    uint32_t realTarget = 0;
    unsigned realStep = 0;
    unsigned realEntries = 0;
};
inline ExperimentMemoryProtection experimentMemoryProtection;

inline void experiment_memory_protection_write16(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    static constexpr std::array<std::array<uint32_t, 3>, 3> commands{{
        {0x802186ac, 0xcc004020, 0}, {0x802186bc, 0xcc004010, 0xff}, {0x802176e4, 0xcc00401c, 0x10}
    }};
    auto& profile = experimentMemoryProtection;
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
    if (!profile.enabled || profile.phase >= commands.size() || context.msr != 0x2032 || bat_context(context).hid0 != 0xc200 ||
        mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5 ||
        commands[profile.phase] != std::array<uint32_t, 3>{instruction, address, value}) {
        throw std::runtime_error("MI memory-protection command/profile unverified");
    }
    MMIODispatcher::get().write16(address, value);
    profile.writes.push_back({instruction, address, value});
    ++profile.phase;
}
inline void experiment_memory_protection_mask_write(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    if (context.msr == 0x2030) {
        experiment_mi_mask_boot_write16(context, address, value, instruction);
        return;
    }
    experiment_memory_protection_write16(context, address, value, instruction);
}

struct MemoryProtectionBatStep {
    uint32_t instruction;
    bool instructionBank;
    unsigned index;
    bool lower;
    uint32_t value;
};
#include "memory-protection-bat-plan.h"

inline void experiment_memory_protection_real_enter(CPUContext& context) {
    auto& profile = experimentMemoryProtection;
    const uint32_t target = context.srr0 | 0x80000000u;
    if (!profile.enabled || profile.phase != 2 || profile.realOwner || context.msr != 0x2032 || context.srr1 != 0x2002 ||
        ((target != 0x80218070 || context.lr != 0x80218578) && (target != 0x802180f0 || context.lr != 0x802185a8)) ||
        context.srr0 != (target & 0x3fffffffu) || context.gpr[30] != 0x000ba2cf ||
        profile.realEntries != (target == 0x80218070 ? 0u : 1u)) {
        throw std::runtime_error("Memory-protection real-mode entry unverified");
    }
    for (const auto& expected : std::array<std::array<uint32_t, 2>, 4>{{
        {0x80003100, 0x01800000}, {0x80003104, 0x01800000}, {0x8000311c, 0x04000000}, {0x80003120, 0x93400000}}}) {
        if (bat_memory_read32(context, expected[0]) != expected[1]) {
            throw std::runtime_error("Memory-protection size profile unverified");
        }
    }
    const uint32_t size = target == 0x80218070 ? 128 : 212;
    const auto& images = bat_context(context).instructionImages;
    const auto found = std::find_if(images.begin(), images.end(),
        [target, size](const auto& image) { return image.first <= target && uint64_t(image.first) + image.second.size() >= uint64_t(target) + size; });
    if (found == images.end() || !context.mmu.get_ptr((target & 0x3fffffffu) + size - 1) ||
        !std::equal(found->second.begin() + target - found->first, found->second.begin() + target - found->first + size,
            context.mmu.get_ptr(target & 0x3fffffffu))) {
        throw std::runtime_error("Memory-protection real-mode code image unverified");
    }
    profile.realOwner = &context;
    profile.realTarget = target;
    profile.realStep = 0;
    ++profile.realEntries;
}
inline void experiment_memory_protection_bat_write(CPUContext& context, bool instructionBank, unsigned index, bool lower,
                                                  uint32_t value, uint32_t instruction) {
    auto& profile = experimentMemoryProtection;
    const bool mem1 = profile.realTarget == 0x80218070;
    const auto* plan = mem1 ? memoryProtectionMem1Plan.data() : memoryProtectionMem2Plan.data();
    const auto count = mem1 ? memoryProtectionMem1Plan.size() : memoryProtectionMem2Plan.size();
    if (!profile.enabled || profile.realOwner != &context || context.msr != 0x2002 || profile.realStep >= count ||
        (profile.realTarget != 0x80218070 && profile.realTarget != 0x802180f0) || context.pc != profile.realTarget) {
        throw std::runtime_error("Memory-protection real-mode BAT owner/phase unverified");
    }
    const auto& expected = plan[profile.realStep];
    if (expected.instruction != instruction || expected.instructionBank != instructionBank || expected.index != index ||
        expected.lower != lower || expected.value != value) {
        throw std::runtime_error("Memory-protection BAT instruction/value/order unverified");
    }
    auto& pair = (instructionBank ? bat_context(context).ibat : bat_context(context).dbat)[index];
    (lower ? pair.lower : pair.upper) = value;
    ++profile.realStep;
}
inline void experiment_memory_protection_real_return(CPUContext& context, uint32_t instruction) {
    auto& profile = experimentMemoryProtection;
    const bool mem1 = profile.realTarget == 0x80218070;
    if (!profile.enabled || profile.realOwner != &context || context.msr != 0x2002 || context.srr1 != 0x2032 ||
        (profile.realTarget != 0x80218070 && profile.realTarget != 0x802180f0) || context.pc != profile.realTarget ||
        profile.realStep != (mem1 ? memoryProtectionMem1Plan.size() : memoryProtectionMem2Plan.size()) ||
        instruction != (mem1 ? 0x802180ec : 0x802181c0) || context.srr0 != (mem1 ? 0x80218578 : 0x802185a8) || context.lr != context.srr0) {
        throw std::runtime_error("Memory-protection real-mode return unverified");
    }
    for (const auto& [address, image] : bat_context(context).instructionImages) {
        for (uint64_t offset = 0; offset < image.size();) {
            const auto span = std::min<uint64_t>(image.size() - offset, 0x20000 - ((address + offset) & 0x1ffff));
            const auto first = resolve_reference_bat(bat_context(context).ibat, bat_context(context).hid4, context.srr1, address + offset, true);
            const auto last = resolve_reference_bat(bat_context(context).ibat, bat_context(context).hid4, context.srr1, address + offset + span - 1, true);
            if (first.physical != ((address + offset) & 0x3fffffffu) || last.physical != first.physical + span - 1) {
                throw std::runtime_error("Memory-protection restored instruction mapping unverified");
            }
            offset += span;
        }
    }
    profile.realOwner = nullptr;
    profile.realTarget = 0;
    profile.realStep = 0;
}
}
