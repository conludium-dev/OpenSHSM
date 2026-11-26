// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_voice_input.h"
#include "stock_axwii_remote_mix.h"

namespace openshsm::experiment {

inline uint32_t axwii_mixer_control(uint32_t original) {
    constexpr unsigned input_shifts[] = {0, 16, 21, 26};
    constexpr unsigned output_bits[] = {1, 4, 15, 16, 48};
    uint32_t result = 0;
    for (unsigned group = 0; group < 4; ++group) {
        for (unsigned bit = 0; bit < 5; ++bit) {
            if (original & (1u << (input_shifts[group] + bit))) {
                result |= output_bits[bit] << (group * 6);
            }
        }
    }
    return result;
}

template<class ReadByte>
inline void process_axwii_voice_from(AxWiiParameterBlock& pb, AxWiiMainBuffers& main,
    AxWiiRemoteBuffers& remote, ReadByte&& read_byte,
    std::span<const int16_t> coefficient_banks = {}) {
    if (pb.running() != 1) {
        return;
    }
    if (pb.words[34]) {
        throw std::runtime_error("Unverified AXWii initial time delay");
    }
    auto next_pb = pb;
    auto next_main = main;
    auto next_remote = remote;
    const uint32_t original_control = uint32_t(pb.words[6]) << 16 | pb.words[7];
    const auto input = get_axwii_voice_input_from(next_pb, read_byte, 96, coefficient_banks);
    const auto samples = mix_axwii_main_voice(next_pb, next_main, input.output, axwii_mixer_control(original_control));
    const auto remote_bank = coefficient_banks.empty() ? coefficient_banks : coefficient_banks.first(512);
    mix_axwii_remote(next_pb, next_remote, samples, remote_bank);
    pb = next_pb;
    main = next_main;
    remote = next_remote;
}

inline void process_axwii_voice(AxWiiParameterBlock& pb, AxWiiMainBuffers& main,
    AxWiiRemoteBuffers& remote, std::span<const uint8_t> memory,
    std::span<const int16_t> coefficient_banks = {}) {
    process_axwii_voice_from(pb, main, remote, [&](uint32_t address) {
        if (address >= memory.size()) {
            throw std::runtime_error("AXWii sample outside supplied memory");
        }
        return memory[address];
    }, coefficient_banks);
}

}
