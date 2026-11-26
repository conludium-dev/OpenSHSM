#include <processor_adapter.h>
#include "runtime/gx/fifo_parser.h"
#include "runtime/gx/tev_shader_gen.h"
#include <cassert>
#include <cstdio>
#include <memory>

namespace nwii::runtime {
extern MMU* g_mmu;
namespace gx {
extern GXState g_state;
}
}

static void word(std::vector<uint8_t>& bytes, uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8) {
        bytes.push_back(uint8_t(value >> shift));
    }
}

static std::vector<uint8_t> masked(uint8_t reg, uint32_t mask, uint32_t value) {
    std::vector<uint8_t> result{0x78, 0, reg};
    word(result, mask);
    word(result, value);
    return result;
}

int main() {
    using namespace nwii::runtime;
    auto ctx = std::make_unique<CPUContext>();
    g_mmu = &ctx->mmu;
    gx::g_state = {};
    gx::g_state.numTevStages = 16;
    gx::g_state.bp[0x41] = 0x123456;
    for (auto& stage : gx::g_state.tevStages) {
        stage.texMap = stage.colorChan = 0xFF;
        stage.colorInD = 14;
    }
    for (unsigned index = 0; index < 8; ++index) {
        const uint8_t reg = 0xF6 + index;
        const auto before = gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source;
        std::vector<uint8_t> fifo{0x61, reg, 0, 1, 0};
        std::vector<gx::GXCommand> commands;
        gx::FifoParser::Parse(fifo, commands);
        assert(fifo.empty() && commands.size() == 1 && commands[0].val == 0x100);
        assert(gx::g_state.bp[reg] == 0);
        assert(gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source == before);
        fifo = masked(reg, 0xFF, 0x55);
        gx::FifoParser::Parse(fifo, commands);
        assert(commands.size() == 2 && commands.back().val == 0x155 && gx::g_state.bp[reg] == 0);
        const auto split = masked(reg, 0xF00, 0xB00);
        fifo.assign(split.begin(), split.end() - 1);
        gx::FifoParser::Parse(fifo, commands);
        assert(commands.size() == 2 && fifo.size() == 10 && gx::g_state.bp[reg] == 0);
        fifo.push_back(split.back());
        gx::FifoParser::Parse(fifo, commands);
        assert(fifo.empty() && commands.size() == 3 && commands.back().val == 0xB55);
        assert(gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source == before);
        for (const auto& command : commands) {
            gx::ApplyBPRegister(uint8_t(command.reg), command.val);
            assert(gx::g_state.bp[reg] == command.val);
        }
        assert(gx::GenerateTEVShader(gx::g_state, 0x80).fragment_source != before);
    }
    auto initial = masked(0x41, 0xFF, 0xAA);
    std::vector<gx::GXCommand> commands;
    gx::FifoParser::Parse(initial, commands);
    assert(commands.size() == 1 && commands[0].val == 0x1234AA && gx::g_state.bp[0x41] == 0x123456);
    const uint32_t address = 0x80580000;
    const auto dl = masked(0xF6, 0xFF, 0xAA);
    for (size_t index = 0; index < dl.size(); ++index) {
        ctx->mmu.write8(address + uint32_t(index), dl[index]);
    }
    for (unsigned iteration = 0; iteration < 3; ++iteration) {
        std::vector<uint8_t> call{0x40};
        word(call, address);
        word(call, uint32_t(dl.size()));
        commands.clear();
        const auto hits = gx::g_prof_dl_hits;
        gx::FifoParser::Parse(call, commands);
        assert(call.empty() && commands.size() == 1 && commands[0].val == 0xBAA);
        assert(gx::g_state.bp[0xF6] == 0xB55);
        if (iteration == 2) {
            assert(gx::g_prof_dl_hits == hits + 1);
        }
    }
    std::vector<uint8_t> changed{0x61, 0xF6, 0, 0xC, 0x55, 0x40};
    word(changed, address);
    word(changed, uint32_t(dl.size()));
    commands.clear();
    const auto hits = gx::g_prof_dl_hits;
    gx::FifoParser::Parse(changed, commands);
    assert(changed.empty() && commands.size() == 2 && commands.back().val == 0xCAA);
    assert(gx::g_prof_dl_hits == hits && gx::g_state.bp[0xF6] == 0xB55);
    std::puts("BP_ORDER_DIRECT8_MASK8_SPLIT8_APPLY24_INITIAL1_DL4_KONST8_PASS");
}
