#include "fp64_transfer.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    nwii::runtime::SeededBatContext context;
    uint64_t bits, ps1;
    uint32_t fpscr, load, store;
    unsigned alignment;
    while (std::cin >> bits >> ps1 >> fpscr >> load >> store >> alignment) {
        context.dataLines = {};
        context.replacement.fill(0);
        context.hid0 = 0xc200;
        context.msr = 0x2030;
        context.fpscr = fpscr;
        context.gpr.fill(0);
        context.fpr.fill(1.0);
        context.ps1.fill(std::bit_cast<double>(ps1));
        const uint32_t source = 0x80700000 + alignment;
        const uint32_t destination = 0x80700100 + alignment;
        auto pointer = context.mmu.get_ptr(source);
        for (unsigned byte = 0; byte < 8; ++byte) {
            pointer[byte] = bits >> (56 - byte * 8);
        }
        const unsigned loadRa = (load >> 16) & 31, storeRa = (store >> 16) & 31;
        const uint32_t loadOffset = load >> 26 == 31 ? 0 : uint32_t(int32_t(int16_t(load)));
        const uint32_t storeOffset = store >> 26 == 31 ? 0 : uint32_t(int32_t(int16_t(store)));
        context.gpr[loadRa] = source - loadOffset;
        if (load >> 26 == 31) {
            context.gpr[(load >> 11) & 31] = 0;
        }
        nwii::runtime::experiment_fp64_transfer(context, load);
        const uint32_t loadRaAfter = context.gpr[loadRa];
        context.gpr[storeRa] = destination - storeOffset;
        if (store >> 26 == 31) {
            context.gpr[(store >> 11) & 31] = 0;
        }
        nwii::runtime::experiment_fp64_transfer(context, store);
        const unsigned reg = (load >> 21) & 31;
        std::cout << std::bit_cast<uint64_t>(context.fpr[reg]) << ' ' << std::bit_cast<uint64_t>(context.ps1[reg]) << ' '
                  << context.fpscr << ' ' << nwii::runtime::bat_memory_read64(context, destination) << ' '
                  << loadRaAfter - source << ' ' << context.gpr[storeRa] - destination << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
