"""Opcode-verified pre-instruction guards; original instructions remain in private output."""
import re
import struct


def uses_fp(opcode, tables):
    primary, xo = opcode >> 26, (opcode >> 1) & 1023
    if primary == 4:
        return xo in tables['table4'] or (xo & 31) in tables['table4_2'] or (xo & 63) in tables['table4_3']
    if primary == 31:
        return xo in tables['table31']
    if primary == 59:
        return (xo & 31) in tables['table59']
    if primary == 63:
        return xo in tables['table63'] or (xo & 31) in tables['table63_2']
    return primary in tables['primary_table']


def lower(text, dol, tables):
    layout = struct.unpack('>64I', dol[:256])
    sites, fpscr = [], []
    def replace(match):
        address, opcode = int(match[1], 16), int(match[2], 16)
        primary, xo = opcode >> 26, (opcode >> 1) & 1023
        guarded = uses_fp(opcode, tables) or primary == 4
        if not guarded:
            return match[0]
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
        sites.append({'address': address, 'opcode': opcode, 'usesFP': uses_fp(opcode, tables)})
        return match[0] + f'    stock_fp_preinstruction(ctx, 0x{opcode:08X}, 0x{address:08X});\n'
    text = re.sub(r'^    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', replace, text, flags=re.M)
    for site in sites:
        address, opcode = site['address'], site['opcode']
        if opcode >> 26 != 63:
            continue
        xo = (opcode >> 1) & 1023
        marker = f'    // 0x{address:08X}: {opcode:08X}\n    stock_fp_preinstruction(ctx, 0x{opcode:08X}, 0x{address:08X});\n'
        if xo == 711:
            before = '    // mtfsf stub (ignore FPSCR write)\n'
            after = f'    experiment_mtfsf(ctx, 0x{opcode:08X});\n'
        elif xo == 583:
            register = (opcode >> 21) & 31
            before = f'    ctx.fpr[{register}] = 0.0; // mffs stub\n'
            after = f'    ctx.fpr[{register}] = std::bit_cast<double>(uint64_t(ctx.fpscr));\n'
            if opcode & 1:
                raise AssertionError('mffs Rc needs separately verified CR1 lowering')
        else:
            continue
        assert text.count(marker + before) >= 1 or text.count(marker + after) >= 1, hex(address)
        text = text.replace(marker + before, marker + after)
        fpscr.append(site)
    marker = 'loc_80213E40: ;\n    // 0x80213E40: 4C000064\n'
    if marker in text:
        section = next(i for i in range(18) if layout[18 + i] <= 0x80213E40 < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + 0x80213E40 - layout[18 + section])[0] == 0x4C000064
        start = text.index(marker)
        end = text.index('\n}', start)
        body = text[start:end]
        before = '        ctx.dispatch_saved_ctx = 0; // exit ISR\n'
        assert body.count(before) == 1
        text = text[:start] + body.replace(before, '') + text[end:]
    if sites:
        text = '#include "stock_fp_unavailable.h"\n#include "fpscr_adapter.h"\n' + text
    return text, sites, fpscr
