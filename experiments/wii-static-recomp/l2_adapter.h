#pragma once
#include "dcache_adapter.h"

namespace nwii::runtime {
struct L2Context : MemoryContext {
    uint32_t l2cr = 0;
};

inline uint32_t experiment_read_l2cr(CPUContext& context) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged L2CR exception delivery unavailable");
    }
    return static_cast<L2Context&>(context).l2cr;
}

inline void experiment_write_l2cr(CPUContext& context, uint32_t value) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged L2CR exception delivery unavailable");
    }
    static_cast<L2Context&>(context).l2cr = value;
}
}
