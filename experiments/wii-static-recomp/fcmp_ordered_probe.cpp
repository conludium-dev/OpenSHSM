#include "fcmp_ordered_adapter.h"
#include <iostream>

int main() {
    nwii::runtime::CPUContext context;
    uint64_t a, b;
    uint32_t fpscr, cr;
    while (std::cin >> a >> b >> fpscr >> cr) {
        context.msr = 0x2030;
        context.fpscr = fpscr;
        context.fpr[1] = std::bit_cast<double>(a);
        context.fpr[0] = std::bit_cast<double>(b);
        context.ps1[0] = context.ps1[1] = 3.0;
        for (unsigned field = 0; field < 8; ++field) {
            const unsigned bits = (cr >> (28 - field * 4)) & 15;
            context.cr[field].lt = bits & 8;
            context.cr[field].gt = bits & 4;
            context.cr[field].eq = bits & 2;
            context.cr[field].so = bits & 1;
        }
        nwii::runtime::experiment_fcmp_ordered(context, 0xfc010040);
        uint32_t result = 0;
        for (const auto& field : context.cr) {
            result = (result << 4) | (field.lt ? 8 : 0) | (field.gt ? 4 : 0) |
                (field.eq ? 2 : 0) | (field.so ? 1 : 0);
        }
        std::cout << result << ' ' << context.fpscr << ' ' << std::bit_cast<uint64_t>(context.fpr[0]) << ' '
            << std::bit_cast<uint64_t>(context.fpr[1]) << ' ' << std::bit_cast<uint64_t>(context.ps1[0]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[1]) << '\n';
    }
    return std::cin.eof() ? 0 : 1;
}
