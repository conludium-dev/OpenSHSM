#include "memory_frontend.h"
#include <cassert>

namespace nwii::runtime {
uint32_t g_watch_addr = 0;
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Watch unavailable"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("HW unavailable"); }
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("HW unavailable"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("HW unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("HW unavailable"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("GX unavailable"); }
}

int main() {
    using namespace nwii::runtime;
    MemoryContext context;
    context.msr = 0x30;
    context.hid0 = 0x4000;
    memory_write32(context, 0xc0618000, 0x11223344);
    memory_write32(context, 0x80618000, 0x55667788);
    std::cout << memory_read32(context, 0x80618000) << ' ' << memory_read32(context, 0xc0618000) << ' ';
    memory_cache_operation(context, 0x80618000, 54);
    std::cout << memory_read32(context, 0xc0618000) << ' ';
    memory_write32(context, 0xc0618000, 0x99aabbcc);
    std::cout << memory_read32(context, 0x80618000) << ' ';
    memory_cache_operation(context, 0x80618000, 470);
    std::cout << memory_read32(context, 0x80618000) << '\n';
    memory_write64(context, 0x8061801d, 0x0123456789abcdefull);
    assert(memory_read64(context, 0x8061801d) == 0x0123456789abcdefull);
    assert(memory_read64(context, 0xc061801d) == 0);
    memory_cache_operation(context, 0x8061801d, 86);
    memory_cache_operation(context, 0x80618020, 86);
    assert(memory_read64(context, 0xc061801d) == 0x0123456789abcdefull);
    memory_write_f32(context, 0x80618100, -2.5f);
    memory_write_f64(context, 0x80618108, 3.125);
    assert(memory_read_f32(context, 0x80618100) == -2.5f && memory_read_f64(context, 0x80618108) == 3.125);
    context.fpr[1] = 4.5;
    context.ps1[1] = -8.25;
    memory_psq_store(context, 1, 0x8061811c, 0, 0);
    memory_psq_load(context, 2, 0x8061811c, 0, 0);
    assert(context.fpr[2] == 4.5 && context.ps1[2] == -8.25);
    memory_write32(context, 0xc0619000, 0);
    for (unsigned index = 0; index < 9; ++index) {
        memory_write32(context, 0x80619000 + index * 4096, 0x100 + index);
    }
    assert(memory_read32(context, 0xc0619000) == 0x100);
    unsigned refusals = 0;
    for (uint32_t address : {0xcc000000u, 0xe0000000u, 0xfffffffcu}) {
        try {
            memory_write64(context, address, 0);
        } catch (const std::runtime_error&) {
            ++refusals;
        }
    }
    assert(refusals == 3);
    context.gqr[1] = 0x00040000;
    try {
        memory_psq_load(context, 3, 0x80618100, 0, 1);
        return 3;
    } catch (const std::runtime_error&) { }
    std::cout << "FRONTEND_CHECKS crossLine integer float pairedFloat eviction strictIO quantizedRefusal PASS\n";
}
