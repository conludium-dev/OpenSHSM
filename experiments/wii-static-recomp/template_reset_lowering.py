"""Permit only the observed reset caller on the existing template word contract."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        if line != '    // 0x80211B0C: 937C0000\n':
            continue
        address = 0x80211b0c
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x937c0000
        before = lines[index + 1]
        assert before == '    nwii::runtime::experiment_table_write_observer(ctx, ctx.gpr[28] + 0, ctx.gpr[27], 0x80211b0c); // stw r27, 0(r28)\n'
        after = before.replace('experiment_table_write_observer', 'experiment_template_reset')
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': '0x937c0000', 'before': before, 'after': after})
    return ''.join(lines), changes
