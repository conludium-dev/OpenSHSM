#include "stock_gx_completed_frame.h"
#include <array>
#include <cassert>
#include <cstdio>

using nwii::runtime::gx::GXCommand;
using nwii::runtime::gx::GXCommandType;

static GXCommand bp(uint16_t reg, uint32_t value) {
    GXCommand command{};
    command.type = GXCommandType::BPRegister;
    command.reg = reg;
    command.val = value;
    return command;
}

int main() {
    GXCommand draw{};
    draw.type = GXCommandType::DrawPrimitive;
    const std::array<GXCommand, 7> alphabet = {draw, bp(0x52, 0x4000), bp(0x45, 2),
        bp(0x47, 0x1234), bp(0x48, 0x5678), bp(0x52, 0), bp(0x45, 3)};
    size_t cases = 0;
    size_t combinations = 1;
    for (size_t length = 0; length <= 6; ++length) {
        for (size_t value = 0; value < combinations; ++value) {
            size_t remainder = value;
            std::vector<GXCommand> commands;
            std::vector<unsigned> symbols;
            for (size_t index = 0; index < length; ++index) {
                const unsigned symbol = remainder % alphabet.size();
                remainder /= alphabet.size();
                commands.push_back(alphabet[symbol]);
                symbols.push_back(symbol);
            }
            int expected_copy = -1;
            int expected_previous = -1;
            int expected_end = -1;
            for (int index = int(length) - 1; index >= 0; --index) {
                if (symbols[index] == 1) {
                    if (expected_copy < 0) {
                        expected_copy = index;
                    } else {
                        expected_previous = index;
                        break;
                    }
                }
            }
            if (expected_copy >= 0) {
                expected_end = expected_copy;
            } else {
                for (int index = int(length) - 1; index >= 0; --index) {
                    if (symbols[index] >= 2 && symbols[index] <= 4) {
                        expected_end = index;
                        break;
                    }
                }
            }
            const auto bounds = stock_gx_completed_frame_bounds(commands);
            assert(bounds.end == expected_end);
            assert(bounds.last_copy == expected_copy);
            assert(bounds.previous_copy == expected_previous);
            auto carry = commands;
            size_t consumed = 0;
            unsigned drains = 0;
            while (true) {
                const auto next = stock_gx_completed_frame_bounds(carry);
                if (next.end < 0) {
                    break;
                }
                assert(++drains <= 2);
                const size_t count = size_t(next.end) + 1;
                assert(count <= carry.size());
                consumed += count;
                carry.erase(carry.begin(), carry.begin() + count);
            }
            for (size_t index = consumed; index < symbols.size(); ++index) {
                assert(symbols[index] != 1 && (symbols[index] < 2 || symbols[index] > 4));
            }
            ++cases;
        }
        combinations *= alphabet.size();
    }
    assert(cases == 137257);
    const auto legacy = stock_gx_execution_bounds({draw, bp(0x52, 0x4000), draw, bp(0x45, 2), draw});
    const auto candidate = stock_gx_completed_frame_bounds({draw, bp(0x52, 0x4000), draw, bp(0x45, 2), draw});
    assert(legacy.end == 3 && candidate.end == 1 && candidate.last_copy == 1);
    std::printf("COMPLETED_COPY_CUTOFF_EXHAUSTIVE_%zu_CARRY_PE_DRAIN_PASS\n", cases);
}
