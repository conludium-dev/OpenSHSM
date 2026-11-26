#include "stock_axwii_resample.h"
#include "axwii-resample-reference.h"
#include <iostream>
#include <vector>

using openshsm::experiment::resample_axwii;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii resample comparison failed");
    }
}

int main() {
    uint32_t random = 0x5348534d;
    auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    unsigned comparisons = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        std::array<int16_t, 384> samples;
        std::array<int16_t, 512> coefficients;
        std::array<int16_t, 4> history;
        for (auto& value : samples) {
            value = int16_t(next());
        }
        for (auto& value : coefficients) {
            value = int16_t(next());
        }
        for (auto& value : history) {
            value = int16_t(next());
        }
        const unsigned count = fixture % 3 == 0 ? 96 : 4 + next() % 93;
        const uint32_t position = fixture % 5 == 0 ? 0 : fixture % 5 == 1 ? 65535 : next() & 65535;
        constexpr uint32_t edges[] = {128, 32768, 65535, 65536, 65537, 131072, 262144};
        const uint32_t ratio = fixture < 7 ? edges[fixture] : 128 + next() % (262144 - 127);
        for (unsigned mode = 0; mode < 4; ++mode) {
            const unsigned type = mode == 3 ? 0 : mode;
            const uint32_t effective_ratio = type == 2 ? (fixture & 1 ? UINT32_MAX : 0) : ratio;
            const auto coeffs = mode == 0 ? std::span<const int16_t>(coefficients) : std::span<const int16_t>{};
            const auto candidate = resample_axwii(samples, count, history, position, effective_ratio, type, coeffs);
            std::array<int16_t, 98> reference_output;
            reference_output.fill(12345);
            auto reference_history = history;
            unsigned consumed = 0;
            const uint32_t reference_position = ResampleAudio([&](uint32_t index) {
                require(index == consumed && index < samples.size());
                ++consumed;
                return samples[index];
            }, reference_output.data() + 1, count, reference_history.data(), position, effective_ratio, type,
                coeffs.empty() ? nullptr : coeffs.data());
            require(candidate.position == reference_position && candidate.consumed == consumed);
            require(candidate.history == reference_history);
            require(std::equal(candidate.output.begin(), candidate.output.begin() + count, reference_output.begin() + 1));
            require(reference_output.front() == 12345 && reference_output[count + 1] == 12345);
            ++comparisons;
        }
    }
    unsigned refused = 0;
    const auto reject = [&](unsigned count, uint32_t position, uint32_t ratio, unsigned type,
        size_t inputs, size_t coeffs) {
        std::array<int16_t, 384> samples{};
        std::array<int16_t, 512> coefficients{};
        try {
            (void)resample_axwii(std::span(samples).first(inputs), count, {}, position, ratio, type,
                std::span(coefficients).first(coeffs));
        } catch (const std::runtime_error&) {
            ++refused;
        }
    };
    reject(0, 0, 65536, 1, 384, 0);
    reject(97, 0, 65536, 1, 384, 0);
    reject(96, 65536, 65536, 1, 384, 0);
    reject(96, 0, 127, 1, 384, 0);
    reject(96, 0, 262145, 1, 384, 0);
    reject(96, 0, 65536, 3, 384, 0);
    reject(3, 0, 65536, 2, 384, 0);
    reject(96, 0, 65536, 1, 95, 0);
    reject(96, 0, 262144, 0, 383, 512);
    reject(96, 0, 65536, 0, 384, 511);
    require(refused == 10);
    std::cout << "AXWII_RESAMPLE_REFERENCE_COMPONENT_PASS " << comparisons
              << " comparisons;" << refused << " refusals\n";
}
