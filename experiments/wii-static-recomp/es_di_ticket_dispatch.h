#pragma once
#include "es_di_ticket_adapter.h"

namespace nwii::runtime {
inline uint32_t experimentEsTicketCaller = 0;
inline void experiment_es_ticket_observe(CPUContext& context, unsigned kind) {
    if ((kind == 1 && stmSubmitted == 36) || (kind == 2 && stmSubmitted == 38)) {
        if (kind == 1) {
            experimentEsTicketCaller = context.gpr[4];
        }
        std::cout << "ES_TICKET_SOURCE " << kind << ' ' << std::hex << context.gpr[3] << ' ' << context.gpr[4]
            << ' ' << context.msr << ' ' << experimentEsTicketCaller << ' ' << bat_memory_read32(context, 0x804b2b4c)
            << std::dec << std::endl;
        if (kind == 2 && experimentEsTicketCaller >= 0x80400000 && experimentEsTicketCaller <= 0x80550000 - 216) {
            std::cout << "ES_TICKET_CALLER_CACHED";
            for (unsigned index = 0; index < 216; ++index) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, experimentEsTicketCaller + index));
            }
            std::cout << std::endl;
        }
    }
}

inline void experiment_es_ticket_validate(CPUContext& context, uint32_t physical) {
    if (physical != 0x135e0080 || !devices::experiment_stm_pending() || !experimentDiBurstFirstRetired ||
        bat_memory_read32(context, 0x80528ce8) != 4 || bat_memory_read32(context, 0x804983c8) != 0x01000000) {
        throw std::runtime_error("Ticket request/FD/inquiry/STM ownership unverified");
    }
    const auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    const std::array<uint32_t, 8> expected{7, 1, 4, 0x1b, 1, 1, 0x53ff10, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
            throw std::runtime_error("Ticket physical request header unverified");
        }
    }
    for (unsigned index = 32; index < 64; ++index) {
        if (packet[index]) {
            throw std::runtime_error("Ticket physical request tail unverified");
        }
    }
    const auto* vectors = experiment_ipc_mem1_span(context, 0x53ff10, 16);
    const std::array<uint32_t, 4> expectedVectors{0, 0, 0x53ff80, 216};
    for (unsigned index = 0; index < 4; ++index) {
        if (experiment_ipc_be32(vectors + index * 4) != expectedVectors[index]) {
            throw std::runtime_error("Ticket physical vectors unverified");
        }
    }
}

inline void experiment_es_ticket_dispatch(CPUContext& context, uint32_t physical) {
    experiment_es_ticket_validate(context, physical);
    auto* packet = experiment_ipc_mem1_span(context, physical, 64);
    IpcRequest request{};
    request.cmd = experiment_ipc_be32(packet);
    request.fd = experiment_ipc_be32(packet + 8);
    request.req_addr = physical;
    request.ioctl_cmd = experiment_ipc_be32(packet + 12);
    request.arg_cnt_in = experiment_ipc_be32(packet + 16);
    request.arg_cnt_out = experiment_ipc_be32(packet + 20);
    const auto* vectors = experiment_ipc_mem1_span(context, experiment_ipc_be32(packet + 24), 16);
    for (unsigned index = 0; index < 2; ++index) {
        request.ioctlv_vecs.push_back({experiment_ipc_be32(vectors + index * 8), experiment_ipc_be32(vectors + index * 8 + 4)});
    }
    const auto result = IOSKernel::get().ioctlv(context, request);
    if (result != IPC_OK) {
        throw std::runtime_error("Ticket service result outside original response");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, request.cmd);
}
}
