// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

struct AxWiiSampleState {
    uint32_t start = 0, end = 0, current = 0;
    uint16_t format = 0, pred_scale = 0;
    int16_t gain = 0, yn1 = 0, yn2 = 0;
    uint16_t looping = 0, is_stream = 0, running = 1;
    uint16_t loop_pred_scale = 0, loop_yn1 = 0, loop_yn2 = 0;
    bool stopped = false;
};

template<class ReadByte>
inline int16_t read_axwii_sample_from(ReadByte&& read_byte,
    const std::array<int16_t, 16>& coefficients, AxWiiSampleState& state) {
    if (state.format != 0 && state.format != 0x19 && state.format != 0x0a) {
        throw std::runtime_error("Unsupported AXWii sample format");
    }
    if (state.stopped) {
        return 0;
    }
    auto next = state;
    const auto read = [&](uint64_t address) {
        if (address > UINT32_MAX) {
            throw std::runtime_error("AXWii sample address overflow");
        }
        return uint8_t(read_byte(uint32_t(address)));
    };
    int16_t raw;
    if (next.format == 0) {
        const uint8_t byte = read(next.current >> 1);
        raw = (next.current & 1) ? byte & 15 : byte >> 4;
    } else if (next.format == 0x19) {
        raw = read(next.current);
    } else {
        const uint64_t address = uint64_t(next.current) * 2;
        raw = int16_t(uint16_t(read(address)) << 8 | read(address + 1));
    }
    const unsigned coefficient = ((next.pred_scale >> 4) & 7) * 2;
    const int64_t first = coefficients[coefficient], second = coefficients[coefficient + 1];
    unsigned step = 2;
    int16_t sample;
    if (next.format == 0) {
        if (raw >= 8) {
            raw -= 16;
        }
        const int64_t predictor = 0x400 + first * next.yn1 + second * next.yn2;
        if (predictor < INT32_MIN || predictor > INT32_MAX) {
            throw std::runtime_error("Unverified AXWii predictor overflow");
        }
        const int64_t decoded = (int64_t(1) << (next.pred_scale & 15)) * raw + (predictor >> 11);
        sample = int16_t(std::clamp(decoded, int64_t(-32768), int64_t(32767)));
        next.yn2 = next.yn1;
        next.yn1 = sample;
        ++next.current;
        if ((next.end & 15) == 0 && next.current == next.end) {
            next.current = next.start + 1;
        } else if ((next.end & 15) == 1 && next.current == next.end - 1) {
            next.current = next.start;
        } else if ((next.current & 15) == 0) {
            next.pred_scale = read((next.current & ~15u) >> 1);
            next.current += 2;
            step += 2;
        }
    } else {
        const unsigned shift = next.format == 0x19 ? 0 : 11;
        const int64_t decoded = ((int64_t(next.gain) * raw) >> shift) +
            ((first * next.yn1) >> shift) + ((second * next.yn2) >> shift);
        if (decoded < INT32_MIN || decoded > INT32_MAX) {
            throw std::runtime_error("Unverified AXWii PCM accumulator overflow");
        }
        sample = int16_t(uint16_t(decoded));
        next.yn2 = next.yn1;
        next.yn1 = sample;
        ++next.current;
    }
    if (next.current == next.end + step - 1) {
        next.current = next.start;
        next.stopped = true;
        if (next.looping) {
            next.pred_scale = next.loop_pred_scale & 0x7f;
            if (next.is_stream != 1) {
                next.yn1 = int16_t(next.loop_yn1);
                next.yn2 = int16_t(next.loop_yn2);
            }
            next.stopped = false;
        } else {
            next.running = 0;
        }
    }
    next.current &= 0xbfffffffu;
    state = next;
    return sample;
}

inline int16_t read_axwii_sample(std::span<const uint8_t> memory,
    const std::array<int16_t, 16>& coefficients, AxWiiSampleState& state) {
    return read_axwii_sample_from([&](uint32_t address) {
        if (address >= memory.size()) {
            throw std::runtime_error("AXWii sample outside supplied memory");
        }
        return memory[address];
    }, coefficients, state);
}

}
