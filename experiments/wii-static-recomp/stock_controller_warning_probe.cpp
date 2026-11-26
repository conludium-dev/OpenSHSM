#include <processor_adapter.h>
#include <fstream>
#include <iostream>
#include <memory>

extern "C" void func_80009F60(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    if (argc != 2) {
        return 1;
    }
    std::ifstream input(argv[1]);
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned initialized, paused, connected, count, error, type, mask, id = 0;
    while (input >> initialized >> paused >> connected >> count >> error >> type >> mask) {
        ctx.mmu.write8(0x80529148, initialized);
        ctx.mmu.write8(0x8052A440, paused);
        ctx.mmu.write8(0x804579C0, connected);
        ctx.mmu.write32(0x804579C0 + 0xB0C, count);
        ctx.mmu.write8(0x804579C0 + 0x65, error);
        ctx.mmu.write8(0x804579C0 + 0x64, type);
        ctx.mmu.write32(0x8052A83C, mask);
        ctx.mmu.write32(0x80529D20, 0x80560000);
        ctx.mmu.write32(0x80561FEC, 0xCAFEBABE);
        ctx.gpr[1] = 0x80700000;
        ctx.gpr[13] = 0x8052E720;
        ctx.gpr[31] = 0x12345678;
        ctx.pc = 0x80009F60;
        ctx.lr = 0x8009BB80;
        ctx.msr = 0;
        func_80009F60(ctx);
        if (ctx.pc != 0x8009BB80 || ctx.lr != 0x8009BB80 || ctx.gpr[1] != 0x80700000 || ctx.gpr[31] != 0x12345678) {
            return 2;
        }
        std::cout << "WARNING " << id++ << ' ' << ctx.mmu.read32(0x8052A83C) << ' ' << ctx.mmu.read32(0x80561FEC) << '\n';
    }
    return input.eof() && id > 0 ? 0 : 3;
}
