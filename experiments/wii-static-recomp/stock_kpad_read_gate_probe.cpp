#include <processor_adapter.h>
#include <iostream>
#include <memory>

extern "C" void func_8027AAC0(nwii::runtime::CPUContext&);

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned id = 0;
    for (unsigned gate = 0; gate < 3; ++gate) {
        for (unsigned channel = 0; channel < 4; ++channel) {
            for (unsigned error_out = 0; error_out < 2; ++error_out) {
                for (unsigned extended = 0; extended < 2; ++extended) {
                    for (unsigned count : {0u, 1u, 16u}) {
                        for (unsigned buffer = 0; buffer < 2; ++buffer) {
                            const uint32_t block = 0x804EFD58 + channel * 0x578;
                            ctx.mmu.write8(0x8052B06C, gate == 0 ? 0 : 1);
                            ctx.mmu.write8(0x804F52A8, gate == 1 ? 2 : 3);
                            ctx.mmu.write8(block + 0x4FF, gate == 2 ? 1 : 0);
                            ctx.mmu.write32(0x80560000, 0xCAFEBABE);
                            for (unsigned i = 0; i < 0xB20; ++i) {
                                ctx.mmu.write8(0x80550000 - 16 + i, 0xCD);
                            }
                            for (unsigned i = 20; i < 32; ++i) {
                                ctx.gpr[i] = 0x11000000 + i;
                            }
                            ctx.gpr[1] = 0x80700000;
                            ctx.gpr[13] = 0x8052E720;
                            ctx.gpr[3] = channel;
                            ctx.gpr[4] = buffer ? 0x80550000 : 0;
                            ctx.gpr[5] = count;
                            ctx.gpr[6] = error_out ? 0x80560000 : 0;
                            ctx.gpr[7] = extended;
                            ctx.msr = 0;
                            ctx.pc = 0x8027AAD0;
                            ctx.lr = 0x8009BB80;
                            func_8027AAC0(ctx);
                            if (ctx.pc != 0x8009BB80 || ctx.lr != 0x8009BB80 || ctx.gpr[1] != 0x80700000 || ctx.gpr[3] != 0) {
                                return 1;
                            }
                            for (unsigned i = 20; i < 32; ++i) {
                                if (ctx.gpr[i] != 0x11000000 + i) {
                                    return 2;
                                }
                            }
                            for (unsigned i = 0; i < 0xB20; ++i) {
                                if (ctx.mmu.read8(0x80550000 - 16 + i) != 0xCD) {
                                    return 3;
                                }
                            }
                            std::cout << "READ_GATE " << id++ << ' ' << ctx.gpr[3] << ' '
                                << ctx.mmu.read32(0x80560000) << ' ' << unsigned(ctx.mmu.read8(block + 0x4FF)) << '\n';
                        }
                    }
                }
            }
        }
    }
    return 0;
}
