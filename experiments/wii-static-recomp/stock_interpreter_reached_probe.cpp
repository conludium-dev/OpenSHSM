#include <processor_adapter.h>
#include <iostream>
#include <memory>

namespace nwii::runtime {
bool interpret_one(CPUContext& ctx);
}

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    uint32_t word, a, b, xer, value;
    while (std::cin >> word >> a >> b >> xer >> value) {
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x12340000u + i * 256u;
        }
        const unsigned ra = (word >> 16) & 31;
        const unsigned rb = (word >> 11) & 31;
        ctx.gpr[ra] = a;
        ctx.gpr[rb] = b;
        ctx.xer = xer;
        for (auto& cr : ctx.cr) {
            cr.lt = true;
            cr.gt = false;
            cr.eq = true;
            cr.so = false;
        }
        ctx.pc = 0x80007000;
        ctx.msr = 0;
        ctx.inst_count = 91;
        ctx.mmu.write32(ctx.pc, word);
        if (((word >> 1) & 1023) == 55) {
            ctx.mmu.write32(ctx.gpr[ra] + ctx.gpr[rb], value);
        }
        nwii::runtime::interpret_one(ctx);
        uint32_t packed_cr = 0;
        for (const auto& cr : ctx.cr) {
            packed_cr = (packed_cr << 4) | (cr.lt ? 8u : 0u) | (cr.gt ? 4u : 0u) |
                (cr.eq ? 2u : 0u) | (cr.so ? 1u : 0u);
        }
        std::cout << "RESULT " << ctx.pc << ' ' << ctx.xer << ' ' << packed_cr << ' ' << ctx.inst_count;
        for (uint32_t reg : ctx.gpr) {
            std::cout << ' ' << reg;
        }
        std::cout << '\n';
    }
}
