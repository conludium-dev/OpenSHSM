#define get_os_time experiment_ai_unverified_time
#include "hw_ai.cpp"
#undef get_os_time
#include "ai_mask_backend.h"
#include <stdexcept>

namespace nwii::runtime {
uint64_t experiment_ai_unverified_time() {
    throw std::runtime_error("AI sample timing outside verified mask profile");
}
}

namespace nwii::runtime::hw {
static void experiment_ai_mask_guard(uint32_t address) {
    if (address != 0xcd006c00 || (ai_cr & ~4u) != 0x42 || ai_vr || ai_scnt || ai_it || ai_start_time
        || (pi_intsr.load() & 0x20u)) {
        throw std::runtime_error("AI mask outside verified quiescent profile");
    }
}

void experiment_register_ai_mask(MMIODispatcher& dispatcher) {
    register_ai(dispatcher);
    if (ai_cr || ai_vr || ai_scnt || ai_it || ai_start_time) {
        throw std::runtime_error("AI loader seed requires unused vendor state");
    }
    dispatcher.write32(0xcc006c00, 0x42);
    dispatcher.register_region(0xcd006c00, 0xcd006c03,
        [](uint32_t address) -> uint32_t {
            experiment_ai_mask_guard(address);
            return MMIODispatcher::get().read32(0xcc006c00);
        },
        [](uint32_t address, uint32_t value) {
            experiment_ai_mask_guard(address);
            if ((value & ~4u) != 0x42) {
                throw std::runtime_error("AI mask write outside observed values");
            }
            ai_cr = value;
        },
        [](uint32_t) -> uint16_t {
            throw std::runtime_error("AI halfword read unverified");
        },
        [](uint32_t, uint16_t) {
            throw std::runtime_error("AI halfword write unverified");
        });
}
}
