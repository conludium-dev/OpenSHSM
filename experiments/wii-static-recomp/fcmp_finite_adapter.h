#pragma once
#include "fcmp_ordered_adapter.h"

namespace nwii::runtime {
inline void experiment_fcmp_finite(CPUContext& context, uint32_t opcode) {
    for (unsigned reg : {0u, 1u}) {
        if ((std::bit_cast<uint64_t>(context.fpr[reg]) & 0x7fffffffffffffffull) > 0x7ff0000000000000ull) {
            throw std::runtime_error("Ordered NaN comparison exception semantics not verified");
        }
    }
    experiment_fcmp_ordered(context, opcode);
}
}
