#include <processor_adapter.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>

extern "C" void func_80278450(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    if (argc != 2) {
        return 1;
    }
    std::ifstream input(argv[1]);
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned id = 0;
    uint32_t type, flag, previous, raw, extra, ext, old_ext, step, timer, next, delay, interval, ext_timer, ext_next;
    while (input >> type >> flag >> previous >> raw >> extra >> ext >> old_ext >> step
        >> timer >> next >> delay >> interval >> ext_timer >> ext_next) {
        constexpr uint32_t block = 0x80540000;
        for (unsigned i = 0; i < 0x600; ++i) {
            ctx.mmu.write8(block + i, 0);
        }
        ctx.mmu.write32(block, previous);
        ctx.mmu.write32(block + 0x60, old_ext);
        ctx.mmu.write8(block + 0x555, flag);
        for (unsigned i = 0; i < 6; ++i) {
            const uint32_t value = i == 0 ? timer : i == 1 ? next : i == 2 ? delay : i == 3 ? interval : i == 4 ? ext_timer : ext_next;
            ctx.mmu.write16(block + 0x500 + i * 2, value);
        }
        ctx.gpr[3] = block;
        ctx.gpr[4] = type;
        ctx.gpr[5] = step;
        ctx.gpr[6] = raw;
        ctx.gpr[7] = extra;
        ctx.gpr[8] = ext;
        ctx.pc = 0x80278450;
        ctx.lr = 0x8009BB80;
        const auto sp = ctx.gpr[1];
        func_80278450(ctx);
        if (ctx.pc != 0x8009BB80 || ctx.lr != 0x8009BB80 || ctx.gpr[1] != sp) {
            return 2;
        }
        std::cout << "BUTTONS " << id++ << ' ';
        for (unsigned i = 0; i < 0x600; ++i) {
            std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(block + i));
        }
        std::cout << std::dec << '\n';
    }
    return input.eof() && id > 0 ? 0 : 3;
}
