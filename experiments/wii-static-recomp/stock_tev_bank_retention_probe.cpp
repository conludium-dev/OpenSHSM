#include "runtime/gx/fifo_parser.h"
#include "runtime/gx_state.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>

extern void stock_read_tev_uniforms(float* color, float* kcolor);

static uint32_t pair(int first, int second, unsigned bank) {
    return (first & 0x7FF) | ((second & 0x7FF) << 12) | (bank << 23);
}

static void append(std::vector<uint8_t>& fifo, unsigned reg, uint32_t word) {
    fifo.insert(fifo.end(), {0x61, uint8_t(reg), uint8_t(word >> 16), uint8_t(word >> 8), uint8_t(word)});
}

int main() {
    using namespace nwii::runtime::gx;
    unsigned cases = 0;
    for (unsigned slot = 0; slot < 4; ++slot) {
        for (unsigned last = 0; last < 2; ++last) {
            std::memset(g_state.tevColorWords, 0, sizeof(g_state.tevColorWords));
            std::vector<uint8_t> fifo;
            const int values[2][4] = {{-1024, 1023, -1, 255}, {31, 159, 95, 63}};
            for (unsigned bank : {1 - last, last}) {
                append(fifo, 0xE0 + slot * 2, pair(values[bank][0], values[bank][3], bank));
                append(fifo, 0xE1 + slot * 2, pair(values[bank][2], values[bank][1], bank));
            }
            std::vector<GXCommand> commands;
            FifoParser::Parse(fifo, commands);
            assert(commands.size() == 4);
            for (auto& bank : g_state.tevColorWords) {
                for (auto value : bank) {
                    assert(value == 0);
                }
            }
            for (const auto& command : commands) {
                ApplyBPRegister(command.reg, command.val);
            }
            float color[16] = {}, kcolor[16] = {};
            stock_read_tev_uniforms(color, kcolor);
            for (unsigned bank = 0; bank < 2; ++bank) {
                const float* actual = bank == 0 ? color : kcolor;
                for (unsigned component = 0; component < 4; ++component) {
                    assert(std::abs(actual[4 * slot + component] - values[bank][component] / 255.0f) < 1e-6f);
                }
            }
            uint32_t before[2][8];
            std::memcpy(before, g_state.tevColorWords, sizeof(before));
            ApplyBPRegister(0xE0 + 2 * slot, pair(17, 19, last));
            for (unsigned bank = 0; bank < 2; ++bank) {
                for (unsigned word = 0; word < 8; ++word) {
                    assert(g_state.tevColorWords[bank][word] == ((bank == last && word == slot * 2)
                        ? pair(17, 19, last) : before[bank][word]));
                }
            }
            ApplyBPRegister(0xE1 + 2 * slot, pair(23, 29, 1 - last));
            assert(g_state.tevColorWords[last][slot * 2] == pair(17, 19, last));
            assert(g_state.tevColorWords[1 - last][slot * 2 + 1] == pair(23, 29, 1 - last));
            std::memcpy(before, g_state.tevColorWords, sizeof(before));
            ApplyBPRegister(0xE8, 0x123456);
            assert(std::memcmp(before, g_state.tevColorWords, sizeof(before)) == 0);
            ++cases;
        }
    }
    std::cout << "TEV_BANK_RETENTION_FIFO_REPLAY_PASS " << cases << " parse-order/independent-pairs/signed-boundaries\n";
}
