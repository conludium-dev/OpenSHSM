#include "stock_axwii_accelerator.h"
#include "axwii-accelerator-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii accelerator comparison failed");
    }
}

int main() {
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    unsigned comparisons = 0;
    for (unsigned fixture = 0; fixture < 1024; ++fixture) {
        std::array<uint8_t, 4096> memory;
        std::array<int16_t, 16> coefficients;
        for (auto& byte : memory) {
            byte = uint8_t(next());
        }
        for (auto& coefficient : coefficients) {
            coefficient = int16_t(int(next() % 8193) - 4096);
        }
        for (uint16_t format : {uint16_t(0), uint16_t(0x19), uint16_t(0x0a)}) {
            for (unsigned mode = 0; mode < 3; ++mode) {
                AxWiiSampleState state;
                state.format = format;
                state.start = 34;
                state.current = 34;
                state.end = fixture % 3 == 0 ? 48 : fixture % 3 == 1 ? 49 : 47;
                state.pred_scale = uint16_t(next() & 0x7f);
                state.gain = int16_t(next());
                state.yn1 = int16_t(next());
                state.yn2 = int16_t(next());
                state.looping = mode != 0;
                state.is_stream = mode == 2;
                state.loop_pred_scale = uint16_t(next() & 0x7f);
                state.loop_yn1 = uint16_t(next());
                state.loop_yn2 = uint16_t(next());
                Oracle oracle(memory, state);
                for (unsigned sample = 0; sample < 96; ++sample) {
                    const int16_t actual = read_axwii_sample(memory, coefficients, state);
                    const int16_t expected = int16_t(oracle.ReadSample(coefficients.data()));
                    require(actual == expected && state.current == oracle.GetCurrentAddress());
                    require(state.yn1 == oracle.GetYn1() && state.yn2 == oracle.GetYn2());
                    require(state.pred_scale == oracle.GetPredScale() && state.stopped == oracle.stopped());
                    require(state.running == oracle.pb.running);
                    ++comparisons;
                }
            }
        }
    }
    std::array<uint8_t, 8> memory{};
    std::array<int16_t, 16> coefficients{};
    AxWiiSampleState invalid;
    invalid.current = 1000;
    bool refused = false;
    try {
        (void)read_axwii_sample(memory, coefficients, invalid);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    require(refused && invalid.current == 1000 && invalid.running == 1 && !invalid.stopped);
    unsigned refusals = 1;
    for (unsigned fixture = 0; fixture < 4; ++fixture) {
        AxWiiSampleState state;
        coefficients.fill(0);
        if (fixture == 0) {
            state.format = 3;
        } else if (fixture == 1) {
            state.current = 15;
            state.end = 100;
        } else {
            coefficients.fill(-32768);
            state.yn1 = state.yn2 = -32768;
            state.format = fixture == 2 ? 0 : 0x19;
        }
        const auto before = state;
        try {
            (void)read_axwii_sample(memory, coefficients, state);
        } catch (const std::runtime_error&) {
            ++refusals;
        }
        require(state.current == before.current && state.running == before.running && state.stopped == before.stopped);
        require(state.yn1 == before.yn1 && state.yn2 == before.yn2 && state.pred_scale == before.pred_scale);
    }
    require(refusals == 5);
    std::cout << "AXWII_ACCELERATOR_REFERENCE_COMPONENT_PASS " << comparisons << " samples;5 refusals\n";
}
