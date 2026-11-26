"""Reuse MI boot lowering and enable the measured original DSP block."""
from mi_mask_boot_lowering import lower as lower_mi
import struct


def lower(text, dol):
    text, changes = lower_mi(text, dol)
    for change in changes:
        if change.get('address') == '0x802176f4':
            before = change['after']
            after = before.replace('experiment_mi_boot_read16', 'experiment_dsp_boot_read16')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-dsp-read16'
    sites = [
        (0x80217724, 0xB0A4500A, '    nwii::runtime::bat_memory_write16(ctx, ctx.gpr[4] + 20490, (uint16_t)ctx.gpr[5]); // sth\n',
         '    nwii::runtime::experiment_dsp_boot_write16(ctx, ctx.gpr[4] + 20490, (uint16_t)ctx.gpr[5], 0x80217724); // sth\n', 'scoped-dsp-write16'),
        (0x80217734, 0x80A46C00, '    ctx.gpr[5] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[4] + 27648); // lwz r5, 27648(r4)\n',
         '    ctx.gpr[5] = nwii::runtime::experiment_dsp_next_read32(ctx, ctx.gpr[4] + 27648, 0x80217734); // lwz r5, 27648(r4)\n', 'read32-observer')]
    header = struct.unpack('>64I', dol[:256])
    for address, opcode, before, after, kind in sites:
        marker = f'    // 0x{address:08X}: {opcode:08X}\n'
        if marker not in text:
            continue
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        assert text.count(marker + before) == 1
        text = text.replace(marker + before, marker + after)
        changes.append({'address': f'0x{address:08x}', 'opcode': f'0x{opcode:08x}', 'kind': kind, 'before': before, 'after': after})
    return text, changes
