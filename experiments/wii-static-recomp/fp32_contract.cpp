#include "fp32_transfer.h"
#include "loader-bat-seed.h"
#include <cstring>
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
    const uint32_t load = (48u << 26) | (1u << 21) | (4u << 16);
    const uint32_t store = (52u << 26) | (1u << 21) | (4u << 16);
    unsigned guards = 0;
    auto refused = [&](uint32_t opcode) {
        const auto gpr = context.gpr;
        const auto fpr = context.fpr;
        const auto ps1 = context.ps1;
        const auto fpscr = context.fpscr;
        const auto lines = context.dataLines;
        const auto replacement = context.replacement;
        bool caught = false;
        try {
            experiment_fp32_transfer(context,opcode);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || context.gpr != gpr || std::memcmp(context.fpr.data(),fpr.data(),sizeof(fpr)) ||
            std::memcmp(context.ps1.data(),ps1.data(),sizeof(ps1)) || context.fpscr != fpscr ||
            std::memcmp(context.dataLines.data(),lines.data(),sizeof(lines)) || context.replacement != replacement) {
            throw std::runtime_error("FP32 refusal mutated registers/cache");
        }
        ++guards;
    };
    for (uint32_t msr : {0x30u,0x2930u,0x2031u}) {
        context.msr = msr;
        refused(load);
    }
    context.msr = 0x2030;
    refused((49u << 26) | (1u << 21) | (4u << 16));
    refused((31u << 26) | (567u << 1));
    refused((31u << 26) | (535u << 1) | 1);
    context.gpr[4] = 0x80700001;
    refused(load);
    context.gpr[4] = 0xe0000000;
    refused(load);
    context.gpr[4] = 0x80700000;
    for (uint64_t bits : {0x3ff0000000000001ull,0x0000000000000001ull,0x7ff0000000000001ull}) {
        context.fpr[1] = std::bit_cast<double>(bits);
        refused(store);
    }
    context.fpr[1] = 1.0;
    context.instructionImages.emplace_back(0x80700000,std::vector<uint8_t>(4));
    refused(store);
    context.instructionImages.clear();
    unsigned roundtrips = 0;
    for (unsigned exponent : {0u,1u,126u,127u,254u,255u}) {
        for (unsigned sign = 0; sign < 2; ++sign) {
            for (unsigned fraction = 0; fraction < 65536; ++fraction) {
                const uint32_t bits = sign << 31 | exponent << 23 | fraction;
                if (experiment_fp32_exact_narrow(experiment_fp32_expand(bits)) != bits) {
                    return 2;
                }
                ++roundtrips;
            }
        }
    }
    context.msr = 0x2020;
    context.gpr[0] = 0xdeadbeef;
    auto* bytes = context.mmu.get_ptr(32);
    const uint32_t bits = 0x7f800042;
    for (unsigned index = 0; index < 4; ++index) {
        bytes[index] = bits >> (24 - index * 8);
    }
    experiment_fp32_transfer(context,(48u << 26) | (31u << 21) | 32);
    if (std::bit_cast<uint64_t>(context.fpr[31]) != experiment_fp32_expand(bits) ||
        std::bit_cast<uint64_t>(context.ps1[31]) != experiment_fp32_expand(bits) || context.gpr[0] != 0xdeadbeef) {
        return 3;
    }
    experiment_fp32_transfer(context,(52u << 26) | (31u << 21) | 64);
    if (bat_memory_read32(context,64) != bits || context.fpscr != 4) {
        return 4;
    }
    std::cout << "FP32_CONTRACT guards=" << guards << " roundtrips=" << roundtrips << " zero_RA=2\n";
}
