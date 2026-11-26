"""Specialize the existing guard on the verified instruction word, retaining runtime state checks."""
import re
import struct


def specialize(header, text, dol):
    start = header.index('inline bool stock_uses_fp(')
    end = header.index('\ninline bool stock_scalar_fp_available', start)
    classification = header[start:end].replace('inline bool stock_uses_fp(',
        'constexpr bool stock_constant_uses_fp(', 1)
    start = header.index('inline void stock_fp_preinstruction(')
    end = header.index('\n}\n}', start) + 2
    guard = header[start:end].replace(
        'inline void stock_fp_preinstruction(CPUContext& ctx, uint32_t opcode, uint32_t instruction)',
        'template<uint32_t Opcode>\ninline void stock_constant_fp_preinstruction(CPUContext& ctx, uint32_t instruction)', 1)
    guard = guard.replace('    const uint32_t primary = opcode >> 26;',
        '    constexpr uint32_t primary = Opcode >> 26;')
    guard = guard.replace('    const bool quantized =', '    constexpr bool quantized =')
    guard = guard.replace('    if (primary == 4 || quantized)', '    if constexpr (primary == 4 || quantized)')
    before = '    if (stock_uses_fp(opcode) && !stock_scalar_fp_available(ctx, instruction)) {\n        longjmp(ctx.exception_jmp_buf, 1);\n    }'
    assert guard.count(before) == 1
    guard = guard.replace(before, '    if constexpr (stock_constant_uses_fp(Opcode)) {\n'
        '        if (!stock_scalar_fp_available(ctx, instruction)) {\n'
        '            longjmp(ctx.exception_jmp_buf, 1);\n        }\n    }')
    generated = '#pragma once\n#include "stock_fp_unavailable.h"\nnamespace nwii::runtime {\n' + classification + guard + '\n}\n'
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = r'    stock_fp_preinstruction\(ctx, 0x([0-9A-F]{8}), 0x([0-9A-F]{8})\);'
    def replace(match):
        opcode, address = int(match[1], 16), int(match[2], 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
        assert f'// 0x{address:08X}: {opcode:08X}' in text
        sites.append({'address': address, 'opcode': opcode})
        return f'    stock_constant_fp_preinstruction<0x{opcode:08X}>(ctx, 0x{address:08X});'
    modified = re.sub(pattern, replace, text)
    assert sites
    restored = re.sub(r'    stock_constant_fp_preinstruction<0x([0-9A-F]{8})>\(ctx, 0x([0-9A-F]{8})\);',
        lambda m: f'    stock_fp_preinstruction(ctx, 0x{m[1]}, 0x{m[2]});', modified)
    assert restored == text
    return generated, '#include "constant_fp_guard.h"\n' + modified, sites
