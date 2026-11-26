#include <processor_adapter.h>
#include <runtime/config.h>
#include <iostream>
#include <memory>

int main(int argc, char**) {
    const bool baseline = argc > 1;
    constexpr uint32_t nested = 0x80540000, first = 0x80541000, second = 0x80542000;
    unsigned cases = 0;
    for (unsigned configured = 0; configured < 2; ++configured) {
        nwii::runtime::Config::get().game_profile.ext_interrupt_dispatch = configured ? 0x80213DC0 : 0;
        for (unsigned route = 0; route < 5; ++route) {
            auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
            auto& ctx = *owned;
            for (uint32_t address : {nested, first, second}) {
                ctx.mmu.write32(address + 4, address + 0x800);
                ctx.mmu.write32(address + 12, address);
                ctx.mmu.write32(address + 0x84, address + 4);
                ctx.mmu.write32(address + 0x88, address + 8);
                ctx.mmu.write32(address + 0x198, address + 12);
                ctx.mmu.write32(address + 0x19C, 0x1032);
            }
            const uint32_t selected = route == 2 || route == 3 ? second : nested;
            const uint32_t current = route == 4 ? 0 : route == 2 ? second : first;
            const uint32_t saved = route == 0 ? 0 : nested;
            ctx.mmu.write32(0x800000D4, selected);
            ctx.mmu.write32(0x800000E4, current);
            ctx.dispatch_saved_ctx = saved;
            ctx.pc = 0xFFFFFFFC;
            ctx.in_callback = false;
            ctx.ext_resched_pending = false;
            const uint32_t expected = saved && (baseline || configured)
                ? (current && current != saved ? current : saved) : selected;
            if (!nwii::runtime::process_pending_callbacks(ctx) || ctx.pc != expected + 12
                || ctx.gpr[3] != expected || ctx.gpr[1] != expected + 0x800 || ctx.lr != expected + 4
                || ctx.ctr != expected + 8 || ctx.dispatch_saved_ctx != 0) {
                return 1;
            }
            std::cout << "POLICY " << configured << ' ' << route << ' ' << std::hex << expected << std::dec << '\n';
            ++cases;
        }
    }
    if (baseline) {
        std::cout << "LEGACY_CONTEXT_BASELINE_POLICY_REPRODUCED " << cases << '\n';
        return 0;
    }
    nwii::runtime::Config::get().game_profile.ext_interrupt_dispatch = 0;
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    for (uint32_t selected : {nested, first}) {
        ctx.mmu.write32(selected + 0x198, selected + 12);
        ctx.mmu.write32(0x800000D4, selected);
        ctx.mmu.write32(0x800000E4, first);
        ctx.dispatch_saved_ctx = selected == nested ? nested : 0;
        ctx.pc = 0xFFFFFFFC;
        ctx.in_callback = false;
        if (!nwii::runtime::process_pending_callbacks(ctx) || ctx.pc != selected + 12) {
            return 2;
        }
        ++cases;
    }
    std::cout << "LEGACY_CONTEXT_SDK_SELECTION_REGRESSION_PASS " << cases << '\n';
    return 0;
}
