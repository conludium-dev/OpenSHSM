#include <processor_adapter.h>
#include "runtime/config.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <memory>

int main(int argc, char** argv) {
    assert(argc == 2);
    using namespace nwii::runtime;
    const unsigned mode = std::atoi(argv[1]);
    assert(mode < 3);
    Config::get().game_profile.ext_interrupt_dispatch = 0x80100000;
    Config::get().game_profile.sched_lock_offset = 0;
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    ctx.is_running = true;
    ctx.inst_count = 12345;
    ctx.pc = 0x80209D80;
    ctx.lr = 0x8009C5E4;
    ctx.msr = mode == 0 ? 0x2032 : 0xA032;
    ctx.dispatch_saved_ctx = mode == 0 ? 0 : 0x80004000;
    ctx.gpr[1] = 0x80020000;
    ctx.gpr[13] = 0x8046F000;
    ctx.mmu.write32(0x800000D4, 0x80004000);
    ctx.mmu.write32(0x800000E4, mode == 2 ? 0 : 0x80008000);
    hw::pi_intsr = 0;
    hw::pi_intmr = 0;
    assert(setjmp(ctx.exception_jmp_buf) == 0);
    assert(!process_pending_callbacks(ctx));
    assert(hw::pi_intsr.load() == 0);
    hw::pi_intmr = 0x100;
    ctx.inst_count += ctx.tb_freq / 60;
    assert(!process_pending_callbacks(ctx));
    assert(hw::pi_intsr.load() == 0x100);
    assert(ctx.pc == 0x80209D80 && ctx.lr == 0x8009C5E4);
    ctx.inst_count += ctx.tb_freq / 60;
    assert(!process_pending_callbacks(ctx));
    assert(hw::pi_intsr.load() == 0x100);
    ctx.msr |= 0x8000;
    ctx.dispatch_saved_ctx = 0;
    const int delivered = setjmp(ctx.exception_jmp_buf);
    if (delivered == 0) {
        process_pending_callbacks(ctx);
        return 2;
    }
    assert(ctx.pc == 0x80100000 && ctx.lr == 0xFFFFFFFC);
    assert(ctx.gpr[3] == 4 && ctx.gpr[4] == 0x80004000);
    assert(!(ctx.msr & 0x8000));
    std::printf("ACTUAL_PERIODIC_VI_LATCH_DEFER_COALESCE_DELIVER_MODE%u_PASS\n", mode);
}
