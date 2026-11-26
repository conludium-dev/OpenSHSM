#pragma once
#include "fpu_first_use.h"
#include <atomic>

namespace nwii::runtime {
inline bool experiment_flush_syscall_enter(CPUContext& context, uint32_t instruction) {
    auto& state = bat_context(context);
    if (!state.flushSyscall || state.flushPhase || state.exceptionVector || context.msr != 0x2032 ||
        instruction != 0x80212ff8 || state.hid0 != 0xc200) {
        throw std::runtime_error("Flush syscall CPU/site/profile unverified");
    }
    const auto found = std::find_if(state.instructionImages.begin(), state.instructionImages.end(),
        [](const auto& image) { return image.first <= 0x8021a120 && uint64_t(image.first) + image.second.size() >= 0x8021a13c; });
    if (found == state.instructionImages.end()) {
        throw std::runtime_error("Flush vector original image missing");
    }
    for (unsigned index = 0; index < 7; ++index) {
        const auto offset = 0x8021a120 - found->first + index * 4;
        uint32_t expected = 0;
        for (unsigned byte = 0; byte < 4; ++byte) { expected = (expected << 8) | found->second[offset + byte]; }
        if (bat_memory_read32(context, 0x80000c00 + index * 4) != expected) {
            throw std::runtime_error("Flush syscall vector mismatch");
        }
    }
    context.srr0 = instruction + 4;
    context.srr1 = context.msr;
    context.msr &= ~0x8032u;
    state.exceptionVector = 9;
    state.flushPhase = 1;
    ++state.flushEntries;
    context.pc = 0x8021a120;
    return true;
}

inline void experiment_flush_hid0_write(CPUContext& context, uint32_t value, uint32_t instruction) {
    auto& state = bat_context(context);
    if (!state.flushSyscall || state.exceptionVector != 9 || context.pc != 0x8021a120 || context.msr != 0x2000) {
        throw std::runtime_error("Flush HID0 vector/profile unverified");
    }
    if (instruction == 0x8021a128 && state.flushPhase == 1 && state.hid0 == 0xc200 && value == 0xc208) {
        state.hid0 = value;
        state.flushPhase = 2;
    } else if (instruction == 0x8021a134 && state.flushPhase == 3 && state.hid0 == 0xc208 && value == 0xc200) {
        state.hid0 = value;
        state.flushPhase = 4;
    } else {
        throw std::runtime_error("Flush HID0 transition unverified");
    }
}

inline void experiment_flush_sync(CPUContext& context) {
    auto& state = bat_context(context);
    if (!state.flushSyscall || state.exceptionVector != 9 || context.pc != 0x8021a120 || context.msr != 0x2000 ||
        state.flushPhase != 2 || state.hid0 != 0xc208) {
        throw std::runtime_error("Flush sync transition unverified");
    }
    std::atomic_thread_fence(std::memory_order_seq_cst);
    ++state.flushBarriers;
    state.flushPhase = 3;
}

inline void experiment_flush_return_guard(CPUContext& context) {
    auto& state = bat_context(context);
    if (!state.flushSyscall || state.exceptionVector != 9 || context.msr != 0x2000 || state.flushPhase != 4 ||
        state.hid0 != 0xc200 || context.srr0 != 0x80212ffc || context.srr1 != 0x2032) {
        throw std::runtime_error("Flush syscall return unverified");
    }
    state.flushPhase = 0;
    state.exceptionVector = 0;
}
}
