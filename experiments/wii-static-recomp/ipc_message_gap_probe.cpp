#include "ipc_reset_backend.cpp"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    auto& dispatcher = MMIODispatcher::get();
    hw::register_ipc(dispatcher);
    hw::experiment_ipc_control_no_request(0x38);
    hw::pi_intsr = 0x10000;
    hw::pi_intmr = 0x40f8;
    for (unsigned index = 0; index < 16; ++index) {
        dispatcher.write32(0xcd000000, 0x135e0020);
        const auto state = hw::experiment_ipc_snapshot();
        if (state.ppcMessage != 0x135e0020 || state.armMessage || state.ppcControl != 0x38 || state.armControl ||
            state.ppcMask != 0x40000000 || state.delay || hw::pi_intsr.load() != 0x10000 || hw::pi_intmr.load() != 0x40f8) {
            return 1;
        }
        std::cout << "MESSAGE_GAP " << index << ' ' << dispatcher.read32(0xcd000000) << ' '
            << dispatcher.read32(0x0d000000) << ' ' << state.ppcControl << '\n';
    }
    return 0;
}
