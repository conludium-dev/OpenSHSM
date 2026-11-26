// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

struct AxWiiResampleResult {
    std::array<int16_t, 96> output{};
    std::array<int16_t, 4> history{};
    uint32_t position = 0;
    unsigned consumed = 0;
};

namespace detail {

inline AxWiiResampleResult resample_axwii_bounded(std::span<const int16_t> input, unsigned count,
    std::array<int16_t, 4> history, uint32_t position, uint32_t ratio, unsigned type,
    std::span<const int16_t> coefficients, uint32_t maximum_ratio) {
    if (!count || count > 96 || position > 0xffff ||
        (type != 2 && (ratio < 128 || ratio > maximum_ratio)) ||
        type > 2 || (type == 2 && count < 4) ||
        (!coefficients.empty() && coefficients.size() != 512)) {
        throw std::runtime_error("Unsupported AXWii resampling input");
    }
    const unsigned needed = type == 2 ? count : unsigned((uint64_t(position) + uint64_t(ratio) * count) >> 16);
    if (input.size() < needed) {
        throw std::runtime_error("Truncated AXWii samples");
    }
    AxWiiResampleResult result;
    result.position = position;
    result.history = history;
    if (type == 2) {
        std::copy_n(input.begin(), count, result.output.begin());
        std::copy_n(input.begin() + count - 4, 4, result.history.begin());
        result.consumed = count;
        return result;
    }
    unsigned cursor = 4;
    for (unsigned index = 0; index < count; ++index) {
        result.position += ratio;
        while (result.position >= 0x10000) {
            history[cursor++ & 3] = input[result.consumed++];
            result.position -= 0x10000;
        }
        if (type == 0 && !coefficients.empty()) {
            const unsigned phase = (result.position >> 9) * 4;
            int64_t value = 0;
            for (unsigned tap = 0; tap < 4; ++tap) {
                value += int64_t(history[cursor++ & 3]) * coefficients[phase + tap];
            }
            result.output[index] = int16_t(std::clamp(value >> 15, int64_t(-32768), int64_t(32767)));
        } else {
            const uint16_t fraction = uint16_t(result.position);
            if (fraction) {
                const int32_t first = history[cursor++ & 3];
                const int32_t second = history[cursor++ & 3];
                result.output[index] = int16_t((first * uint16_t(-fraction) + second * fraction) >> 16);
                cursor += 2;
            } else {
                result.output[index] = history[cursor++ & 3];
                cursor += 3;
            }
        }
    }
    for (unsigned index = 4; index > 0; --index) {
        result.history[index - 1] = history[--cursor & 3];
    }
    return result;
}

}

inline AxWiiResampleResult resample_axwii(std::span<const int16_t> input, unsigned count,
    std::array<int16_t, 4> history, uint32_t position, uint32_t ratio, unsigned type,
    std::span<const int16_t> coefficients = {}) {
    return detail::resample_axwii_bounded(input, count, history, position, ratio, type, coefficients, 0x40000);
}

inline AxWiiResampleResult resample_axwii_remote(std::span<const int16_t> input,
    std::array<int16_t, 4> history, uint32_t position, std::span<const int16_t> coefficients = {}) {
    if (input.size() != 32 && input.size() != 96) {
        throw std::runtime_error("Unsupported AXWii remote frame");
    }
    return detail::resample_axwii_bounded(input, input.size() == 96 ? 18 : 6,
        history, position, 0x55555, 0, coefficients, 0x55555);
}

}
