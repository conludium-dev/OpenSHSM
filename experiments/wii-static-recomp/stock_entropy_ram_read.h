#pragma once
#include <cstdint>

template<class Memory>
inline uint32_t stock_entropy_read32(Memory& memory, uint32_t address) {
    const uint32_t physical = address & 0x3FFFFFFF;
    if (physical == 0xC) {
        return 0;
    }
    const uint8_t* bytes = nullptr;
    if (memory.mem1.size() >= 8 && physical < memory.mem1.size() - 8) {
        bytes = memory.mem1.data() + physical;
    } else if (physical >= 0x10000000 && memory.mem2.size() >= 8
        && physical - 0x10000000 < memory.mem2.size() - 8) {
        bytes = memory.mem2.data() + (physical - 0x10000000);
    } else {
        return memory.read32(address);
    }
    return (uint32_t(bytes[0]) << 24) | (uint32_t(bytes[1]) << 16)
        | (uint32_t(bytes[2]) << 8) | bytes[3];
}
