#pragma once
#include "icache_adapter.h"

namespace nwii::runtime {
struct MemoryContext : ProcessorContext {
    struct Line {
        std::array<uint8_t, 32> bytes{};
        uint32_t address = 0;
        bool valid = false;
        bool dirty = false;
    };
    std::array<std::array<Line, 8>, 128> dataLines{};
    std::array<uint8_t, 128> replacement{};
};

inline MemoryContext& memory_context(CPUContext& context) {
    return static_cast<MemoryContext&>(context);
}

inline uint32_t memory_physical(CPUContext& context, uint32_t address, unsigned length) {
    if (!length || address > UINT32_MAX - (length - 1)) {
        throw std::runtime_error("Memory range overflow");
    }
    if ((address >> 28 == 8 || address >> 28 == 9 || address >> 28 == 12 || address >> 28 == 13) && !(context.msr & 0x10)) {
        throw std::runtime_error("Cached/uncached virtual memory requires the verified DR fixture");
    }
    const uint32_t physical = address & 0x3fffffffu;
    if (context.mmu.is_hw_reg(physical) || !context.mmu.get_ptr(address) || !context.mmu.get_ptr(address + length - 1)) {
        throw std::runtime_error("Unverified MMIO/locked-cache/unmapped memory access");
    }
    return physical;
}

inline void memory_recent(MemoryContext& context, unsigned set, unsigned way) {
    unsigned node = 0;
    for (int shift = 2; shift >= 0; --shift) {
        const bool right = (way >> shift) & 1;
        const uint8_t bit = 1u << node;
        context.replacement[set] = (context.replacement[set] & ~bit) | (right ? 0 : bit);
        node = node * 2 + (right ? 2 : 1);
    }
}

inline MemoryContext::Line* memory_line(CPUContext& base, uint32_t physical, bool allocate) {
    auto& context = memory_context(base);
    const uint32_t aligned = physical & ~31u;
    const unsigned set = (physical >> 5) & 127;
    unsigned way = 0;
    for (; way < 8; ++way) {
        if (context.dataLines[set][way].valid && context.dataLines[set][way].address == aligned) {
            memory_recent(context, set, way);
            return &context.dataLines[set][way];
        }
    }
    if (!allocate) {
        return nullptr;
    }
    for (way = 0; way < 8 && context.dataLines[set][way].valid; ++way) { }
    if (way == 8) {
        unsigned node = 0;
        way = 0;
        for (unsigned level = 0; level < 3; ++level) {
            const unsigned direction = (context.replacement[set] >> node) & 1;
            way = (way << 1) | direction;
            node = node * 2 + direction + 1;
        }
    }
    auto& line = context.dataLines[set][way];
    if (line.valid && line.dirty) {
        std::copy(line.bytes.begin(), line.bytes.end(), base.mmu.get_ptr(line.address));
    }
    memory_physical(base, aligned, 32);
    std::copy_n(base.mmu.get_ptr(aligned), 32, line.bytes.begin());
    line.address = aligned;
    line.valid = true;
    line.dirty = false;
    memory_recent(context, set, way);
    return &line;
}

inline bool memory_cached(CPUContext& context, uint32_t address) {
    return (memory_context(context).hid0 & 0x4000) && ((address >> 28) == 8 || (address >> 28) == 9);
}

inline uint64_t memory_read(CPUContext& context, uint32_t address, unsigned length) {
    memory_physical(context, address, length);
    uint64_t value = 0;
    for (unsigned index = 0; index < length; ++index) {
        const uint32_t physical = (address + index) & 0x3fffffffu;
        uint8_t byte;
        if (memory_cached(context, address)) {
            byte = memory_line(context, physical, true)->bytes[physical & 31];
        } else {
            byte = *context.mmu.get_ptr(physical);
        }
        value = (value << 8) | byte;
    }
    return value;
}

inline void memory_write(CPUContext& context, uint32_t address, uint64_t value, unsigned length) {
    const uint32_t physical = memory_physical(context, address, length);
    for (const auto& [start, image] : memory_context(context).instructionImages) {
        const uint32_t code = start & 0x3fffffffu;
        if (physical < code + image.size() && physical + length > code) {
            throw std::runtime_error("Writing compiled guest code requires a verified dynamic-code path");
        }
    }
    for (unsigned index = 0; index < length; ++index) {
        const uint32_t location = physical + index;
        const uint8_t byte = value >> ((length - 1 - index) * 8);
        if (memory_cached(context, address)) {
            auto line = memory_line(context, location, true);
            line->bytes[location & 31] = byte;
            line->dirty = true;
        } else {
            *context.mmu.get_ptr(location) = byte;
        }
    }
}

inline uint8_t memory_read8(CPUContext& c, uint32_t a) { return memory_read(c, a, 1); }
inline uint16_t memory_read16(CPUContext& c, uint32_t a) { return memory_read(c, a, 2); }
inline uint32_t memory_read32(CPUContext& c, uint32_t a) { return memory_read(c, a, 4); }
inline uint64_t memory_read64(CPUContext& c, uint32_t a) { return memory_read(c, a, 8); }
inline float memory_read_f32(CPUContext& c, uint32_t a) { return std::bit_cast<float>(memory_read32(c, a)); }
inline double memory_read_f64(CPUContext& c, uint32_t a) { return std::bit_cast<double>(memory_read64(c, a)); }
inline void memory_write8(CPUContext& c, uint32_t a, uint8_t v) { memory_write(c, a, v, 1); }
inline void memory_write16(CPUContext& c, uint32_t a, uint16_t v) { memory_write(c, a, v, 2); }
inline void memory_write32(CPUContext& c, uint32_t a, uint32_t v) { memory_write(c, a, v, 4); }
inline void memory_write64(CPUContext& c, uint32_t a, uint64_t v) { memory_write(c, a, v, 8); }
inline void memory_write_f32(CPUContext& c, uint32_t a, float v) { memory_write32(c, a, std::bit_cast<uint32_t>(v)); }
inline void memory_write_f64(CPUContext& c, uint32_t a, double v) { memory_write64(c, a, std::bit_cast<uint64_t>(v)); }

inline void memory_cache_operation(CPUContext& context, uint32_t address, unsigned operation) {
    if (operation == 470 && (context.msr & 0x4000)) {
        throw std::runtime_error("Privileged dcbi exception delivery unavailable");
    }
    const uint32_t physical = memory_physical(context, address, 1);
    if (operation == 278 || operation == 246) {
        memory_line(context, physical, true);
        return;
    }
    auto line = memory_line(context, physical, false);
    if (!line) {
        return;
    }
    if (operation != 470 && line->dirty) {
        std::copy(line->bytes.begin(), line->bytes.end(), context.mmu.get_ptr(line->address));
        line->dirty = false;
    }
    if (operation != 54) {
        line->valid = false;
        line->dirty = false;
    }
}

inline void memory_psq_load(CPUContext& context, uint32_t target, uint32_t address, uint32_t single, uint32_t quantizer) {
    if ((context.gqr[quantizer] >> 16) & 7) {
        throw std::runtime_error("Quantized paired memory conversion requires independent verification");
    }
    memory_physical(context, address, single ? 4 : 8);
    const double first = memory_read_f32(context, address);
    const double second = single ? 1.0 : memory_read_f32(context, address + 4);
    context.fpr[target] = first;
    context.ps1[target] = second;
}

inline void memory_psq_store(CPUContext& context, uint32_t source, uint32_t address, uint32_t single, uint32_t quantizer) {
    if (context.gqr[quantizer] & 7) {
        throw std::runtime_error("Quantized paired memory conversion requires independent verification");
    }
    memory_physical(context, address, single ? 4 : 8);
    memory_write_f32(context, address, static_cast<float>(context.fpr[source]));
    if (!single) {
        memory_write_f32(context, address + 4, static_cast<float>(context.ps1[source]));
    }
}
}
