#include <processor_adapter.h>
#include "runtime/gx/fifo_parser.h"
#include "runtime/gx/tev_shader_gen.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <memory>

namespace nwii::runtime::gx {
extern GXState g_state;
void ApplyBPRegister(uint8_t reg, uint32_t val);
}

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    const bool no_seed = std::getenv("NWII_NOSEED") != nullptr;
    for (unsigned index = 0; index < 8; ++index) {
        gx::g_state = {};
        gx::g_state.numTevStages = 16;
        for (auto& stage : gx::g_state.tevStages) {
            stage.texMap = 0xFF;
            stage.colorChan = 0xFF;
            stage.colorInD = 14;
        }
        const uint8_t reg = 0xF6 + index;
        const auto before = gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source;
        std::vector<uint8_t> fifo{0x61, reg, 0, 1, 0};
        std::vector<gx::GXCommand> commands;
        gx::FifoParser::Parse(fifo, commands);
        assert(fifo.empty() && commands.size() == 1);
        assert(commands[0].reg == reg && commands[0].val == 0x100);
        assert(gx::g_state.bp[reg] == (no_seed ? 0u : 0x100u));
        const auto parsed = gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source;
        assert((parsed != before) == !no_seed);
        gx::ApplyBPRegister(reg, commands[0].val);
        const auto executed = gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source;
        assert(executed != before);
        if (!no_seed) {
            assert(executed == parsed);
        }
        std::printf("BP_SEED_ORDER reg=%u leakedBeforeExecution=%u executedBytes=%zu\n",
            unsigned(reg), unsigned(parsed != before), executed.size());
        std::vector<uint8_t> truncated{0x61, reg, 0, 2};
        commands.clear();
        gx::FifoParser::Parse(truncated, commands);
        assert(commands.empty() && truncated.size() == 4 && gx::g_state.bp[reg] == 0x100);
    }
    std::puts("ACTUAL_LINKED_BP_KONST_FUTURE_STATE_SEED_CONTROL_PASS8");
}
