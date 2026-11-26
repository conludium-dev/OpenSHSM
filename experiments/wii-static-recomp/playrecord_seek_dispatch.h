#pragma once
#include "playrecord_read_dispatch.h"
#include "playrecord_seek_flush.h"

namespace nwii::runtime {
inline bool experimentPlayrecordReadRetired = false;
inline bool experimentPlayrecordSeekReplied = false;
inline bool experimentPlayrecordSeekRetired = false;
inline bool experiment_playrecord_seek_prior_arm(uint32_t message,uint32_t arm) {
    return (stmSubmitted == 47 || stmSubmitted == 48) && message == 0x135e0080 && arm == 0x135e00e0 &&
        experimentPlayrecordReadReplied && !experimentPlayrecordSeekReplied && devices::experiment_stm_pending();
}
inline bool experiment_playrecord_seek_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_playrecord_read_ready(ipc) || (stmSubmitted == 48 && experimentPlayrecordSeekReplied &&
        ipc.ppcControl == 0x3c && ipc.ppcMessage == 0x135e0080 && ipc.armMessage == ipc.ppcMessage);
}
inline void experiment_playrecord_seek_validate(CPUContext& context,uint32_t physical) {
    if (physical != 0x135e0080 || (stmSubmitted != 46 && stmSubmitted != 48) || !experimentPlayrecordReadReplied ||
        experimentPlayrecordSeekReplied || !devices::experiment_stm_pending() ||
        bat_memory_read32(context,0x804931d0) != 4 || bat_memory_read32(context,0x80528a40) != 3 ||
        bat_memory_read32(context,0x8052ab40) != 1 ||
        bat_memory_read32(context,0x935e00a0) != 0x80240680 ||
        bat_memory_read32(context,0x935e00a4) != 0x935e1020 ||
        bat_memory_read32(context,0x935e1120) != 0x802464b0 ||
        bat_memory_read32(context,0x935e1124) != 0x8049325c) {
        throw std::runtime_error("Play-record SEEK owner/callback/state unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context,physical,64);
    const std::array<uint32_t,8> expected{5,4,4,0,0,2,0x8053fd70,0};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("Play-record SEEK physical header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) {
            throw std::runtime_error("Play-record SEEK physical tail unverified");
        }
    }
}
inline void experiment_playrecord_seek_retire(CPUContext& context,uint32_t value,bool final) {
    if (stmSubmitted != 48 || !final || value != 0x38) {
        return;
    }
    const auto head = bat_memory_read32(context,0x804b2b4c);
    const auto state = bat_memory_read32(context,0x80528a40);
    if (context.gpr[31] == 0x935e00e0 && !experimentPlayrecordSeekReplied) {
        if (!experimentPlayrecordReadReplied || head != 0x935e00c0 || state != 3) {
            throw std::runtime_error("Play-record READ source retirement unverified");
        }
        experimentPlayrecordReadRetired = true;
        std::cout << "PLAYRECORD_READ_RETIRED" << std::endl;
    } else if (context.gpr[31] == 0x935e0080 && experimentPlayrecordSeekReplied) {
        if (!experimentPlayrecordReadRetired || head != 0x935e0060 || state != 4 ||
            bat_memory_read32(context,0x8052ab40) != 1 || bat_memory_read32(context,0x804931d0) != 4) {
            throw std::runtime_error("Play-record SEEK source retirement unverified");
        }
        experimentPlayrecordSeekRetired = true;
        std::cout << "PLAYRECORD_SEEK_RETIRED" << std::endl;
    }
}
inline void experiment_playrecord_seek_dispatch(CPUContext& context,uint32_t physical) {
    experiment_playrecord_seek_validate(context,physical);
    if (!experimentPlayrecordReadRetired || bat_memory_read32(context,0x804b2b4c) != 0x935e00c0) {
        throw std::runtime_error("Play-record SEEK before original READ retirement");
    }
    auto* packet = experiment_ipc_mem1_span(context,physical,64);
    const auto result = IOSKernel::get().seek(context,4,0,0);
    if (result != 0) {
        throw std::runtime_error("Play-record SEEK result differs from original LAB");
    }
    experiment_ipc_store_be32(packet,8);
    experiment_ipc_store_be32(packet + 4,uint32_t(result));
    experiment_ipc_store_be32(packet + 8,5);
    experimentPlayrecordSeekReplied = true;
    std::cout << "PLAYRECORD_KERNEL_SEEK " << result << std::endl;
}
inline void experiment_playrecord_seek_observe(CPUContext& context,unsigned kind) {
    if (stmSubmitted == 48 && experimentPlayrecordSeekReplied) {
        std::cout << "PLAYRECORD_SEEK_OBSERVE " << kind << ' ' << std::hex << context.gpr[3] << ' '
            << context.gpr[4] << ' ' << context.msr << ' ' << bat_memory_read32(context,0x804931d0) << ' '
            << bat_memory_read32(context,0x80528a40) << ' ' << bat_memory_read32(context,0x804b2b4c)
            << std::dec << std::endl;
        if (kind <= 2) {
            for (bool cached : {false,true}) {
                std::cout << (cached ? "PLAYRECORD_SEEK_REPLY_CACHED" : "PLAYRECORD_SEEK_REPLY_PHYSICAL") << ' ' << kind;
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(bat_memory_read8(context,(cached ? 0x935e0080u : 0xd35e0080u) + index));
                }
                std::cout << std::endl;
            }
        }
    }
}
}
