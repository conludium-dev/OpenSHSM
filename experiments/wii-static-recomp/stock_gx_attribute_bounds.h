#pragma once
#include "runtime/cpu_context.h"

namespace openshsm::experiment {

inline const uint8_t* gx_attribute_pointer(const nwii::runtime::MMU& mmu, uint32_t address, size_t bytes) {
    if (address >= 0xe0000000u && address < 0xe0040000u) {
        const size_t offset = address - 0xe0000000u;
        if (mmu.locked_cache.size() >= 8 && uint64_t(offset) + bytes <= mmu.locked_cache.size() - 8) {
            return mmu.locked_cache.data() + offset;
        }
        return nullptr;
    }
    const uint32_t physical = address & 0x3fffffffu;
    if (mmu.mem1.size() >= 8 && uint64_t(physical) + bytes <= mmu.mem1.size() - 8) {
        return mmu.mem1.data() + physical;
    }
    if (physical >= 0x10000000u && mmu.mem2.size() >= 8 &&
            uint64_t(physical - 0x10000000u) + bytes <= mmu.mem2.size() - 8) {
        return mmu.mem2.data() + physical - 0x10000000u;
    }
    return nullptr;
}

}
