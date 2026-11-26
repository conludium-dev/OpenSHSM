#pragma once
#include <processor_adapter.h>
#include <sstream>
#include <iostream>

namespace openshsm::experiment {
inline uint32_t cache_context_word(nwii::runtime::CPUContext& ctx, uint32_t address) {
    const uint64_t end = uint64_t(address) + 4;
    if (!((address >= 0x80000000 && end <= 0x81800000)
        || (address >= 0x90000000 && end <= 0x94000000))) {
        return 0;
    }
    return ctx.mmu.read32(address);
}

inline void observe_cache_irq(nwii::runtime::CPUContext& ctx, unsigned stage, uint32_t subject = 0) {
    const auto stored_pc = subject ? cache_context_word(ctx, subject + 0x198) : 0;
    const auto stored_lr = subject ? cache_context_word(ctx, subject + 0x84) : 0;
    const auto relevant_lr = [](uint32_t lr) { return lr == 0x8009BBD0 || lr == 0x8035AF38; };
    if (!((ctx.pc == 0x80212FF4 && relevant_lr(ctx.lr))
        || (stored_pc == 0x80212FF4 && relevant_lr(stored_lr))) || stage >= 6) {
        return;
    }
    static unsigned ordinary[6] = {}, abnormal[6] = {};
    const auto ctr = stage == 2 ? cache_context_word(ctx, subject + 0x88) : ctx.ctr;
    const bool unusual = ctr == 0 || ctr > 4096;
    auto& count = unusual ? abnormal[stage] : ordinary[stage];
    if (count >= (unusual ? 64u : 512u)) {
        return;
    }
    ++count;
    const auto selected = cache_context_word(ctx, 0x800000D4);
    std::ostringstream out;
    out << "[Cache IRQ] stage=" << stage << std::hex << " pc=" << ctx.pc << " lr=" << ctx.lr
        << " ctr=" << ctx.ctr << " r3=" << ctx.gpr[3] << " r4=" << ctx.gpr[4]
        << " msr=" << ctx.msr << " sp=" << ctx.gpr[1] << " subject=" << subject
        << " selected=" << selected << " saved=" << ctx.dispatch_saved_ctx
        << " memory-ctr=" << (subject ? cache_context_word(ctx, subject + 0x88) : 0)
        << " memory-pc=" << stored_pc << " memory-lr="
        << (subject ? cache_context_word(ctx, subject + 0x84) : 0);
    std::cout << out.str() << '\n';
}
}
