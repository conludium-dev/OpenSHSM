#include "processor_adapter.h"
#include <array>
#include <cassert>
#include <iostream>
#include <stdexcept>

extern "C" void func_802107D0(nwii::runtime::CPUContext& ctx);
extern "C" void func_802107E0(nwii::runtime::CPUContext& ctx);

int main() {
    nwii::runtime::ProcessorContext ctx;
    const std::array<uint32_t, 8> values = {0, 0xFFFFFFFF, 0x0F000000, 0xA0000000,
        0xF0FF0000, 0xFFFF, 0x55555555, 0xAAAAAAAA};
    unsigned cases = 0;
    for (uint32_t prior : values) {
        for (uint32_t value : values) {
            const uint32_t expected = (value & 0xF0FF0000) | (prior & 0x0F000000);
            ctx.hid2 = prior;
            ctx.msr = 0;
            ctx.lr = 0x807F0000;
            ctx.pc = 0x802107E0;
            ctx.gpr[3] = value;
            func_802107E0(ctx);
            assert(ctx.hid2 == expected && ctx.pc == ctx.lr && ctx.gpr[3] == value);
            ctx.pc = 0x802107D0;
            func_802107D0(ctx);
            assert(ctx.gpr[3] == expected && ctx.pc == ctx.lr);
            ctx.hid2 = prior;
            ctx.gpr[3] = value;
            ctx.pc = 0x80008000;
            ctx.mmu.write32(ctx.pc, 0x7C78E3A6);
            assert(nwii::runtime::interpret_one(ctx));
            assert(ctx.hid2 == expected && ctx.pc == 0x80008004);
            ctx.mmu.write32(ctx.pc, 0x7C78E2A6);
            assert(nwii::runtime::interpret_one(ctx));
            assert(ctx.gpr[3] == expected && ctx.pc == 0x80008008);
            ++cases;
        }
    }
    ctx.msr = 0x4000;
    const uint32_t prior = ctx.hid2;
    bool refused = false;
    try {
        nwii::runtime::experiment_write_hid2(ctx, 0xFFFFFFFF);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    assert(refused && ctx.hid2 == prior);
    std::cout << "PASS " << cases << " static/interpreter HID2 policy cases; user-mode refusal; no boot acceptance\n";
}
