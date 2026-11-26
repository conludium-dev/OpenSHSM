"""Correct CR0.SO on the backend's rlwimi./rlwinm. record forms."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index in range(len(lines) - 1, -1, -1):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', lines[index])
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if opcode >> 26 not in (20, 21) or not opcode & 1:
            continue
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = ''.join(lines[index + 1:index + 5])
        assert '// rlw' in lines[index + 1]
        assert 'ctx.cr[0].lt' in lines[index + 2] and 'ctx.cr[0].gt' in lines[index + 3] and 'ctx.cr[0].eq' in lines[index + 4]
        assert 'ctx.cr[0].so' not in lines[index + 5]
        added = '    ctx.cr[0].so = (ctx.xer >> 31) & 1;\n'
        lines.insert(index + 5, added)
        changes.append({'kind': 'rotate-record', 'address': hex(address), 'opcode': hex(opcode), 'before': before, 'after': before + added})
    return ''.join(lines), list(reversed(changes))
