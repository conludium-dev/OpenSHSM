#include "ipc_reset_backend.cpp"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::register_ipc(dispatcher);
    unsigned index, before, value, message;
    while (std::cin >> index >> before >> value >> message) {
        hw::ipc_ppc_ctrl = before;
        hw::ipc_arm_msg = message;
        dispatcher.write32(0xcd000004, value);
        const auto vendorFirst = hw::experiment_ipc_snapshot();
        dispatcher.write32(0xcd000004, 0x38);
        const auto vendorX2 = hw::experiment_ipc_snapshot();
        hw::ipc_ppc_ctrl = before;
        hw::experiment_ipc_control_no_request(value);
        const auto correctedFirst = hw::experiment_ipc_snapshot();
        hw::experiment_ipc_control_no_request(0x38);
        const auto correctedX2 = hw::experiment_ipc_snapshot();
        std::cout << "IPC_CONTROL " << index << ' ' << vendorFirst.ppcControl << ' ' << vendorX2.ppcControl
                  << ' ' << correctedFirst.ppcControl << ' ' << correctedX2.ppcControl
                  << ' ' << correctedFirst.armMessage << ' ' << correctedX2.armMessage << '\n';
    }
    unsigned refused = 0;
    auto reject = [&](uint32_t value) {
        const auto prior = hw::experiment_ipc_snapshot();
        bool caught = false;
        try {
            hw::experiment_ipc_control_no_request(value);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        const auto after = hw::experiment_ipc_snapshot();
        if (!caught || prior.ppcControl != after.ppcControl || prior.ppcMessage != after.ppcMessage
            || prior.armMessage != after.armMessage || prior.armControl != after.armControl
            || prior.ppcMask != after.ppcMask || prior.delay != after.delay) {
            throw std::runtime_error("Refused control write changed IPC state");
        }
        ++refused;
    };
    for (uint32_t value : {1u, 0x31u, 0x40u, 0x80000000u}) {
        reject(value);
    }
    hw::ipc_ppc_ctrl |= 1;
    reject(0x38);
    hw::ipc_ppc_ctrl &= ~1u;
    CPUContext context;
    g_ctx_ptr = &context;
    reject(0x38);
    g_ctx_ptr = nullptr;
    g_mmu = &context.mmu;
    reject(0x38);
    g_mmu = nullptr;
    g_ipc_interrupt_delay = 1;
    reject(0x38);
    g_ipc_interrupt_delay = 0;
    std::cout << "IPC_CONTROL_GUARDS " << refused << '\n';
}
