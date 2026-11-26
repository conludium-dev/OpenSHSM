#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <iostream>
#include <stdexcept>

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
MMU* g_mmu = nullptr;
int g_ipc_interrupt_delay = 0;
}

namespace nwii::runtime::hw {
extern "C" int32_t handle_ios_ipc(CPUContext&, uint32_t) {
    throw std::runtime_error("IOS request outside isolated register measurement");
}
}

int main() {
    using namespace nwii::runtime;
    hw::register_pi(MMIODispatcher::get());
    hw::register_ipc(MMIODispatcher::get());
    const uint32_t values[] = {0, 0x40000000, 0x80000000, 0xffffffff};
    for (unsigned index = 0; index < 32; ++index) {
        auto& dispatcher = MMIODispatcher::get();
        dispatcher.write32(0xcd000034, 0);
        dispatcher.write32(0xcd000004, ((index & 3) << 4) | 6);
        dispatcher.write32(0xcd000030, 0x40000000);
        const auto controlBefore = dispatcher.read32(0xcd000004);
        const auto armBefore = dispatcher.read32(0xcd000008);
        dispatcher.write32(0xcd000034, values[(index & 15) / 4]);
        const auto controlAfter = dispatcher.read32(0xcd000004);
        const auto armAfter = dispatcher.read32(0xcd000008);
        std::cout << "IPC_VENDOR_CASE " << index << ' ' << controlBefore << ' ' << controlAfter
                  << ' ' << armBefore << ' ' << armAfter << '\n';
    }
    return 0;
}
