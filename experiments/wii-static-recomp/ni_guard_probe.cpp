#include "ni_guard.h"
#include <iostream>

int main() {
    uint32_t opcode, fpscr, msr;
    unsigned mode;
    nwii::runtime::CPUContext context;
    const auto sentinel = context.mmu.get_ptr(0x80010000);
    if (!sentinel) {
        return 14;
    }
    sentinel[0] = 0xde;
    sentinel[1] = 0xad;
    sentinel[2] = 0xbe;
    sentinel[3] = 0xef;
    while (std::cin >> mode >> opcode >> fpscr >> msr) {
        context.fpscr = fpscr;
        context.msr = msr;
        context.gpr.fill(0x12345678);
        context.fpr.fill(std::bit_cast<double>(uint64_t(0x3ff0000000000000)));
        context.ps1.fill(std::bit_cast<double>(uint64_t(0x4000000000000000)));
        context.pc = 0x80000000;
        context.lr = 0x80000004;
        context.ctr = 7;
        context.xer = 0x20000000;
        for (auto& field : context.cr) {
            field.lt = true;
            field.gt = false;
            field.eq = true;
            field.so = false;
        }
        bool refused = false;
        try {
            if (mode == 0) {
                nwii::runtime::experiment_ni_set(context, opcode);
            } else {
                nwii::runtime::experiment_ni_guard(context, opcode, 0x80000000);
            }
        } catch (const std::runtime_error&) {
            refused = true;
        }
        if ((refused || mode != 0) && context.fpscr != fpscr) {
            return 9;
        }
        if (context.msr != msr || context.pc != 0x80000000 || context.lr != 0x80000004 ||
            context.ctr != 7 || context.xer != 0x20000000) {
            return 10;
        }
        for (unsigned index = 0; index < 32; ++index) {
            if (context.gpr[index] != 0x12345678 || std::bit_cast<uint64_t>(context.fpr[index]) != 0x3ff0000000000000ull ||
                std::bit_cast<uint64_t>(context.ps1[index]) != 0x4000000000000000ull) {
                return 11;
            }
        }
        for (const auto& field : context.cr) {
            if (!field.lt || field.gt || !field.eq || field.so) {
                return 12;
            }
        }
        if (sentinel[0] != 0xde || sentinel[1] != 0xad || sentinel[2] != 0xbe || sentinel[3] != 0xef) {
            return 13;
        }
        std::cout << refused << ' ' << context.fpscr << ' ' << nwii::runtime::experiment_fp_opcode(opcode) << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
