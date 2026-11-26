#pragma once
#include "es_title_adapter.h"

namespace nwii::runtime {
inline int32_t experiment_es_datadir_write(CPUContext& context, const IpcRequest& request,
    const std::array<uint8_t, 8>& title) {
    if (request.cmd != 7 || request.fd != 3 || request.req_addr != 0x135e0080 || request.ioctl_cmd != 0x1d ||
        request.arg_cnt_in != 1 || request.arg_cnt_out != 1 || request.ioctlv_vecs.size() != 2 ||
        request.ioctlv_vecs[0].addr != 0x53ff40 || request.ioctlv_vecs[0].len != 8 ||
        request.ioctlv_vecs[1].addr != 0x4b2cc0 || request.ioctlv_vecs[1].len != 30) {
        throw std::runtime_error("ES data-dir request outside measured native profile");
    }
    const auto* input = experiment_ipc_mem1_span(context, 0x53ff40, 8);
    if (!std::equal(title.begin(), title.end(), input)) {
        throw std::runtime_error("ES data-dir input differs from own-disc title");
    }
    std::string path = "/title/";
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned index = 0; index < title.size(); ++index) {
        if (index == 4) {
            path += '/';
        }
        path += hex[input[index] >> 4];
        path += hex[input[index] & 15];
    }
    path += "/data";
    if (path.size() != 29) {
        throw std::runtime_error("ES data-dir output extent unverified");
    }
    auto* output = experiment_ipc_mem1_span(context, 0x4b2cc0, 30);
    std::copy(path.begin(), path.end(), output);
    return IPC_OK;
}

inline void experiment_es_datadir_dispatch(CPUContext& context, uint32_t physical) {
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{7, 0, 3, 0x1d, 1, 1, 0x540010, 0};
    if (physical != 0x135e0080 || !devices::experiment_stm_pending()) {
        throw std::runtime_error("ES data-dir packet/pending owner unverified");
    }
    for (unsigned index = 0; index < expected.size(); ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("ES data-dir physical header unverified");
        }
    }
    IpcRequest request{};
    request.cmd = 7;
    request.fd = 3;
    request.req_addr = physical;
    request.ioctl_cmd = 0x1d;
    request.arg_cnt_in = 1;
    request.arg_cnt_out = 1;
    const auto* vectors = experiment_ipc_mem1_span(context, 0x540010, 16);
    for (unsigned index = 0; index < 2; ++index) {
        request.ioctlv_vecs.push_back({experiment_ipc_be32(vectors + index * 8),
            experiment_ipc_be32(vectors + index * 8 + 4)});
    }
    if (IOSKernel::get().ioctlv(context, request) != IPC_OK) {
        throw std::runtime_error("ES data-dir device result unverified");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, 0);
    experiment_ipc_store_be32(packet + 8, 7);
}
}
