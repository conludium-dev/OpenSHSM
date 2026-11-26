#pragma once
#include <cstdint>

namespace openshsm::experiment {

template<class Memory>
inline void read_adma_stereo(Memory& memory, uint32_t address, int16_t (&samples)[16]) {
    for (unsigned frame = 0; frame < 8; ++frame) {
        samples[frame * 2] = int16_t(memory.read16(address + frame * 4 + 2));
        samples[frame * 2 + 1] = int16_t(memory.read16(address + frame * 4));
    }
}

}
