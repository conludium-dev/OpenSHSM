#include "runtime/cpu_context.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <iostream>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
extern void GX_WGPIPE_Write8(uint8_t);
extern void GX_WGPIPE_Write32(uint32_t);
namespace hw {
extern void register_cp(MMIODispatcher&);
extern void register_pi(MMIODispatcher&);
}
}
extern void ProcessGXFifo();

int main() {
    using namespace nwii::runtime;
    CPUContext ctx;
    g_mmu = &ctx.mmu;
    g_ctx_ptr = &ctx;
    auto& bus = MMIODispatcher::get();
    hw::register_cp(bus);
    hw::register_pi(bus);
    for (uint32_t address : {0xCC00300Cu, 0xCC003010u, 0xCC003014u}) {
        bus.write32(address, 0xF000401F);
        assert(bus.read32(address) == 0x10004000);
    }
    auto reg = [&](uint32_t address, uint32_t value) {
        bus.write32(address, value & 0xFFFF);
        bus.write32(address + 2, value >> 16);
    };
    for (uint32_t address = 0xCC000020; address <= 0xCC00003C; address += 4) {
        reg(address, 0xF000401F);
        assert(bus.read32(address) == 0x4000);
        assert(bus.read32(address + 2) == 0x1000);
    }
    unsigned cases = 0;
    for (uint32_t base : {0x4000u, 0x10004000u}) {
        bus.write32(0xCC000002, 0x10);
        reg(0xCC000020, base);
        reg(0xCC000024, base + 96);
        reg(0xCC000034, base);
        reg(0xCC000038, base);
        reg(0xCC000030, 0);
        reg(0xCC00003C, base + 32);
        bus.write32(0xCC00300C, base);
        bus.write32(0xCC003010, base + 96);
        bus.write32(0xCC003014, base);
        ctx.mmu.write8(base, 0xA5);
        for (unsigned i = 0; i < 31; ++i) {
            GX_WGPIPE_Write8(0);
        }
        assert(ctx.mmu.read8(base) == 0xA5);
        assert(bus.read32(0xCC003014) == base);
        assert(bus.read32(0xCC000030) == 0);
        GX_WGPIPE_Write8(0);
        assert(ctx.mmu.read8(base) == 0);
        assert(bus.read32(0xCC003014) == base + 32);
        assert(bus.read32(0xCC000030) == 32);
        bus.write32(0xCC000002, 0x33);
        ProcessGXFifo();
        assert(bus.read32(0xCC000030) == 0);
        assert(bus.read32(0xCC000000) & 0x10);
        assert(hw::pi_intsr & 0x800);
        for (unsigned i = 0; i < 8; ++i) {
            GX_WGPIPE_Write32(0);
        }
        ProcessGXFifo();
        assert(bus.read32(0xCC000030) == 32);
        bus.write32(0xCC000002, 0x11);
        ProcessGXFifo();
        assert(bus.read32(0xCC000030) == 0);
        assert(!(hw::pi_intsr & 0x800));
        bus.write32(0xCC000002, 0x10);
        for (unsigned i = 0; i < 24; ++i) {
            GX_WGPIPE_Write32(0);
        }
        assert(bus.read32(0xCC003014) == base + 32);
        assert(bus.read32(0xCC000030) == 96);
        bus.write32(0xCC000002, 0x11);
        ProcessGXFifo();
        assert(bus.read32(0xCC000030) == 0);
        const uint32_t rp = bus.read32(0xCC000038) | (bus.read32(0xCC00003A) << 16);
        assert(rp == base + 32);
        ++cases;
    }
    bus.write32(0xCC000002, 0);
    bus.write32(0xCC00300C, 0x10008000);
    bus.write32(0xCC003010, 0x10008020);
    bus.write32(0xCC003014, 0x10008000);
    for (unsigned i = 0; i < 8; ++i) {
        GX_WGPIPE_Write32(0x01020304);
    }
    assert(ctx.mmu.read32(0x10008000) == 0x01020304);
    assert(bus.read32(0xCC003014) == 0x10008020);
    assert(bus.read32(0xCC000030) == 0);
    std::cout << "PASS " << std::dec << cases << " MEM1/MEM2 linked burst/decode/BP/wrap cases; unlinked RAM endian publication\n";
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
}
