#include "fp32_transfer.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    uint32_t bits, fpscr, load, store;
    while (std::cin >> bits >> fpscr >> load >> store) {
        context.dataLines = {};
        context.replacement.fill(0);
        context.hid0 = 0xc200;
        context.msr = 0x2030;
        context.fpscr = fpscr;
        context.gpr.fill(0);
        context.fpr.fill(1.0);
        context.ps1.fill(3.0);
        const uint32_t source = 0x80700000;
        const uint32_t destination = 0x80700100;
        auto* data = context.mmu.get_ptr(source);
        for (unsigned index = 0; index < 4; ++index) {
            data[index] = bits >> (24 - index * 8);
        }
        const unsigned loadRa = (load >> 16) & 31;
        const unsigned storeRa = (store >> 16) & 31;
        context.gpr[loadRa] = source - (load >> 26 == 31 ? 0 : uint32_t(int32_t(int16_t(load))));
        if (load >> 26 == 31) {
            context.gpr[(load >> 11) & 31] = 0;
        }
        experiment_fp32_transfer(context,load);
        context.gpr[storeRa] = destination - (store >> 26 == 31 ? 0 : uint32_t(int32_t(int16_t(store))));
        if (store >> 26 == 31) {
            context.gpr[(store >> 11) & 31] = 0;
        }
        experiment_fp32_transfer(context,store);
        const unsigned reg = (load >> 21) & 31;
        std::cout << std::bit_cast<uint64_t>(context.fpr[reg]) << ' ' << std::bit_cast<uint64_t>(context.ps1[reg])
            << ' ' << context.fpscr << ' ' << bat_memory_read32(context,destination) << '\n';
    }
    return std::cin.eof() ? 0 : 1;
}
