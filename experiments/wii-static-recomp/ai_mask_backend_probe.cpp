#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "ai_mask_backend.h"
#include <bit>
#include <iostream>
#include <memory>
#include <string>
#include "ai-mask-generated.h"

static bool experimentAiVendorNegative = false;
static uint32_t experiment_ai_probe_read(uint32_t address) {
    return nwii::runtime::MMIODispatcher::get().read32(experimentAiVendorNegative ? 0xcc006c00 : address);
}
static void experiment_ai_probe_write(uint32_t address, uint32_t value) {
    nwii::runtime::MMIODispatcher::get().write32(experimentAiVendorNegative ? 0xcc006c00 : address, value);
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::experiment_register_ai_mask(dispatcher);
    hw::pi_intsr = 0x10000;
    experimentAiVendorNegative = argc == 2 && std::string(argv[1]) == "--vendor";
    unsigned refused = 0;
    for (unsigned mode = 0; mode < 4; ++mode) {
        try {
            if (mode == 0) {
                dispatcher.write32(0xcd006c00, 0x20);
            } else if (mode == 1) {
                dispatcher.read32(0xcd006c01);
            } else if (mode == 2) {
                dispatcher.write16(0xcd006c00, 0);
            } else {
                dispatcher.read16(0xcd006c00);
            }
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (dispatcher.read32(0xcd006c00) != 0x42) {
            return 3;
        }
    }
    if (refused != 4) {
        return 4;
    }
    std::cout << "AI_GUARDS 4\n";
    auto context = std::make_unique<CPUContext>();
    uint32_t softwareMask, ni;
    while (std::cin >> softwareMask >> ni) {
        context->gpr[3] = 0x00800000;
        context->gpr[4] = softwareMask;
        context->fpscr = ni * 4;
        const auto before = experiment_ai_probe_read(0xcd006c00);
        experiment_ai_mask_block(*context);
        const auto after = experiment_ai_probe_read(0xcd006c00);
        std::cout << "AI_MASK_CASE " << before << ' ' << context->gpr[5] << ' ' << after << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
