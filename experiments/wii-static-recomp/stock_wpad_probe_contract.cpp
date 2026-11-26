#include <processor_adapter.h>
#include <iostream>
#include <memory>

extern "C" void func_80280AC0(nwii::runtime::CPUContext&);

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    for (unsigned channel = 0; channel < 4; ++channel) {
        const uint32_t block = 0x80540000 + channel * 0x1000;
        ctx.mmu.write32(0x804F13F0 + channel * 4, block);
        for (uint32_t state : {0xFFFFFFFFu, 0u, 0xFFFFFFFEu, 7u}) {
            for (uint32_t type : {0u, 1u, 0xFDu}) {
                for (uint32_t ready : {0u, 1u}) {
                    for (unsigned output = 0; output < 2; ++output) {
                        ctx.mmu.write32(block + 0x8BC, state);
                        ctx.mmu.write8(block + 0x8C1, type);
                        ctx.mmu.write32(block + 0x8DC, ready);
                        ctx.mmu.write32(0x80560000, 0xCAFEBABE);
                        ctx.pc = 0x80280AC0;
                        ctx.lr = 0x8009BB80;
                        ctx.gpr[1] = 0x80570000;
                        ctx.gpr[3] = channel;
                        ctx.gpr[4] = output ? 0x80560000 : 0;
                        ctx.msr = 0;
                        func_80280AC0(ctx);
                        if (ctx.pc != 0x8009BB80 || ctx.gpr[1] != 0x80570000) {
                            return 1;
                        }
                        std::cout << "PROBE " << channel << ' ' << state << ' ' << type << ' ' << ready
                            << ' ' << output << ' ' << ctx.gpr[3] << ' ' << ctx.mmu.read32(0x80560000) << '\n';
                    }
                }
            }
        }
    }
    return 0;
}
