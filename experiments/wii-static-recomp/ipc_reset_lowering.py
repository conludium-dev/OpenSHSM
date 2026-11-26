"""Expose one original store to an isolated fixture; retain unchanged live refusal."""
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        if line != '    // 0x802175D4: 90030034\n':
            continue
        address = 0x802175d4
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x90030034
        before = lines[index + 1]
        assert before == '    nwii::runtime::experiment_mmio_write_observer(ctx, ctx.gpr[3] + 52, ctx.gpr[0], 0x802175d4); // stw r0, 52(r3)\n'
        after = before.replace('experiment_mmio_write_observer', 'experiment_isolated_ipc_store')
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': '0x90030034', 'before': before, 'after': after})
    return ''.join(lines), changes
