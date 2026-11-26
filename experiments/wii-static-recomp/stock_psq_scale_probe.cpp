#include "psq_scale.h"
#include <processor_adapter.h>
#include <bit>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>

int main() {
    using namespace nwii::runtime;
    auto a = std::make_unique<ProcessorContext>();
    auto b = std::make_unique<ProcessorContext>();
    unsigned count = 0, refusals = 0;
    const double values[] = {0.0, -0.0, 1.25, -127.75, 65535.25,
        std::numeric_limits<double>::infinity(), -std::numeric_limits<double>::infinity(),
        std::bit_cast<double>(0x7FF8000012345678ull)};
    for (uint32_t scale = 0; scale < 64; ++scale) {
        const int exponent = int(scale ^ 32u) - 32;
        if (std::bit_cast<uint32_t>(std::ldexp(1.0f, exponent)) != uint32_t(127 + exponent) << 23
            || std::bit_cast<uint32_t>(std::ldexp(1.0f, -exponent)) != uint32_t(127 - exponent) << 23) {
            return 8;
        }
        for (uint32_t type = 0; type < 8; ++type) {
            for (uint32_t single = 0; single < 2; ++single) {
                for (uint32_t address : {0x80568000u, 0x91002000u, 0xE0000100u}) {
                    for (unsigned sample = 0; sample < 8; ++sample) {
                        for (auto* ctx : {a.get(), b.get()}) {
                            ctx->gqr[5] = (scale << 24) | (type << 16) | (scale << 8) | type;
                            ctx->fpr[1] = values[sample];
                            ctx->ps1[1] = sample == 3 ? values[7] : values[sample];
                            for (unsigned i = 0; i < 32; ++i) {
                                ctx->mmu.write8(address + i, uint8_t(i * 31 + sample));
                            }
                        }
                        std::string first, second;
                        try { a->psq_store(1, address, single, 5); }
                        catch (const std::runtime_error& error) { first = error.what(); }
                        try { stock_psq_store(*b, 1, address, single, 5); }
                        catch (const std::runtime_error& error) { second = error.what(); }
                        if (first != second || std::memcmp(a->mmu.get_ptr(address), b->mmu.get_ptr(address), 32) != 0) {
                            return 9;
                        }
                        refusals += !first.empty();
                        ++count;
                        a->psq_load(1, address, single, 5);
                        stock_psq_load(*b, 1, address, single, 5);
                        if (std::memcmp(a->fpr.data(), b->fpr.data(), sizeof(a->fpr)) != 0
                            || std::memcmp(a->ps1.data(), b->ps1.data(), sizeof(a->ps1)) != 0) {
                            return 10;
                        }
                        ++count;
                    }
                }
            }
        }
    }
    std::cout << "PSQ_SCALE_DIFFERENTIAL_PASS " << count << " refusals=" << refusals << '\n';
}
