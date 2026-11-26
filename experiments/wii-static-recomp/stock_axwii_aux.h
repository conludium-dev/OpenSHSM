// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_buffers.h"

namespace openshsm::experiment {

inline std::array<uint16_t, 96> axwii_aux_ramp(uint16_t previous, uint16_t volume) {
    std::array<uint16_t, 96> result;
    float current = previous;
    for (auto& value : result) {
        current += (int(volume) - int(previous)) / 96.0f;
        value = uint16_t(current);
    }
    return result;
}

inline void write_axwii_aux_buffer(std::span<uint8_t> destination,
    const std::array<int32_t, 96>& buffer) {
    if (destination.size() != 384) {
        throw std::runtime_error("Invalid AXWii auxiliary output span");
    }
    for (unsigned index = 0; index < 96; ++index) {
        const uint32_t word = uint32_t(buffer[index]);
        for (unsigned byte = 0; byte < 4; ++byte) {
            destination[index * 4 + byte] = uint8_t(word >> (24 - byte * 8));
        }
    }
}

template<class Resolve>
inline void mix_axwii_aux(AxWiiMainBuffers& main, std::array<uint16_t, 3>& volumes,
    unsigned id, uint16_t volume, uint32_t write_address, uint32_t read_address, Resolve&& resolve) {
    if (id >= 3) {
        throw std::runtime_error("Invalid AXWii auxiliary channel");
    }
    std::span<uint8_t> upload;
    if (write_address) {
        upload = resolve(write_address, 1152);
        if (upload.size() != 1152) {
            throw std::runtime_error("Invalid AXWii auxiliary upload span");
        }
    }
    const auto input = resolve(read_address, 1152);
    if (input.size() != 1152) {
        throw std::runtime_error("Invalid AXWii auxiliary input span");
    }
    const auto ramp = axwii_aux_ramp(volumes[id], volume);
    if (write_address) {
        for (unsigned channel = 0; channel < 3; ++channel) {
            write_axwii_aux_buffer(upload.subspan(channel * 384, 384), main[3 + id * 3 + channel]);
        }
    }
    auto next = main;
    for (unsigned channel = 0; channel < 3; ++channel) {
        for (unsigned index = 0; index < 96; ++index) {
            const int64_t sample = axwii_buffer_word(input, channel * 384 + index * 4);
            next[channel][index] = axwii_buffer_checked(int64_t(main[channel][index]) + ((sample * ramp[index]) >> 15));
        }
    }
    main = next;
    volumes[id] = volume;
}

template<class Resolve>
inline void upload_axwii_aux_lrsc(AxWiiMainBuffers& main, std::array<uint16_t, 3>& volumes,
    unsigned id, uint16_t volume, const std::array<uint32_t, 6>& addresses, Resolve&& resolve) {
    if (id >= 2) {
        throw std::runtime_error("Invalid AXWii LRSC auxiliary channel");
    }
    auto upload = resolve(addresses[0], 1152);
    auto auxc = resolve(addresses[1], 384);
    std::array<std::span<uint8_t>, 4> inputs;
    if (upload.size() != 1152 || auxc.size() != 384) {
        throw std::runtime_error("Invalid AXWii LRSC upload span");
    }
    for (unsigned index = 0; index < 4; ++index) {
        inputs[index] = resolve(addresses[index + 2], 384);
        if (inputs[index].size() != 384) {
            throw std::runtime_error("Invalid AXWii LRSC input span");
        }
    }
    const unsigned base = 3 + id * 3;
    for (unsigned channel = 0; channel < 3; ++channel) {
        write_axwii_aux_buffer(upload.subspan(channel * 384, 384), main[base + channel]);
    }
    write_axwii_aux_buffer(auxc, main[id ? 11 : 10]);
    const auto ramp = axwii_aux_ramp(volumes[id], volume);
    auto next = main;
    constexpr unsigned destinations[] = {0, 1, 2, 9};
    for (unsigned channel = 0; channel < 4; ++channel) {
        for (unsigned index = 0; index < 96; ++index) {
            const int64_t sample = axwii_buffer_word(inputs[channel], index * 4);
            next[base][index] = int32_t(sample);
            next[destinations[channel]][index] = axwii_buffer_checked(
                int64_t(next[destinations[channel]][index]) + ((sample * ramp[index]) >> 15));
        }
    }
    main = next;
    volumes[id] = volume;
}

}
