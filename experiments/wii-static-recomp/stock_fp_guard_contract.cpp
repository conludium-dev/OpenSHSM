#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include <processor_adapter.h>
#include "stock_fp_unavailable.h"
#include "fp-classification.h"
#include <memory>

namespace nwii::runtime {
uint32_t experiment_read_hid2(CPUContext& ctx) { return static_cast<ProcessorContext&>(ctx).hid2; }
}

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned classified = 0, faults = 0;
    for (uint32_t primary = 0; primary < 64; ++primary) {
        for (uint32_t xo = 0; xo < 1024; ++xo) {
            for (uint32_t rc = 0; rc < 2; ++rc) {
                const uint32_t opcode = (primary << 26) | (xo << 1) | rc;
                const bool expected = fp_expected[primary * 1024 + xo];
                if (nwii::runtime::stock_uses_fp(opcode) != expected) {
                    return 2;
                }
                ++classified;
                if (!expected || rc) {
                    continue;
                }
                ctx.msr = 0x9032; ctx.hid2 = 0xA0000000;
                ctx.pc = 0x8020AFD4; ctx.fpr[0] = 123.25; ctx.gpr[0] = 0xBADF00D;
                if (setjmp(ctx.exception_jmp_buf) == 0) {
                    nwii::runtime::stock_fp_preinstruction(ctx, opcode, 0x8020AFD4);
                    return 3;
                }
                if (ctx.pc != 0x800 || ctx.srr0 != 0x8020AFD4 || ctx.srr1 != 0x9032
                    || ctx.msr != (0x9032u & ~0x4EF36u) || ctx.gpr[0] != 0xBADF00D || ctx.fpr[0] != 123.25) {
                    return 4;
                }
                ++faults;
                ctx.msr = 0xB032; ctx.pc = 0x8020AFD4;
                nwii::runtime::stock_fp_preinstruction(ctx, opcode, 0x8020AFD4);
                if (ctx.msr != 0xB032 || ctx.pc != 0x8020AFD4) {
                    return 5;
                }
            }
        }
    }
    unsigned refused = 0;
    for (uint32_t opcode : {0x10000000u, 0xE0000000u, 0xF0000000u}) {
        ctx.msr = 0x9032; ctx.hid2 = 0; ctx.pc = 0x1234; ctx.srr0 = 0x5678;
        try {
            nwii::runtime::stock_fp_preinstruction(ctx, opcode, 0x1234);
        } catch (const std::runtime_error&) {
            if (ctx.msr != 0x9032 || ctx.pc != 0x1234 || ctx.srr0 != 0x5678) {
                return 6;
            }
            ++refused;
        }
    }
    if (refused != 3) {
        return 7;
    }
    std::printf("PASS %u classification cases; %u nonlocal FP faults and enabled no-ops; 3 invalid paired profiles refused\n", classified, faults);
}
