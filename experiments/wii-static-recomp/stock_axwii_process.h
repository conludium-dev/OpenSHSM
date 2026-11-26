// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_voice.h"

namespace openshsm::experiment {

template<class ResolvePB, class ReadByte>
inline unsigned process_axwii_pb_list(uint32_t address, AxWiiMainBuffers& main,
    AxWiiRemoteBuffers& remote, ResolvePB&& resolve_pb, ReadByte&& read_byte,
    std::span<const int16_t> coefficient_banks = {}, uint32_t profile = 0x4cc52064) {
    if (profile != 0x4cc52064) {
        throw std::runtime_error("Unsupported AXWii list profile");
    }
    std::array<uint32_t, 256> visited{};
    unsigned count = 0;
    while (address) {
        const uint32_t physical = address & 0x3fffffffu;
        if ((address & 1) || count == visited.size() ||
            std::find(visited.begin(), visited.begin() + count, physical) != visited.begin() + count) {
            throw std::runtime_error("Invalid or unbounded AXWii PB chain");
        }
        auto destination = resolve_pb(address, AxWiiParameterBlock::wire_bytes);
        if (destination.size() != AxWiiParameterBlock::wire_bytes) {
            throw std::runtime_error("Truncated AXWii PB memory");
        }
        auto pb = decode_axwii_pb(destination, profile);
        process_axwii_voice_from(pb, main, remote, read_byte, coefficient_banks);
        const auto wire = encode_axwii_pb(pb, profile);
        std::copy(wire.begin(), wire.end(), destination.begin());
        visited[count++] = physical;
        address = pb.next_address();
    }
    return count;
}

}
