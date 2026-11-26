#include "runtime/hw/hw.h"
#include "runtime/cpu_context.h"
#include <cassert>
#include <iostream>

static uint64_t clock_us = 0;
namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
MMU* g_mmu = nullptr;
int g_ipc_interrupt_delay = 0;
uint64_t get_os_time() {
    return clock_us;
}
}
namespace nwii::runtime::hw {
std::atomic<uint32_t> pi_intsr = 0;
}
extern "C" int32_t handle_ios_ipc(nwii::runtime::CPUContext&, uint32_t) {
    assert(false);
    return 0;
}

int main() {
    using namespace nwii::runtime;
    auto& bus = MMIODispatcher::get();
    hw::register_ai(bus);
    hw::register_ipc(bus);
    bus.write32(0xCD006C00, 0x20);
    assert(bus.read32(0xCD006C00) == 0);
    bus.write32(0xCD006C00, 0x01);
    clock_us += 10000;
    assert(bus.read32(0xCD006C08) == 320);
    assert(bus.read32(0xCC006C08) == 320);
    assert(bus.read32(0x0D006C08) == 320);
    bus.write32(0xCD006C00, 0x03);
    for (int i = 0; i < 1000; ++i) {
        ++clock_us;
        bus.read32(0xCD006C08);
    }
    assert(bus.read32(0xCD006C08) == 368);
    bus.write32(0xCD006C00, 0);
    clock_us += 100000;
    assert(bus.read32(0xCD006C08) == 368);
    bus.write32(0xCD006C00, 0x20);
    assert(bus.read32(0xCD006C08) == 0);
    bus.write32(0xCD006C0C, 10);
    bus.write32(0xCD006C00, 3);
    clock_us += 1000;
    assert(bus.read32(0xCD006C08) == 48);
    assert(bus.read32(0xCD006C00) == 0x0B);
    assert(!(hw::pi_intsr & 0x20));
    bus.write32(0xCD006C00, 7);
    assert(hw::pi_intsr & 0x20);
    bus.write32(0xCD006C00, 0x0F);
    assert(bus.read32(0xCD006C00) == 7);
    assert(!(hw::pi_intsr & 0x20));
    bus.write32(0xCD006C04, 0x1234);
    assert(bus.read32(0xCC006C04) == 0x1234);
    assert(bus.read32(0xCD000004) == 0);
    std::cout << "PASS Wii AI routing, rates, sub-sample accumulation, stop/reset, IRQ mask/W1C and IPC separation\n";
}
