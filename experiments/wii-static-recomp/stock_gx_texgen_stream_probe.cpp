#include "runtime/gx/fifo_parser.h"
#include <array>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    using namespace nwii::runtime::gx;
    if (argc != 2) {
        return 2;
    }
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) {
        return 3;
    }
    std::vector<uint8_t> fifo(std::istreambuf_iterator<char>{file}, {});
    const size_t input_size = fifo.size();
    std::vector<GXCommand> commands;
    FifoParser::Parse(fifo, commands);
    std::array<uint32_t, 8> controls{};
    std::array<bool, 8> known{};
    std::array<uint64_t, 8> uv_rows{};
    std::array<uint64_t, 4> special_rows{};
    uint8_t generators = 0;
    bool count_known = false;
    uint64_t draws = 0, regular = 0, other = 0, unresolved = 0, zero = 0;
    for (const auto& command : commands) {
        if (command.type == GXCommandType::BPRegister && command.reg == 0) {
            generators = command.val & 15;
            count_known = true;
        } else if (command.type == GXCommandType::XFRegister) {
            for (size_t index = 0; index < command.payload.size(); ++index) {
                const unsigned address = command.reg + index;
                if (address >= 0x1040 && address <= 0x1047) {
                    controls[address - 0x1040] = std::bit_cast<uint32_t>(command.payload[index]);
                    known[address - 0x1040] = true;
                }
            }
        } else if (command.type == GXCommandType::DrawPrimitive) {
            ++draws;
            if (!count_known || generators > 8) {
                ++unresolved;
                continue;
            }
            if (generators == 0) {
                ++zero;
                continue;
            }
            bool complete = true, all_regular = true;
            for (unsigned index = 0; index < generators; ++index) {
                complete &= known[index];
                all_regular &= ((controls[index] >> 4) & 7) == 0;
            }
            if (!complete) {
                ++unresolved;
                continue;
            }
            if (!all_regular) {
                ++other;
                continue;
            }
            ++regular;
            for (unsigned index = 0; index < generators; ++index) {
                const unsigned row = (controls[index] >> 7) & 31;
                if (row >= 5 && row <= 12) {
                    ++uv_rows[row - 5];
                } else if (row < 4) {
                    ++special_rows[row];
                }
            }
        }
    }
    std::printf("GX_STREAM_TEXGEN input=%zu remaining=%zu commands=%zu draws=%llu regular=%llu other=%llu unresolved=%llu zero=%llu\n",
        input_size, fifo.size(), commands.size(), draws, regular, other, unresolved, zero);
    std::printf("GX_STREAM_UV_ROWS");
    for (const auto value : uv_rows) {
        std::printf(" %llu", value);
    }
    std::printf("\nGX_STREAM_SPECIAL_ROWS");
    for (const auto value : special_rows) {
        std::printf(" %llu", value);
    }
    std::puts("");
    return draws > 0 ? 0 : 4;
}
