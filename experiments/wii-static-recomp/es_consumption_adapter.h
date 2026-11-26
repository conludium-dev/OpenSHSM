#pragma once
#include "es_di_ticket_adapter.h"

namespace nwii::runtime {
inline int32_t experiment_es_consumption_write(CPUContext& context, const IpcRequest& request,
    const std::array<uint8_t, 8>& title, const char* ticketPath) {
    const char* policy = std::getenv("SHSM_ES_LAB_CONSUMPTION");
    if (!policy || std::string(policy) != "1" || request.cmd != 7 || request.fd != 4 ||
        request.req_addr != 0x135e0080 || request.ioctl_cmd != 0x16 ||
        request.arg_cnt_in != 1 || request.arg_cnt_out != 2 || request.ioctlv_vecs.size() != 3 ||
        request.ioctlv_vecs[0].addr != 0x53fca0 || request.ioctlv_vecs[0].len != 8 ||
        request.ioctlv_vecs[1].addr || request.ioctlv_vecs[1].len ||
        request.ioctlv_vecs[2].addr != 0x53fcc0 || request.ioctlv_vecs[2].len != 4) {
        throw std::runtime_error("ES16 outside explicit measured LAB ticket-ID/NULL-array/count profile");
    }
    const auto* input = experiment_ipc_mem1_span(context, request.ioctlv_vecs[0].addr, 8);
    auto* output = experiment_ipc_mem1_span(context, request.ioctlv_vecs[2].addr, 4);
    const auto view = experiment_load_es_ticket_view(ticketPath, title);
    if (!std::equal(view.begin() + 4, view.begin() + 12, input)) {
        throw std::runtime_error("ES16 input does not match own-Wii ticket ID");
    }
    experiment_ipc_store_be32(output, 0);
    return IPC_OK;
}
}
