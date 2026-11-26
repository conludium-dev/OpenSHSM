// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment::detail {

inline void axwii_low_pass(std::span<int16_t> samples, std::span<uint16_t, 4> filter) {
    for (auto& sample : samples) {
        const int64_t value = int64_t(filter[2]) * sample +
            int64_t(int16_t(filter[3])) * int16_t(filter[1]);
        if (value < INT32_MIN || value > INT32_MAX) {
            throw std::runtime_error("Unverified AXWii low-pass overflow");
        }
        sample = int16_t(std::clamp(value >> 15, int64_t(-32768), int64_t(32767)));
        filter[1] = uint16_t(sample);
    }
}

inline void axwii_biquad(std::span<int16_t> samples, std::span<uint16_t, 10> filter) {
    for (auto& sample : samples) {
        const int16_t current = sample;
        int64_t value = int64_t(int16_t(filter[5])) * current +
            int64_t(int16_t(filter[6])) * int16_t(filter[1]) +
            int64_t(int16_t(filter[7])) * int16_t(filter[2]) +
            int64_t(int16_t(filter[8])) * int16_t(filter[3]) +
            int64_t(int16_t(filter[9])) * int16_t(filter[4]);
        value *= 4;
        value += (value & 0x10000) ? 0x8000 : 0x7fff;
        sample = int16_t(std::clamp(value >> 16, int64_t(-32768), int64_t(32767)));
        filter[2] = filter[1];
        filter[4] = filter[3];
        filter[1] = uint16_t(current);
        filter[3] = uint16_t(sample);
    }
}

}
