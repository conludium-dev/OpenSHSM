"""Restore Wii HID2 guest accesses through the existing processor adapter."""
import re
import struct


def lower_hid2(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines = text.splitlines(True)
    changes = []
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if opcode >> 26 != 31 or ((opcode >> 1) & 1023) not in (339, 467):
            continue
        spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        if spr != 920:
            continue
        section = next(section for section in range(18)
            if header[18 + section] <= address < header[18 + section] + header[36 + section])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        write = ((opcode >> 1) & 1023) == 467
        prior = lines[index + 1]
        if write:
            assert prior.strip() == '// unhandled mtspr 920'
            replacement = f'    nwii::runtime::experiment_write_hid2(ctx, ctx.gpr[{register}]);\n'
        else:
            assert prior.strip() == f'ctx.gpr[{register}] = 0; // mfspr HID 920'
            replacement = f'    ctx.gpr[{register}] = nwii::runtime::experiment_read_hid2(ctx);\n'
        lines[index + 1] = replacement
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'spr': spr,
            'operation': 'write' if write else 'read', 'register': register,
            'priorLowering': prior.strip(), 'adapterLowering': replacement.strip()})
    return ''.join(lines), changes
