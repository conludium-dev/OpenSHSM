"""Bounded read-only argument/context snapshots in existing CPU trace paths."""

helper = '''
static void observe_numeric_state(const char* event, uint32_t subject, CPUContext& ctx) {
    static unsigned calls[2] = {};
    static unsigned contexts[2] = {};
    unsigned* counter = nullptr;
    if (event[0] == 'c') {
        counter = &calls[subject == 0x8019734C ? 0 : 1];
    } else {
        if (ctx.pc < 0x80197270 || ctx.pc >= 0x801979DC) {
            return;
        }
        counter = &contexts[event[0] == 's' ? 0 : 1];
    }
    const unsigned hit = ++*counter;
    if (hit > 32 && (hit % 4096 != 0 || hit > 393216)) {
        return;
    }
    std::ostringstream line;
    line << "[NumericState] event=" << event << " hit=" << std::dec << hit
         << " subject=" << std::hex << subject << " pc=" << ctx.pc << " lr=" << ctx.lr
         << " ctr=" << ctx.ctr << " xer=" << ctx.xer << " msr=" << ctx.msr;
    uint32_t cr = 0;
    for (const auto& field : ctx.cr) {
        cr = (cr << 4) | (unsigned(field.lt) << 3) | (unsigned(field.gt) << 2)
            | (unsigned(field.eq) << 1) | unsigned(field.so);
    }
    line << " cr=" << cr << " gpr=";
    for (unsigned i = 0; i < 32; ++i) {
        line << ctx.gpr[i] << ",";
    }
    for (unsigned reg = 3; reg <= 5; ++reg) {
        const uint32_t address = ctx.gpr[reg];
        line << " mem" << reg << "=";
        if (ctx.mmu.get_ptr(address) && address <= 0xFFFFFFC0 && ctx.mmu.get_ptr(address + 63)) {
            for (unsigned i = 0; i < 64; ++i) {
                line << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(address + i));
            }
        } else {
            line << "-";
        }
    }
    line << "\\n";
    fprintf(stderr, "%s", line.str().c_str());
}
'''

def adapt_calls(text):
    marker = 'void trace_call(uint32_t func_addr, CPUContext &ctx) {'
    assert text.count(marker) == 1
    text = text.replace(marker, helper + marker)
    marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''
  if (func_addr == 0x8019734C || func_addr == 0x801976C0) {
      observe_numeric_state("call", func_addr, ctx);
      return;
  }
''')
    assert 'write' not in helper
    return '#include <sstream>\n#include <iomanip>\n#include <cstdio>\n' + text

def adapt_contexts(text):
    marker = 'static void hle_save_context_to_guest(CPUContext &ctx, uint32_t c) {'
    assert text.count(marker) == 1
    text = text.replace(marker, helper + marker + '\n  observe_numeric_state("save", c, ctx);')
    marker = '  ctx.msr = ctx.mmu.read32(c + 0x19C);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n  observe_numeric_state("load", c, ctx);')
    return '#include <sstream>\n#include <iomanip>\n#include <cstdio>\n' + text
