"""Observe original callback checkpoints and same-block resume without changing guest state."""
import re
import struct

def adapt_callbacks(text, dol, numeric=False, nonlocal_unwind=False):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n    ctx.pc = 0x[0-9A-F]{8};\n)    if \(process_pending_callbacks\(ctx\)\) return;')
    def replace(match):
        address, word = int(match[2], 16), int(match[3], 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        sites.append({'address': address, 'word': word})
        return match[1] + f'    if (observe_block_callback(ctx, 0x{address:08X})) return;'
    for entry in (('8019734C', '801978F4') if numeric else ('8020AFD0', '8020B460')):
        start = text.index(f'void func_{entry}(')
        end = text.index('\nvoid func_', start + 1)
        text = text[:start] + pattern.sub(replace, text[start:end]) + text[end:]
    assert sites
    helper = '''
struct IDCTCheckpoint {
    uint32_t pc = 0, context = 0, block = 0;
    std::array<uint32_t, 32> gpr;
    std::array<double, 32> fpr, ps1;
    std::array<uint8_t, 256> matrix;
};
static IDCTCheckpoint idct_checkpoint(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    IDCTCheckpoint state;
    state.pc = pc; state.context = ctx.mmu.read32(0x800000D4); state.block = last_idct_block.serial;
    state.gpr = ctx.gpr; state.fpr = ctx.fpr; state.ps1 = ctx.ps1;
    std::memcpy(state.matrix.data(), ctx.mmu.get_ptr(0x80491E40), 256);
    return state;
}
static void log_idct_transition(const char* phase, const IDCTCheckpoint& before, const IDCTCheckpoint& after, bool handled) {
    static unsigned count = 0;
    if (count >= 512) { return; }
    uint32_t gpr_mask = 0, fpr_mask = 0, ps1_mask = 0;
    for (unsigned i = 0; i < 32; ++i) {
        if (before.gpr[i] != after.gpr[i]) { gpr_mask |= 1u << i; }
        if (std::memcmp(&before.fpr[i], &after.fpr[i], 8)) { fpr_mask |= 1u << i; }
        const float old_ps = float(before.ps1[i]), new_ps = float(after.ps1[i]);
        if (std::memcmp(&old_ps, &new_ps, 4)) { ps1_mask |= 1u << i; }
    }
    std::ostringstream line;
    line << "[IDCTTransition] phase=" << phase << " hit=" << ++count << " handled=" << handled;
    line << std::hex << " pc=" << before.pc << " next=" << after.pc;
    line << " block=" << before.block << " currentBlock=" << after.block;
    line << " context=" << before.context << " nextContext=" << after.context;
    line << " gprMask=" << gpr_mask << " fprMask=" << fpr_mask << " ps1Mask=" << ps1_mask;
    line << " matrixChanged=" << (before.matrix != after.matrix) << " diffs=" << std::hexfloat;
    for (unsigned i = 0; i < 32; ++i) {
        if ((fpr_mask | ps1_mask) & (1u << i)) {
            line << std::dec << i << ":" << before.fpr[i] << "," << before.ps1[i]
                << "," << after.fpr[i] << "," << after.ps1[i] << ";";
        }
    }
    line << "\\n";
    const std::string record = line.str();
    std::fwrite(record.data(), 1, record.size(), stderr);
}
static bool observe_block_callback(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    if (!std::getenv("NWII_THPDUMP")) {
        return nwii::runtime::process_pending_callbacks(ctx);
    }
    static std::map<uint32_t, IDCTCheckpoint> pending;
    const auto before = idct_checkpoint(ctx, pc);
    auto found = pending.find(before.context);
    if (found != pending.end() && found->second.pc == pc && found->second.block == before.block) {
        log_idct_transition("resume", found->second, before, false);
        pending.erase(found);
    }
    const bool handled = nwii::runtime::process_pending_callbacks(ctx);
    auto after = idct_checkpoint(ctx, ctx.pc);
    if (handled || before.gpr != after.gpr || before.pc != after.pc || before.context != after.context
        || before.fpr != after.fpr || before.ps1 != after.ps1 || before.matrix != after.matrix) {
        log_idct_transition("checkpoint", before, after, handled);
    }
    if (handled) {
        pending[before.context] = before;
    }
    return handled;
}
'''
    assert 'ctx.mmu.write' not in helper
    if nonlocal_unwind:
        marker = '    const bool handled = nwii::runtime::process_pending_callbacks(ctx);'
        assert helper.count(marker) == 1
        helper = helper.replace(marker, '    pending[before.context] = before;\n' + marker)
        marker = '''    if (handled) {
        pending[before.context] = before;
    }'''
        assert helper.count(marker) == 1
        helper = helper.replace(marker, '''    if (!handled) {
        pending.erase(before.context);
    }''')
    if numeric:
        helper = helper.replace('last_idct_block.serial', '0u').replace('[IDCTTransition]', '[NumericTransition]')
        helper = helper.replace('before.context != after.context\n',
            'before.context != after.context || before.ctr != after.ctr || before.lr != after.lr\n'
            '        || before.xer != after.xer || before.msr != after.msr || before.cr != after.cr\n')
        helper = helper.replace('uint32_t pc = 0, context = 0, block = 0;',
            'uint32_t pc = 0, context = 0, block = 0, ctr = 0, lr = 0, xer = 0, msr = 0, cr = 0;')
        marker = '    state.gpr = ctx.gpr; state.fpr = ctx.fpr; state.ps1 = ctx.ps1;'
        helper = helper.replace(marker, '''    state.ctr = ctx.ctr; state.lr = ctx.lr; state.xer = ctx.xer; state.msr = ctx.msr;
    for (unsigned i = 0; i < 8; ++i) {
        const auto& f = ctx.cr[i];
        state.cr |= ((f.lt ? 8u : 0) | (f.gt ? 4u : 0) | (f.eq ? 2u : 0) | (f.so ? 1u : 0)) << (28 - 4 * i);
    }
''' + marker)
        marker = '    const auto before = idct_checkpoint(ctx, pc);'
        helper = helper.replace(marker, marker + '''
    static uint64_t calls = 0;
    ++calls;
    if (calls == 1 || (calls & 8191u) == 0) {
        std::fprintf(stderr, "[NumericCoverage] calls=%llu pc=%08x context=%08x\\n", (unsigned long long)calls, pc, before.context);
    }
''')
        marker = '    line << "\\n";'
        assert helper.count(marker) == 1
        helper = helper.replace(marker, '''    line << std::hex << " ctrBefore=" << before.ctr << " ctrAfter=" << after.ctr;
    line << " lrBefore=" << before.lr << " lrAfter=" << after.lr;
    line << " xerBefore=" << before.xer << " xerAfter=" << after.xer;
    line << " msrBefore=" << before.msr << " msrAfter=" << after.msr;
    line << " crBefore=" << before.cr << " crAfter=" << after.cr << " gprDiffs=";
    for (unsigned i = 0; i < 32; ++i) {
        if (gpr_mask & (1u << i)) {
            line << std::dec << i << ":" << std::hex << before.gpr[i] << "," << after.gpr[i] << ";";
        }
    }
''' + marker)
        helper = helper.replace('found->second.block == before.block)',
            'found->second.block == before.block && found->second.gpr[1] == before.gpr[1])')
        marker = 'using namespace nwii::runtime;'
        assert text.count(marker) == 1
        return '#include <map>\n#include <sstream>\n#include <iomanip>\n#include <cstdio>\n' + text.replace(marker, marker + helper), sites
    marker = 'static bool observe_psq_anomaly('
    assert text.count(marker) == 1
    return '#include <map>\n' + text.replace(marker, helper + marker), sites
