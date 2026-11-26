"""Replace only six original boot setter writes; context restores stay quarantined."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    sites = {0x80210720: (0, 952), 0x80210730: (1, 956), 0x80210740: (2, 953),
             0x80210750: (3, 954), 0x80210760: (4, 957), 0x80210770: (5, 958)}
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if address not in sites:
            continue
        target, ident = sites[address]
        assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) == 467 and (opcode >> 21) & 31 == 3
        assert ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5) == ident
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = lines[index + 1]
        assert before == f'    // unhandled mtspr {ident}\n'
        after = f'    nwii::runtime::experiment_reset_performance(ctx, {target}, ctx.gpr[3]);\n'
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'inputLine': index + 2, 'before': before, 'after': after})
    return ''.join(lines), changes
