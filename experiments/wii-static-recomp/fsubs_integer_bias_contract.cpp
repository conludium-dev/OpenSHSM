#include "fsubs_integer_bias.h"
#include "loader-bat-seed.h"
#include <cstring>
#include <iostream>

int main() {
    using namespace nwii::runtime;
    SeededBatContext context;
    context.msr = 0x2030;
    context.fpscr = 4;
    context.fpr[0] = std::bit_cast<double>(0x4330000080000210ull);
    context.fpr[1] = std::bit_cast<double>(0x4330000080000000ull);
    unsigned guards = 0;
    auto refused = [&](uint32_t opcode) {
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto fpscr = context.fpscr;
        const auto cache = context.dataLines;
        bool caught = false;
        try {
            experiment_fsubs_integer_bias(context,opcode);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.gpr != gpr || std::memcmp(context.fpr.data(),fpr.data(),sizeof(fpr)) ||
            std::memcmp(context.ps1.data(),ps1.data(),sizeof(ps1)) || context.fpscr != fpscr ||
            std::memcmp(context.dataLines.data(),cache.data(),sizeof(cache))) {
            throw std::runtime_error("Fsubs integer-bias refusal changed CPU/cache");
        }
        ++guards;
    };
    for (uint32_t msr : {0x30u,0x2930u,0x2031u}) {
        context.msr = msr;
        refused(0xec000828);
    }
    context.msr = 0x2030;
    for (uint32_t fpscr : {1u,2u,3u,0x80u}) {
        context.fpscr = fpscr;
        refused(0xec000828);
    }
    context.fpscr = 4;
    for (uint32_t opcode : {0xec000829u,0xfc000828u,0xec00082au,0xec000868u}) {
        refused(opcode);
    }
    for (uint64_t bits : {0ull,0x7ff8000000000000ull,0x4330000100000000ull}) {
        context.fpr[0] = std::bit_cast<double>(bits);
        refused(0xec000828);
    }
    context.fpr[0] = std::bit_cast<double>(0x4330000080000210ull);
    for (uint64_t bits : {0ull,0x4330000080000001ull}) {
        context.fpr[1] = std::bit_cast<double>(bits);
        refused(0xec000828);
    }
    std::cout << "Fsubs_BIAS_CONTRACT guards=" << guards << '\n';
}
