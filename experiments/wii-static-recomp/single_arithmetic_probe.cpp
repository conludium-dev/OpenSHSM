#include "single_arithmetic_adapter.h"
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
        const bool divide = opcode == 0xec220824;
        const unsigned left = divide ? 2 : 0;
        const unsigned destination = divide ? 1 : 0;
        context.fpr[left] = std::bit_cast<double>(a);
        context.fpr[1] = std::bit_cast<double>(b);
        experiment_single_arithmetic(context, opcode);
        const unsigned preserved = divide ? 2 : 1;
        std::cout << std::bit_cast<uint64_t>(context.fpr[destination]) << ' ' << std::bit_cast<uint64_t>(context.ps1[destination]) << ' '
            << context.fpscr << ' ' << std::bit_cast<uint64_t>(context.fpr[preserved]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[preserved]) << '\n';
    }
    return std::cin.eof() ? 0 : 1;
}
