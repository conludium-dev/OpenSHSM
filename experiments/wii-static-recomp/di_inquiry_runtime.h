#pragma once
#include "di_inquiry_adapter.h"

namespace nwii::runtime {
inline bool experimentInquiryTicketReturned = false;
inline bool experimentInquiryReplyActive = false;
inline unsigned experimentInquiryInputInvalidates = 0;
inline bool experiment_inquiry_arm(uint32_t message, uint32_t arm) {
    return stmSubmitted == 38 && experimentInquiryTicketReturned && experimentInquiryReplyActive &&
        message == 0x135e0080 && arm == 0x135e00e0;
}
inline bool experiment_inquiry_reply_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return experiment_di_burst_reply_ready(ipc) || (ipc.ppcControl == 0x3c && experiment_inquiry_arm(ipc.ppcMessage, ipc.armMessage));
}
inline void experiment_inquiry_ticket_return(CPUContext& context) {
    if (stmSubmitted == 38 && !std::getenv("SHSM_DI_INQUIRY_DISABLED")) {
        if (context.gpr[3] || context.msr != 0xa032 || experimentInquiryTicketReturned ||
            bat_memory_read32(context, 0x804b2b4c) != 0x935e0060) {
            throw std::runtime_error("Inquiry delivery requires actual ticket return/free");
        }
        experimentInquiryTicketReturned = true;
    }
}
inline void experiment_inquiry_dispatch(CPUContext& context) {
    if (!experimentInquiryTicketReturned || experimentInquiryReplyActive || stmSubmitted != 38 ||
        !devices::experiment_stm_pending() || bat_memory_read32(context, 0x804983c0) != 0x80222f80 ||
        bat_memory_read32(context, 0x804983c8) != 0x01000000 || bat_memory_read32(context, 0x804983cc) != 0xfeebdaed) {
        throw std::runtime_error("Inquiry original callback/ownership unverified");
    }
    auto* packet = experiment_ipc_mem1_span(context, 0x135e00e0, 64);
    const std::array<uint32_t, 8> expected{6, 0, 3, 0x12, 0x135e2580, 32, 0x492260, 32};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("Inquiry physical request header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) {
            throw std::runtime_error("Inquiry physical request tail unverified");
        }
    }
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = 0x135e00e0;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.in_buf = experiment_ipc_be32(packet + 16);
    request.in_size = experiment_ipc_be32(packet + 20);
    request.out_buf = experiment_ipc_be32(packet + 24);
    request.out_size = experiment_ipc_be32(packet + 28);
    const auto result = IOSKernel::get().ioctl(context, request);
    if (result != 1) { throw std::runtime_error("Inquiry service result outside original LAB response"); }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, request.cmd);
    experimentInquiryReplyActive = true;
}
inline void experiment_inquiry_cache_operation(CPUContext& context, uint32_t address, unsigned operation) {
    if (operation == 470 && address == 0x135e2580 && stmSubmitted == 38 && experimentInquiryReplyActive &&
        context.pc == 0x80212fa0 && context.lr == 0x80241d88 && (context.msr == 0x30 || context.msr == 0x2030) &&
        context.gpr[31] == 0x935e00e0 && context.gpr[4] == 1 && context.ctr == 1 &&
        !experimentInquiryInputInvalidates) {
        const std::array<uint32_t, 8> expected{8, 1, 6, 0x12, 0x135e2580, 32, 0x80492260, 32};
        for (unsigned index = 0; index < 8; ++index) {
            if (bat_memory_read32(context, 0x935e00e0 + index * 4) != expected[index]) {
                throw std::runtime_error("Inquiry LAB dcbi header unverified");
            }
        }
        ++experimentInquiryInputInvalidates;
        return;
    }
    experiment_di_burst_cache_operation(context, address, operation);
}
inline void experiment_inquiry_observe(CPUContext& context, unsigned kind) {
    if (stmSubmitted != 38 || !experimentInquiryReplyActive) { return; }
    std::cout << "INQUIRY_SOURCE " << kind << ' ' << std::hex << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.msr
        << ' ' << bat_memory_read32(context, 0x804983c8) << ' ' << bat_memory_read32(context, 0x804b2b4c)
        << ' ' << bat_memory_read32(context, 0x8049228c) << ' ' << bat_memory_read32(context, 0x804922a0)
        << ' ' << bat_memory_read16(context, 0x800030e6) << std::dec << std::endl;
    for (bool cached : {false, true}) {
        std::cout << (cached ? "INQUIRY_REPLY_CACHED" : "INQUIRY_REPLY_PHYSICAL") << ' ' << kind;
        for (unsigned index = 0; index < 64; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x935e00e0u : 0xd35e00e0u) + index));
        }
        std::cout << std::endl;
        std::cout << (cached ? "INQUIRY_DATA_CACHED" : "INQUIRY_DATA_PHYSICAL") << ' ' << kind;
        for (unsigned index = 0; index < 32; ++index) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, (cached ? 0x80492260u : 0xc0492260u) + index));
        }
        std::cout << std::endl;
    }
}
}
