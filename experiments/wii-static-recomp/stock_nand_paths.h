#pragma once
#include <cstdio>
#include <cstdint>
#include <string>

namespace openshsm::experiment {

inline std::string title_data_path(uint32_t high, uint32_t low) {
    char path[64];
    std::snprintf(path, sizeof(path), "/title/%08x/%08x/data", high, low);
    return path;
}

inline uint32_t nand_virtual(uint32_t address) {
    return address < 0x01800000 || (address >= 0x10000000 && address < 0x14000000)
        ? address | 0x80000000 : address;
}

inline bool nand_span(uint32_t address, uint32_t length) {
    const uint64_t start = nand_virtual(address), end = start + length;
    return (start >= 0x80004000 && end <= 0x81800000)
        || (start >= 0x90000000 && end <= 0x94000000);
}

}
