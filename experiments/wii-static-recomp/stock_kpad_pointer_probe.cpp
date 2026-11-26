#include <processor_adapter.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>

extern "C" void func_80279440(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    if (argc != 2) {
        return 1;
    }
    std::ifstream input(argv[1], std::ios::binary);
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned id = 0;
    unsigned char constants[8];
    if (!input.read(reinterpret_cast<char*>(constants), 8)) {
        return 2;
    }
    for (unsigned i = 0; i < 8; ++i) {
        ctx.mmu.write8(0x8052EDB0 + i, constants[i]);
        ctx.mmu.write8(0x8052B070 + i, 0);
    }
    unsigned char header[2], block_data[0x600];
    while (input.read(reinterpret_cast<char*>(header), 2)) {
        if (!input.read(reinterpret_cast<char*>(block_data), sizeof(block_data))) {
            return 3;
        }
        constexpr uint32_t block = 0x80540000;
        for (unsigned i = 0; i < sizeof(block_data); ++i) {
            ctx.mmu.write8(block + i, block_data[i]);
        }
        for (unsigned i = 0; i < 16; ++i) {
            ctx.mmu.write8(block - 16 + i, 0xCD);
            ctx.mmu.write8(block + sizeof(block_data) + i, 0xCD);
        }
        ctx.gpr[1] = header[0] == 0 ? 0x80700020 : 0x80700000;
        ctx.gpr[2] = 0x805335E0;
        ctx.gpr[13] = 0x8052E720;
        ctx.gpr[3] = block;
        ctx.gpr[4] = 0;
        ctx.gpr[30] = block;
        ctx.gpr[31] = header[1];
        ctx.mmu.write32(0x80700018, 0x12345678);
        ctx.mmu.write32(0x8070001C, 0x23456789);
        ctx.mmu.write32(0x80700024, 0x8009BB80);
        ctx.lr = 0x8009BB80;
        ctx.msr = 0x2000;
        ctx.pc = header[0] == 0 ? 0x80279440 : 0x802797BC;
        func_80279440(ctx);
        if (ctx.pc != 0x8009BB80 || ctx.lr != 0x8009BB80 || ctx.gpr[1] != 0x80700020) {
            return 4;
        }
        std::cout << "POINTER " << id++ << ' ';
        for (unsigned i = 0; i < sizeof(block_data); ++i) {
            std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(block + i));
        }
        std::cout << std::dec << '\n';
        for (unsigned i = 0; i < 16; ++i) {
            if (ctx.mmu.read8(block - 16 + i) != 0xCD || ctx.mmu.read8(block + sizeof(block_data) + i) != 0xCD) {
                return 5;
            }
        }
    }
    return input.eof() && id > 0 ? 0 : 6;
}
