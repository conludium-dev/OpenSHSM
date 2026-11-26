"""Route original TBL/TBU reads to one explicit experimental clock provider."""
import re
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines = text.splitlines(True)
    changes = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        after = lines[index + 1]
        if 'ctx.read_timebase()' not in after:
            continue
        ident = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) in (339, 371) and ident in (268, 269)
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        expected = f'    ctx.gpr[{register}] = (uint32_t)(ctx.read_timebase() ' + ('>> 32); // mftbu\n' if ident == 269 else '& 0xFFFFFFFF); // mftb\n')
        assert after == expected
        replacement = after.replace('ctx.read_timebase()', 'nwii::runtime::experiment_read_timebase(ctx)')
        lines[index + 1] = replacement
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'inputLine': index + 2, 'before': after, 'after': replacement})
    result = ''.join(lines)
    assert 'ctx.read_timebase()' not in result
    return result, changes
