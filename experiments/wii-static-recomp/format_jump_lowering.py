"""Restore the original parse_format jump table without changing vendor code."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    def offset(address):
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        return header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', dol, offset(0x80199db4))[0] == 0x4e800420
    entries = struct.unpack_from('>56I', dol, offset(0x80427a18))
    targets = sorted(set(entries))
    assert len(targets) == 10 and all(0x80199a24 <= target < 0x80199fe0 for target in targets)
    start = text.index('void func_80199A24(CPUContext& ctx) {')
    end = text.index('\nvoid func_', start + 1)
    body = text[start:end]
    before = '    // 0x80199DB4: 4E800420\n    ctx.pc = ctx.ctr; return;\n    ++ctx.inst_count;\n'
    assert body.count(before) == 1
    after = '    // 0x80199DB4: 4E800420\n    ctx.pc = ctx.ctr;\n    ++ctx.inst_count;\n    switch (ctx.ctr) {\n'
    for target in targets:
        if f'loc_{target:08X}: ;' in body:
            after += f'        case 0x{target:08X}: goto loc_{target:08X};\n'
        else:
            alias_start = text.index(f'void func_{target:08X}(CPUContext& ctx) {{')
            alias_end = text.find('\nvoid func_', alias_start + 1)
            alias = text[alias_start:alias_end if alias_end >= 0 else len(text)]
            assert f'// 0x{target:08X}:' in alias
            for address, opcode in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', alias):
                assert struct.unpack_from('>I', dol, offset(int(address, 16)))[0] == int(opcode, 16)
            after += f'        case 0x{target:08X}: func_{target:08X}(ctx); return;\n'
    after += '        default: throw std::runtime_error("parse_format target outside original jump table");\n    }\n'
    changed = body.replace(before, after)
    return text[:start] + changed + text[end:], [{'address': '0x80199db4', 'opcode': '0x4e800420',
        'table': '0x80427a18', 'entries': list(entries), 'targets': targets, 'before': before, 'after': after}]
