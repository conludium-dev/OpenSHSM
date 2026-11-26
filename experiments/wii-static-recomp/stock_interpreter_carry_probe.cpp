#include <processor_adapter.h>
#include <iostream>
#include <memory>

namespace nwii::runtime {
bool interpret_one(CPUContext& ctx);
}

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    uint32_t address, opcode, a, b, xer;
    while (std::cin >> address >> opcode >> a >> b >> xer) {
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x12340000u + i * 256u;
        }
        ctx.gpr[(opcode >> 16) & 31] = a;
        if (((opcode >> 1) & 1023) != 202) {
            ctx.gpr[(opcode >> 11) & 31] = b;
        }
        ctx.xer = xer;
        ctx.msr = 0;
        ctx.pc = address;
        ctx.mmu.write32(address, opcode);
        nwii::runtime::interpret_one(ctx);
        std::cout << "CARRY " << ctx.gpr[(opcode >> 21) & 31] << ' '
                  << ctx.xer << ' ' << ctx.pc << '\n';
    }
    return 0;
}
