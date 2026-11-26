#pragma once
#include "ipc_open_packet.h"

namespace nwii::runtime::devices {
const IpcRequest* experiment_stm_pending();
}

namespace nwii::runtime {
inline unsigned stmAsyncDispatched = 0;
inline void experiment_stm_dispatch_async(CPUContext& context, uint32_t physical) {
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = physical;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.in_buf = experiment_ipc_be32(packet + 16);
    request.in_size = experiment_ipc_be32(packet + 20);
    request.out_buf = experiment_ipc_be32(packet + 24);
    request.out_size = experiment_ipc_be32(packet + 28);
    if (physical != 0x135e0020 || request.cmd != 6 || request.fd != 1 || request.ioctl_cmd != 0x1000 ||
        request.in_buf != 0x493060 || request.in_size != 32 || request.out_buf != 0x493080 || request.out_size != 32 ||
        stmAsyncDispatched || devices::experiment_stm_pending()) {
        throw std::runtime_error("STM async packet/state outside original pending profile");
    }
    if (IOSKernel::get().ioctl(context, request) != IPC_NO_REPLY || !devices::experiment_stm_pending()) {
        throw std::runtime_error("STM async device did not retain deferred request");
    }
    ++stmAsyncDispatched;
}
}
