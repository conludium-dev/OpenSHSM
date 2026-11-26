#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <bit>
#include <iostream>
#include <memory>
#include "dsp-mask-generated.h"

namespace nwii::runtime {
MMU* g_mmu = nullptr;
CPUContext* g_ctx_ptr = nullptr;
uint16_t HW_Reg_Read16(uint32_t address) {
    return MMIODispatcher::get().read16(address);
}
void HW_Reg_Write16(uint32_t address, uint16_t value) {
    MMIODispatcher::get().write16(address, value);
}
}

int main() {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::register_dsp(dispatcher);
    hw::pi_intsr = 0x10000;
    dispatcher.write16(0xcc00500a, 0x0804);
    auto context = std::make_unique<CPUContext>();
    uint32_t softwareMask, ni;
    while (std::cin >> softwareMask >> ni) {
        context->gpr[3] = 0x04000000;
        context->gpr[4] = softwareMask;
        context->fpscr = ni * 4;
        const auto before = dispatcher.read16(0xcc00500a);
        experiment_dsp_mask_block(*context);
        const auto after = dispatcher.read16(0xcc00500a);
        std::cout << "DSP_MASK_CASE " << before << ' ' << context->gpr[5] << ' ' << after << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
