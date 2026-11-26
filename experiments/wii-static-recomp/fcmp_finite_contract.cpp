#include "fcmp_finite_adapter.h"
#include <cstring>
#include <iostream>

int main() {
    using namespace nwii::runtime;
    CPUContext context;
    context.msr = 0x2030;
    context.fpscr = 4;
    context.fpr.fill(1.0);
    context.ps1.fill(3.0);
    unsigned guards = 0;
    auto refuse = [&](uint32_t opcode) {
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto cr = context.cr;
        const auto fpscr = context.fpscr;
        bool caught = false;
        try {
            experiment_fcmp_finite(context, opcode);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.fpscr != fpscr || std::memcmp(context.fpr.data(), fpr.data(), sizeof(fpr)) ||
            std::memcmp(context.ps1.data(), ps1.data(), sizeof(ps1)) || std::memcmp(context.cr.data(), cr.data(), sizeof(cr))) {
            throw std::runtime_error("Ordered compare refusal changed CPU state");
        }
        ++guards;
    };
    for (uint32_t msr : {0x30u, 0x2930u, 0x2031u}) {
        context.msr = msr;
        refuse(0xfc010040);
    }
    context.msr = 0x2030;
    for (uint32_t status : {1u, 2u, 3u, 0x80u}) {
        context.fpscr = status;
        refuse(0xfc010040);
    }
    context.fpscr = 4;
    for (uint32_t opcode : {0xfc010041u, 0xfc010000u}) {
        refuse(opcode);
    }
    for (unsigned reg : {0u, 1u}) {
        for (uint64_t value : {0x7ff8000000000001ull, 0xfff8000000000042ull,
            0x7ff0000000000001ull, 0xfff0000000000042ull}) {
            context.fpr[reg] = std::bit_cast<double>(value);
            refuse(0xfc010040);
        }
        context.fpr[reg] = 1.0;
    }
    std::cout << "FCMP_FINITE_CONTRACT guards=" << guards << '\n';
}
