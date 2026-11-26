#pragma once
#include "bat_context.h"

namespace nwii::runtime {
inline BatTranslation bat_memory_range(CPUContext& context, uint32_t address, unsigned length) {
    if (!length || address > UINT32_MAX - (length - 1)) {
        throw std::runtime_error("BAT memory range overflow");
    }
    auto& state = bat_context(context);
    const auto first = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    const auto last = resolve_reference_bat(state.dbat, state.hid4, context.msr, address + length - 1, false);
    if (uint64_t(first.physical) + length - 1 != last.physical || first.wimg != last.wimg) {
        throw std::runtime_error("Non-contiguous or mixed-policy BAT access requires verification");
    }
    if (first.physical >= 0x40000000 || context.mmu.is_hw_reg(first.physical) ||
        context.mmu.is_hw_reg(last.physical) || !context.mmu.get_ptr(first.physical) || !context.mmu.get_ptr(last.physical)) {
        throw std::runtime_error("BAT MMIO/locked-cache/unmapped backing access unavailable");
    }
    return first;
}

inline bool bat_memory_cached(CPUContext& context, const BatTranslation& translation) {
#ifdef SHSM_SI_EXTERNAL_DELIVERY
    if (context.pc == 0x80211ba0 && (context.msr == 0x2000 ||
        (context.msr == 0 && bat_context(context).exceptionVector == 7)) &&
        translation.slot == -1 && translation.physical < 0x01800000) {
        return (memory_context(context).hid0 & 0x4000) != 0;
    }
#endif
    return (memory_context(context).hid0 & 0x4000) && !(translation.wimg & 12);
}

inline uint64_t bat_memory_read(CPUContext& context, uint32_t address, unsigned length) {
    const auto mapping = bat_memory_range(context, address, length);
    uint64_t value = 0;
    for (unsigned index = 0; index < length; ++index) {
        const uint32_t physical = mapping.physical + index;
        const uint8_t byte = bat_memory_cached(context, mapping) ?
            memory_line(context, physical, true)->bytes[physical & 31] : *context.mmu.get_ptr(physical);
        value = (value << 8) | byte;
    }
    return value;
}

inline void bat_memory_write(CPUContext& context, uint32_t address, uint64_t value, unsigned length) {
    const auto mapping = bat_memory_range(context, address, length);
    for (const auto& [start, image] : memory_context(context).instructionImages) {
        const uint32_t code = start & 0x3fffffffu;
        if (uint64_t(mapping.physical) < uint64_t(code) + image.size() && uint64_t(mapping.physical) + length > code) {
            throw std::runtime_error("Writing translated compiled guest code requires recompilation");
        }
    }
    for (unsigned index = 0; index < length; ++index) {
        const uint32_t physical = mapping.physical + index;
        const uint8_t byte = value >> ((length - 1 - index) * 8);
        if (bat_memory_cached(context, mapping)) {
            auto line = memory_line(context, physical, true);
            line->bytes[physical & 31] = byte;
            line->dirty = true;
        } else {
            *context.mmu.get_ptr(physical) = byte;
        }
    }
}

inline uint8_t bat_memory_read8(CPUContext& c, uint32_t a) { return bat_memory_read(c, a, 1); }
inline uint16_t bat_memory_read16(CPUContext& c, uint32_t a) { return bat_memory_read(c, a, 2); }
inline uint32_t bat_memory_read32(CPUContext& c, uint32_t a) { return bat_memory_read(c, a, 4); }
inline uint64_t bat_memory_read64(CPUContext& c, uint32_t a) { return bat_memory_read(c, a, 8); }
inline float bat_memory_read_f32(CPUContext& c, uint32_t a) { return std::bit_cast<float>(bat_memory_read32(c, a)); }
inline double bat_memory_read_f64(CPUContext& c, uint32_t a) { return std::bit_cast<double>(bat_memory_read64(c, a)); }
inline void bat_memory_write8(CPUContext& c, uint32_t a, uint8_t v) { bat_memory_write(c, a, v, 1); }
inline void bat_memory_write16(CPUContext& c, uint32_t a, uint16_t v) { bat_memory_write(c, a, v, 2); }
inline void bat_memory_write32(CPUContext& c, uint32_t a, uint32_t v) { bat_memory_write(c, a, v, 4); }
inline void bat_memory_write64(CPUContext& c, uint32_t a, uint64_t v) { bat_memory_write(c, a, v, 8); }
inline void bat_memory_write_f32(CPUContext& c, uint32_t a, float v) { bat_memory_write32(c, a, std::bit_cast<uint32_t>(v)); }
inline void bat_memory_write_f64(CPUContext& c, uint32_t a, double v) { bat_memory_write64(c, a, std::bit_cast<uint64_t>(v)); }

inline void bat_memory_cache_operation(CPUContext& context, uint32_t address, unsigned operation) {
    const auto mapping = bat_memory_range(context, address, 1);
    memory_cache_operation(context, mapping.physical, operation);
}

inline void bat_memory_psq_load(CPUContext& context, uint32_t target, uint32_t address, uint32_t single, uint32_t quantizer) {
    if ((context.gqr[quantizer] >> 16) & 7) {
        throw std::runtime_error("Quantized BAT paired conversion requires verification");
    }
    bat_memory_range(context, address, single ? 4 : 8);
    context.fpr[target] = bat_memory_read_f32(context, address);
    context.ps1[target] = single ? 1.0 : bat_memory_read_f32(context, address + 4);
}

inline void bat_memory_psq_store(CPUContext& context, uint32_t source, uint32_t address, uint32_t single, uint32_t quantizer) {
    if (context.gqr[quantizer] & 7) {
        throw std::runtime_error("Quantized BAT paired conversion requires verification");
    }
    bat_memory_range(context, address, single ? 4 : 8);
    bat_memory_write_f32(context, address, static_cast<float>(context.fpr[source]));
    if (!single) {
        bat_memory_write_f32(context, address + 4, static_cast<float>(context.ps1[source]));
    }
}
}
