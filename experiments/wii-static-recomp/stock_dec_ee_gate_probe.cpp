#include <processor_adapter.h>
#include <cstdio>
#include <memory>

int main(int argc, char** argv) {
    if (argc != 2) { return 1; }
    FILE* output = std::fopen(argv[1], "wb");
    if (!output) { return 2; }
    for (unsigned mode = 0; mode < 9; ++mode) {
        auto owned = std::make_unique<nwii::runtime::CPUContext>();
        auto& ctx = *owned;
        const bool masked = mode < 2 || mode == 7;
        const bool notdue = mode == 0 || mode == 2;
        const bool blocked = mode == 6 || mode == 7;
        const bool expected_jump = mode == 4;
        ctx.inst_count = 12345;
        ctx.pc = 0x80209D80;
        ctx.lr = 0x8009C5E4;
        ctx.msr = masked ? 0x2032 : 0xA032;
        ctx.is_running = true;
        ctx.in_callback = blocked;
        ctx.dec_irq_pending = true;
        ctx.dec_written_tb = 12344;
        ctx.dec_value = notdue ? 10 : 1;
        for (unsigned i = 0; i < 32; ++i) { ctx.gpr[i] = 0x12340000 + i; }
        ctx.gpr[1] = 0x80020000;
        ctx.gpr[13] = 0x8046F000;
        ctx.mmu.write32(0x800000D4, mode == 5 ? 0 : 0x80004000);
        ctx.mmu.write32(0x80003020, mode == 8 ? UINT32_MAX : (mode >= 4 ? 0x80100000 : 0));
        const int jumped = setjmp(ctx.exception_jmp_buf);
        if (!jumped) {
            if (nwii::runtime::process_pending_callbacks(ctx) || expected_jump) { return 3; }
        } else if (!expected_jump || ctx.pc != 0x80100000 || ctx.lr != 0xFFFFFFFC ||
            ctx.gpr[3] != 8 || ctx.gpr[4] != 0x80004000 || (ctx.msr & 0x8000)) {
            return 4;
        }
        if (ctx.dec_irq_pending != (masked || blocked || notdue)) { return 5; }
        auto write = [&](const auto& value) { return std::fwrite(&value, sizeof(value), 1, output) == 1; };
        if (!write(mode) || !write(jumped) || !write(ctx.gpr) || !write(ctx.fpr) || !write(ctx.ps1) ||
            !write(ctx.gqr) || !write(ctx.cr) || !write(ctx.pc) || !write(ctx.lr) || !write(ctx.msr) ||
            !write(ctx.srr0) || !write(ctx.srr1) || !write(ctx.dispatch_saved_ctx) || !write(ctx.in_callback) ||
            !write(ctx.dec_irq_pending) || !write(ctx.dec_value) || !write(ctx.dec_written_tb)) { return 6; }
        if (std::fwrite(ctx.mmu.get_ptr(0x80004000), 1, 1024, output) != 1024) { return 7; }
    }
    if (std::fclose(output) != 0) { return 8; }
    std::puts("DEC_EE_MASK_DUE_HANDLER_NONLOCAL_ENDPOINT_PASS9");
}
