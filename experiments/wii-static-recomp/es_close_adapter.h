#pragma once
#include "stm_async_dispatch.h"

namespace nwii::runtime {
inline void experiment_es_close_dispatch(CPUContext& context, uint32_t physical) {
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{2, 0, 3, 0x1d, 1, 1, 0x80540010, 0};
    if (physical != 0x135e0080 || !devices::experiment_stm_pending()) {
        throw std::runtime_error("ES CLOSE packet/pending owner unverified");
    }
    for (unsigned index = 0; index < expected.size(); ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("ES CLOSE physical header unverified");
        }
    }
    const auto result = IOSKernel::get().close(context, experiment_ipc_be32(packet + 8));
    if (result != IPC_OK) {
        throw std::runtime_error("ES CLOSE kernel result outside measured profile");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, 2);
}
}
