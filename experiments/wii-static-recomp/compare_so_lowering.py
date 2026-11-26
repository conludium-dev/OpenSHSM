"""Restore XER.SO propagation for opcode-checked integer comparisons."""
import re
import struct


def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    pattern = r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)(.*?)(?=    // 0x[0-9A-F]{8}:|\Z)'
    changes = []

    def replace(match):
        address, opcode = int(match[2], 16), int(match[3], 16)
        primary = opcode >> 26
        if primary not in (10, 11) and not (primary == 31 and ((opcode >> 1) & 1023) in (0, 32)):
            return match[0]
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == opcode
        field = (opcode >> 23) & 7
        body = match[4]
        if f'ctx.cr[{field}].so =' in body:
            assert f'ctx.cr[{field}].so = (ctx.xer >> 31) & 1;' in body
            return match[0]
        equality = re.search(rf'    ctx\.cr\[{field}\]\.eq = [^\n]+;\n', body)
        assert equality, hex(address)
        addition = f'    ctx.cr[{field}].so = (ctx.xer >> 31) & 1;\n'
        body = body[:equality.end()] + addition + body[equality.end():]
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'crField': field})
        return match[1] + body

    return re.sub(pattern, replace, text, flags=re.S), changes
