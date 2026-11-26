"""Admit indexed addressing through existing PSQ helpers in an explicit verified float profile."""
import re
import struct


def lower_indexed(text, dol):
    pattern = re.compile(r'(?P<prefix>loc_(?P<address>[0-9A-F]+): ;\n    // 0x(?P=address): (?P<word>[0-9A-F]{8})\n)'
        r'    std::cerr << "UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << [67] << " XO_10 " << \d+ << " at 0x" << std::hex << ctx.pc << std::dec << "\\n"; std::exit\(1\);\n'
        r'    ctx.fpr\[\d+\] = 0.0;\n    ctx.ps1\[\d+\] = 0.0;\n')
    sites = []
    def replace(match):
        address = int(match['address'], 16)
        word = int(match['word'], 16)
        assert word >> 26 == 4 and ((word >> 1) & 63) in (6, 7, 38, 39) and not word & 1
        matched = False
        for index in range(7):
            offset = struct.unpack_from('>I', dol, index * 4)[0]
            start = struct.unpack_from('>I', dol, 0x48 + index * 4)[0]
            size = struct.unpack_from('>I', dol, 0x90 + index * 4)[0]
            if start <= address and address + 4 <= start + size:
                assert struct.unpack_from('>I', dol, offset + address - start)[0] == word
                matched = True
        assert matched
        sites.append({'address': address, 'word': word})
        return match['prefix'] + '    shsm_psq_indexed(ctx, 0x' + match['word'] + 'u, 0x' + match['address'] + 'u);\n'
    lowered = pattern.sub(replace, text)
    if sites:
        lowered = '#include "stock_psq_indexed.h"\n' + lowered
    return lowered, sites
