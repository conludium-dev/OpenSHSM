#include "runtime/cpu_context.h"
#include "exi_init_backend.h"
#include <bit>
#include <iostream>
#include <memory>
#include <string>

static bool experimentDropInit = false;
static void experiment_init_probe_write(uint32_t address, uint32_t value) {
    if (!experimentDropInit) {
        nwii::runtime::hw::experiment_exi_init_csr_write(address, value);
    }
}
#include "exi-init-generated.h"

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::experiment_register_exi_masks(dispatcher);
    hw::experiment_register_exi_idle_controls(dispatcher);
    hw::pi_intsr = 0x10000;
    unsigned refused = 0;
    for (unsigned mode = 0; mode < 16; ++mode) {
        const auto state = hw::experimentExiMaskState;
        try {
            if (mode < 12) {
                const auto address = 0xcd00680c + (mode / 4) * 20;
                if (mode % 4 == 0) {
                    dispatcher.write32(address, 1);
                } else if (mode % 4 == 1) {
                    dispatcher.read32(address + 1);
                } else if (mode % 4 == 2) {
                    dispatcher.read16(address);
                } else {
                    dispatcher.write16(address, 0);
                }
            } else {
                hw::experiment_exi_init_csr_write(mode == 15 ? 0xcd006801 : 0xcd006800, mode == 15 ? 0 : 1u << (mode - 12));
            }
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (hw::experimentExiMaskState != state || hw::pi_intsr.load() != 0x10000) {
            return 3;
        }
    }
    if (refused != 16) {
        return 4;
    }
    std::cout << "EXI_INIT_GUARDS 16\n";
    experimentDropInit = argc == 2 && std::string(argv[1]) == "--drop-init";
    auto context = std::make_unique<CPUContext>();
    unsigned mode, ni;
    while (std::cin >> mode >> ni) {
        if (mode > 1 || ni > 1) {
            return 2;
        }
        context->gpr[3] = 0xcd000000;
        context->fpscr = ni * 4;
        std::array<uint32_t, 3> before, controls;
        for (unsigned channel = 0; channel < 3; ++channel) {
            before[channel] = dispatcher.read32(0xcd006800 + channel * 20);
            controls[channel] = dispatcher.read32(0xcd00680c + channel * 20);
        }
        const auto cause = hw::pi_intsr.load();
        if (mode) {
            experiment_exi_init_block(*context);
        } else {
            experiment_exi_poll_block(*context);
        }
        std::cout << "EXI_INIT_CASE " << context->gpr[0];
        for (auto value : before) { std::cout << ' ' << value; }
        for (auto value : controls) { std::cout << ' ' << value; }
        for (unsigned channel = 0; channel < 3; ++channel) { std::cout << ' ' << dispatcher.read32(0xcd006800 + channel * 20); }
        for (unsigned channel = 0; channel < 3; ++channel) { std::cout << ' ' << dispatcher.read32(0xcd00680c + channel * 20); }
        std::cout << ' ' << cause << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
