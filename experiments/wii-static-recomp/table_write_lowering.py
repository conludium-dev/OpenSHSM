"""Observe OS handler-table stores while retaining existing memory guards."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(word, 16) for word in match.groups())
        if not 0x80211a80 <= address < 0x80211b10 or opcode >> 26 != 36:
            continue
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = lines[index + 1]
        assert before.startswith('    nwii::runtime::bat_memory_write32(')
        after = before.replace('bat_memory_write32', 'experiment_table_write_observer').replace(');', f', 0x{address:08x});', 1)
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'before': before, 'after': after})
    return ''.join(lines), changes
