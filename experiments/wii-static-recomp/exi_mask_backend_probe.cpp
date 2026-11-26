#include "runtime/cpu_context.h"
#include "exi_mask_backend.h"
#include <bit>
#include <iostream>
#include <memory>
#include <string>
#include "exi-mask-generated.h"

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::experiment_register_exi_masks(dispatcher);
    hw::pi_intsr = 0x10000;
    unsigned refused = 0;
    for (unsigned channel = 0; channel < 3; ++channel) {
        const uint32_t address = 0xcd006800 + channel * 20;
        const auto before = dispatcher.read32(address);
        for (unsigned mode = 0; mode < 4; ++mode) {
            try {
                if (mode == 0) {
                    dispatcher.write32(address, 0xffffffff);
                } else if (mode == 1) {
                    dispatcher.read32(address + 1);
                } else if (mode == 2) {
                    dispatcher.write16(address, 0);
                } else {
                    dispatcher.read16(address);
                }
            } catch (const std::runtime_error&) {
                ++refused;
            }
            if (dispatcher.read32(address) != before || hw::pi_intsr.load() != 0x10000) {
                return 3;
            }
        }
    }
    if (refused != 12) {
        return 4;
    }
    std::cout << "EXI_GUARDS 12\n";
    if (argc == 2 && std::string(argv[1]) == "--unregistered") {
        dispatcher.clear();
    }
    auto context = std::make_unique<CPUContext>();
    uint32_t channel, softwareMask, ni;
    while (std::cin >> channel >> softwareMask >> ni) {
        if (channel >= 3 || ni > 1) {
            return 2;
        }
        context->gpr[3] = 1u << (channel == 0 ? 22 : channel == 1 ? 19 : 16);
        context->gpr[4] = softwareMask;
        context->fpscr = ni * 4;
        const auto address = 0xcd006800 + channel * 20;
        const auto before = dispatcher.read32(address);
        const auto causeBefore = hw::pi_intsr.load();
        if (channel == 0) {
            experiment_exi_mask_block0(*context);
        } else if (channel == 1) {
            experiment_exi_mask_block1(*context);
        } else {
            experiment_exi_mask_block2(*context);
        }
        const auto after = dispatcher.read32(address);
        std::cout << "EXI_MASK_CASE " << before << ' ' << context->gpr[5] << ' ' << after << ' '
                  << causeBefore << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
