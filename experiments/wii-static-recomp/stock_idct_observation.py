"""Bounded read-only observations at own-DOL-checked original IDCT instructions."""
import re
import struct

def adapt_idct(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)(    ctx\.psq_store\((\d+), ([^\n]+), 0, 6\); // psq_st\n)')
    def check(address, word):
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
    def store(match):
        address, word = int(match[2], 16), int(match[3], 16)
        check(address, word)
        sites.append({'address': address, 'word': word, 'kind': 'store', 'register': int(match[5])})
        return match[1] + f'    observe_idct(ctx, 0x{address:08X}, false, {match[6]});\n' + match[4]
    text = pattern.sub(store, text)
    for address in (0x8020AFD0, 0x8020B460, 0x8020B900):
        marker = f'loc_{address:08X}: ;\n'
        assert text.count(marker) == 1
        word = int(re.search(marker + r'    // 0x[0-9A-F]+: ([0-9A-F]+)', text)[1], 16)
        check(address, word)
        sites.append({'address': address, 'word': word, 'kind': 'entry'})
        text = text.replace(marker, marker + f'    observe_idct(ctx, 0x{address:08X}, true, ctx.gpr[3]);\n')
    helper = '''
static void observe_idct(nwii::runtime::CPUContext& ctx, uint32_t pc, bool entry, uint32_t address) {
    if (!std::getenv("NWII_THPDUMP")) {
        return;
    }
    static unsigned entries = 0, stores = 0;
    unsigned& count = entry ? entries : stores;
    if (count >= (entry ? 6u : 32u)) {
        return;
    }
    ++count;
    std::ostringstream line;
    line << "[IDCTState] kind=" << (entry ? "entry" : "store") << " hit=" << count;
    line << std::hex << " pc=" << pc << " address=" << address;
    line << " r2=" << ctx.gpr[2] << " r13=" << ctx.gpr[13];
    line << " gqr0=" << ctx.gqr[0] << " gqr5=" << ctx.gqr[5] << " gqr6=" << ctx.gqr[6];
    auto memory = [&](const char* name, uint32_t location, unsigned size) {
        line << " " << name << "=";
        if (location > 0xFFFFFFFFu - size || !ctx.mmu.get_ptr(location) || !ctx.mmu.get_ptr(location + size - 1)) {
            line << "-";
            return;
        }
        const uint8_t* bytes = ctx.mmu.get_ptr(location);
        for (unsigned i = 0; i < size; ++i) {
            line << std::setw(2) << std::setfill('0') << unsigned(bytes[i]);
        }
    };
    memory("data", address, entry ? 128 : 16);
    const uint32_t table_slot = ctx.gpr[13] - 15904u;
    if (ctx.mmu.get_ptr(table_slot) && ctx.mmu.get_ptr(table_slot + 3)) {
        const uint32_t table = ctx.mmu.read32(table_slot);
        line << " table=" << table;
        memory("qdata", table, 256);
    }
    memory("constants", ctx.gpr[2] - 19232u, 20);
    line << " fpr=" << std::hexfloat;
    for (unsigned i = 0; i < 32; ++i) {
        line << ctx.fpr[i] << "," << ctx.ps1[i] << ";";
    }
    line << "\\n";
    const std::string record = line.str();
    std::fwrite(record.data(), 1, record.size(), stderr);
}
'''
    assert 'ctx.mmu.write' not in helper
    marker = 'using namespace nwii::runtime;'
    assert text.count(marker) == 1
    return '#include <sstream>\n#include <iomanip>\n#include <cstdio>\n#include <cstdlib>\n' + text.replace(marker, marker + helper), sites
