#pragma once
#include "ipc_open_packet.h"
#include "stm_async_dispatch.h"

namespace nwii::runtime {
inline void experiment_di86_validate(CPUContext& context, uint32_t physical) {
    if (physical != 0x135e0080 || !devices::experiment_stm_pending()) {
        throw std::runtime_error("DI86 request/STM owner unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{6, 3, 3, 0x86, 0x135e2560, 32, 0, 0};
    for (unsigned index = 0; index < expected.size(); ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("DI86 physical header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) {
            throw std::runtime_error("DI86 physical packet tail unverified");
        }
    }
    if (bat_memory_read32(context, 0x935e00a0) != 0x802258a0 ||
        bat_memory_read32(context, 0x935e00a4) != 0x804983a0 ||
        bat_memory_read32(context, 0x804983a0) != 0 ||
        bat_memory_read32(context, 0x804983a4) != 1 ||
        bat_memory_read32(context, 0x804983a8) != 0x01000000 ||
        bat_memory_read32(context, 0x804983ac) != 0xfeebdaed) {
        throw std::runtime_error("DI86 callback state unverified");
    }
}

inline void experiment_di86_dispatch(CPUContext& context, uint32_t physical) {
    experiment_di86_validate(context, physical);
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = physical;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.in_buf = experiment_ipc_be32(packet + 16);
    request.in_size = experiment_ipc_be32(packet + 20);
    request.out_buf = experiment_ipc_be32(packet + 24);
    request.out_size = experiment_ipc_be32(packet + 28);
    const auto result = IOSKernel::get().ioctl(context, request);
    if (result != 1) {
        throw std::runtime_error("DI86 result outside original measured profile");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, request.cmd);
}
}
