#pragma once
#include "template_patch.h"

namespace nwii::runtime {
inline void experiment_template_nop(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x80211a30u || address != 0x80211bf8u || value != 0x60000000u ||
        context.msr != 0x2030 || memory_context(context).hid0 != 0xc200) {
        throw std::runtime_error("NOP template store outside verified instruction/word/value/CPU profile");
    }
    const auto mapping = bat_memory_range(context, 0x80211ba0, 152);
    if (mapping.physical != 0x00211ba0 || !bat_memory_cached(context, mapping)) {
        throw std::runtime_error("NOP template BAT/cache profile unavailable");
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
        throw std::runtime_error("Original NOP template image missing");
    }
    uint32_t originalId = 0;
    uint32_t currentId = 0;
    uint32_t originalNop = 0;
    for (unsigned index = 0; index < 152; ++index) {
        const uint8_t expected = (*image)[offset + index];
        const uint8_t actual = template_visible_byte(context, mapping.physical + index);
        if (index >= 104 && index < 108) {
            originalId = (originalId << 8) | expected;
            currentId = (currentId << 8) | actual;
        } else if (actual != expected) {
            throw std::runtime_error("NOP template bytes outside verified ID word changed");
        }
        if (index >= 88 && index < 92) {
            originalNop = (originalNop << 8) | expected;
        }
    }
    if (originalId != 0x38600000u || (currentId & 0xfffffff0u) != 0x38600000u || originalNop != value) {
        throw std::runtime_error("Original/current NOP template words unavailable");
    }
    const uint32_t physical = 0x00211bf8;
    auto line = memory_line(context, physical, true);
    for (unsigned index = 0; index < 4; ++index) {
        line->bytes[(physical & 31) + index] = value >> (24 - index * 8);
    }
    line->dirty = true;
}
}
