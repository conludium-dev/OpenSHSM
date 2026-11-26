#include "general_subtract_adapter.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    uint64_t a, b;
    uint32_t status, opcode;
    while (std::cin >> a >> b >> status >> opcode) {
        context.msr = 0x2030;
        context.fpscr = status;
        context.fpr.fill(3.0);
        context.ps1.fill(3.0);
        context.fpr[2] = std::bit_cast<double>(a);
        context.fpr[0] = std::bit_cast<double>(b);
        experiment_general_subtract(context, opcode);
        std::cout << std::bit_cast<uint64_t>(context.fpr[0]) << ' ' << std::bit_cast<uint64_t>(context.ps1[0]) << ' '
            << context.fpscr << ' ' << std::bit_cast<uint64_t>(context.fpr[2]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[2]) << '\n';
    }
    return std::cin.eof() ? 0 : 1;
}
