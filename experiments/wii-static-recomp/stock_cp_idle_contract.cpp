#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <iostream>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
extern uint16_t GX_CPIdleBits();
extern void GX_WGPIPE_Write8(uint8_t);
namespace hw { extern void register_cp(MMIODispatcher&); }
}
extern void ProcessGXFifo();

int main() {
    using namespace nwii::runtime;
    MMU memory;
    g_mmu = &memory;
    g_ctx_ptr = nullptr;
    auto& bus = MMIODispatcher::get();
    hw::register_cp(bus);
    assert(GX_CPIdleBits() == 0x0C);
    assert((bus.read32(0xCC000000) & 0x0C) == 0x0C);
    GX_WGPIPE_Write8(0);
    assert(GX_CPIdleBits() == 0);
    assert((bus.read32(0xCC000000) & 0x0C) == 0);
    ProcessGXFifo();
    assert(GX_CPIdleBits() == 0x0C);
    GX_WGPIPE_Write8(0x08);
    ProcessGXFifo();
    assert(GX_CPIdleBits() == 0x04);
    assert((bus.read32(0xCC000000) & 0x0C) == 0x04);
    for (unsigned i = 0; i < 5; ++i) {
        GX_WGPIPE_Write8(0);
    }
    assert(GX_CPIdleBits() == 0);
    ProcessGXFifo();
    assert(GX_CPIdleBits() == 0x0C);
    unsigned cases = 0;
    for (unsigned distance : {0u, 32u}) {
        for (bool equal : {false, true}) {
            for (bool breakpoint : {false, true}) {
                for (bool enabled : {false, true}) {
                    bus.write32(0xCC000030, distance);
                    bus.write32(0xCC000034, 0x2000);
                    bus.write32(0xCC000038, equal ? 0x2000 : 0x1000);
                    bus.write32(0xCC00003C, breakpoint ? (equal ? 0x2000 : 0x1000) : 0x3000);
                    bus.write32(0xCC000002, 2 | (enabled ? 1 : 0));
                    const uint32_t status = bus.read32(0xCC000000);
                    assert(bool(status & 4) == (distance == 0 || equal));
                    assert(bool(status & 8) == (distance == 0 || breakpoint || !enabled));
                    assert(bool(status & 0x10) == breakpoint);
                    ++cases;
                }
            }
        }
    }
    std::cout << "PASS actual WGP/decoder partial-command transitions and " << std::dec << cases
              << " actual CP-MMIO idle/distance/pointer/breakpoint/read-enable cases\n";
    g_mmu = nullptr;
}
