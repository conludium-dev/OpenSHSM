"""Read-only paired snapshots at nonpositive/nonfinite original integer PSQ stores."""
import re
import struct

def adapt_anomalies(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n    observe_idct\([^\n]+\);\n)(    ctx\.psq_store\((\d+), ([^\n]+), 0, 6\); // psq_st\n)')
    def replace(match):
        address, word = int(match[2], 16), int(match[3], 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        sites.append({'address': address, 'word': word, 'register': int(match[5])})
        return match[1] + f'''    {{
        const uint32_t psq_address = {match[6]};
        const bool capture = observe_psq_anomaly(ctx, 0x{address:08X}, {match[5]}, psq_address, false);
{match[4]}        if (capture) {{
            observe_psq_anomaly(ctx, 0x{address:08X}, {match[5]}, psq_address, true);
        }}
    }}
'''
    text = pattern.sub(replace, text)
    assert len(sites) == 32
    helper = '''
static bool observe_psq_anomaly(nwii::runtime::CPUContext& ctx, uint32_t pc, unsigned reg, uint32_t address, bool after) {
    if (!std::getenv("NWII_THPDUMP")) {
        return false;
    }
    static unsigned count = 0;
    if (!after) {
        if (count >= 64 || (ctx.fpr[reg] > 0 && ctx.ps1[reg] > 0
            && std::isfinite(ctx.fpr[reg]) && std::isfinite(ctx.ps1[reg]))) {
            return false;
        }
        ++count;
    }
    std::ostringstream line;
    line << "[PSQAnomaly] phase=" << (after ? "after" : "before") << " hit=" << count;
    line << std::hex << " pc=" << pc << " address=" << address << " reg=" << reg;
    line << " gqr6=" << ctx.gqr[6] << " lr=" << ctx.lr;
    line << " context=" << ctx.mmu.read32(0x800000D4);
    line << " value0=" << std::hexfloat << ctx.fpr[reg] << " value1=" << ctx.ps1[reg];
    line << " bytes=" << std::hex;
    if (ctx.mmu.get_ptr(address) && address != 0xFFFFFFFF && ctx.mmu.get_ptr(address + 1)) {
        line << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(address));
        line << std::setw(2) << unsigned(ctx.mmu.read8(address + 1));
    } else {
        line << "-";
    }
    line << "\\n";
    const std::string record = line.str();
    std::fwrite(record.data(), 1, record.size(), stderr);
    return true;
}
'''
    assert 'ctx.mmu.write' not in helper
    marker = 'static void observe_idct('
    assert text.count(marker) == 1
    return text.replace(marker, helper + marker), sites
