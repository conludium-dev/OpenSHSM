#include "fp64_transfer.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    context.msr = 0x2030;
    context.hid0 = 0xc200;
    context.fpscr = 4;
    context.gpr.fill(0);
    context.fpr.fill(1.0);
    context.ps1.fill(3.0);
    context.gpr[4] = 0x80700000;
    const uint32_t load = (50u << 26) | (1u << 21) | (4u << 16);
    unsigned guards = 0;
    auto refused = [&](uint32_t opcode) {
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto fpscr = context.fpscr;
        bool caught = false;
        try {
            experiment_fp64_transfer(context, opcode);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.gpr != gpr || context.fpr != fpr || context.ps1 != ps1 || context.fpscr != fpscr) {
            throw std::runtime_error("FP64 refusal state changed");
        }
        ++guards;
    };
    for (uint32_t msr : {0x30u, 0x2930u, 0x2031u}) {
        context.msr = msr;
        refused(load);
    }
    context.msr = 0x2030;
    refused((51u << 26) | (1u << 21));
    refused((31u << 26) | (631u << 1));
    refused((31u << 26) | (599u << 1) | 1);
    context.gpr[4] = 0x80700001;
    refused(load);
    context.gpr[4] = 0xe0000000;
    refused(load);
    context.gpr[4] = 0x80700000;
    context.instructionImages.emplace_back(0x80700000, std::vector<uint8_t>(8));
    refused((54u << 26) | (1u << 21) | (4u << 16));
    context.instructionImages.clear();
    context.msr = 0x2020;
    context.gpr[0] = 0xdeadbeef;
    const uint64_t bits = 0x7ff0000000000042ull;
    auto pointer = context.mmu.get_ptr(32);
    for (unsigned byte = 0; byte < 8; ++byte) {
        pointer[byte] = bits >> (56 - byte * 8);
    }
    experiment_fp64_transfer(context, (50u << 26) | (31u << 21) | 32);
    if (std::bit_cast<uint64_t>(context.fpr[31]) != bits || context.ps1[31] != 3.0 || context.gpr[0] != 0xdeadbeef) {
        return 9;
    }
    experiment_fp64_transfer(context, (54u << 26) | (31u << 21) | 64);
    if (bat_memory_read64(context, 64) != bits || context.fpscr != 4) {
        return 10;
    }
    context.msr = 0x2030;
    context.gpr[5] = 0x80700000;
    pointer = context.mmu.get_ptr(context.gpr[5]);
    for (unsigned byte = 0; byte < 8; ++byte) {
        pointer[byte] = bits >> (56 - byte * 8);
    }
    experiment_fp64_transfer(context, (31u << 26) | (31u << 21) | (5u << 11) | (599u << 1));
    if (std::bit_cast<uint64_t>(context.fpr[31]) != bits || context.gpr[0] != 0xdeadbeef) {
        return 11;
    }
    std::cout << "FP64_CONTRACT guards=" << guards << " zero_RA=3\n";
}
