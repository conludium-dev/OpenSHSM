#pragma once
#include <cstdint>

namespace openshsm::experiment {
inline uint32_t gx_display_list_physical(uint32_t address) {
    return address & 0x3fffffff;
}

inline bool gx_display_list_range(uint32_t address, uint32_t size) {
    const uint32_t physical = gx_display_list_physical(address);
    if (!size) {
        return false;
    }
    if (physical < 0x01800000) {
        return size <= 0x01800000 - physical;
    }
    if (physical >= 0x10000000 && physical < 0x14000000) {
        return size <= 0x14000000 - physical;
    }
    return false;
}
}
