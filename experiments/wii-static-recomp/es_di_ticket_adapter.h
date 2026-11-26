#pragma once
#include "es_title_adapter.h"
#include <algorithm>

namespace nwii::runtime {
inline std::array<uint8_t, 216> experiment_load_es_ticket_view(const char* path, const std::array<uint8_t, 8>& title) {
    if (!path || !*path) {
        throw std::runtime_error("ES ticket view requires explicit own-Wii ticket path");
    }
    std::ifstream file(path, std::ios::binary);
    std::array<uint8_t, 677> ticket{};
    file.read(reinterpret_cast<char*>(ticket.data()), ticket.size());
    if (file.bad() || file.gcount() != 676 || experiment_ipc_be32(ticket.data()) != 0x10001 || ticket[0x1bc] != 0 ||
        !std::equal(title.begin(), title.end(), ticket.begin() + 0x1dc)) {
        throw std::runtime_error("ES ticket outside measured RSA2048-v0/own-title profile");
    }
    std::array<uint8_t, 216> view{};
    view[0] = ticket[0x1bc];
    std::copy_n(ticket.begin() + 0x1d0, 212, view.begin() + 4);
    return view;
}

inline int32_t experiment_es_di_ticket_write(CPUContext& context, const IpcRequest& request,
    const std::array<uint8_t, 8>& title, const char* path) {
    if (request.cmd != 7 || request.fd != 4 || request.req_addr != 0x135e0080 || request.ioctl_cmd != 0x1b ||
        request.arg_cnt_in != 1 || request.arg_cnt_out != 1 || request.ioctlv_vecs.size() != 2 ||
        request.ioctlv_vecs[0].addr || request.ioctlv_vecs[0].len ||
        request.ioctlv_vecs[1].addr != 0x53ff80 || request.ioctlv_vecs[1].len != 216) {
        throw std::runtime_error("ES DI-ticket view outside measured NULL-input/vector profile");
    }
    auto* output = experiment_ipc_mem1_span(context, request.ioctlv_vecs[1].addr, 216);
    const auto view = experiment_load_es_ticket_view(path, title);
    std::copy(view.begin(), view.end(), output);
    return IPC_OK;
}
}
