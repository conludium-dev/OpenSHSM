#include "stock_psq_indexed.h"
#include <bit>
#include <cassert>
#include <iostream>
#include <limits>

namespace nwii::runtime {
uint32_t g_watch_addr = 0;
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Unexpected watch"); }
void GX_WGPIPE_Write8(uint8_t) { throw std::runtime_error("Unexpected GPU write8"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("Unexpected GPU write16"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("Unexpected GPU write32"); }
void GX_WGPIPE_WriteF32(float) { throw std::runtime_error("Unexpected GPU write float"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("Unexpected MMIO read"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("Unexpected MMIO write"); }
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Unexpected MMIO read16"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Unexpected MMIO write16"); }
}

int main() {
    nwii::runtime::CPUContext ctx;
    float values[] = {0, -0.0f, 1, -2.5f, 32768, std::numeric_limits<float>::min(), std::numeric_limits<float>::max()};
    size_t cases = 0;
    for (uint32_t op : {6u, 7u, 38u, 39u}) {
        for (uint32_t fr = 0; fr < 32; ++fr) {
            for (uint32_t i = 0; i < 8; ++i) {
                for (uint32_t w = 0; w < 2; ++w) {
                    for (uint32_t base : {0x80000000u, 0x90000000u, 0xC0000000u, 0xD0000000u}) {
                        uint32_t ea = base + 0x4000;
                        uint32_t ra = (op & 32) ? 5 : ((fr & 1) ? 5 : 0);
                        ctx.gpr[0] = 0xDEADBEEF;
                        ctx.gpr[5] = ea - 16;
                        ctx.gpr[6] = ra ? 16 : ea;
                        ctx.gqr[i] = 0;
                        float a = values[fr % 7], b = values[(fr + 1) % 7];
                        ctx.fpr[fr] = (op & 1) ? a : 9.5;
                        ctx.ps1[fr] = (op & 1) ? b : -4.0;
                        ctx.fpscr = 0x4004;
                        ctx.cr[3].eq = true;
                        ctx.lr = 0x81234560;
                        ctx.mmu.write32(ea - 4, 0x11111111);
                        ctx.mmu.write32(ea, (op & 1) ? 0x55555555 : std::bit_cast<uint32_t>(a));
                        ctx.mmu.write32(ea + 4, (op & 1) ? 0x66666666 : std::bit_cast<uint32_t>(b));
                        ctx.mmu.write32(ea + 8, 0x22222222);
                        uint32_t word = (4u << 26) | (fr << 21) | (ra << 16) | (6u << 11) | (w << 10) | (i << 7) | (op << 1);
                        shsm_psq_indexed(ctx, word, 0x8034C2D4);
                        assert(ctx.mmu.read32(ea) == std::bit_cast<uint32_t>(a));
                        assert(ctx.mmu.read32(ea + 4) == (((op & 1) && w) ? 0x66666666 : std::bit_cast<uint32_t>(b)));
                        assert(ctx.mmu.read32(ea - 4) == 0x11111111 && ctx.mmu.read32(ea + 8) == 0x22222222);
                        assert(std::bit_cast<uint64_t>(ctx.fpr[fr]) == std::bit_cast<uint64_t>(static_cast<double>(a)));
                        assert(std::bit_cast<uint64_t>(ctx.ps1[fr]) == std::bit_cast<uint64_t>((!(op & 1) && w) ? 1.0 : static_cast<double>(b)));
                        assert(ctx.gpr[0] == 0xDEADBEEF && ctx.gpr[5] == ((op & 32) ? ea : ea - 16));
                        assert(ctx.fpscr == 0x4004 && ctx.cr[3].eq && ctx.lr == 0x81234560);
                        ++cases;
                    }
                }
            }
        }
    }
    ctx.gpr[1] = 0x80005000;
    ctx.gpr[0] = 8;
    ctx.gqr[0] = 0;
    ctx.fpr[31] = 1.5;
    ctx.ps1[31] = -2;
    shsm_psq_indexed(ctx, 0x13E1000E, 0x8034C2D4);
    assert(ctx.mmu.read32(0x80005008) == 0x3FC00000);
    assert(ctx.mmu.read32(0x8000500C) == 0xC0000000);
    ctx.gqr[0] = 4;
    bool refused = false;
    try { shsm_psq_indexed(ctx, 0x13E1000E, 0x8034C2D4); } catch (const std::runtime_error&) { refused = true; }
    assert(refused && ctx.mmu.read32(0x80005008) == 0x3FC00000);
    ctx.gqr[0] = 0;
    ctx.fpr[31] = 1.0 / 3.0;
    shsm_psq_indexed(ctx, 0x13E1000E, 0x8034C2D4);
    assert(ctx.mmu.read32(0x80005008) == 0x3EAAAAAA);
    std::cout << "PASS " << cases << " indexed float/address cases; original13E1000E form; fractional store truncated; non-float profiles refused\n";
}
