"""Enable one measured MI write and observe the next original DSP read."""
from ipc_reset_boot_lowering import lower as lower_reset
import struct


def lower(text, dol):
    text, changes = lower_reset(text, dol)
    for change in changes:
        if change.get('kind') == 'write16-observer':
            before = change['after']
            after = before.replace('experiment_boot_mmio_write16', 'experiment_mi_mask_boot_write16')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'] = after
            change['kind'] = 'scoped-mi-write16'
    marker = '    // 0x802176F4: A0A5500A\n'
    if marker in text:
        header = struct.unpack('>64I', dol[:256])
        section = next(i for i in range(7) if header[18 + i] <= 0x802176F4 < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + 0x802176F4 - header[18 + section])[0] == 0xA0A5500A
        before = '    ctx.gpr[5] = nwii::runtime::bat_memory_read16(ctx, ctx.gpr[5] + 20490); // lhz\n'
        assert text.count(marker + before) == 1
        after = '    ctx.gpr[5] = nwii::runtime::experiment_mi_boot_read16(ctx, ctx.gpr[5] + 20490, 0x802176f4); // lhz\n'
        text = text.replace(marker + before, marker + after)
        changes.append({'address': '0x802176f4', 'opcode': '0xa0a5500a', 'kind': 'read16-observer', 'before': before, 'after': after})
    return text, changes
