#include "runtime/gx/fifo_parser.h"
#include "runtime/gx_state.h"
#include <cassert>
#include <cmath>
#include <iostream>

extern void stock_read_tev_uniforms(float* color, float* kcolor);

static void write(std::vector<uint8_t>& fifo, unsigned address, uint32_t word) {
    fifo.push_back(0x61);
    fifo.push_back(address);
    fifo.push_back(word >> 16);
    fifo.push_back(word >> 8);
    fifo.push_back(word);
}

static uint32_t pair(int first, int second, unsigned bank) {
    return (first & 0x7FF) | ((second & 0x7FF) << 12) | (bank << 23);
}

int main() {
    using namespace nwii::runtime::gx;
    unsigned cases = 0;
    for (unsigned slot = 0; slot < 4; ++slot) {
        for (unsigned last = 0; last < 2; ++last) {
            std::vector<uint8_t> fifo;
            const unsigned first = 1 - last;
            const int r[2] = {127, 31}, a[2] = {255, 63};
            const int b[2] = {-128, 95}, g[2] = {1023, 159};
            write(fifo, 0xE0 + 2 * slot, pair(r[first], a[first], first));
            write(fifo, 0xE1 + 2 * slot, pair(b[first], g[first], first));
            write(fifo, 0xE0 + 2 * slot, pair(r[last], a[last], last));
            write(fifo, 0xE1 + 2 * slot, pair(b[last], g[last], last));
            std::vector<GXCommand> commands;
            FifoParser::Parse(fifo, commands);
            assert(commands.size() == 4);
            for (const auto& command : commands) {
                assert(command.type == GXCommandType::BPRegister);
                ApplyBPRegister(command.reg, command.val);
            }
            float color[16] = {}, kcolor[16] = {};
            stock_read_tev_uniforms(color, kcolor);
            const float* retained = last ? kcolor : color;
            const float* lost = last ? color : kcolor;
            const unsigned offset = 4 * slot;
            assert(std::abs(retained[offset] - r[last] / 255.0f) < 1e-6f);
            assert(std::abs(retained[offset + 1] - g[last] / 255.0f) < 1e-6f);
            assert(std::abs(retained[offset + 2] - b[last] / 255.0f) < 1e-6f);
            assert(std::abs(retained[offset + 3] - a[last] / 255.0f) < 1e-6f);
            for (unsigned component = 0; component < 4; ++component) {
                assert(lost[offset + component] == 0.0f);
            }
            ++cases;
        }
    }
    std::cout << "ACTUAL_FIFO_RENDER_UNIFORM_BANK_LOSS_REPRODUCED " << cases << '\n';
}
