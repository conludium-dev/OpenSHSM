"""Enable measured three-channel EXI masks and observe the next PI write."""
from ai_mask_boot_lowering import lower as lower_ai
import struct


def lower(text, dol):
    text, changes = lower_ai(text, dol)
    for change in changes:
        if change.get('address') == '0x80217760':
            before = change['after']
            after = before.replace('experiment_dsp_next_read32', 'experiment_exi_boot_read32')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-exi-read32'
    sites = []
    for address, opcode, offset in [(0x802177a4, 0x80a56814, 26644), (0x802177e8, 0x80a56828, 26664)]:
        before = f'    ctx.gpr[5] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[5] + {offset}); // lwz r5, {offset}(r5)\n'
        after = f'    ctx.gpr[5] = nwii::runtime::experiment_exi_boot_read32(ctx, ctx.gpr[5] + {offset}, 0x{address:08x}); // lwz r5, {offset}(r5)\n'
        sites.append((address, opcode, before, after, 'scoped-exi-read32'))
    for address, opcode, offset in [(0x80217794, 0x90a46800, 26624), (0x802177d8, 0x90a46814, 26644), (0x8021780c, 0x90a46828, 26664)]:
        before = f'    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[4] + {offset}, ctx.gpr[5]); // stw r5, {offset}(r4)\n'
        after = f'    nwii::runtime::experiment_exi_boot_write32(ctx, ctx.gpr[4] + {offset}, ctx.gpr[5], 0x{address:08x}); // stw r5, {offset}(r4)\n'
        sites.append((address, opcode, before, after, 'scoped-exi-write32'))
    sites.append((0x802178a4, 0x90a43004,
                  '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[4] + 12292, ctx.gpr[5]); // stw r5, 12292(r4)\n',
                  '    nwii::runtime::experiment_exi_next_write32(ctx, ctx.gpr[4] + 12292, ctx.gpr[5], 0x802178a4); // stw r5, 12292(r4)\n', 'write32-observer'))
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
