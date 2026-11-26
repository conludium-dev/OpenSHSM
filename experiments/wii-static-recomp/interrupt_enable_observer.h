#pragma once
namespace nwii::runtime {
inline void experiment_interrupt_enable_observe(CPUContext& context) {
    if (context.pc != 0x8021750c || context.lr != 0x80211630 || context.msr != 0xa032) {
        return;
    }
    std::cout << "IRQ_ENABLE_STATE " << std::hex << context.pc << ' ' << context.lr << ' ' << context.msr
              << ' ' << hw::pi_intsr.load() << ' ' << hw::pi_intmr.load()
              << ' ' << (hw::pi_intsr.load() & hw::pi_intmr.load())
              << ' ' << hw::experimentSiControl << ' ' << hw::experimentSiControlWritten
              << ' ' << hw::experimentSiQuery.interruptProfile << ' ' << siExternalEntries << std::dec << '\n';
    std::cout << "IRQ_ENABLE_OS" << std::hex;
    for (uint32_t address : {0x800000c0u, 0x800000d4u, 0x80003010u, 0x8052aad8u,
            0x80003090u, 0x800000c4u, 0x800000c8u, 0x8052ab00u, 0x8052ab04u}) {
        std::cout << ' ' << address << ' ' << bat_memory_read32(context, address);
    }
    std::cout << std::dec << '\n';
    std::cout << "IRQ_ENABLE_VECTOR" << std::hex;
    for (uint32_t index = 0; index < 38; ++index) {
        std::cout << ' ' << bat_memory_read32(context, 0x80000500 + index * 4);
    }
    std::cout << std::dec << '\n';
}
}
