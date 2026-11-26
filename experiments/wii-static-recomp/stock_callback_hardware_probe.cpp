#include "runtime/cpu_context.h"
#include "runtime/event_scheduler.h"
#include "runtime/hw/hw.h"
#include <array>
#include <cassert>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    assert(argc == 3);
    const std::string mode = argv[1];
    const bool stalled = std::string(argv[2]) == "stalled";
    const bool active = mode == "callback-ee0" || mode == "callback-ee1";
    assert(active || mode == "normal" || mode == "sentinel");
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    g_ctx_ptr = &ctx;
    g_mmu = &ctx.mmu;
    ctx.tb_freq = 60750000;
    ctx.pc = mode == "sentinel" ? 0xFFFFFFFC : 0x80212FC4;
    ctx.lr = 0x8022FBA0;
    ctx.msr = mode == "callback-ee1" ? 0x8000 : 0;
    ctx.in_callback = active || mode == "sentinel";
    ctx.callback_depth = ctx.in_callback ? 1 : 0;
    ctx.vblank_pending = active;
    ctx.dec_value = 0;
    ctx.dec_written_tb = 0;
    ctx.dec_irq_pending = true;
    for (unsigned i = 0; i < 32; ++i) {
        ctx.gpr[i] = 0x80560000 + i * 32;
        ctx.fpr[i] = double(i) + 0.25;
        ctx.ps1[i] = double(i) - 0.5;
    }
    ctx.cr[3].lt = true;
    ctx.cr[5].so = true;
    ctx.gqr.fill(0x12340000);
    ctx.sprg.fill(0x80561234);
    ctx.fpscr = 0x12;
    ctx.srr0 = 0x80212340;
    ctx.srr1 = 0x1032;
    ctx.ctr = 0x1234;
    ctx.xer = 0x80000000;
    ctx.queue_callback(0x80012340, 0x123, 0x456);
    const auto gpr = ctx.gpr;
    const auto gqr = ctx.gqr;
    const auto sprg = ctx.sprg;
    const auto fpr = ctx.fpr, ps1 = ctx.ps1;
    const auto cr = ctx.cr;
    auto pc = ctx.pc;
    const auto lr = ctx.lr, msr = ctx.msr;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_ai(mmio);
    hw::register_dsp(mmio);
    hw::pi_intmr = 0x140;
    hw::pi_intsr = 0;
    mmio.write32(0xCC006C00, 0x40);
    for (unsigned i = 0; i < 128; ++i) {
        ctx.mmu.write16(0x80560000 + i * 2, uint16_t(int16_t(int(i) * 71 - 3900)));
    }
    mmio.write16(0xCC005030, 0x56);
    mmio.write16(0xCC005032, 0);
    mmio.write16(0xCC00500A, 0x10);
    mmio.write16(0xCC005036, 0x8008);
    unsigned fired = 0;
    scheduler.schedule_after(121500, [&](CPUContext& c, uint64_t late) {
        assert(&c == &ctx && late == ctx.inst_count - 121500);
        ++fired;
        scheduler.advance(c, c.read_timebase());
    });
    std::array<int16_t, 2048> pcm{};
    unsigned total = 0;
    const bool expect_stall = stalled && active;
    for (unsigned step = 1; step <= 10; ++step) {
        ctx.inst_count = uint64_t(step) * 121500;
        assert(!process_pending_callbacks(ctx));
        const auto frames = hw::dsp_audio_pull(pcm.data(), 1024);
        assert(frames == (expect_stall ? 0 : 64));
        for (unsigned i = 0; i < frames * 2; ++i) {
            assert(pcm[i] == int(i ^ 1) * 71 - 3900);
        }
        total += frames;
        assert(ctx.gpr == gpr && ctx.gqr == gqr && ctx.sprg == sprg);
        assert(ctx.fpr == fpr && ctx.ps1 == ps1);
        assert(ctx.pc == pc && ctx.lr == lr && ctx.msr == msr);
        assert(std::memcmp(ctx.cr.data(), cr.data(), sizeof(cr)) == 0);
        assert(ctx.ctr == 0x1234 && ctx.xer == 0x80000000);
        assert(ctx.fpscr == 0x12 && ctx.srr0 == 0x80212340 && ctx.srr1 == 0x1032);
        assert(ctx.in_callback == active && ctx.callback_depth == (mode == "normal" ? 0 : 1));
        assert(ctx.backup_stack.empty() && ctx.pending_cb_count.load() == 1);
        assert(ctx.pending_callbacks.size() == 1 && ctx.dec_irq_pending);
        if (active) {
            assert(ctx.vblank_pending && !(hw::pi_intsr & 0x100));
        }
        if (mode == "sentinel" && step == 1) {
            pc = ctx.pc = 0x80212FC4;
        }
    }
    assert(fired == (expect_stall ? 0 : 1));
    assert(scheduler.now() == (expect_stall ? 0 : ctx.inst_count));
    assert(bool(hw::pi_intsr & 0x40) == !expect_stall);
    if (expect_stall) {
        ctx.in_callback = false;
        ctx.msr = 0;
        assert(!process_pending_callbacks(ctx));
        assert(hw::dsp_audio_pull(pcm.data(), 1024) == 640);
        assert(fired == 1);
    }
    mmio.write16(0xCC005036, 8);
    ctx.inst_count += 121500;
    assert(!process_pending_callbacks(ctx));
    assert(hw::dsp_audio_pull(pcm.data(), 1024) == 0);
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
    std::cout << "CALLBACK_HARDWARE_PASS mode=" << mode << " frames=" << total
              << " stalled=" << expect_stall << '\n';
}
