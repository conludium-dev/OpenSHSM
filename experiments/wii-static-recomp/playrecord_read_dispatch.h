#pragma once
#include "playrecord_open_dispatch.h"
#include "playrecord_read_flush.h"

namespace nwii::runtime {
inline bool experimentPlayrecordOpenRetired = false;
inline bool experimentPlayrecordReadReplied = false;
inline bool experiment_playrecord_read_prior_arm(uint32_t message,uint32_t arm) {
    return (stmSubmitted == 45 || stmSubmitted == 46) && message == 0x135e00e0 && arm == 0x135e0080 &&
        experimentPlayrecordOpened && !experimentPlayrecordReadReplied && devices::experiment_stm_pending();
}
inline bool experiment_playrecord_read_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_playrecord_open_ready(ipc) || (stmSubmitted == 46 && experimentPlayrecordReadReplied &&
        ipc.ppcControl == 0x3c && ipc.ppcMessage == 0x135e00e0 && ipc.armMessage == ipc.ppcMessage);
}
inline void experiment_playrecord_read_validate(CPUContext& context,uint32_t physical) {
    if (physical != 0x135e00e0 || (stmSubmitted != 44 && stmSubmitted != 46) || !experimentPlayrecordOpened ||
        experimentPlayrecordReadReplied || !devices::experiment_stm_pending() ||
        bat_memory_read32(context,0x804931d0) != 4 || bat_memory_read32(context,0x80528a40) != 2 ||
        bat_memory_read32(context,0x935e0100) != 0x80240680 ||
        bat_memory_read32(context,0x935e0104) != 0x935e1180 ||
        bat_memory_read32(context,0x935e1280) != 0x802464b0 ||
        bat_memory_read32(context,0x935e1284) != 0x8049325c) {
        throw std::runtime_error("Play-record READ owner/callback/state unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context,physical,64);
    const std::array<uint32_t,8> expected{3,1,4,0x493120,128,32,0x80492260,32};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("Play-record READ physical header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) {
            throw std::runtime_error("Play-record READ physical tail unverified");
        }
    }
}
inline void experiment_playrecord_open_retire(CPUContext& context,uint32_t value,bool final) {
    if (stmSubmitted == 46 && final && value == 0x38 && context.gpr[31] == 0x935e0080) {
        if (!experimentPlayrecordOpened || bat_memory_read32(context,0x804b2b4c) != 0x935e0060 ||
            bat_memory_read32(context,0x804931d0) != 4 || bat_memory_read32(context,0x80528a40) != 2) {
            throw std::runtime_error("Play-record OPEN source retirement unverified");
        }
        experimentPlayrecordOpenRetired = true;
        std::cout << "PLAYRECORD_OPEN_RETIRED" << std::endl;
    }
}
inline void experiment_playrecord_read_dispatch(CPUContext& context,uint32_t physical) {
    experiment_playrecord_read_validate(context,physical);
    if (!experimentPlayrecordOpenRetired || bat_memory_read32(context,0x804b2b4c) != 0x935e0060) {
        throw std::runtime_error("Play-record READ before original OPEN retirement");
    }
    auto* packet = experiment_ipc_mem1_span(context,physical,64);
    const auto result = IOSKernel::get().read(context,4,0x493120,128);
    if (result != 128) {
        throw std::runtime_error("Play-record READ result differs from original LAB");
    }
    experiment_ipc_store_be32(packet,8);
    experiment_ipc_store_be32(packet + 4,uint32_t(result));
    experiment_ipc_store_be32(packet + 8,3);
    experimentPlayrecordReadReplied = true;
    std::cout << "PLAYRECORD_KERNEL_READ " << result << std::endl;
}
inline void experiment_playrecord_read_observe(CPUContext& context,unsigned kind) {
    if (stmSubmitted == 46 && experimentPlayrecordReadReplied) {
        std::cout << "PLAYRECORD_READ_CALLBACK " << kind << ' ' << std::hex << context.gpr[3] << ' '
            << context.gpr[4] << ' ' << context.msr << ' ' << bat_memory_read32(context,0x804931d0) << ' '
            << bat_memory_read32(context,0x80528a40) << ' ' << bat_memory_read32(context,0x804b2b4c)
            << std::dec << std::endl;
        for (bool cached : {false,true}) {
            std::cout << (cached ? "PLAYRECORD_READ_REPLY_CACHED" : "PLAYRECORD_READ_REPLY_PHYSICAL") << ' ' << kind;
            for (unsigned index = 0; index < 64; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context,(cached ? 0x935e00e0u : 0xd35e00e0u) + index));
            }
            std::cout << std::endl;
            std::cout << (cached ? "PLAYRECORD_READ_DATA_CACHED" : "PLAYRECORD_READ_DATA_PHYSICAL") << ' ' << kind;
            for (unsigned index = 0; index < 128; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context,(cached ? 0x80493120u : 0xc0493120u) + index));
            }
            std::cout << std::endl;
        }
    }
}
}
