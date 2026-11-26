#include <processor_adapter.h>
#include <iostream>
#include <memory>

extern "C" void func_80212FA0(nwii::runtime::CPUContext&);

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    auto run = [&](uint32_t entry, uint32_t address, uint32_t size, uint32_t counter) {
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x12340000 + i * 256;
        }
        ctx.gpr[3] = address;
        ctx.gpr[4] = size;
        ctx.gpr[5] = 0xCAFEBABE;
        const auto registers = ctx.gpr;
        for (auto& field : ctx.cr) {
            field.lt = true;
            field.gt = false;
            field.eq = true;
            field.so = false;
        }
        ctx.pc = entry;
        ctx.lr = 0x8009BB9C;
        ctx.ctr = counter;
        ctx.inst_count = 1;
        ctx.msr = 0x1032;
        ctx.in_callback = true;
        func_80212FA0(ctx);
        if (ctx.pc != 0x8009BB9C || ctx.lr != 0x8009BB9C || ctx.msr != 0x1032 || !ctx.in_callback) {
            return false;
        }
        for (unsigned i = 0; i < 32; ++i) {
            if ((i < 3 || i > 5) && ctx.gpr[i] != registers[i]) {
                return false;
            }
        }
        uint32_t cr = 0;
        for (const auto& field : ctx.cr) {
            cr = (cr << 4) | (uint32_t(field.lt) << 3) | (uint32_t(field.gt) << 2)
                | (uint32_t(field.eq) << 1) | uint32_t(field.so);
        }
        std::cout << "CACHE " << entry << ' ' << address << ' ' << size << ' ' << counter
            << ' ' << ctx.gpr[3] << ' ' << ctx.gpr[4] << ' ' << ctx.gpr[5]
            << ' ' << ctx.ctr << ' ' << cr << ' ' << ctx.pc << '\n';
        return true;
    };
    for (uint32_t alignment : {0u, 1u, 7u, 15u, 16u, 23u, 30u, 31u}) {
        for (uint32_t size : {0u, 1u, 31u, 32u, 33u, 383u, 384u, 385u}) {
            if (!run(0x80212FA0, 0x80500000 + alignment, size, 0x55667788)) {
                return 1;
            }
        }
    }
    for (uint32_t counter : {1u, 2u, 12u, 13u}) {
        if (!run(0x80212FC4, 0x80500100, 12, counter)) {
            return 2;
        }
    }
    return 0;
}
