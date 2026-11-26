#pragma once
#include <array>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <vector>

namespace openshsm::experiment {

struct AxWiiCommand {
    uint16_t opcode;
    size_t word_offset;
    unsigned argument_count;
    std::array<uint16_t, 13> arguments{};
};

inline std::vector<AxWiiCommand> decode_axwii_commands(std::span<const uint8_t> bytes, uint32_t ucode) {
    if (ucode != 0x4cc52064 || bytes.empty() || bytes.size() > 512 || bytes.size() % 2) {
        throw std::runtime_error("Unsupported AXWii command profile");
    }
    constexpr unsigned argument_counts[] = {2, 2, 2, 2, 2, 5, 5, 5, 13, 13, 4, 5, 5, 8, 0};
    const auto word = [&](size_t index) {
        return uint16_t(uint16_t(bytes[index * 2]) << 8 | bytes[index * 2 + 1]);
    };
    std::vector<AxWiiCommand> result;
    size_t cursor = 0;
    while (cursor < bytes.size() / 2) {
        const size_t offset = cursor;
        const uint16_t opcode = word(cursor++);
        if (opcode > 14) {
            throw std::runtime_error("Unknown AXWii command");
        }
        const unsigned count = argument_counts[opcode];
        if (count > bytes.size() / 2 - cursor) {
            throw std::runtime_error("Truncated AXWii command");
        }
        AxWiiCommand command{opcode, offset, count};
        for (unsigned index = 0; index < count; ++index) {
            command.arguments[index] = word(cursor++);
        }
        result.push_back(command);
        if (opcode == 14) {
            return result;
        }
    }
    throw std::runtime_error("Unterminated AXWii command list");
}

}
