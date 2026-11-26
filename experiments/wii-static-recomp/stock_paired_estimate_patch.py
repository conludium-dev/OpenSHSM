"""Replace only DOL-verified estimate fatal blocks; retain guards and instruction counts."""
import re
import struct


def adapt(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = (r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n'
        r'    stock_fp_preinstruction\(ctx, 0x\3, 0x\2\);\n)'
        r'    std::cerr << "UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << (24|26)'
        r' << " XO_10 " << (24|26) << " at 0x" << std::hex << ctx.pc << std::dec'
        r' << "\\n"; std::exit\(1\);\n'
        r'    ctx.fpr\[(\d+)\] = 0.0;\n    ctx.ps1\[\6\] = 0.0;\n')

    def replace(match):
        address, opcode = int(match[2], 16), int(match[3], 16)
        xo = (opcode >> 1) & 1023
        assert opcode >> 26 == 4 and xo == int(match[4]) == int(match[5])
        assert not opcode & 0x001f0000 and (opcode >> 21) & 31 == int(match[6])
        index = next(i for i in range(18) if layout[18 + i] <= address
            and address + 4 <= layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[index] + address - layout[18 + index])[0] == opcode
        sites.append({'address': address, 'opcode': opcode})
        return match[1] + f'    stock_paired_estimate(ctx, 0x{opcode:08X});\n'

    patched = re.sub(pattern, replace, text)
    if sites:
        patched = '#include "stock_paired_estimates.h"\n' + patched
    assert patched.count('++ctx.inst_count;') == text.count('++ctx.inst_count;')
    assert patched.count('stock_fp_preinstruction(') == text.count('stock_fp_preinstruction(')
    return patched, sites
