#pragma once
#include "es_close_after_consumption_adapter.h"

namespace nwii::runtime {
inline bool experimentPlayrecordOpened = false;
inline bool experiment_playrecord_open_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_post_consumption_close_ready(ipc) || (stmSubmitted == 44 && experimentPlayrecordOpened &&
        ipc.ppcControl == 0x3c && ipc.ppcMessage == 0x135e0080 && ipc.armMessage == ipc.ppcMessage);
}
inline void experiment_playrecord_open_validate(CPUContext& context, uint32_t physical) {
    if (physical != 0x135e0080 || (stmSubmitted != 42 && stmSubmitted != 44) ||
        !experimentPostConsumptionClosed || experimentPlayrecordOpened || !devices::experiment_stm_pending() ||
        bat_memory_read32(context, 0x80528ce8) != 0xffffffff ||
        bat_memory_read32(context, 0x935e00a0) != 0x80240680 ||
        bat_memory_read32(context, 0x935e00a4) != 0x935e1020 ||
        bat_memory_read32(context, 0x935e1120) != 0x80244e30 ||
        bat_memory_read32(context, 0x935e1124) != 0x8049325c || bat_memory_read32(context, 0x935e1128)) {
        throw std::runtime_error("Play-record OPEN callback/lifetime unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t,8> expected{1,0,0,0x135e1020,3,2,0x8053fd70,0};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index] ||
            bat_memory_read32(context, 0x935e0080 + index * 4) != expected[index]) {
            throw std::runtime_error("Play-record OPEN header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) { throw std::runtime_error("Play-record OPEN physical tail unverified"); }
    }
    constexpr char path[] = "/title/00000001/00000002/data/play_rec.dat";
    for (unsigned index = 0; index < sizeof(path); ++index) {
        if (bat_memory_read8(context, 0xd35e1020 + index) != uint8_t(path[index]) ||
            bat_memory_read8(context, 0x935e1020 + index) != uint8_t(path[index])) {
            throw std::runtime_error("Play-record OPEN path unverified");
        }
    }
}
inline void experiment_playrecord_open_dispatch(CPUContext& context, uint32_t physical) {
    experiment_playrecord_open_validate(context, physical);
    const auto result = experiment_ipc_open_packet(context, physical);
    if (result != 4) { throw std::runtime_error("Play-record kernel FD differs from original LAB"); }
    experimentPlayrecordOpened = true;
    std::cout << "PLAYRECORD_KERNEL_OPEN " << result << std::endl;
}
inline void experiment_playrecord_callback_observe(CPUContext& context, unsigned kind) {
    if (stmSubmitted == 44) {
        std::cout << "PLAYRECORD_OPEN_CALLBACK " << kind << ' ' << std::hex << context.gpr[3] << ' '
            << context.gpr[4] << ' ' << context.msr << ' ' << bat_memory_read32(context,0x804931d0)
            << ' ' << bat_memory_read32(context,0x80528a40) << ' ' << bat_memory_read32(context,0x804b2b4c)
            << std::dec << std::endl;
    }
}
}
