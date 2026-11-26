#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include "runtime/gx/fifo_parser.h"
#include <cassert>
#include <iostream>

namespace nwii::runtime::hw {
void register_pe(MMIODispatcher&);
}

int main() {
    using namespace nwii::runtime;
    using namespace nwii::runtime::gx;
    auto& bus = MMIODispatcher::get();
    hw::register_pe(bus);
    unsigned cases = 0;
    for (uint32_t value : {0u, 2u, 0x12u, 0x102u, 0x4003u, 0x800u}) {
        for (uint8_t reg : {uint8_t(0x45), uint8_t(0x52)}) {
            bus.write32(0xCC00100A, 0xF);
            std::vector<uint8_t> fifo{0x61, reg, uint8_t(value >> 16), uint8_t(value >> 8), uint8_t(value)};
            std::vector<GXCommand> commands;
            FifoParser::Parse(fifo, commands);
            assert(fifo.empty() && commands.size() == 1);
            const bool finish = reg == 0x45 && (value & 0xFF) == 2;
            assert(bool(hw::g_pe_sr.load() & 8) == finish);
            bus.write32(0xCC00100A, 0xF);
            ApplyBPRegister(reg, value);
            assert(!(hw::g_pe_sr.load() & 8));
            ++cases;
        }
    }
    std::cout << "PASS " << std::dec << cases << " actual parser/apply DrawDone vs EFB-copy cases\n";
}
