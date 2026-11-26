"""Bounded, read-only PE event and original callback-state observations."""

def adapt_completion_calls(text):
    marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
    assert text.count(marker) == 1
    observation = '''
  static unsigned observed = 0;
  auto& bus = MMIODispatcher::get();
  const bool registration = func_addr == 0x80228950 || func_addr == 0x8009B0A4 || func_addr == 0x8009B37C
      || func_addr == 0x80099AB4 || func_addr == 0x8009AA00;
  if (!registration && bus.read32(0xCC00100E) < 0x1100) {
      return;
  }
  if (observed++ < 30000) {
      std::ostringstream line;
      line << "[CompletionCall] ns=" << std::chrono::steady_clock::now().time_since_epoch().count()
           << " fn=" << std::hex << func_addr << " lr=" << ctx.lr << " state=";
      for (unsigned i = 0; i < 12; ++i) {
          line << " " << ctx.mmu.read32(0x8052B23C + i * 4);
      }
      line << " ring=";
      for (unsigned i = 0; i < 6; ++i) {
          line << " " << ctx.mmu.read32(0x804F74A8 + i * 4);
      }
      line << " watchdog=" << ctx.mmu.read32(0x8052B274) << ":"
           << ctx.mmu.read32(0x8052B278) << ":" << ctx.mmu.read32(0x8052AD1C);
      line << " saved80529780=" << ctx.mmu.read32(0x80529780);
      line << " module=" << ctx.mmu.read32(0x8046BBE0) << ":"
           << unsigned(ctx.mmu.read8(0x8046BBE4)) << ":" << ctx.mmu.read32(0x8046BBF0);
      if (func_addr == 0x8009AA00 || func_addr == 0x80099AB4) {
          const uint32_t address = ctx.gpr[3];
          line << " input=";
          if (ctx.mmu.get_ptr(address) && ctx.mmu.get_ptr(address + 31)) {
              for (unsigned i = 0; i < 32; ++i) {
                  line << unsigned(ctx.mmu.read8(address + i)) << ",";
              }
          }
      }
      line << " pe=" << nwii::runtime::hw::g_pe_sr.load() << ":"
           << bus.read32(0xCC00100A) << ":" << bus.read32(0xCC00100E)
           << " cp=" << bus.read32(0xCC000000) << ":" << bus.read32(0xCC000002)
           << ":" << bus.read32(0xCC000030) << ":" << bus.read32(0xCC000032)
           << "\\n";
      fprintf(stderr, "%s", line.str().c_str());
  }
'''
    assert 'ctx.mmu.write' not in observation
    return '#include <sstream>\n#include <cstdio>\n' + text.replace(marker, marker + observation)

def adapt_completion_pe(text):
    marker = 'void register_pe(MMIODispatcher &dispatcher) {'
    assert text.count(marker) == 1
    helper = '''static void observe_pe(const char* event, uint32_t value) {
    static std::atomic<unsigned> observed{0};
    if (g_pe_token.load() >= 0x1100 && observed.fetch_add(1) < 30000) {
        fprintf(stderr, "[CompletionPE] ns=%lld event=%s value=%08x pending=%x control=%x token=%x\\n",
                (long long)std::chrono::steady_clock::now().time_since_epoch().count(), event, value,
                g_pe_sr.load(), g_pe_ctrl.load(), g_pe_token.load());
    }
}

'''
    text = '#include <chrono>\n#include <cstdio>\n' + text.replace(marker, helper + marker)
    marker = '                g_pe_ctrl = val & 0x03;\n                pe_update_interrupts();'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n                observe_pe("control", val);')
    marker = '        g_pe_token_pending = true;\n        pe_update_interrupts();\n    }\n}'
    assert text.count(marker) == 1
    text = text.replace(marker, marker[:-1] + '    observe_pe(raise_interrupt ? "token-irq" : "token", token);\n}')
    marker = '    g_pe_finish_pending = true;\n    pe_update_interrupts();'
    assert text.count(marker) == 1
    return text.replace(marker, marker + '\n    observe_pe("finish", 0);')
