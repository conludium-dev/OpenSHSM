#pragma once
#include "timebase_adapter.h"

namespace nwii::runtime {
struct PerformanceContext : ClockContext {
    std::array<uint32_t, 6> performanceRegisters{};
};

inline void experiment_reset_performance(CPUContext& context, unsigned index, uint32_t value) {
    if (index >= 6 || value != 0 || (context.msr & 0xC000)) {
        throw std::runtime_error("Performance counting/interrupt/privilege contract unavailable");
    }
    static_cast<PerformanceContext&>(context).performanceRegisters[index] = 0;
}
}
