"""Route existing full-module memory helpers and opcode-checked BAT/HID4 registers."""
import re
import struct
from rotate_record_lowering import lower as lower_rotate_record

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    registers = {1011: None}
    for base, instruction, first in [(528, True, 0), (536, False, 0), (560, True, 4), (568, False, 4)]:
        for offset in range(8):
            registers[base + offset] = (instruction, first + offset // 2, bool(offset & 1))
    lines, changes = text.splitlines(True), []
    memory_sites = 0
    for index, line in enumerate(lines):
        updated = re.sub(r'nwii::runtime::memory_(read\w*|write\w*|psq_load|psq_store|cache_operation)\(', r'nwii::runtime::bat_memory_\1(', line)
        if updated != line:
            memory_sites += 1
            lines[index] = updated
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        ident = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        operation = (opcode >> 1) & 1023
        if opcode >> 26 != 31 or operation not in (339, 467) or ident not in registers:
            continue
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        args = '' if ident == 1011 else ', '.join(['true' if registers[ident][0] else 'false', str(registers[ident][1]), 'true' if registers[ident][2] else 'false'])
        helper = 'hid4' if ident == 1011 else 'bat'
        if operation == 467:
            before = lines[index + 1]
            assert before == f'    // unhandled mtspr {ident}\n'
            after = f'    nwii::runtime::experiment_write_{helper}(ctx, ' + (args + ', ' if args else '') + f'ctx.gpr[{register}]);\n'
            lines[index + 1] = after
        else:
            before = ''.join(lines[index + 1:index + 3])
            assert f'<< " spr=" << {ident}' in before and f'ctx.gpr[{register}] = 0; // unknown spr stub' in before
            after = f'    ctx.gpr[{register}] = nwii::runtime::experiment_read_{helper}(ctx' + (', ' + args if args else '') + ');\n'
            lines[index + 1:index + 3] = [after, '']
        changes.append({'kind': 'register', 'address': hex(address), 'opcode': hex(opcode), 'inputLine': index + 2, 'before': before, 'after': after})
    result = ''.join(lines)
    if memory_sites:
        changes.append({'kind': 'memory', 'sites': memory_sites})
    assert not re.search(r'nwii::runtime::memory_(?:read\w*|write\w*|psq_load|psq_store|cache_operation)\(', result)
    result, rotate_changes = lower_rotate_record(result, dol)
    return result, changes + rotate_changes
