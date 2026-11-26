#include "processor_adapter.h"
#include <cassert>
#include <cstdio>
#include <memory>
#include <stdexcept>

namespace nwii::runtime {
bool interpret_one(CPUContext& ctx);
}

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.pc = 0x80007000;
    ctx.msr = 0;
    ctx.gpr[7] = 0xA1B2C3D4;
    ctx.gpr[28] = 0x80012000;
    ctx.gpr[8] = 0x40;
    ctx.mmu.write32(ctx.pc, 0x7CFC416E);
    ctx.mmu.write32(0x80012040, 0x11223344);
    assert(nwii::runtime::interpret_one(ctx));
    assert(ctx.mmu.read32(0x80012040) == 0xA1B2C3D4);
    assert(ctx.gpr[28] == 0x80012040);
    assert(ctx.gpr[7] == 0xA1B2C3D4 && ctx.gpr[8] == 0x40);
    assert(ctx.pc == 0x80007004);

    ctx.pc = 0x80007000;
    ctx.mmu.write32(ctx.pc, 0x7CFC416F);
    bool rejected = false;
    try {
        nwii::runtime::interpret_one(ctx);
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    assert(rejected);
    std::puts("WII_STWUX_FALLBACK_PASS");
}
