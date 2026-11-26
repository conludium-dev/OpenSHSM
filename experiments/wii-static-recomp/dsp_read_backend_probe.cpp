#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <iostream>

namespace nwii::runtime {
MMU* g_mmu = nullptr;
CPUContext* g_ctx_ptr = nullptr;
uint16_t HW_Reg_Read16(uint32_t address) {
    return MMIODispatcher::get().read16(address);
}
}

int main() {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::register_dsp(dispatcher);
    hw::pi_intsr = 0x10000;
    const auto initial = dispatcher.read16(0xcc00500a);
    std::cout << "DSP_DEFAULT " << initial << ' ' << hw::pi_intsr.load() << '\n';
    dispatcher.write16(0xcc00500a, 0x0804);
    const auto seeded = dispatcher.read16(0xcc00500a);
    std::cout << "DSP_LOADER_SEED " << seeded << ' ' << hw::pi_intsr.load() << '\n';
    return 0;
}
