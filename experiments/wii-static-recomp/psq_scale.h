#pragma once
#include "runtime/cpu_context.h"
#include <bit>
namespace nwii::runtime {
  inline void stock_psq_load(CPUContext& ctx, uint32_t frD, uint32_t addr, uint32_t W, uint32_t I) {
    uint32_t gqr_val = ctx.gqr[I];
    uint32_t ld_type = (gqr_val >> 16) & 0x7;
    uint32_t ld_scale = (gqr_val >> 24) & 0x3F;
    const int signed_scale = int(ld_scale ^ 32u) - 32;
    float scale = std::bit_cast<float>(uint32_t(127 - signed_scale) << 23);

    auto load_element = [&](uint32_t a) -> double {
      switch (ld_type) {
      case 0:
        return ctx.mmu.read_f32(a);
      case 4:
        return ctx.mmu.read8(a) * scale;
      case 5:
        return ctx.mmu.read16(a) * scale;
      case 6:
        return (int8_t)ctx.mmu.read8(a) * scale;
      case 7:
        return (int16_t)ctx.mmu.read16(a) * scale;
      default:
        return 0.0;
      }
    };

    uint32_t elem_size =
        (ld_type == 0) ? 4 : ((ld_type == 4 || ld_type == 6) ? 1 : 2);

    ctx.fpr[frD] = load_element(addr);
    if (W == 0) { 
      ctx.ps1[frD] = load_element(addr + elem_size);
    } else { 
      ctx.ps1[frD] = 1.0;
    }
  }

  inline void stock_psq_store(CPUContext& ctx, uint32_t frS, uint32_t addr, uint32_t W, uint32_t I) {
    uint32_t gqr_val = ctx.gqr[I];
    uint32_t st_type = gqr_val & 0x7;
    uint32_t st_scale = (gqr_val >> 8) & 0x3F;
    const int signed_scale = int(st_scale ^ 32u) - 32;
    float scale = std::bit_cast<float>(uint32_t(127 + signed_scale) << 23);

    auto quantize = [&](double value, float low, float high) {
        const float scaled = float(value) * scale;
        if (std::isnan(scaled)) {
            throw std::runtime_error("PSQ integer NaN is not verified");
        }
        return std::fmin(high, std::fmax(low, scaled));
    };
    auto store_element = [&](uint32_t a, double val) {
      switch (st_type) {
      case 0:
        ctx.mmu.write_f32(a, (float)val);
        break;
      case 4:
        ctx.mmu.write8(a, (uint8_t)quantize(val, 0.0f, 255.0f));
        break;
      case 5:
        ctx.mmu.write16(a, (uint16_t)quantize(val, 0.0f, 65535.0f));
        break;
      case 6:
        ctx.mmu.write8(a, (int8_t)quantize(val, -128.0f, 127.0f));
        break;
      case 7:
        ctx.mmu.write16(a, (int16_t)quantize(val, -32768.0f, 32767.0f));
        break;
      }
    };

    uint32_t elem_size =
        (st_type == 0) ? 4 : ((st_type == 4 || st_type == 6) ? 1 : 2);

    store_element(addr, ctx.fpr[frS]);
    if (W == 0) {
      store_element(addr + elem_size, ctx.ps1[frS]);
    }
  }


}
