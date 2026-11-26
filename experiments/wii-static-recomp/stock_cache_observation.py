"""Extend the existing context observer privately; keep earlier headers and captures immutable."""
import struct

def extend_header(text, filtered=False):
    text = text.replace('stage > 3', 'stage > 8').replace('std::array<uint64_t, 4>', 'std::array<uint64_t, 9>')
    text = text.replace('    static unsigned records = 0;',
        '    static unsigned records = 0, criticalRecords = 0;\n    static std::array<unsigned, 9> stageRecords{};')
    start = text.index('    const bool zero_resume =')
    end = text.index('    std::ofstream file', start)
    text = text[:start] + '''    const bool critical = (stage == 2 || stage == 3) && target != 0
        && context_word(ctx, target + 0x198) == 0;
    if (stage >= 4 && stage != 8 && ctx.lr != 0x8009BB9C) {
        return;
    }
    if (critical) {
        if (criticalRecords >= 16) {
            return;
        }
        ++criticalRecords;
    } else {
        const unsigned limit = stage < 4 ? 512 : 1024;
        const bool selected = stage < 4 ? (hit <= 16 || hit % 1024 == 0 || ctx.pc == 0x80212FC4)
            : (hit <= 256 || hit % 60 == 0);
        if (stageRecords[stage] >= limit || !selected) {
            return;
        }
        ++stageRecords[stage];
    }
''' + text[end:]
    text = text.replace(r'<< ",\"msr\":" << ctx.msr',
        r'<< ",\"ctr\":" << ctx.ctr << ",\"gpr3\":" << ctx.gpr[3] << ",\"gpr4\":" << ctx.gpr[4]'
        + '\n        ' + r'<< ",\"gpr5\":" << ctx.gpr[5] << ",\"msr\":" << ctx.msr')
    assert 'gpr3' in text and 'criticalRecords >= 16' in text
    if filtered:
        marker = '    if (stage >= 4 && stage != 8 && ctx.lr != 0x8009BB9C) {\n        return;\n    }\n'
        assert text.count(marker) == 1
        text = text.replace(marker, '')
        marker_hit = '    const uint64_t hit = ++hits[stage];'
        assert text.count(marker_hit) == 1
        text = text.replace(marker_hit, marker + marker_hit)
    return text

sites = {0x8009BB98: 0x48177409, 0x80212FA0: 0x28040000,
    0x80212FC4: 0x4200FFF8, 0x80212FC8: 0x4E800020}

def verify_sites(dol):
    header = struct.unpack('>64I', dol[:256])
    for address, expected in sites.items():
        section = next(i for i in range(18) if header[18 + i] <= address
            and address + 4 <= header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == expected, hex(address)

def adapt_guest(text, index):
    points = [(0x8009BB98, 8)] if index == 11 else [(0x80212FA0, 4), (0x80212FC4, 5), (0x80212FC8, 7)]
    for address, stage in points:
        marker = f'loc_{address:08X}: ;'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'\n    stock_loading_observation::observe_context(ctx, {stage}, 0x{address:08X});')
    if index == 38:
        start = text.index('void func_80212FA0(')
        end = text.index('\nvoid func_', start + 1)
        body = text[start:end]
        marker = '    if (process_pending_callbacks(ctx)) return;'
        assert body.count(marker) == 1
        body = body.replace(marker, marker + '\n    stock_loading_observation::observe_context(ctx, 6, 0x80212FC4);')
        text = text[:start] + body + text[end:]
    return '#include "stock_context_observation.h"\n' + text
