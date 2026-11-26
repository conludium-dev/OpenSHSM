#include "runtime/ios_kernel.h"
#include "runtime/devices.h"
#include <iostream>
#include <stdexcept>

namespace nwii::runtime {
uint32_t g_watch_addr = 0;
uint32_t HW_Reg_Read32(uint32_t) {
    throw std::runtime_error("Unexpected MMIO in FS OPEN component");
}
void GX_WGPIPE_Write8(uint8_t) {
    throw std::runtime_error("Unexpected GX in FS OPEN component");
}
void watch_hit(uint32_t, uint32_t, int) {
    throw std::runtime_error("Unexpected memory watch in FS OPEN component");
}
}

namespace nwii::runtime::devices {
const IpcRequest* experiment_stm_pending();
}

int main() {
    using namespace nwii::runtime;
    CPUContext context;
    auto& kernel = IOSKernel::get();
    kernel.init();
    kernel.register_device(devices::create_stm_device());
    if (kernel.open(context, "/dev/stm/immediate", 0) != 0 || kernel.open(context, "/dev/stm/eventhook", 0) != 1) {
        return 2;
    }
    IpcRequest request{};
    request.cmd = 6;
    request.fd = 1;
    request.req_addr = 0x135e0020;
    request.ioctl_cmd = 0x1000;
    request.in_buf = 0x493060;
    request.in_size = 32;
    request.out_buf = 0x493080;
    request.out_size = 32;
    if (kernel.ioctl(context, request) != IPC_NO_REPLY) {
        return 3;
    }
    const auto* pending = devices::experiment_stm_pending();
    kernel.register_device(devices::create_fs_device());
    for (unsigned index = 3; index < 16; ++index) {
        const auto result = kernel.open(context, index < 10 ? "/dev/fs" : "/dev/openshsm_missing", 0);
        if (!pending || devices::experiment_stm_pending() != pending || pending->cmd != 6 || pending->fd != 1 ||
            pending->req_addr != 0x135e0020 || pending->ioctl_cmd != 0x1000 || pending->in_buf != 0x493060 ||
            pending->in_size != 32 || pending->out_buf != 0x493080 || pending->out_size != 32) {
            return 4;
        }
        std::cout << "FS_PENDING_DEVICE " << index << ' ' << result << '\n';
    }
    return 0;
}
