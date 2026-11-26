#include "runtime/cpu_context.h"
#include <algorithm>
#include <cstdio>
#include <stdexcept>

namespace nwii::runtime {
uint32_t g_watch_addr = 0;
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("unexpected watch"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("unexpected MMIO read"); }
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("unexpected MMIO read"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("unexpected MMIO write"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("unexpected MMIO write"); }
void GX_WGPIPE_Write8(uint8_t) { throw std::runtime_error("unexpected GX write"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("unexpected GX write"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("unexpected GX write"); }
void GX_WGPIPE_WriteF32(float) { throw std::runtime_error("unexpected GX float write"); }
}

int main() {
    nwii::runtime::CPUContext ctx;
    unsigned stores = 0, loads = 0, store_mismatches = 0, load_mismatches = 0;
    for (uint32_t address : {0x80010000u, 0xE0001000u}) {
        for (unsigned type = 4; type <= 7; ++type) {
            const int low = type < 6 ? 0 : (type == 6 ? -128 : -32768);
            const int high = type == 4 ? 255 : (type == 5 ? 65535 : (type == 6 ? 127 : 32767));
            const unsigned width = (type == 4 || type == 6) ? 1 : 2;
            for (unsigned scale = 0; scale < 64; ++scale) {
                const int exponent = scale < 32 ? int(scale) : int(scale) - 64;
                ctx.gqr[6] = (scale << 24) | (type << 16) | (scale << 8) | type;
                for (unsigned w : {0u, 1u}) {
                    for (float value : {-1e20f, -262144.0f, -1025.0f, -1.75f, 0.0f, 1.75f, 1024.0f, 2040.0f, 524288.0f, 1e20f}) {
                        ctx.fpr[9] = value;
                        ctx.ps1[9] = -value;
                        ctx.psq_store(9, address, w, 6);
                        for (unsigned lane = 0; lane <= (w == 0 ? 1u : 0u); ++lane) {
                            const float input = lane ? -value : value;
                            const float scaled = std::ldexp(input, exponent);
                            const int expected = int(std::clamp(scaled, float(low), float(high)));
                            const uint32_t raw = width == 1 ? ctx.mmu.read8(address + lane) : ctx.mmu.read16(address + lane * 2);
                            const int actual = type == 6 ? int(int8_t(raw)) : (type == 7 ? int(int16_t(raw)) : int(raw));
                            ++stores;
                            store_mismatches += actual != expected;
                        }
                    }
                    if (width == 1) {
                        ctx.mmu.write8(address, uint8_t(high));
                        ctx.mmu.write8(address + 1, uint8_t(low));
                    } else {
                        ctx.mmu.write16(address, uint16_t(high));
                        ctx.mmu.write16(address + 2, uint16_t(low));
                    }
                    ctx.psq_load(9, address, w, 6);
                    ++loads;
                    load_mismatches += ctx.fpr[9] != std::ldexp(float(high), -exponent)
                        || ctx.ps1[9] != (w ? 1.0 : std::ldexp(float(low), -exponent));
                }
            }
        }
    }
    std::printf("stores=%u storeMismatches=%u loads=%u loadMismatches=%u\n", stores, store_mismatches, loads, load_mismatches);
    return store_mismatches || load_mismatches ? 2 : 0;
}
