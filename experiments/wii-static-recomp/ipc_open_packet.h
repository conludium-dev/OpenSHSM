#pragma once
#include "runtime/ios_kernel.h"
#include <stdexcept>

namespace nwii::runtime {
inline uint8_t* experiment_ipc_mem1_span(CPUContext& context, uint32_t physical, unsigned length) {
    if (!length || physical < 0x00400000u || physical >= 0x01800000u || length > 0x01800000u - physical) {
        throw std::runtime_error("IPC packet outside bounded physical MEM1 data profile");
    }
    auto first = context.mmu.get_ptr(physical);
    auto last = context.mmu.get_ptr(physical + length - 1);
    if (!first || last != first + length - 1) {
        throw std::runtime_error("IPC packet backing unavailable");
    }
    return first;
}

inline uint32_t experiment_ipc_be32(const uint8_t* bytes) {
    return (uint32_t(bytes[0]) << 24) | (uint32_t(bytes[1]) << 16) | (uint32_t(bytes[2]) << 8) | bytes[3];
}

inline void experiment_ipc_store_be32(uint8_t* bytes, uint32_t value) {
    for (unsigned index = 0; index < 4; ++index) {
        bytes[index] = value >> (24 - index * 8);
    }
}

inline int32_t experiment_ipc_open_packet(CPUContext& context, uint32_t physical) {
    if (physical & 31) {
        throw std::runtime_error("IPC packet alignment outside verified profile");
    }
    auto packet = experiment_ipc_mem1_span(context, physical, 64);
    const auto command = experiment_ipc_be32(packet);
    const auto mode = experiment_ipc_be32(packet + 16);
    if (command != 1 || mode != 1) {
        throw std::runtime_error("IPC command/mode outside verified read-only OPEN profile");
    }
    const auto pathAddress = experiment_ipc_be32(packet + 12);
    std::string path;
    bool terminated = false;
    for (unsigned index = 0; index < 64; ++index) {
        const auto byte = *experiment_ipc_mem1_span(context, pathAddress + index, 1);
        if (!byte) {
            terminated = true;
            break;
        }
        if (byte < 32 || byte >= 127) {
            throw std::runtime_error("IPC path outside verified ASCII profile");
        }
        path.push_back(char(byte));
    }
    if (!terminated || path.rfind("/dev/", 0) != 0) {
        throw std::runtime_error("IPC path termination/device namespace unavailable");
    }
    const auto result = IOSKernel::get().open(context, path, mode);
    if (result == IPC_NO_REPLY) {
        throw std::runtime_error("Deferred OPEN completion requires verified request lifecycle");
    }
    experiment_ipc_store_be32(packet, 8);
    experiment_ipc_store_be32(packet + 4, uint32_t(result));
    experiment_ipc_store_be32(packet + 8, command);
    return result;
}
}
