#include <processor_adapter.h>
#include "runtime/gx/fifo_parser.h"
#include "runtime/hw/hw.h"
#include "stock_gx_completion.h"
#include <cassert>
#include <cstdio>
#include <memory>

static nwii::runtime::gx::GXCommand command(uint16_t reg, uint32_t value) {
    nwii::runtime::gx::GXCommand result{};
    result.type = nwii::runtime::gx::GXCommandType::BPRegister;
    result.reg = reg;
    result.val = value;
    return result;
}
int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    auto& bus = MMIODispatcher::get();
    hw::register_pe(bus);
    hw::pi_intsr = 0;
    hw::pi_intmr = 0;
    for (unsigned mode = 0; mode < 5; ++mode) {
        bus.write32(0xCC00100A, 0x0F);
        const uint8_t reg = mode < 2 ? 0x45 : mode == 2 ? 0x47 : 0x48;
        const uint32_t value = mode == 0 ? 2 : mode == 1 ? 3 : 0x5678;
        std::vector<uint8_t> fifo{0x61, reg, uint8_t(value >> 16), uint8_t(value >> 8), uint8_t(value)};
        if (mode == 4) {
            fifo.pop_back();
        }
        std::vector<gx::GXCommand> commands;
        gx::FifoParser::Parse(fifo, commands);
        assert(hw::g_pe_sr.load() == 0 && hw::pi_intsr.load() == 0);
        assert(commands.size() == (mode == 4 ? 0u : 1u));
        for (const auto& item : commands) {
            gx::ApplyBPRegister(item.reg, item.val);
        }
        assert(hw::g_pe_sr.load() == (mode == 0 ? 8u : mode == 3 ? 4u : 0u));
        assert(hw::pi_intsr.load() == (mode == 0 ? 0x400u : mode == 3 ? 0x200u : 0u));
        if (mode == 2 || mode == 3) {
            assert(bus.read32(0xCC00100E) == 0x5678);
        }
    }
    gx::GXCommand draw{};
    draw.type = gx::GXCommandType::DrawPrimitive;
    assert(stock_gx_execution_bounds({}).end == -1);
    assert(stock_gx_execution_bounds({draw, command(0x45, 3)}).end == -1);
    for (auto completed : {command(0x45, 2), command(0x47, 0x1234), command(0x48, 0x5678)}) {
        const auto alone = stock_gx_execution_bounds({draw, completed, draw});
        assert(alone.end == 1 && alone.previous_copy == -1);
    }
    const auto copy = command(0x52, 0x4000);
    const auto finish = command(0x45, 2);
    const auto combined = stock_gx_execution_bounds({draw, copy, draw, copy, draw, finish, draw});
    assert(combined.end == 5 && combined.previous_copy == 1);
    const auto preceding = stock_gx_execution_bounds({draw, finish, draw, copy, draw});
    assert(preceding.end == 3 && preceding.previous_copy == -1);
    std::puts("PE_PARSE_NO_ACK_APPLY_ACK5_COMPLETION_PREFIX_BOUNDS7_PASS");
}
