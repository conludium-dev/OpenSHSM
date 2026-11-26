#pragma once
#include "runtime/cpu_context.h"
#include "stock_psq_float.h"
#include <bit>
#include <cmath>
#include <stdexcept>

inline void shsm_psq_indexed(nwii::runtime::CPUContext& ctx, uint32_t word, uint32_t address) {
    uint32_t subop = (word >> 1) & 0x3F;
    if ((word >> 26) != 4 || (word & 1) ||
        (subop != 6 && subop != 7 && subop != 38 && subop != 39)) {
        throw std::runtime_error("Invalid indexed paired-quantized opcode");
    }
    uint32_t fr = (word >> 21) & 31;
    uint32_t ra = (word >> 16) & 31;
    uint32_t rb = (word >> 11) & 31;
    uint32_t w = (word >> 10) & 1;
    uint32_t i = (word >> 7) & 7;
    bool update = (subop & 32) != 0;
    bool store = (subop & 1) != 0;
    if (update && ra == 0) {
        throw std::runtime_error("Invalid update-form RA zero");
    }
    uint32_t ea = (ra == 0 ? 0 : ctx.gpr[ra]) + ctx.gpr[rb];
    uint32_t physical = ea & 0x3FFFFFFF;
    uint32_t bytes = w ? 4 : 8;
    bool ram = physical < ctx.mmu.mem1.size() && bytes <= ctx.mmu.mem1.size() - physical;
    if (physical >= 0x10000000 && physical - 0x10000000 < ctx.mmu.mem2.size()) {
        ram = bytes <= ctx.mmu.mem2.size() - (physical - 0x10000000);
    }
    uint32_t type = store ? ctx.gqr[i] & 7 : (ctx.gqr[i] >> 16) & 7;
    if (!ram || type != 0) {
        ctx.pc = address;
        throw std::runtime_error("Unverified indexed PSQ memory/quantization profile");
    }
    if (store) {
        ctx.mmu.write32(ea, shsm_psq_single_ftz(std::bit_cast<uint64_t>(ctx.fpr[fr])));
        if (!w) {
            ctx.mmu.write32(ea + 4, shsm_psq_single_ftz(std::bit_cast<uint64_t>(ctx.ps1[fr])));
        }
    } else {
        const uint64_t first = shsm_psq_double(ctx.mmu.read32(ea));
        const uint64_t second = w ? 0x3ff0000000000000ull : shsm_psq_double(ctx.mmu.read32(ea + 4));
        ctx.fpr[fr] = std::bit_cast<double>(first);
        ctx.ps1[fr] = std::bit_cast<double>(second);
    }
    if (update) {
        ctx.gpr[ra] = ea;
    }
}
