"""Route only original PI-mask store through the existing vendor register."""
import struct

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    lines, changes = text.splitlines(True), []
    for index, line in enumerate(lines):
        if line != '    // 0x802175D0: 90A43004\n':
            continue
        address = 0x802175d0
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x90a43004
        before = lines[index + 1]
        assert before == '    nwii::runtime::experiment_mmio_write_observer(ctx, ctx.gpr[4] + 12292, ctx.gpr[5], 0x802175d0); // stw r5, 12292(r4)\n'
        after = before.replace('experiment_mmio_write_observer', 'experiment_pi_mask_write')
        lines[index + 1] = after
        changes.append({'address': hex(address), 'opcode': '0x90a43004', 'before': before, 'after': after})
    return ''.join(lines), changes
