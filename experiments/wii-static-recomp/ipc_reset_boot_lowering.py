"""Reuse the exact original reset-store lowering for a separate guarded boot profile."""
from ipc_reset_lowering import lower as lower_isolated
import struct


def lower(text, dol):
    text, changes = lower_isolated(text, dol)
    for change in changes:
        before = change['after']
        after = before.replace('experiment_isolated_ipc_store', 'experiment_boot_ipc_store')
        assert text.count(before) == 1 and before != after
        text = text.replace(before, after)
        change['after'] = after
    marker = '    // 0x802176E4: B0A4401C\n'
    before = '    nwii::runtime::bat_memory_write16(ctx, ctx.gpr[4] + 16412, (uint16_t)ctx.gpr[5]); // sth\n'
    if marker in text:
        header = struct.unpack('>64I', dol[:256])
        section = next(i for i in range(7) if header[18 + i] <= 0x802176E4 < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + 0x802176E4 - header[18 + section])[0] == 0xB0A4401C
        assert text.count(marker + before) == 1
        after = '    nwii::runtime::experiment_boot_mmio_write16(ctx, ctx.gpr[4] + 16412, (uint16_t)ctx.gpr[5], 0x802176e4); // sth\n'
        text = text.replace(marker + before, marker + after)
        changes.append({'address': '0x802176e4', 'opcode': '0xb0a4401c', 'kind': 'write16-observer', 'before': before, 'after': after})
    return text, changes
