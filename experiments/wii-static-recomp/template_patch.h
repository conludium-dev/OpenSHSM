#pragma once
#include "fp64_transfer.h"

namespace nwii::runtime {
inline uint8_t template_visible_byte(CPUContext& context, uint32_t physical) {
    const auto& state = memory_context(context);
    const unsigned set = (physical >> 5) & 127;
    for (const auto& line : state.dataLines[set]) {
        if (line.valid && line.address == (physical & ~31u)) {
            return line.bytes[physical & 31];
        }
    }
    return *context.mmu.get_ptr(physical);
}

inline void experiment_template_execution_guard(CPUContext&, uint32_t address) {
    if (address >= 0x80211ba0u && address < 0x80211c38u) {
        throw std::runtime_error("Mutable exception template execution requires verified relocated dispatch");
    }
}

inline void experiment_template_patch(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x802119a8u || address != 0x80211c08u || (value & 0xfffffff0u) != 0x38600000u ||
        context.msr != 0x2030 || memory_context(context).hid0 != 0xc200) {
        throw std::runtime_error("Template patch outside verified instruction/word/value/CPU profile");
    }
    const auto mapping = bat_memory_range(context, 0x80211ba0, 152);
    if (mapping.physical != 0x00211ba0 || !bat_memory_cached(context, mapping)) {
        throw std::runtime_error("Template patch BAT/cache mapping outside verified profile");
    }
    const std::vector<uint8_t>* image = nullptr;
    unsigned offset = 0;
    for (const auto& [start, bytes] : memory_context(context).instructionImages) {
        if (start <= 0x80211ba0u && uint64_t(start) + bytes.size() >= 0x80211c38u) {
            image = &bytes;
            offset = 0x80211ba0u - start;
            break;
        }
    }
    if (!image) {
        throw std::runtime_error("Original template image missing");
    }
    uint32_t original = 0;
    uint32_t current = 0;
    for (unsigned index = 0; index < 152; ++index) {
        const uint8_t expected = (*image)[offset + index];
        const uint8_t actual = template_visible_byte(context, mapping.physical + index);
        if (index >= 104 && index < 108) {
            original = (original << 8) | expected;
            current = (current << 8) | actual;
        } else if (actual != expected) {
            throw std::runtime_error("Template bytes outside verified patch word changed");
        }
    }
    if (original != 0x38600000u || (current & 0xfffffff0u) != 0x38600000u) {
        throw std::runtime_error("Original/current template patch word unavailable");
    }
    const uint32_t physical = 0x00211c08;
    auto line = memory_line(context, physical, true);
    for (unsigned index = 0; index < 4; ++index) {
        line->bytes[(physical & 31) + index] = value >> (24 - index * 8);
    }
    line->dirty = true;
}
}
