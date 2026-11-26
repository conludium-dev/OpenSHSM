#pragma once
#include "stock_desktop_qte_draw.h"

namespace openshsm::experiment {

// Caller supplies a live, authorized GUI pass and its advertised glyph index.
template<class Context>
class DesktopQTEQuad {
public:
    template<class Pass>
    bool begin(Context& ctx, const Pass& pass, uint32_t resource, unsigned glyph) {
        const uint32_t stack = ctx.gpr[1];
        if (active || pass.return_pc != 0x800EBA90 || pass.record == 0 || pass.context == 0
            || ctx.gpr[13] != 0x8052E720 || ctx.in_callback || ctx.callback_depth != 0
            || (stack & 15) != 0 || !desktop_qte_draw_span(stack, 0x98)
            || ctx.mmu.read32(stack) != stack + 0x90
            || !desktop_qte_draw_span(ctx.gpr[29], 0x84)) {
            return false;
        }
        const auto geometry = desktop_qte_group_geometry(ctx, ctx.gpr[28], pass.root,
            pass.page, ctx.gpr[30], ctx.fpr[29]);
        DesktopQTEQuadBounds bounds;
        if (!desktop_qte_draw_span(ctx.gpr[28], 0x48)
            || ctx.mmu.read32(ctx.gpr[28] + 0x44) == 0
            || !desktop_qte_upright_bounds(geometry, 48, bounds)) {
            return false;
        }
        const uint32_t texture = desktop_qte_bank_texture(ctx, resource, glyph);
        if (texture == 0) {
            return false;
        }
        saved = {ctx.gpr, ctx.fpr, ctx.ps1, ctx.cr, ctx.lr, ctx.ctr, ctx.xer, ctx.pc,
            ctx.srr0, ctx.srr1, ctx.msr, ctx.fpscr, ctx.gqr, ctx.sprg};
        reservation = ctx.reservation_addr;
        thread = ctx.mmu.read32(0x800000E4);
        os_context = ctx.mmu.read32(0x800000D8);
        for (unsigned i = 0; i < scratch.size(); ++i) {
            scratch[i] = ctx.mmu.read32(stack + 4 + i * 4);
        }
        for (unsigned i = 0; i < 2; ++i) {
            ctx.mmu.write_f32(stack + 8 + i * 4, bounds.minimum[i]);
            ctx.mmu.write_f32(stack + 16 + i * 4, bounds.maximum[i]);
            ctx.mmu.write_f32(stack + 24 + i * 4, 0);
            ctx.mmu.write_f32(stack + 32 + i * 4, 1);
        }
        ctx.gpr[3] = ctx.gpr[29];
        ctx.gpr[4] = texture;
        ctx.gpr[5] = stack + 8;
        ctx.gpr[6] = stack + 16;
        ctx.gpr[7] = 0;
        ctx.gpr[8] = 0x80477AC8;
        ctx.gpr[9] = stack + 24;
        ctx.gpr[10] = stack + 32;
        ctx.fpr[1] = geometry.opacity;
        ctx.pc = 0x8010A3B4;
        ctx.lr = 0x8010C480;
        active = true;
        return true;
    }

    bool resume(Context& ctx) {
        if (!active || ctx.pc != 0x8010C480 || ctx.lr != 0x8010C480
            || ctx.gpr[1] != saved.gpr[1] || ctx.gpr[13] != saved.gpr[13]
            || ctx.gpr[28] != saved.gpr[28] || ctx.gpr[29] != saved.gpr[29]
            || ctx.gpr[30] != saved.gpr[30]
            || ctx.mmu.read32(0x800000E4) != thread
            || ctx.mmu.read32(0x800000D8) != os_context
            || ctx.in_callback || ctx.callback_depth != 0) {
            return false;
        }
        for (unsigned i = 0; i < scratch.size(); ++i) {
            ctx.mmu.write32(saved.gpr[1] + 4 + i * 4, scratch[i]);
        }
        ctx.gpr = saved.gpr;
        ctx.fpr = saved.fpr;
        ctx.ps1 = saved.ps1;
        ctx.cr = saved.cr;
        ctx.lr = saved.lr;
        ctx.ctr = saved.ctr;
        ctx.xer = saved.xer;
        ctx.pc = saved.pc;
        ctx.srr0 = saved.srr0;
        ctx.srr1 = saved.srr1;
        ctx.msr = saved.msr;
        ctx.fpscr = saved.fpscr;
        ctx.gqr = saved.gqr;
        ctx.sprg = saved.sprg;
        ctx.reservation_addr = reservation;
        active = false;
        return true;
    }

    bool pending() const {
        return active;
    }

private:
    typename Context::BackupState saved{};
    std::array<uint32_t, 9> scratch{};
    uint32_t reservation = 0, thread = 0, os_context = 0;
    bool active = false;
};

}
