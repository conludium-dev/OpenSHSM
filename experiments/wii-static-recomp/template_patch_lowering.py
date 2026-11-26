"""Allow only the measured data-word patch and guard every emitted template instruction."""
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
        if address != 0x802119a8 and not 0x80211ba0 <= address < 0x80211c38:
            continue
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = lines[index + 1]
        if address == 0x802119a8:
            assert opcode == 0x901c0000
            assert before == '    nwii::runtime::experiment_observed_write32(ctx, ctx.gpr[28] + 0, ctx.gpr[0], 0x802119a8);\n'
            after = '    nwii::runtime::experiment_template_patch(ctx, ctx.gpr[28] + 0, ctx.gpr[0], 0x802119a8);\n'
            kind = 'patch'
        else:
            after = f'    nwii::runtime::experiment_template_execution_guard(ctx, 0x{address:08x});\n' + before
            kind = 'execution-guard'
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'kind': kind, 'before': before, 'after': after})
    return ''.join(lines), changes
