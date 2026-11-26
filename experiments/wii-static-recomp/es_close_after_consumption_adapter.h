#pragma once
#include "es_consumption_dispatch.h"

namespace nwii::runtime {
inline bool experimentPostConsumptionClosed = false;
inline bool experiment_post_consumption_close_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_es_consumption_reply_ready(ipc) || (stmSubmitted == 42 && experimentPostConsumptionClosed &&
        ipc.ppcControl == 0x3c && ipc.ppcMessage == 0x135e0080 && ipc.armMessage == ipc.ppcMessage);
}
inline void experiment_post_consumption_close_validate(CPUContext& context, uint32_t physical) {
    if (physical != 0x135e0080 || (stmSubmitted != 40 && stmSubmitted != 42) || !experimentEsConsumptionReply ||
        experimentPostConsumptionClosed || !devices::experiment_stm_pending() ||
        bat_memory_read32(context, 0x80528ce8) != 4 || bat_memory_read32(context, 0x804983c8) ||
        bat_memory_read32(context, 0x8052ac50) || bat_memory_read32(context, 0x804b2b4c) != 0x935e00c0) {
        throw std::runtime_error("Post-ES16 CLOSE owner/lifetime unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{2, 0, 4, 0x16, 1, 2, 0x8053fd70, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("Post-ES16 CLOSE physical header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) { throw std::runtime_error("Post-ES16 CLOSE physical tail unverified"); }
    }
}
inline void experiment_post_consumption_close_dispatch(CPUContext& context, uint32_t physical) {
    experiment_post_consumption_close_validate(context, physical);
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const auto result = IOSKernel::get().close(context, experiment_ipc_be32(packet + 8));
    if (result != IPC_OK) { throw std::runtime_error("Post-ES16 CLOSE kernel result outside original profile"); }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, 2);
    experimentPostConsumptionClosed = true;
}
inline void experiment_post_consumption_close_observe(CPUContext& context, unsigned kind) {
    if ((kind == 1 && stmSubmitted == 40) || (kind == 2 && stmSubmitted == 42)) {
        std::cout << "POST_ES16_CLOSE_SOURCE " << kind << ' ' << std::hex << context.gpr[3] << ' ' << context.msr
            << ' ' << bat_memory_read32(context, 0x80528ce8) << ' ' << bat_memory_read32(context, 0x804b2b4c)
            << std::dec << std::endl;
        if (kind == 2) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "POST_ES16_CLOSE_CACHED" : "POST_ES16_CLOSE_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
                }
                std::cout << std::endl;
            }
        }
    }
}
}
