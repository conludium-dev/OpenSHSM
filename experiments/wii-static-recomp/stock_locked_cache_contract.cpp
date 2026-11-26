#include "processor_adapter.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <stdexcept>

extern "C" void func_80213240(nwii::runtime::CPUContext& ctx);

int main() {
    nwii::runtime::ProcessorContext ctx;
    ctx.hid2 = 0x10000000;
    unsigned cases = 0;
    for (uint32_t memory : {0x80010000u, 0x90010000u}) {
        for (unsigned blocks : {1u, 2u, 3u, 128u}) {
            for (bool load : {false, true}) {
                const unsigned length = blocks * 32;
                for (unsigned i = 0; i < length; ++i) {
                    ctx.mmu.write8(memory + i, load ? uint8_t(i * 13 + 7) : 0xA5);
                    ctx.mmu.write8(0xE0000020 + i, load ? 0xA5 : uint8_t(i * 13 + 7));
                }
                ctx.pc = 0x80213240;
                ctx.lr = 0x807F0000;
                ctx.gpr[3] = memory;
                ctx.gpr[4] = 0xE0000020 | (load ? 0x10 : 0);
                ctx.gpr[5] = blocks == 128 ? 0 : blocks;
                func_80213240(ctx);
                assert(ctx.pc == ctx.lr && !(ctx.dma_l & 2));
                for (unsigned i = 0; i < length; ++i) {
                    assert(ctx.mmu.read8((load ? 0xE0000020 : memory) + i) == uint8_t(i * 13 + 7));
                }
                ++cases;
            }
        }
    }
    ctx.mmu.write64(0xE0000100, 0x0123456789ABCDEF);
    assert(ctx.mmu.read64(0xE0000100) == 0x0123456789ABCDEF);
    assert(ctx.mmu.get_ptr(0xE0040000) == nullptr);
    const uint32_t old_low = ctx.dma_l;
    ctx.dma_u = 0x0C000000;
    bool refused = false;
    try {
        nwii::runtime::experiment_write_dma(ctx, 923, 0xE0000002);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    assert(refused && ctx.dma_l == old_low);
    ctx.msr = 0x4000;
    refused = false;
    try {
        nwii::runtime::experiment_write_dma(ctx, 922, 0);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    assert(refused && ctx.dma_u == 0x0C000000);
    std::cout << "PASS " << cases << " original DMA-command MEM1/MEM2 load/store cases; cache endian/range/refusal; no THP acceptance\n";
}
