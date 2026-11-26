#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

struct AxWiiParameterBlock {
    static constexpr size_t wire_bytes = 300;
    static constexpr size_t expanded_words = 155;
    static constexpr size_t updates_word = 53;
    static constexpr size_t updates_words = 5;
    std::array<uint16_t, expanded_words> words{};

    uint32_t next_address() const {
        return uint32_t(words[0]) << 16 | words[1];
    }

    uint16_t running() const {
        return words[8];
    }
};

inline AxWiiParameterBlock decode_axwii_pb(std::span<const uint8_t> wire, uint32_t profile) {
    if (profile != 0x4cc52064 || wire.size() != AxWiiParameterBlock::wire_bytes) {
        throw std::runtime_error("Unsupported AXWii parameter block");
    }
    AxWiiParameterBlock pb;
    for (size_t index = 0; index < wire.size() / 2; ++index) {
        const size_t expanded = index < pb.updates_word ? index : index + pb.updates_words;
        pb.words[expanded] = uint16_t(uint16_t(wire[index * 2]) << 8 | wire[index * 2 + 1]);
    }
    return pb;
}

inline std::array<uint8_t, AxWiiParameterBlock::wire_bytes> encode_axwii_pb(
    const AxWiiParameterBlock& pb, uint32_t profile) {
    if (profile != 0x4cc52064) {
        throw std::runtime_error("Unsupported AXWii parameter block");
    }
    std::array<uint8_t, AxWiiParameterBlock::wire_bytes> wire{};
    for (size_t index = 0; index < wire.size() / 2; ++index) {
        const size_t expanded = index < pb.updates_word ? index : index + pb.updates_words;
        wire[index * 2] = uint8_t(pb.words[expanded] >> 8);
        wire[index * 2 + 1] = uint8_t(pb.words[expanded]);
    }
    return wire;
}

}
