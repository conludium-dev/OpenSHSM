#include <processor_adapter.h>
#include <iostream>
#include <memory>

int main() {
    constexpr uint32_t saved = 0x80540000, other = 0x80541000;
    for (unsigned route = 0; route < 4; ++route) {
        for (uint32_t resume : {0u, 0x8020B9C8u}) {
            auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
            auto& ctx = *owned;
            const uint32_t current = route < 2 ? 0 : route == 2 ? saved : other;
            const uint32_t selected = route == 3 ? other : saved;
            for (uint32_t address : {saved, other}) {
                for (unsigned offset = 0; offset < 0x2D0; offset += 4) {
                    ctx.mmu.write32(address + offset, 0);
                }
                ctx.mmu.write32(address + 4, 0x8053FC20);
                ctx.mmu.write32(address + 12, address);
                ctx.mmu.write32(address + 0x198, address == selected ? resume : 0x8009BB80);
                ctx.mmu.write32(address + 0x19C, 0x9032);
                ctx.mmu.write16(address + 0x1A2, 2);
            }
            ctx.mmu.write32(0x800000D4, saved);
            ctx.mmu.write32(0x800000E4, current);
            ctx.dispatch_saved_ctx = route == 0 ? 0 : saved;
            ctx.pc = 0xFFFFFFFC;
            ctx.in_callback = false;
            ctx.ext_resched_pending = false;
            const auto fpr = ctx.fpr, ps1 = ctx.ps1;
            const bool handled = nwii::runtime::process_pending_callbacks(ctx);
            if (!handled || ctx.pc != resume || ctx.gpr[3] != selected || ctx.lr != 0
                || ctx.mmu.read32(0x800000D4) != selected || ctx.dispatch_saved_ctx != 0
                || ctx.fpr != fpr || ctx.ps1 != ps1 || ctx.mmu.read16(selected + 0x1A2) != 0) {
                return 1;
            }
            std::cout << "RESTORE " << route << ' ' << selected << ' ' << ctx.pc << ' '
                << ctx.gpr[1] << ' ' << ctx.lr << '\n';
        }
    }
    std::cout << "LINKED_CONTEXT_RESTORE_FIXTURES_PASS 8\n";
    return 0;
}
