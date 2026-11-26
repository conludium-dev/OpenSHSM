#include "single_arithmetic_adapter.h"
#include "loader-bat-seed.h"
#include <cstring>
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    context.msr = 0x2030;
    context.fpscr = 4;
    context.fpr.fill(1.0);
    context.ps1.fill(3.0);
    unsigned guards = 0;
    auto refuse = [&](uint32_t opcode) {
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto cr = context.cr;
        const auto status = context.fpscr;
        bool caught = false;
        try {
            experiment_single_arithmetic(context, opcode);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.fpscr != status || std::memcmp(context.fpr.data(), fpr.data(), sizeof(fpr)) ||
            std::memcmp(context.ps1.data(), ps1.data(), sizeof(ps1)) || std::memcmp(context.cr.data(), cr.data(), sizeof(cr))) {
            throw std::runtime_error("Arithmetic refusal changed CPU");
        }
        ++guards;
    };
    for (uint32_t opcode : {0xec220825u, 0xec000073u, 0xfc220824u, 0xec220828u}) {
        refuse(opcode);
    }
    for (uint32_t msr : {0x30u, 0x2930u, 0x2031u}) {
        context.msr = msr;
        refuse(0xec220824);
        refuse(0xec000072);
    }
    context.msr = 0x2030;
    for (uint32_t status : {1u, 2u, 3u, 0x80u, 0x10u}) {
        context.fpscr = status;
        refuse(0xec220824);
        refuse(0xec000072);
    }
    std::cout << "SINGLE_ARITHMETIC_CONTRACT guards=" << guards << '\n';
}
