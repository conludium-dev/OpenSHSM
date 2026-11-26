"""Change only opcode-checked HID0 writers; preserve existing BAT/cache helper routes."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match or 'experiment_write_hid0_dcache' not in lines[index + 1]:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) == 467
        assert ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5) == 1008
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        before = lines[index + 1]
        assert before == f'    nwii::runtime::experiment_write_hid0_dcache(ctx, ctx.gpr[{register}]);\n'
        after = before.replace('experiment_write_hid0_dcache', 'experiment_write_hid0_spd')
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'before': before, 'after': after})
    return ''.join(lines), changes
