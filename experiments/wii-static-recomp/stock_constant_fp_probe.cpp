#include "constant_fp_cases.h"
#include <cassert>
#include <iostream>
#include <memory>
#include <string>

using namespace nwii::runtime;

struct Outcome {
    int kind;
    std::string message;
};

static Outcome invoke(ProcessorContext& ctx, const GuardCase& item, bool specialized) {
    if (setjmp(ctx.exception_jmp_buf) != 0) {
        return {2, {}};
    }
    try {
        if (specialized) {
            item.call(ctx, 0x8020AFD4);
        } else {
            stock_fp_preinstruction(ctx, item.opcode, 0x8020AFD4);
        }
        return {0, {}};
    } catch (const std::runtime_error& error) {
        return {1, error.what()};
    }
}

int main() {
    auto a = std::make_unique<ProcessorContext>();
    auto b = std::make_unique<ProcessorContext>();
    unsigned count = 0, traps = 0, refusals = 0;
    for (const auto& item : cases) {
        assert(stock_uses_fp(item.opcode) == item.uses_fp);
        for (uint32_t msr : {0u, 0x32u, 0x2032u, 0x8032u, 0xA032u,
                0x41u, 0x10000u, 0x2033u, 0x4000u, 0x6032u}) {
            for (uint32_t hid2 : {0u, 0x20000000u, 0x80000000u, 0xA0000000u}) {
                for (auto* ctx : {a.get(), b.get()}) {
                    ctx->msr = msr;
                    ctx->hid2 = hid2;
                    ctx->pc = 0x8020AFD4;
                    ctx->srr0 = 0x11223344;
                    ctx->srr1 = 0x55667788;
                    ctx->lr = 0x807F0000;
                }
                const auto old = invoke(*a, item, false);
                const auto current = invoke(*b, item, true);
                assert(old.kind == current.kind && old.message == current.message);
                assert(a->pc == b->pc && a->msr == b->msr && a->hid2 == b->hid2);
                assert(a->srr0 == b->srr0 && a->srr1 == b->srr1 && a->lr == b->lr);
                assert(a->gpr == b->gpr && a->fpr == b->fpr && a->ps1 == b->ps1 && a->gqr == b->gqr);
                traps += old.kind == 2;
                refusals += old.kind == 1;
                ++count;
            }
        }
    }
    std::cout << "CONSTANT_FP_DIFFERENTIAL_PASS " << count << " traps=" << traps
        << " refusals=" << refusals << '\n';
}
