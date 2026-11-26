#include "frsp_adapter.h"
#include <iostream>

int main() {
    nwii::runtime::CPUContext context;
    uint64_t input;
    uint32_t fpscr, opcode;
    while (std::cin >> input >> fpscr >> opcode) {
        context.msr = 0x2030;
        context.fpscr = fpscr;
        context.fpr.fill(std::bit_cast<double>(uint64_t(0x3ff0000000000000)));
        context.ps1.fill(std::bit_cast<double>(uint64_t(0x4000000000000000)));
        for (auto& field : context.cr) {
            field.lt = true;
            field.gt = false;
            field.eq = true;
            field.so = false;
        }
        const unsigned source = (opcode >> 11) & 31, destination = (opcode >> 21) & 31;
        context.fpr[source] = std::bit_cast<double>(input);
        const auto beforeFpr = context.fpr;
        const auto beforePs1 = context.ps1;
        try {
            nwii::runtime::experiment_frsp(context, opcode);
        } catch (const std::runtime_error&) {
            if (context.fpscr != fpscr) {
                return 9;
            }
            for (unsigned index = 0; index < 32; ++index) {
                if (std::bit_cast<uint64_t>(context.fpr[index]) != std::bit_cast<uint64_t>(beforeFpr[index]) ||
                    std::bit_cast<uint64_t>(context.ps1[index]) != std::bit_cast<uint64_t>(beforePs1[index])) {
                    return 10;
                }
            }
            std::cout << "REFUSED\n";
            continue;
        }
        bool preserved = true;
        for (unsigned index = 0; index < 32; ++index) {
            if (index != destination) {
                preserved &= std::bit_cast<uint64_t>(context.fpr[index]) == std::bit_cast<uint64_t>(beforeFpr[index]);
                preserved &= std::bit_cast<uint64_t>(context.ps1[index]) == std::bit_cast<uint64_t>(beforePs1[index]);
            }
        }
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << std::bit_cast<uint64_t>(context.fpr[destination]) << ' '
                  << std::bit_cast<uint64_t>(context.ps1[destination]) << ' ' << context.fpscr << ' ' << cr << ' ' << preserved << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
