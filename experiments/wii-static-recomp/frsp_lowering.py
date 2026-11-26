"""Replace original-address FRSP casts with verified FPR/status updates."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if opcode >> 26 != 63 or ((opcode >> 1) & 1023) != 12:
            continue
        assert not opcode & 1
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        source, destination = (opcode >> 11) & 31, (opcode >> 21) & 31
        before = lines[index + 1]
        assert before == f'    ctx.fpr[{destination}] = (double)(float)ctx.fpr[{source}]; // frsp\n'
        after = f'    nwii::runtime::experiment_frsp(ctx, 0x{opcode:08x});\n'
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'before': before, 'after': after})
    return ''.join(lines), changes
