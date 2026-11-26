"""Respect original SDK-selected D4 on legacy interrupt return; keep configured dispatcher policy intact."""
def adapt(text):
    old = '''    if (ctx.dispatch_saved_ctx) {
      uint32_t current_thread = ctx.mmu.read32(0x800000E4);
      if (current_thread != 0 && current_thread != ctx.dispatch_saved_ctx) {
        ctx.mmu.write32(0x800000D4, current_thread);
      } else {
        ctx.mmu.write32(0x800000D4, ctx.dispatch_saved_ctx);
      }
      ctx.dispatch_saved_ctx = 0;
    }'''
    new = '''    if (ctx.dispatch_saved_ctx) {
        if (Config::get().game_profile.ext_interrupt_dispatch != 0) {
            uint32_t current_thread = ctx.mmu.read32(0x800000E4);
            if (current_thread != 0 && current_thread != ctx.dispatch_saved_ctx) {
                ctx.mmu.write32(0x800000D4, current_thread);
            } else {
                ctx.mmu.write32(0x800000D4, ctx.dispatch_saved_ctx);
            }
        }
        ctx.dispatch_saved_ctx = 0;
    }'''
    assert text.count(old) == 1
    return text.replace(old, new)
