#include <processor_adapter.h>
#include <cstdio>
#include <memory>

int main(int argc, char** argv) {
    if (argc != 2) {
        return 1;
    }
    FILE* output = std::fopen(argv[1], "wb");
    if (!output) {
        return 2;
    }
    for (unsigned mode = 0; mode < 4; ++mode) {
        auto owned = std::make_unique<nwii::runtime::CPUContext>();
        auto& ctx = *owned;
        ctx.inst_count = 12345;
        ctx.pc = 0x80209D80;
        ctx.lr = 0x8009C5E4;
        ctx.msr = mode == 0 ? 0x2032 : 0xA032;
        ctx.is_running = true;
        ctx.vblank_pending = false;
        ctx.in_callback = mode == 1;
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x12340000 + i;
        }
        ctx.gpr[1] = 0x80020000;
        ctx.gpr[13] = 0x8046F000;
        ctx.mmu.write32(0x800000D4, mode == 3 ? 0x80004000 : 0);
        ctx.queue_callback(0x80100000, 0xABCD, 0x4567);
        int jumped = setjmp(ctx.exception_jmp_buf);
        if (jumped == 0) {
            const bool result = nwii::runtime::process_pending_callbacks(ctx);
            if (mode >= 2 || result) {
                return 3;
            }
        } else {
            if (mode < 2 || ctx.pc != 0x80100000 || ctx.lr != 0xFFFFFFFC ||
                ctx.gpr[3] != 0xABCD || ctx.gpr[4] != 0x4567) {
                return 4;
            }
        }
        auto write = [&](const auto& value) {
            return std::fwrite(&value, sizeof(value), 1, output) == 1;
        };
        const int pending = ctx.pending_cb_count.load();
        const unsigned backups = unsigned(ctx.backup_stack.size());
        if (pending != int(mode < 2) || !write(mode) || !write(jumped) || !write(ctx.gpr) ||
            !write(ctx.fpr) || !write(ctx.ps1) || !write(ctx.cr) || !write(ctx.gqr) ||
            !write(ctx.pc) || !write(ctx.lr) || !write(ctx.msr) || !write(ctx.srr0) || !write(ctx.srr1) ||
            !write(ctx.in_callback) || !write(ctx.callback_depth) || !write(ctx.dispatch_saved_ctx) ||
            !write(pending) || !write(backups)) {
            return 5;
        }
        for (const auto& range : {std::pair{0x800000D0u, 32u}, std::pair{0x80004000u, 1024u},
                std::pair{0x816EFFC0u, 64u}}) {
            if (std::fwrite(ctx.mmu.get_ptr(range.first), 1, range.second, output) != range.second) {
                return 6;
            }
        }
    }
    if (std::fclose(output) != 0) {
        return 7;
    }
    std::puts("ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4");
    return 0;
}
