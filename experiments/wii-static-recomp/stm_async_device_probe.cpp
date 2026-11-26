#include "runtime/ios_kernel.h"
#include "runtime/devices.h"
#include <array>
#include <iostream>
#include <stdexcept>

namespace nwii::runtime::devices {
const IpcRequest* experiment_stm_pending();
}

int main() {
    using namespace nwii::runtime;
    CPUContext context;
    IOSKernel::get().init();
    IOSKernel::get().register_device(devices::create_stm_device());
    if (IOSKernel::get().open(context, "/dev/stm/immediate", 0) != 0 ||
        IOSKernel::get().open(context, "/dev/stm/eventhook", 0) != 1) {
        return 2;
    }
    IpcRequest valid{};
    valid.cmd = 6;
    valid.fd = 1;
    valid.req_addr = 0x135e0020;
    valid.ioctl_cmd = 0x1000;
    valid.in_buf = 0x493060;
    valid.in_size = 32;
    valid.out_buf = 0x493080;
    valid.out_size = 32;
    for (unsigned test = 0; test < 8; ++test) {
        auto invalid = valid;
        std::array<uint32_t*, 8> fields{&invalid.cmd, &invalid.fd, &invalid.req_addr, &invalid.ioctl_cmd,
            &invalid.in_buf, &invalid.in_size, &invalid.out_buf, &invalid.out_size};
        *fields[test] ^= 1;
        bool rejected = false;
        try {
            rejected = IOSKernel::get().ioctl(context, invalid) != IPC_NO_REPLY;
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        if (!rejected || devices::experiment_stm_pending()) { return 3; }
    }
    if (IOSKernel::get().ioctl(context, valid) != IPC_NO_REPLY) { return 4; }
    const auto* pending = devices::experiment_stm_pending();
    if (!pending || pending->cmd != 6 || pending->req_addr != 0x135e0020 || pending->fd != 1 || pending->ioctl_cmd != 0x1000) { return 5; }
    bool rejected = false;
    try {
        IOSKernel::get().ioctl(context, valid);
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    if (!rejected || devices::experiment_stm_pending() != pending || pending->out_buf != valid.out_buf) { return 6; }
    std::cout << "STM_ASYNC_DEVICE deferred1 malformed8 duplicate1 retained\n";
    return 0;
}
