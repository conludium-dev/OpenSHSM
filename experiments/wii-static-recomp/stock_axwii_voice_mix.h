// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_pb.h"
#include "stock_axwii_filters.h"
#include <algorithm>
#include <array>
#include <span>

namespace openshsm::experiment {

using AxWiiMainBuffers = std::array<std::array<int32_t, 96>, 12>;

inline std::array<int16_t, 96> mix_axwii_main_voice(AxWiiParameterBlock& pb,
    AxWiiMainBuffers& buffers, std::span<const int16_t> input, uint32_t control) {
    if (input.empty() || input.size() > 96 || (control & 0xff000000u)) {
        throw std::runtime_error("Unsupported AXWii main mix input");
    }
    auto words = pb.words;
    auto next_buffers = buffers;
    std::array<int16_t, 96> samples{};
    const auto clamp = [](int64_t value) {
        return int16_t(std::clamp(value, int64_t(-32768), int64_t(32767)));
    };
    for (size_t index = 0; index < input.size(); ++index) {
        samples[index] = clamp((int32_t(input[index]) * words[58]) >> 15);
        words[58] = uint16_t(words[58] + words[59]);
    }
    if (words[98]) {
        detail::axwii_low_pass(std::span(samples).first(input.size()), std::span(words).subspan<98, 4>());
    }
    if (words[102]) {
        detail::axwii_biquad(std::span(samples).first(input.size()), std::span(words).subspan<102, 10>());
    }
    constexpr unsigned volumes[] = {10, 12, 26, 14, 16, 28, 18, 20, 30, 22, 24, 32};
    constexpr unsigned dpop[] = {41, 45, 49, 42, 46, 50, 43, 47, 51, 44, 48, 52};
    for (unsigned channel = 0; channel < 12; ++channel) {
        if (!(control & (1u << (channel * 2)))) {
            continue;
        }
        const unsigned volume = volumes[channel];
        const uint16_t delta = control & (2u << (channel * 2)) ? words[volume + 1] : 0;
        for (size_t index = 0; index < input.size(); ++index) {
            const int16_t value = clamp((int64_t(samples[index]) * words[volume]) >> 15);
            const int64_t mixed = int64_t(next_buffers[channel][index]) + value;
            if (mixed < INT32_MIN || mixed > INT32_MAX) {
                throw std::runtime_error("Unverified AXWii mix overflow");
            }
            next_buffers[channel][index] = int32_t(mixed);
            words[volume] = uint16_t(words[volume] + delta);
            words[dpop[channel]] = uint16_t(value);
        }
    }
    pb.words = words;
    buffers = next_buffers;
    return samples;
}

}
