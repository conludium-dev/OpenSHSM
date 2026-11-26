#include "runtime/cpu_context.h"
#include "exi_select_backend.h"
#include <bit>
#include <iostream>
#include <memory>
#include <string>

static bool experimentPreserveRomdis = false;
static void experiment_select_probe_write(uint32_t address, uint32_t value) {
    if (experimentPreserveRomdis) {
        nwii::runtime::hw::experimentExiMaskState[0] = 0x3800 | value;
    } else {
        nwii::runtime::hw::experiment_exi_select_csr_write(address, value);
    }
}
#include "exi-select-generated.h"

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::experiment_register_exi_masks(dispatcher);
    hw::pi_intsr = 0x10000;
    hw::experiment_exi_init_csr_write(0xcd006800, 0x2000);
    unsigned refused = 0;
    for (unsigned mode = 0; mode < 7; ++mode) {
        const auto state = hw::experimentExiMaskState;
        if (mode == 5) { hw::experimentExiMaskState[0] = 0; }
        if (mode == 6) { hw::pi_intsr = 0x10; }
        const auto before = hw::experimentExiMaskState;
        const auto cause = hw::pi_intsr.load();
        try {
            hw::experiment_exi_select_csr_write(mode == 3 ? 0xcd006814 : mode == 4 ? 0xcd006801 : 0xcd006800,
                                               mode == 0 ? 0 : mode == 1 ? 0x220 : mode == 2 ? 0x400 : 0x200);
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (hw::experimentExiMaskState != before || hw::pi_intsr.load() != cause) {
            return 3;
        }
        hw::experimentExiMaskState = state;
        hw::pi_intsr = 0x10000;
    }
    if (refused != 7) { return 4; }
    std::cout << "EXI_SELECT_GUARDS 7\n";
    experimentPreserveRomdis = argc == 2 && std::string(argv[1]) == "--preserve-romdis";
    auto context = std::make_unique<CPUContext>();
    unsigned device, clock, ni;
    while (std::cin >> device >> clock >> ni) {
        if (device > 2 || clock > 1 || ni > 1) { return 2; }
        context->gpr[4] = 0xcd000000;
        context->gpr[28] = device;
        context->gpr[29] = clock;
        context->fpscr = ni * 4;
        const auto before = dispatcher.read32(0xcd006800);
        const auto cause = hw::pi_intsr.load();
        experiment_exi_select_block(*context);
        const auto after = dispatcher.read32(0xcd006800);
        std::cout << "EXI_SELECT_CASE " << before << ' ' << context->gpr[3] << ' ' << after << ' ' << cause << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
