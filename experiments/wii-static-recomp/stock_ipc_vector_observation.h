#pragma once
#include <processor_adapter.h>
#include <iostream>
#include <sstream>

namespace openshsm::experiment {

inline bool ipc_observed_span(uint32_t address, uint32_t length) {
    const uint64_t start = address, end = start + length;
    return (start >= 0x80004000 && end <= 0x81800000)
        || (start >= 0x90000000 && end <= 0x94000000);
}

inline void observe_ipc_vector(nwii::runtime::CPUContext& ctx) {
    static unsigned ordinary = 0, abnormal = 0;
    const bool valid = ipc_observed_span(ctx.gpr[3], ctx.gpr[4]);
    if ((valid && ordinary++ >= 128) || (!valid && abnormal++ >= 16)) {
        return;
    }
    std::ostringstream out;
    out << "[IPC vector snapshot] valid=" << valid << std::hex << " pc=" << ctx.pc
        << " lr=" << ctx.lr << " msr=" << ctx.msr << " request=" << ctx.gpr[31]
        << " index=" << ctx.gpr[28] << " offset=" << ctx.gpr[29]
        << " address=" << ctx.gpr[3] << " length=" << ctx.gpr[4] << " header=";
    if (ipc_observed_span(ctx.gpr[31], 32)) {
        for (unsigned i = 0; i < 8; ++i) {
            out << ' ' << ctx.mmu.read32(ctx.gpr[31] + i * 4);
        }
        const uint32_t vectors = ctx.mmu.read32(ctx.gpr[31] + 24);
        out << " vectors=";
        if (ipc_observed_span(vectors, 32)) {
            for (unsigned i = 0; i < 8; ++i) {
                out << ' ' << ctx.mmu.read32(vectors + i * 4);
            }
        }
    }
    std::cout << out.str() << '\n';
}

}
