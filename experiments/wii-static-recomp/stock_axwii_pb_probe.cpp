#include "stock_axwii_pb.h"
#include "axwii-pb-reference.h"
#include <cstring>
#include <iostream>

using openshsm::experiment::AxWiiParameterBlock;
using openshsm::experiment::decode_axwii_pb;
using openshsm::experiment::encode_axwii_pb;

static void require(bool result) {
    if (!result) {
        throw std::runtime_error("AXWii PB comparison failed");
    }
}

int main() {
    static_assert(sizeof(AXPBWii) == 310);
    static_assert(offsetof(AXPBWii, updates) == 106);
    static_assert(sizeof(PBUpdatesWii) == 10);
    constexpr uint32_t profile = 0x4cc52064;
    uint32_t random = 0x5348534d;
    AXWiiUCode reference;
    Memory::MemoryManager memory;
    unsigned cases = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        std::array<uint8_t, 300> wire;
        for (auto& byte : wire) {
            random ^= random << 13;
            random ^= random >> 17;
            random ^= random << 5;
            byte = uint8_t(random);
        }
        std::copy(wire.begin(), wire.end(), memory.bytes.begin() + 16);
        const auto original_memory = memory.bytes;
        AXPBWii ref;
        std::memset(&ref, 0xa5, sizeof(ref));
        reference.ReadPB(memory, 16, ref);
        const auto decoded = decode_axwii_pb(wire, profile);
        require(std::memcmp(&ref, decoded.words.data(), sizeof(ref)) == 0);
        require(memory.bytes == original_memory);
        require(decoded.next_address() == (uint32_t(ref.next_pb_hi) << 16 | ref.next_pb_lo));
        require(decoded.running() == ref.running);
        require(encode_axwii_pb(decoded, profile) == wire);
        ++cases;

        auto changed = decoded;
        for (size_t index = 0; index < changed.words.size(); ++index) {
            changed.words[index] ^= uint16_t(index * 997 + fixture);
        }
        std::memcpy(&ref, changed.words.data(), sizeof(ref));
        memory.bytes.fill(0x5a);
        reference.WritePB(memory, 16, ref);
        const auto encoded = encode_axwii_pb(changed, profile);
        require(std::equal(encoded.begin(), encoded.end(), memory.bytes.begin() + 16));
        for (size_t index = 0; index < memory.bytes.size(); ++index) {
            if (index < 16 || index >= 316) {
                require(memory.bytes[index] == 0x5a);
            }
        }
        ++cases;
    }
    unsigned refused = 0;
    for (size_t size : {size_t(0), size_t(1), size_t(298), size_t(299), size_t(301), size_t(310)}) {
        std::array<uint8_t, 512> bytes{};
        try {
            (void)decode_axwii_pb(std::span(bytes).first(size), profile);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    for (uint32_t variant : {0u, 0x7699af32u, 0x347112bau, 0xadbc06bdu}) {
        std::array<uint8_t, 300> bytes{};
        try {
            (void)decode_axwii_pb(bytes, variant);
        } catch (const std::runtime_error&) {
            ++refused;
        }
        try {
            (void)encode_axwii_pb(AxWiiParameterBlock{}, variant);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    require(refused == 14);
    std::cout << "AXWII_PB_REFERENCE_ROUNDTRIP_COMPONENT_PASS " << cases
              << " comparisons;" << refused << " refusals\n";
}
