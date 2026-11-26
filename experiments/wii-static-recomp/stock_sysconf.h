#pragma once
#include <cstdint>
#include <vector>

namespace openshsm::experiment {

inline std::vector<uint8_t> wii_sysconf_aspect(bool widescreen) {
    std::vector<uint8_t> bytes(0x4000, 0);
    bytes[0] = 'S';
    bytes[1] = 'C';
    bytes[2] = 'v';
    bytes[3] = '0';
    bytes[5] = 1;
    bytes[7] = 10;
    bytes[9] = 18;
    bytes[10] = 0x65;
    const uint8_t name[] = {'I', 'P', 'L', '.', 'A', 'R'};
    for (unsigned i = 0; i < 6; ++i) {
        bytes[11 + i] = name[i];
    }
    bytes[17] = widescreen ? 1 : 0;
    bytes[0x3ffc] = 'S';
    bytes[0x3ffd] = 'C';
    bytes[0x3ffe] = 'e';
    bytes[0x3fff] = 'd';
    return bytes;
}

}
