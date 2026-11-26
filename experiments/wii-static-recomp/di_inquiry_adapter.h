#pragma once
#include "es_title_adapter.h"
#include <algorithm>

namespace nwii::runtime {
inline std::array<uint8_t, 32> experiment_load_di_lab_inquiry(const char* path) {
    if (!path || !*path) {
        throw std::runtime_error("DI inquiry experiment requires explicit Dolphin LAB metadata path");
    }
    std::ifstream file(path, std::ios::binary);
    std::array<uint8_t, 33> data{};
    file.read(reinterpret_cast<char*>(data.data()), data.size());
    if (file.bad() || file.gcount() != 32 || experiment_ipc_be32(data.data()) != 2 ||
        experiment_ipc_be32(data.data() + 4) != 0x20060526 || experiment_ipc_be32(data.data() + 8) != 0x41000000 ||
        std::any_of(data.begin() + 12, data.begin() + 32, [](uint8_t value) { return value != 0; })) {
        throw std::runtime_error("DI inquiry metadata outside measured Dolphin LAB profile");
    }
    std::array<uint8_t, 32> result{};
    std::copy_n(data.begin(), 32, result.begin());
    return result;
}

inline int32_t experiment_di_inquiry_write(CPUContext& context, const IpcRequest& request, const char* path) {
    if (request.cmd != 6 || request.fd != 3 || request.req_addr != 0x135e00e0 || request.ioctl_cmd != 0x12 ||
        request.in_buf != 0x135e2580 || request.in_size != 32 || request.out_buf != 0x492260 || request.out_size != 32) {
        throw std::runtime_error("DI inquiry outside measured request profile");
    }
    const auto* input = context.mmu.get_ptr(request.in_buf);
    if (!input || context.mmu.get_ptr(request.in_buf + 31) != input + 31) {
        throw std::runtime_error("DI inquiry command backing unavailable");
    }
    if (input[0] != 0x12 || std::any_of(input + 1, input + 32, [](uint8_t value) { return value != 0; })) {
        throw std::runtime_error("DI inquiry command buffer unverified");
    }
    auto* output = experiment_ipc_mem1_span(context, request.out_buf, 32);
    const auto metadata = experiment_load_di_lab_inquiry(path);
    std::copy(metadata.begin(), metadata.end(), output);
    return 1;
}
}
