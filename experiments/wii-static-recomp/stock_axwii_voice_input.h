// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_accelerator.h"
#include "stock_axwii_pb.h"
#include "stock_axwii_resample.h"

namespace openshsm::experiment {

template<class ReadByte>
inline AxWiiResampleResult get_axwii_voice_input_from(AxWiiParameterBlock& pb,
    ReadByte&& read_byte, unsigned count, std::span<const int16_t> coefficient_banks = {}) {
    const unsigned type = pb.words[4];
    const uint32_t ratio = uint32_t(pb.words[88]) << 16 | pb.words[89];
    const uint32_t position = pb.words[90];
    if (!count || count > 96 || type > 2 || (type == 2 && count < 4) ||
        (type != 2 && (ratio < 128 || ratio > 0x40000)) ||
        (!coefficient_banks.empty() && (coefficient_banks.size() != 2048 || pb.words[5] >= 4))) {
        throw std::runtime_error("Unsupported AXWii voice input");
    }
    const auto pair = [&](unsigned index) {
        return uint32_t(pb.words[index]) << 16 | pb.words[index + 1];
    };
    AxWiiSampleState state;
    state.start = pair(62) & 0x3fffffffu;
    state.end = pair(64) & 0x3fffffffu;
    state.current = pair(66) & 0xbfffffffu;
    state.looping = pb.words[60];
    state.format = pb.words[61];
    state.gain = int16_t(pb.words[84]);
    state.pred_scale = pb.words[85] & 0x7f;
    state.yn1 = int16_t(pb.words[86]);
    state.yn2 = int16_t(pb.words[87]);
    state.running = pb.words[8];
    state.is_stream = pb.words[9];
    state.loop_pred_scale = pb.words[95];
    state.loop_yn1 = pb.words[96];
    state.loop_yn2 = pb.words[97];
    std::array<int16_t, 16> adpcm;
    for (unsigned index = 0; index < adpcm.size(); ++index) {
        adpcm[index] = int16_t(pb.words[68 + index]);
    }
    const unsigned needed = type == 2 ? count : unsigned((uint64_t(position) + uint64_t(ratio) * count) >> 16);
    std::array<int16_t, 384> input{};
    for (unsigned index = 0; index < needed; ++index) {
        input[index] = read_axwii_sample_from(read_byte, adpcm, state);
    }
    std::array<int16_t, 4> history;
    for (unsigned index = 0; index < history.size(); ++index) {
        history[index] = int16_t(pb.words[91 + index]);
    }
    const auto bank = coefficient_banks.empty() ? coefficient_banks : coefficient_banks.subspan(pb.words[5] * 512, 512);
    auto output = resample_axwii(std::span(input).first(needed), count, history, position, ratio, type, bank);
    pb.words[8] = state.running;
    pb.words[66] = uint16_t(state.current >> 16);
    pb.words[67] = uint16_t(state.current);
    pb.words[85] = state.pred_scale;
    pb.words[86] = uint16_t(state.yn1);
    pb.words[87] = uint16_t(state.yn2);
    pb.words[90] = uint16_t(output.position);
    for (unsigned index = 0; index < history.size(); ++index) {
        pb.words[91 + index] = uint16_t(output.history[index]);
    }
    return output;
}

inline AxWiiResampleResult get_axwii_voice_input(AxWiiParameterBlock& pb,
    std::span<const uint8_t> memory, unsigned count, std::span<const int16_t> coefficient_banks = {}) {
    return get_axwii_voice_input_from(pb, [&](uint32_t address) {
        if (address >= memory.size()) {
            throw std::runtime_error("AXWii sample outside supplied memory");
        }
        return memory[address];
    }, count, coefficient_banks);
}

}
