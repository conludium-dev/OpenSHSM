#include <processor_adapter.h>
#include <iostream>
#include <memory>

extern "C" void func_8022CD40(nwii::runtime::CPUContext&);

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    for (uint32_t target : {0x8046E3C8u, 0x80540000u}) {
        for (uint32_t thread : {0u, target, 0x8046D4D0u}) {
            for (uint32_t owner : {0u, target}) {
                ctx.mmu.write32(0x800000D4, 0x80541000);
                ctx.mmu.write32(0x800000E4, thread);
                ctx.mmu.write32(0x800000D8, owner);
                ctx.mmu.write32(target + 0x19C, 0xB032);
                ctx.mmu.write32(0x80550000 + 740, 0xFFFFFFFC);
                ctx.mmu.write32(0x80550000 + 732, 0xAABBCCDD);
                ctx.pc = 0x8022CDCC;
                ctx.gpr[1] = 0x80550000;
                ctx.gpr[31] = target;
                ctx.msr = 0;
                func_8022CD40(ctx);
                if (ctx.mmu.read32(0x800000D4) != target || ctx.mmu.read32(0x800000E4) != thread
                    || ctx.pc != 0xFFFFFFFC || ctx.gpr[1] != 0x805502E0 || ctx.gpr[31] != 0xAABBCCDD) {
                    return 1;
                }
                std::cout << "TAIL " << target << ' ' << thread << ' ' << owner << ' '
                    << ctx.mmu.read32(0x800000D4) << ' ' << ctx.mmu.read32(0x800000E4)
                    << ' ' << ctx.pc << ' ' << ctx.gpr[1] << ' ' << ctx.lr << ' ' << ctx.gpr[31] << '\n';
            }
        }
    }
    return 0;
}
