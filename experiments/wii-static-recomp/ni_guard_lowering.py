"""Guard unverified FP instructions before effects; lower only original NI bit setter."""
import re
import struct

def fp_opcode(opcode):
    primary = opcode >> 26
    return primary == 4 or 48 <= primary <= 57 or primary in (59, 60, 61, 63) or (
        primary == 31 and ((opcode >> 1) & 1023) in (535, 567, 599, 631, 663, 695, 727, 759, 983))

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if not fp_opcode(opcode):
            continue
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = lines[index + 1]
        if address == 0x80210830:
            assert opcode == 0xffa0004c and 'mtfsb1/mtfsb0 stub' in before
            after = f'    nwii::runtime::experiment_ni_set(ctx, 0x{opcode:08x});\n'
            kind = 'setter'
        else:
            after = f'    nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x});\n' + before
            kind = 'guard'
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'kind': kind, 'before': before, 'after': after})
    return ''.join(lines), changes
