#pragma once
#include "dc_zero_frontend.h"
namespace nwii::runtime {
inline bool experimentFiniteMem2 = false;
inline CPUContext* experimentFiniteMem2Owner = nullptr;
inline uint32_t experimentFiniteMem2Steps = 0;
inline bool experimentFiniteMem2Returned = false;
inline constexpr uint32_t experimentFiniteMem2Start = 0x90000800;
inline constexpr uint32_t experimentFiniteMem2End = 0x935e0000;
inline constexpr uint32_t experimentFiniteMem2Count = (experimentFiniteMem2End - experimentFiniteMem2Start) / 32;

inline void experiment_finite_mem2_validate(CPUContext& context, uint32_t completed) {
    if (context.msr != 0x2032 || context.pc != 0x80213084 || context.lr != 0x80210ec8 ||
        memory_context(context).hid0 != 0xc200 || !experimentDcZero || experimentFiniteMem2Returned ||
        (experimentFiniteMem2Owner && experimentFiniteMem2Owner != &context) ||
        completed > experimentFiniteMem2Count || context.ctr != experimentFiniteMem2Count - completed ||
        context.gpr[3] != experimentFiniteMem2Start + completed * 32 ||
        context.gpr[4] != experimentFiniteMem2Count || context.gpr[5] != 0) {
        throw std::runtime_error("Finite MEM2 clear progress/profile unverified");
    }
}

inline bool experiment_finite_mem2_poll(CPUContext& context, bool (*poll)(CPUContext&)) {
    if (!experimentFiniteMem2 || context.lr != 0x80210ec8) {
        return poll(context);
    }
    const uint32_t completed = experimentFiniteMem2Steps + 1;
    experiment_finite_mem2_validate(context, completed);
    if (completed >= experimentFiniteMem2Count) {
        throw std::runtime_error("Finite MEM2 clear extra backedge forbidden");
    }
    const uint64_t before = bootPollChecks;
    const bool dispatched = poll(context);
    if (dispatched || bootPollChecks != before + 1) {
        throw std::runtime_error("Finite MEM2 clear unexpected scheduler transition");
    }
    bootPollChecks = before;
    experimentFiniteMem2Owner = &context;
    experimentFiniteMem2Steps = completed;
    return false;
}

inline void experiment_finite_mem2_return(CPUContext& context) {
    if (!experimentFiniteMem2 || context.lr != 0x80210ec8) {
        return;
    }
    if (experimentFiniteMem2Steps + 1 != experimentFiniteMem2Count) {
        throw std::runtime_error("Finite MEM2 clear early return forbidden");
    }
    experiment_finite_mem2_validate(context, experimentFiniteMem2Count);
    experimentFiniteMem2Steps = experimentFiniteMem2Count;
    experimentFiniteMem2Returned = true;
}
}
