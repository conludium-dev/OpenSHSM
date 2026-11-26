#pragma once
#include "stm_async_dispatch.h"
#include <array>
#include <fstream>
#include <iterator>

namespace nwii::runtime {
inline std::array<uint8_t, 8> experiment_load_es_title(const char* path) {
    if (!path || !*path) {
        throw std::runtime_error("ES title requires explicit own-disc TMD path");
    }
    std::ifstream file(path, std::ios::binary);
    const std::vector<uint8_t> data{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
    if (data.size() < 0x1e4 || experiment_ipc_be32(data.data()) != 0x10001 ||
        experiment_ipc_be32(data.data() + 0x184) != 1 || experiment_ipc_be32(data.data() + 0x188) != 53 ||
        experiment_ipc_be32(data.data() + 0x18c) != 0x10000 ||
        data[0x190] != 'R' || data[0x191] != '5' || data[0x192] != 'W' || data[0x193] != 'E') {
        throw std::runtime_error("ES title metadata outside verified Wii US0/IOS53 profile");
    }
    std::array<uint8_t, 8> title{};
    std::copy_n(data.data() + 0x18c, 8, title.begin());
    return title;
}

inline void experiment_es_title_dispatch(CPUContext& context, uint32_t physical) {
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = physical;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.arg_cnt_in = experiment_ipc_be32(packet + 16);
    request.arg_cnt_out = experiment_ipc_be32(packet + 20);
    const auto vector = experiment_ipc_be32(packet + 24);
    if (physical != 0x135e0080 || request.cmd != 7 || request.fd != 3 || request.ioctl_cmd != 0x20 ||
        request.arg_cnt_in || request.arg_cnt_out != 1 || vector != 0x53fff0 ||
        !devices::experiment_stm_pending()) {
        throw std::runtime_error("ES title packet outside measured native caller profile");
    }
    const auto* bytes = experiment_ipc_mem1_span(context, vector, 8);
    const auto address = experiment_ipc_be32(bytes);
    const auto length = experiment_ipc_be32(bytes + 4);
    if (address != 0x53ff20 || length != 8) {
        throw std::runtime_error("ES title physical vector unverified");
    }
    request.ioctlv_vecs.push_back({address, length});
    const auto result = IOSKernel::get().ioctlv(context, request);
    if (result != IPC_OK) {
        throw std::runtime_error("ES title device did not produce verified response");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, request.cmd);
}
}
