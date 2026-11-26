#include "runtime/hw/hw.h"
#include "runtime/cpu_context.h"
#include <cassert>
#include <iostream>

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
uint32_t HW_Reg_Read32(uint32_t address) {
    return MMIODispatcher::get().read32(address);
}
void GX_WGPIPE_Write8(uint8_t) {
    assert(false);
}
}
namespace nwii::runtime::hw {
std::atomic<uint32_t> pi_intsr = 0;
extern void register_cp(MMIODispatcher&);
}

int main() {
    using namespace nwii::runtime;
    auto& bus = MMIODispatcher::get();
    hw::register_cp(bus);
    bus.write32(0xCC000038, 0x1000);
    bus.write32(0xCC00003A, 0x006C);
    bus.write32(0xCC00003C, 0x1000);
    bus.write32(0xCC00003E, 0x006C);
    assert(bus.read32(0xCC00003C) == 0x1000);
    assert(bus.read32(0xCC00003E) == 0x006C);
    bus.write32(0xCC000002, 0x37);
    assert(bus.read32(0xCC000000) & 0x10);
    assert(hw::pi_intsr & 0x800);
    bus.write32(0xCC000002, 0x36);
    assert(bus.read32(0xCC000000) & 0x10);
    assert(!(hw::pi_intsr & 0x800));
    bus.write32(0xCC000002, 0x17);
    assert(!(hw::pi_intsr & 0x800));
    bus.write32(0xCC00003C, 0x2000);
    assert(!(bus.read32(0xCC000000) & 0x10));
    bus.write32(0xCC000002, 0x37);
    assert(!(hw::pi_intsr & 0x800));
    bus.write32(0xCC000038, 0x2000);
    assert(hw::pi_intsr & 0x800);
    bus.write32(0xCC000002, 0x35);
    assert(!(bus.read32(0xCC000000) & 0x10));
    assert(!(hw::pi_intsr & 0x800));
    assert(bus.read32(0xCC000038) == 0x2000);
    std::cout << "PASS breakpoint halves, pointer equality, enable/read/IRQ masks and clear on disable\n";
}
