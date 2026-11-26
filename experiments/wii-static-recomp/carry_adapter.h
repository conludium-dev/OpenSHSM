#pragma once
#include "l2_adapter.h"

namespace nwii::runtime {
inline void experiment_subfic(CPUContext& context, unsigned destination, unsigned source, int32_t immediate) {
    const uint32_t left = context.gpr[source];
    const uint32_t right = static_cast<uint32_t>(immediate);
    const uint64_t sum = uint64_t(~left) + uint64_t(right) + 1;
    context.gpr[destination] = static_cast<uint32_t>(sum);
    context.xer = (context.xer & ~0x20000000u) | (static_cast<uint32_t>((sum >> 32) & 1) << 29);
}

inline void experiment_addic(CPUContext& context, unsigned destination, unsigned source, int32_t immediate, bool record) {
    const uint64_t sum = uint64_t(context.gpr[source]) + uint64_t(static_cast<uint32_t>(immediate));
    const uint32_t result = static_cast<uint32_t>(sum);
    context.gpr[destination] = result;
    context.xer = (context.xer & ~0x20000000u) | (static_cast<uint32_t>((sum >> 32) & 1) << 29);
    if (record) {
        context.cr[0].lt = static_cast<int32_t>(result) < 0;
        context.cr[0].gt = static_cast<int32_t>(result) > 0;
        context.cr[0].eq = result == 0;
        context.cr[0].so = (context.xer >> 31) & 1;
    }
}
}
