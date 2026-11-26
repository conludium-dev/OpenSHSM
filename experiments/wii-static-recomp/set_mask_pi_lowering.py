"""Enable the final measured-value PI store without changing the earlier caller."""
from exi_mask_boot_lowering import lower as lower_exi
import struct


def lower(text, dol):
    text, changes = lower_exi(text, dol)
    for change in changes:
        if change.get('address') == '0x802178a4':
            before = change['after']
            after = before.replace('experiment_exi_next_write32', 'experiment_set_mask_pi_write32')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-final-pi-write32'
    marker = '    // 0x8020E910: 8003680C\n'
    if marker in text:
        header = struct.unpack('>64I', dol[:256])
        section = next(i for i in range(7) if header[18 + i] <= 0x8020e910 < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + 0x8020e910 - header[18 + section])[0] == 0x8003680c
        before = '    ctx.gpr[0] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[3] + 26636); // lwz r0, 26636(r3)\n'
        after = '    ctx.gpr[0] = nwii::runtime::experiment_dsp_next_read32(ctx, ctx.gpr[3] + 26636, 0x8020e910); // lwz r0, 26636(r3)\n'
        assert text.count(marker + before) == 1
        text = text.replace(marker + before, marker + after)
        changes.append({'address': '0x8020e910', 'opcode': '0x8003680c', 'kind': 'read32-observer', 'before': before, 'after': after})
    return text, changes
