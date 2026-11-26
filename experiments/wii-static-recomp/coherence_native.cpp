#include "runtime/cpu_context.h"
#include <stdexcept>

namespace nwii::runtime {
uint32_t g_watch_addr = 0;
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Watch access unavailable"); }
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Hardware read unavailable"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("Hardware read unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Hardware write unavailable"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("Hardware write unavailable"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("GX write unavailable"); }
}

int main() {
    nwii::runtime::MMU memory;
    memory.write32(0xc0618000, 0x11223344);
    memory.write32(0x80618000, 0x55667788);
    const uint32_t cached = memory.read32(0x80618000);
    const uint32_t uncached = memory.read32(0xc0618000);
    const uint32_t afterStore = memory.read32(0xc0618000);
    memory.write32(0xc0618000, 0x99aabbcc);
    const uint32_t beforeInvalidate = memory.read32(0x80618000);
    const uint32_t afterInvalidate = memory.read32(0x80618000);
    std::cout << cached << ' ' << uncached << ' ' << afterStore << ' ' << beforeInvalidate << ' ' << afterInvalidate << '\n';
}
