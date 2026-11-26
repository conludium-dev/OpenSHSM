#include "mi_mask_backend.h"
#include "runtime/hw/hw.h"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::experiment_register_mi_mask(dispatcher);
    const bool unregistered = argc == 2 && std::string(argv[1]) == "--unregistered";
    const uint32_t cause = argc == 2 && std::string(argv[1]) == "--pi-zero" ? 0 : 0x10000;
    if (unregistered) {
        dispatcher.clear();
    } else {
        dispatcher.write16(0xcc00401c, 31);
        unsigned refused = 0;
        for (unsigned mode = 0; mode < 4; ++mode) {
            try {
                if (mode == 0) {
                    dispatcher.write32(0xcc00401c, 0);
                } else if (mode == 1) {
                    dispatcher.read32(0xcc00401c);
                } else if (mode == 2) {
                    dispatcher.write16(0xcc00401d, 0);
                } else {
                    dispatcher.read16(0xcc00401d);
                }
            } catch (const std::runtime_error&) {
                ++refused;
            }
            if (dispatcher.read16(0xcc00401c) != 31) {
                return 3;
            }
        }
        if (refused != 4) {
            return 4;
        }
        std::cout << "MI_GUARDS " << refused << '\n';
    }
    unsigned prior, value;
    while (std::cin >> prior >> value) {
        if (prior > 65535 || value > 65535) {
            return 2;
        }
        hw::pi_intsr = cause;
        dispatcher.write16(0xcc00401c, prior);
        const auto before = dispatcher.read16(0xcc00401c);
        dispatcher.write16(0xcc00401c, value);
        const auto after = dispatcher.read16(0xcc00401c);
        std::cout << "MI_CASE " << before << ' ' << after << ' ' << hw::pi_intsr.load() << '\n';
    }
    return 0;
}
