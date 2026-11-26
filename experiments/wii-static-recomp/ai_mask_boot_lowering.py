"""Enable original AI mask block and observe the next EXI read."""
from dsp_mask_boot_lowering import lower as lower_dsp
import struct


def lower(text, dol):
    text, changes = lower_dsp(text, dol)
    for change in changes:
        if change.get('address') == '0x80217734':
            before = change['after']
            after = before.replace('experiment_dsp_next_read32', 'experiment_ai_boot_read32')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-ai-read32'
    sites = [
        (0x80217750, 0x90A46C00, '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[4] + 27648, ctx.gpr[5]); // stw r5, 27648(r4)\n',
         '    nwii::runtime::experiment_ai_boot_write32(ctx, ctx.gpr[4] + 27648, ctx.gpr[5], 0x80217750); // stw r5, 27648(r4)\n', 'scoped-ai-write32'),
        (0x80217760, 0x80A56800, '    ctx.gpr[5] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[5] + 26624); // lwz r5, 26624(r5)\n',
         '    ctx.gpr[5] = nwii::runtime::experiment_dsp_next_read32(ctx, ctx.gpr[5] + 26624, 0x80217760); // lwz r5, 26624(r5)\n', 'read32-observer')]
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
