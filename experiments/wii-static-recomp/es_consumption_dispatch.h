#pragma once
#include "es_consumption_adapter.h"

namespace nwii::runtime {
inline bool experimentEsConsumptionReply = false;
inline uint32_t experimentEsConsumptionCaller = 0;
inline bool experiment_es_consumption_prior_arm(uint32_t message, uint32_t arm) {
    return (stmSubmitted == 39 || stmSubmitted == 40) && message == 0x135e0080 && arm == 0x135e00e0 &&
        experimentInquiryTicketReturned && experimentInquiryReplyActive && experimentInquiryInputInvalidates == 1;
}
inline bool experiment_es_consumption_reply_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_inquiry_reply_ready(ipc) || (stmSubmitted == 40 && experimentEsConsumptionReply &&
        ipc.ppcControl == 0x3c && ipc.ppcMessage == 0x135e0080 && ipc.armMessage == ipc.ppcMessage);
}
inline void experiment_es_consumption_validate(CPUContext& context, uint32_t physical) {
    if (physical != 0x135e0080 || (stmSubmitted != 38 && stmSubmitted != 40) ||
        !devices::experiment_stm_pending() || !experimentInquiryTicketReturned || !experimentInquiryReplyActive ||
        experimentInquiryInputInvalidates != 1 || bat_memory_read32(context, 0x80528ce8) != 4 ||
        bat_memory_read32(context, 0x804983c8) || bat_memory_read32(context, 0x8052ac50) ||
        bat_memory_read32(context, 0x804b2b4c) != 0x935e00c0) {
        throw std::runtime_error("ES16 request/FD/retired inquiry/STM ownership unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{7, 0, 4, 0x16, 1, 2, 0x53fd70, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("ES16 physical header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) { throw std::runtime_error("ES16 physical tail unverified"); }
    }
    const auto* vectors = experiment_ipc_mem1_span(context, 0x53fd70, 24);
    const std::array<uint32_t, 6> expectedVectors{0x53fca0, 8, 0, 0, 0x53fcc0, 4};
    for (unsigned index = 0; index < 6; ++index) {
        if (experiment_ipc_be32(vectors + index * 4) != expectedVectors[index]) {
            throw std::runtime_error("ES16 physical vectors unverified");
        }
    }
}
inline void experiment_es_consumption_dispatch(CPUContext& context, uint32_t physical) {
    experiment_es_consumption_validate(context, physical);
    if (experimentEsConsumptionReply) { throw std::runtime_error("ES16 repeated response unverified"); }
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = physical;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.arg_cnt_in = experiment_ipc_be32(packet + 16);
    request.arg_cnt_out = experiment_ipc_be32(packet + 20);
    const auto* vectors = experiment_ipc_mem1_span(context, experiment_ipc_be32(packet + 24), 24);
    for (unsigned index = 0; index < 3; ++index) {
        request.ioctlv_vecs.push_back({experiment_ipc_be32(vectors + index * 8), experiment_ipc_be32(vectors + index * 8 + 4)});
    }
    std::cout << "ES16_SERVICE_COUNT_BEFORE " << std::hex << experiment_ipc_be32(experiment_ipc_mem1_span(context, 0x53fcc0, 4)) << std::dec << std::endl;
    const auto result = IOSKernel::get().ioctlv(context, request);
    if (result != IPC_OK) { throw std::runtime_error("ES16 service result outside measured LAB response"); }
    std::cout << "ES16_SERVICE_COUNT_AFTER " << std::hex << experiment_ipc_be32(experiment_ipc_mem1_span(context, 0x53fcc0, 4)) << std::dec << std::endl;
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, request.cmd);
    experimentEsConsumptionReply = true;
}
inline void experiment_es_consumption_observe(CPUContext& context, unsigned kind) {
    if ((kind == 1 && stmSubmitted == 38) || (kind == 2 && stmSubmitted == 40)) {
        if (kind == 1) { experimentEsConsumptionCaller = context.gpr[6]; }
        std::cout << "ES16_SOURCE " << kind << ' ' << std::hex << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.gpr[5] << ' ' << context.gpr[6] << ' ' << context.msr << ' ' << experimentEsConsumptionCaller
            << ' ' << bat_memory_read32(context, 0x804b2b4c) << std::dec << std::endl;
        if (experimentEsConsumptionCaller >= 0x80400000 && experimentEsConsumptionCaller <= 0x80550000 - 4) {
            std::cout << "ES16_CALLER " << kind;
            for (unsigned index = 0; index < 4; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, experimentEsConsumptionCaller + index));
            }
            std::cout << std::endl;
        }
        if (kind == 2) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "ES16_REPLY_CACHED" : "ES16_REPLY_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
                }
                std::cout << std::endl;
            }
        }
    }
}
}
