#pragma once
#include "fp64_transfer.h"
#include "si_external_delivery.h"

namespace nwii::runtime {
inline bool experiment_fpu_first_use_transfer(CPUContext& context, uint32_t opcode, uint32_t instruction) {
    auto& state = bat_context(context);
    if (context.msr & 0x2000) {
        if (state.exceptionVector == 7) {
            if (instruction != state.fpuResume || context.pc != instruction || context.msr != 0x2032) {
                throw std::runtime_error("FPU first-use return unverified");
            }
            state.exceptionVector = 0;
        }
        experiment_fp64_transfer(context, opcode);
        return false;
    }
    if (!state.fpuFirstUse || state.exceptionVector || instruction != 0x800060f4 || opcode != 0xc824fff8 || context.msr != 0x32) {
        throw std::runtime_error("FPU first-use CPU/instruction profile unverified");
    }
    const uint32_t current = bat_memory_read32(context, 0x800000d4);
    if ((current != 0x80501000 && current != 0x80492658) ||
        bat_memory_read32(context, 0x800000c0) != (current & 0x3fffffffu) ||
        bat_memory_read32(context, 0x800000d8) != 0 || bat_memory_read32(context, 0x8000301c) != 0x80213dc0 ||
        bat_memory_read16(context, current + 0x1a2) != 0) {
        throw std::runtime_error("FPU first-use owner/context unverified");
    }
    bat_memory_range(context, current, 0x1c8);
    const auto found = std::find_if(memory_context(context).instructionImages.begin(), memory_context(context).instructionImages.end(),
        [](const auto& image) { return image.first <= 0x80211ba0 && uint64_t(image.first) + image.second.size() >= 0x80211c38; });
    if (found == memory_context(context).instructionImages.end()) {
        throw std::runtime_error("FPU vector original image missing");
    }
    for (unsigned index = 0; index < 38; ++index) {
        const auto offset = 0x80211ba0 - found->first + index * 4;
        uint32_t expected = 0;
        for (unsigned byte = 0; byte < 4; ++byte) {
            expected = (expected << 8) | found->second[offset + byte];
        }
        if (index == 26) {
            if (expected != 0x38600000) {
                throw std::runtime_error("FPU original vector ID unverified");
            }
            expected = 0x38600007;
        }
        if (bat_memory_read32(context, 0x80000800 + index * 4) != expected) {
            throw std::runtime_error("FPU relocated vector mismatch");
        }
    }
    context.srr0 = instruction;
    context.srr1 = context.msr;
    context.msr &= ~0x8032u;
    state.exceptionVector = 7;
    state.fpuResume = instruction;
    ++state.fpuEntries;
    context.pc = 0x80211ba0;
    return true;
}
}
