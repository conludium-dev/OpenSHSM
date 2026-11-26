#include "stock_axwii_accelerator.h"
#include "stock_axwii_sample_memory.h"
#include "axwii-mapped-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii mapped sample comparison failed");
    }
}

int main() {
    std::array<uint8_t, 4096> mem1{}, mem2{};
    for (unsigned index = 0; index < mem1.size(); ++index) {
        mem1[index] = uint8_t(index * 13 + 7);
        mem2[index] = uint8_t(index * 23 + 113);
    }
    AxWiiSampleMemory reader{mem1, mem2, 4095, 4095};
    ReferenceMemory mapping{mem1, mem2, 4095, 4095};
    uint32_t random = 0x5348534d;
    for (unsigned index = 0; index < 131072; ++index) {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        require(reader(random) == mapping.ReadARAM(random));
    }
    std::array<int16_t, 16> coefficients{1024, -256};
    unsigned samples = 0;
    for (uint16_t format : {uint16_t(0), uint16_t(0x19), uint16_t(0x0a)}) {
        for (unsigned bank = 0; bank < 2; ++bank) {
            for (unsigned loop = 0; loop < 3; ++loop) {
                AxWiiSampleState state;
                const uint32_t base = bank ? (format == 0 ? 0x20000000u :
                    format == 0x19 ? 0x10000000u : 0x08000000u) : 0;
                state.format = format;
                state.start = state.current = base + 34;
                state.end = base + 47;
                state.looping = loop != 0;
                state.is_stream = loop == 2;
                state.gain = 1024;
                state.pred_scale = 3;
                state.loop_pred_scale = 2;
                Oracle oracle(mapping, state);
                for (unsigned index = 0; index < 192; ++index) {
                    const auto actual = read_axwii_sample_from(reader, coefficients, state);
                    require(actual == int16_t(oracle.ReadSample(coefficients.data())));
                    require(state.current == oracle.GetCurrentAddress() && state.yn1 == oracle.GetYn1());
                    require(state.yn2 == oracle.GetYn2() && state.pred_scale == oracle.GetPredScale());
                    require(state.running == oracle.pb.running && state.stopped == oracle.stopped());
                    ++samples;
                }
            }
        }
    }
    AxWiiSampleMemory short_reader{std::span(mem1).first(24), std::span(mem2).first(24), 31, 31};
    unsigned refusals = 0;
    for (uint32_t address : {24u, 31u, 0x10000018u, 0x1000001fu}) {
        try {
            (void)short_reader(address);
        } catch (const std::runtime_error&) {
            ++refusals;
        }
    }
    AxWiiSampleState state;
    state.format = 0x0a;
    state.current = 0x80000000u;
    try {
        (void)read_axwii_sample_from(reader, coefficients, state);
    } catch (const std::runtime_error&) {
        ++refusals;
    }
    require(refusals == 5 && state.current == 0x80000000u && state.yn1 == 0);
    std::cout << "AXWII_SAMPLE_MEMORY_PASS 131072 addresses;" << samples << " samples;5 refusals\n";
}
