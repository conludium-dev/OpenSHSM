"""Read decoded planes at original queue publication, never modify guest memory."""

def adapt_thp_calls(text):
    marker = 'void trace_call(uint32_t func_addr, CPUContext &ctx) {'
    assert text.count(marker) == 1
    helper = '''
static void observe_thp(uint32_t function, CPUContext& ctx) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix || !*prefix) {
        return;
    }
    auto dump = [&](const std::string& suffix, uint32_t address, uint32_t bytes) {
        if (!bytes || bytes > 1024 * 1024 || address > 0xFFFFFFFFu - bytes
            || !ctx.mmu.get_ptr(address) || !ctx.mmu.get_ptr(address + bytes - 1)) {
            return false;
        }
        const std::string path = std::string(prefix) + suffix;
        std::ofstream file(path, std::ios::binary);
        if (!file) {
            return false;
        }
        file.write(reinterpret_cast<const char*>(ctx.mmu.get_ptr(address)), bytes);
        return bool(file);
    };
    static unsigned packets = 0;
    if (function == 0x80209D80 && packets < 3) {
        const uint32_t address = ctx.gpr[3];
        if (address >= 8 && ctx.mmu.get_ptr(address - 8) && ctx.mmu.read16(address) == 0xFFD8) {
            const uint32_t size = ctx.mmu.read32(address - 8);
            if (dump("-packet" + std::to_string(packets) + ".bin", address, size)) {
                fprintf(stderr, "[THPInput] index=%u address=%08x bytes=%u\\n", packets, address, size);
                ++packets;
            }
        }
    }
    static unsigned seen = 0;
    if (function == 0x80217D30 && ctx.lr == 0x8009C628) {
        const uint32_t descriptor = ctx.gpr[4];
        if (!ctx.mmu.get_ptr(descriptor) || !ctx.mmu.get_ptr(descriptor + 15)) {
            return;
        }
        const uint32_t y = ctx.mmu.read32(descriptor);
        const uint32_t u = ctx.mmu.read32(descriptor + 4);
        const uint32_t v = ctx.mmu.read32(descriptor + 8);
        const uint32_t frame = ctx.mmu.read32(descriptor + 12);
        if (frame >= 3 || (seen & (1u << frame)) || u - y != 307200 || v - u != 76800) {
            return;
        }
        const std::string stem = "-frame" + std::to_string(frame);
        if (dump(stem + "-Y.bin", y, 307200) && dump(stem + "-U.bin", u, 76800)
            && dump(stem + "-V.bin", v, 76800)) {
            seen |= 1u << frame;
            fprintf(stderr, "[THPPlanes] frame=%u y=%08x u=%08x v=%08x width=640 height=480\\n", frame, y, u, v);
        }
    }
}
'''
    text = text.replace(marker, helper + marker)
    marker = '  if (!g_trace_only.empty() && !g_trace_only.count(func_addr)) return;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''
  if (func_addr == 0x80209D80 || func_addr == 0x80217D30) {
      observe_thp(func_addr, ctx);
      if (func_addr == 0x80217D30) {
          return;
      }
  }
''')
    assert 'ctx.mmu.write' not in helper
    return '#include <fstream>\n#include <cstdio>\n' + text
