"""Opcode-checked conditional backedge polling, preserving strict taken-path callbacks."""
import re
import struct

def condition(opcode):
    bo, bi = (opcode >> 21) & 31, (opcode >> 16) & 31
    terms = []
    if not bo & 4:
        terms.append('ctx.ctr == 0' if bo & 2 else 'ctx.ctr != 0')
    if not bo & 16:
        field = ('lt', 'gt', 'eq', 'so')[bi % 4]
        terms.append(('' if bo & 8 else '!') + f'ctx.cr[{bi // 4}].{field}')
    return ' && '.join(terms) or 'true'

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines = text.splitlines(True)
    output, changes = [], []
    index = 0
    while index < len(lines):
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', lines[index])
        if not match:
            output.append(lines[index])
            index += 1
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if opcode >> 26 != 16 or condition(opcode) == 'true' or lines[index + 1].strip() != f'ctx.pc = 0x{address:X};':
            output.append(lines[index])
            index += 1
            continue
        assert lines[index + 2].strip() == 'if (process_pending_callbacks(ctx)) return;'
        assert 'Spinning at PC:' in lines[index + 3]
        end = index + 4
        while lines[end].strip() in ('ctx.ctr--;', f'ctx.lr = 0x{address + 4:X}; // save return address'):
            end += 1
        jump = re.fullmatch(r'    if \((.+)\) goto loc_([0-9A-F]{8});\n', lines[end])
        assert jump and jump[1] == condition(opcode), (hex(address), lines[end])
        displacement = opcode & 0xfffc
        if displacement & 0x8000:
            displacement -= 0x10000
        target = (displacement if opcode & 2 else address + displacement) & 0xffffffff
        assert int(jump[2], 16) == target and target <= address
        assert f'loc_{target:08X}: ;' in text
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == opcode
        setup = lines[index + 4:end]
        assert sum(line.strip() == 'ctx.ctr--;' for line in setup) == int(not ((opcode >> 21) & 4))
        assert sum('ctx.lr =' in line for line in setup) == (opcode & 1)
        before = ''.join(lines[index:end + 1])
        after = lines[index] + ''.join(setup) + lines[index + 1] + f'    if ({jump[1]}) {{\n'
        after += '    ' + lines[index + 2] + '    ' + lines[index + 3]
        after += f'        goto loc_{target:08X};\n    }}\n'
        output.append(after)
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'target': hex(target),
                        'condition': jump[1], 'inputLine': index + 1, 'before': before, 'after': after})
        index = end + 1
    return ''.join(output), changes
