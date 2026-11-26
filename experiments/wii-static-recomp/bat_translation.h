#pragma once
#include <array>
#include <cstdint>
#include <stdexcept>

namespace nwii::runtime {
struct BatPair {
    uint32_t upper = 0;
    uint32_t lower = 0;
};

struct BatTranslation {
    uint32_t physical;
    uint32_t wimg;
    int slot;
};

inline BatTranslation resolve_reference_bat(const std::array<BatPair, 8>& bank, uint32_t hid4,
                                           uint32_t msr, uint32_t address, bool instruction) {
    if (msr & 0x4000) {
        throw std::runtime_error("User-mode BAT protection requires independent verification");
    }
    if (!(msr & (instruction ? 0x20 : 0x10))) {
        return {address, 4, -1};
    }
    BatTranslation result{0, 0, -1};
    const unsigned count = (hid4 & 0x02000000) ? 8 : 4;
    for (unsigned index = 0; index < count; ++index) {
        const auto& pair = bank[index];
        if (!(pair.upper & 2)) {
            continue;
        }
        const uint32_t blocks = (pair.upper >> 2) & 0x7ff;
        const uint32_t mask = (blocks << 17) | 0x1ffff;
        if ((blocks & (blocks + 1)) || (pair.upper & 0xfffe0000 & mask) || (pair.lower & 0xfffe0000 & mask)) {
            throw std::runtime_error("Invalid BAT mask/alignment requires hardware evidence");
        }
        if ((pair.lower & 3) != 2) {
            throw std::runtime_error("BAT PP protection outside verified supervisor RW profile");
        }
        if ((address & ~mask) == (pair.upper & 0xfffe0000)) {
            result = {(pair.lower & 0xfffe0000) | (address & mask), (pair.lower >> 3) & 15, int(index)};
        }
    }
    if (result.slot < 0) {
        throw std::runtime_error("No verified BAT mapping; page-table/exception path unavailable");
    }
    return result;
}
}
