#include <processor_adapter.h>
#include "runtime/gx/fifo_parser.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <cstdio>
#include <memory>

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<CPUContext>();
    auto& bus = MMIODispatcher::get();
    hw::register_pe(bus);
    hw::pi_intsr = 0;
    hw::pi_intmr = 0;
    for (unsigned mode = 0; mode < 5; ++mode) {
        bus.write32(0xCC00100A, 0x0F);
        assert(hw::g_pe_sr.load() == 0 && hw::pi_intsr.load() == 0);
        const uint8_t reg = mode < 2 ? 0x45 : mode == 2 ? 0x47 : 0x48;
        const uint32_t value = mode == 0 ? 2 : mode == 1 ? 3 : 0x1234;
        std::vector<uint8_t> fifo{0x61, reg, uint8_t(value >> 16), uint8_t(value >> 8), uint8_t(value)};
        if (mode == 4) {
            fifo.pop_back();
        }
        std::vector<gx::GXCommand> commands;
        gx::FifoParser::Parse(fifo, commands);
        const uint32_t expected_pe = mode == 0 ? 8 : mode == 3 ? 4 : 0;
        const uint32_t expected_pi = mode == 0 ? 0x400 : mode == 3 ? 0x200 : 0;
        assert(hw::g_pe_sr.load() == expected_pe && hw::pi_intsr.load() == expected_pi);
        assert(commands.size() == (mode == 4 ? 0u : 1u));
        assert(fifo.size() == (mode == 4 ? 4u : 0u));
        if (mode == 2 || mode == 3) {
            assert(bus.read32(0xCC00100E) == 0x1234);
        }
        std::printf("PARSE_ONLY mode=%u pe=%u pi=%u commands=%zu renderCalls=0\n",
            mode, hw::g_pe_sr.load(), hw::pi_intsr.load(), commands.size());
    }
    std::puts("ACTUAL_PE_FINISH_TOKEN_SIGNAL_DURING_PARSE_BEFORE_RENDER_PASS5");
}
