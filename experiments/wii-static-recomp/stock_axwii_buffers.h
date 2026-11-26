// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_remote_mix.h"
#include <bit>
#include <limits>

namespace openshsm::experiment {

inline int32_t axwii_buffer_word(std::span<const uint8_t> bytes, size_t offset) {
    uint32_t value = 0;
    for (unsigned index = 0; index < 4; ++index) {
        value = (value << 8) | bytes[offset + index];
    }
    return std::bit_cast<int32_t>(value);
}

inline int32_t axwii_buffer_checked(int64_t value) {
    if (value < std::numeric_limits<int32_t>::min() || value > std::numeric_limits<int32_t>::max()) {
        throw std::runtime_error("Unverified AXWii buffer arithmetic overflow");
    }
    return int32_t(value);
}

inline void setup_axwii_buffers(AxWiiMainBuffers& main, AxWiiRemoteBuffers& remote,
    std::span<const uint8_t> initialization) {
    if (initialization.size() != 120) {
        throw std::runtime_error("Invalid AXWii setup buffer size");
    }
    AxWiiMainBuffers next_main{};
    AxWiiRemoteBuffers next_remote{};
    for (unsigned channel = 0; channel < 20; ++channel) {
        const size_t offset = channel * 6;
        const int32_t value = axwii_buffer_word(initialization, offset);
        const int16_t delta = std::bit_cast<int16_t>(uint16_t(uint16_t(initialization[offset + 4]) << 8 |
            initialization[offset + 5]));
        const unsigned count = channel < 12 ? 96 : 18;
        for (unsigned index = 0; index < count; ++index) {
            const int32_t sample = value == 0 ? 0 : axwii_buffer_checked(int64_t(value) + int64_t(index) * delta);
            if (channel < 12) {
                next_main[channel][index] = sample;
            } else {
                next_remote[channel - 12][index] = sample;
            }
        }
    }
    main = next_main;
    remote = next_remote;
}

inline void add_axwii_lr(AxWiiMainBuffers& main, std::span<const uint8_t> input,
    bool subtract, bool separate = false) {
    if (input.size() != (separate ? 768 : 384) || (separate && subtract)) {
        throw std::runtime_error("Invalid AXWii LR input");
    }
    auto next_main = main;
    for (unsigned index = 0; index < 96; ++index) {
        const int64_t left = axwii_buffer_word(input, index * 4);
        const int64_t right = separate ? -int64_t(axwii_buffer_word(input, 384 + index * 4)) :
            (subtract ? -left : left);
        const int64_t left_delta = subtract ? -left : left;
        next_main[0][index] = axwii_buffer_checked(int64_t(main[0][index]) + left_delta);
        next_main[1][index] = axwii_buffer_checked(int64_t(main[1][index]) + right);
    }
    main = next_main;
}

inline void compress_axwii_buffers(AxWiiMainBuffers& main, uint16_t& position,
    uint16_t threshold, uint16_t release_frames, std::span<const uint8_t> table) {
    bool triggered = false;
    for (unsigned index = 0; index < 96; ++index) {
        for (unsigned channel = 0; channel < 2; ++channel) {
            const int64_t sample = main[channel][index];
            if (sample == std::numeric_limits<int32_t>::min()) {
                throw std::runtime_error("Unverified AXWii compressor minimum sample");
            }
            if ((sample < 0 ? -sample : sample) > threshold) {
                triggered = true;
            }
        }
    }
    uint16_t next_position = position;
    size_t entry = 0;
    if (triggered) {
        entry = position;
        next_position = release_frames;
    } else if (position) {
        next_position = uint16_t(position - 1);
        entry = 11u + next_position;
    } else {
        return;
    }
    const size_t offset = entry * 192;
    if (offset > table.size() || table.size() - offset < 192) {
        throw std::runtime_error("Invalid AXWii compressor table range");
    }
    auto next_main = main;
    for (unsigned index = 0; index < 96; ++index) {
        const uint16_t coefficient = uint16_t(uint16_t(table[offset + index * 2]) << 8 |
            table[offset + index * 2 + 1]);
        for (unsigned channel = 0; channel < 2; ++channel) {
            next_main[channel][index] = axwii_buffer_checked((int64_t(main[channel][index]) * coefficient) >> 15);
        }
    }
    main = next_main;
    position = next_position;
}

}
