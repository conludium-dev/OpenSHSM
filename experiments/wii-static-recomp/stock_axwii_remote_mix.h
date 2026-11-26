// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_voice_mix.h"
#include "stock_axwii_resample.h"

namespace openshsm::experiment {

using AxWiiRemoteBuffers = std::array<std::array<int32_t, 18>, 8>;

inline void mix_axwii_remote(AxWiiParameterBlock& pb, AxWiiRemoteBuffers& buffers,
    std::span<const int16_t> input, std::span<const int16_t> coefficient_bank = {}) {
    if (!pb.words[112]) {
        return;
    }
    if (input.size() != 32 && input.size() != 96) {
        throw std::runtime_error("Unsupported AXWii remote frame");
    }
    auto words = pb.words;
    auto next_buffers = buffers;
    std::array<int16_t, 96> samples{};
    std::copy(input.begin(), input.end(), samples.begin());
    auto frame = std::span(samples).first(input.size());
    if (words[143] == 2) {
        detail::axwii_biquad(frame, std::span(words).subspan<143, 10>());
    } else if (words[143]) {
        detail::axwii_low_pass(frame, std::span(words).subspan<143, 4>());
    }
    std::array<int16_t, 4> history;
    for (unsigned index = 0; index < 4; ++index) {
        history[index] = int16_t(words[139 + index]);
    }
    const auto result = resample_axwii_remote(frame, history, words[138], coefficient_bank);
    words[138] = uint16_t(result.position);
    for (unsigned index = 0; index < 4; ++index) {
        words[139 + index] = uint16_t(result.history[index]);
    }
    constexpr unsigned dpop[] = {130, 134, 131, 135, 132, 136, 133, 137};
    const unsigned count = input.size() == 96 ? 18 : 6;
    for (unsigned channel = 0; channel < 8; ++channel) {
        const unsigned mode = (words[113] >> (channel * 2)) & 3;
        if (!mode) {
            continue;
        }
        const unsigned volume = 114 + channel * 2;
        const uint16_t delta = mode & 2 ? words[volume + 1] : 0;
        for (unsigned index = 0; index < count; ++index) {
            const int64_t value = (int64_t(result.output[index]) * words[volume]) >> 15;
            const int16_t sample = int16_t(std::clamp(value, int64_t(-32768), int64_t(32767)));
            const int64_t mixed = int64_t(next_buffers[channel][index]) + sample;
            if (mixed < INT32_MIN || mixed > INT32_MAX) {
                throw std::runtime_error("Unverified AXWii remote mix overflow");
            }
            next_buffers[channel][index] = int32_t(mixed);
            words[volume] = uint16_t(words[volume] + delta);
            words[dpop[channel]] = uint16_t(sample);
        }
    }
    pb.words = words;
    buffers = next_buffers;
}

}
