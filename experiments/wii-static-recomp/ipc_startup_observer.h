#pragma once
namespace nwii::runtime {
inline void experiment_ipc_startup_observe_store(CPUContext& context, uint32_t address, uint32_t value) {
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, true);
    const auto ipc = hw::experiment_ipc_snapshot();
    std::cout << "IPC_STARTUP_ACCESS " << std::hex << context.pc << ' ' << context.lr << ' ' << context.msr
              << " 80241c38 " << address << ' ' << value << ' ' << mapping.physical << ' ' << mapping.slot
              << ' ' << mapping.wimg << " 4" << std::dec << '\n';
    std::cout << "IPC_STARTUP_BEFORE " << std::hex << ipc.ppcMessage << ' ' << ipc.armMessage << ' '
              << ipc.ppcControl << ' ' << ipc.armControl << ' ' << ipc.ppcMask << ' ' << ipc.delay
              << ' ' << hw::pi_intsr.load() << ' ' << hw::pi_intmr.load() << std::dec << '\n';
    bat_memory_write32(context, address, value);
}
}
