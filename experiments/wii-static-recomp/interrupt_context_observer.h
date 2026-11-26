#pragma once
#include "interrupt_enable_observer.h"
namespace nwii::runtime {
inline void experiment_interrupt_context_observe(CPUContext& context) {
    experiment_interrupt_enable_observe(context);
    if (context.pc != 0x8021750c || context.lr != 0x80211630 || context.msr != 0xa032) {
        return;
    }
    const uint32_t address = bat_memory_read32(context, 0x800000d4);
    std::cout << "IRQ_ENABLE_CONTEXT " << std::hex << address;
    for (uint32_t offset = 0; offset < 0x1c8; offset += 4) {
        std::cout << ' ' << bat_memory_read32(context, address + offset);
    }
    std::cout << std::dec << '\n';
    std::cout << "IRQ_ENABLE_SI_MEMORY" << std::hex;
    for (uint32_t location : {0x800000d8u, 0x8052aac8u, 0x8052aaccu, 0x8042b6f0u, 0x8042b6f4u,
            0x8042b6f8u, 0x8042b6fcu, 0x8042b700u, 0x8042b704u, 0x8042b708u, 0x8042b70cu,
            0x8042b710u, 0x8042b714u, 0x8042b718u, 0x8042b71cu}) {
        std::cout << ' ' << location << ' ' << bat_memory_read32(context, location);
    }
    std::cout << std::dec << '\n';
    std::cout << "IRQ_ENABLE_PACKETS" << std::hex;
    for (uint32_t offset = 0; offset < 128; offset += 4) {
        std::cout << ' ' << bat_memory_read32(context, 0x80492010 + offset);
    }
    std::cout << std::dec << '\n';
}
}
