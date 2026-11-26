// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_remote_mix.h"
#include <type_traits>

namespace openshsm::experiment {

struct AxWiiOutput {
    AxWiiMainBuffers next_main;
    std::array<uint8_t, 384> stereo{}, surround{}, auxc{};
    std::array<std::array<uint8_t, 36>, 4> wiimote{};
    uint16_t next_volume;
    bool upload_auxc;
    static constexpr uint32_t sync_mail = 0xdcd10004;
};

inline AxWiiOutput prepare_axwii_output(const AxWiiMainBuffers& main,
    const AxWiiRemoteBuffers& remote, uint16_t previous_volume, uint16_t volume, bool upload_auxc) {
    AxWiiOutput output;
    output.next_main = main;
    output.next_volume = volume;
    output.upload_auxc = upload_auxc;
    const auto word16 = [](uint8_t* bytes, uint16_t value) {
        bytes[0] = uint8_t(value >> 8);
        bytes[1] = uint8_t(value);
    };
    const auto word32 = [](uint8_t* bytes, uint32_t value) {
        for (unsigned index = 0; index < 4; ++index) {
            bytes[index] = uint8_t(value >> (24 - index * 8));
        }
    };
    float current_volume = previous_volume;
    const float delta = (int(volume) - int(previous_volume)) / 96.0f;
    for (unsigned index = 0; index < 96; ++index) {
        current_volume += delta;
        const uint16_t ramp = uint16_t(current_volume);
        word32(output.surround.data() + index * 4, uint32_t(main[2][index]));
        if (upload_auxc) {
            word32(output.auxc.data() + index * 4, uint32_t(main[9][index]));
        }
        for (unsigned channel = 0; channel < 2; ++channel) {
            const int64_t scaled = (int64_t(main[channel][index]) * ramp) >> 15;
            output.next_main[channel][index] = int32_t(std::clamp(scaled, int64_t(-32768), int64_t(32767)));
        }
        word16(output.stereo.data() + index * 4, uint16_t(output.next_main[1][index]));
        word16(output.stereo.data() + index * 4 + 2, uint16_t(output.next_main[0][index]));
    }
    for (unsigned channel = 0; channel < 4; ++channel) {
        for (unsigned index = 0; index < 18; ++index) {
            const int16_t sample = int16_t(std::clamp(remote[channel * 2][index], int32_t(-32768), int32_t(32767)));
            word16(output.wiimote[channel].data() + index * 2, uint16_t(sample));
        }
    }
    return output;
}

// Resolve must return side-effect-free backed RAM spans; signal must not throw after committed writes.
template<class Resolve, class Signal>
inline void commit_axwii_output(const AxWiiOutput& output, AxWiiMainBuffers& main,
    uint16_t& volume, uint32_t lr_address, uint32_t surround_address, Resolve&& resolve, Signal&& signal) {
    static_assert(std::is_nothrow_invocable_v<Signal, uint32_t>);
    if (output.upload_auxc && uint64_t(surround_address) + output.surround.size() > UINT32_MAX) {
        throw std::runtime_error("Invalid AXWii auxC output address");
    }
    auto surround = resolve(surround_address, output.surround.size());
    std::span<uint8_t> auxc;
    if (output.upload_auxc) {
        auxc = resolve(surround_address + uint32_t(output.surround.size()), output.auxc.size());
    }
    auto stereo = resolve(lr_address, output.stereo.size());
    if (surround.size() != output.surround.size() || stereo.size() != output.stereo.size() ||
            (output.upload_auxc && auxc.size() != output.auxc.size())) {
        throw std::runtime_error("Invalid AXWii output RAM spans");
    }
    std::copy(output.surround.begin(), output.surround.end(), surround.begin());
    if (output.upload_auxc) {
        std::copy(output.auxc.begin(), output.auxc.end(), auxc.begin());
    }
    std::copy(output.stereo.begin(), output.stereo.end(), stereo.begin());
    main = output.next_main;
    volume = output.next_volume;
    signal(output.sync_mail);
}

template<class Resolve>
inline void commit_axwii_wm_output(const AxWiiOutput& output,
    const std::array<uint32_t, 4>& addresses, Resolve&& resolve) {
    std::array<std::span<uint8_t>, 4> targets;
    for (unsigned channel = 0; channel < 4; ++channel) {
        targets[channel] = resolve(addresses[channel], output.wiimote[channel].size());
        if (targets[channel].size() != output.wiimote[channel].size()) {
            throw std::runtime_error("Invalid AXWii Wiimote output RAM span");
        }
    }
    for (unsigned channel = 0; channel < 4; ++channel) {
        std::copy(output.wiimote[channel].begin(), output.wiimote[channel].end(), targets[channel].begin());
    }
}

}
