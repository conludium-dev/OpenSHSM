#include "fsubs_integer_bias.h"
#include "loader-bat-seed.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    int64_t value;
    uint32_t status;
    while (std::cin >> value >> status) {
        context.msr = 0x2030;
        context.fpscr = status;
        context.fpr.fill(3.0);
        context.ps1.fill(3.0);
        context.fpr[0] = std::bit_cast<double>(0x4330000000000000ull | (uint32_t(value) ^ 0x80000000u));
        context.fpr[3] = std::bit_cast<double>(0x4330000080000000ull);
        experiment_fsubs_integer_bias(context, 0xec401828);
        std::cout << std::bit_cast<uint64_t>(context.fpr[2]) << ' ' << std::bit_cast<uint64_t>(context.ps1[2]) << ' '
            << context.fpscr << ' ' << std::bit_cast<uint64_t>(context.fpr[0]) << ' '
            << std::bit_cast<uint64_t>(context.fpr[3]) << ' ' << std::bit_cast<uint64_t>(context.ps1[0]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[3]) << '\n';
    }
    return std::cin.eof() ? 0 : 1;
}
