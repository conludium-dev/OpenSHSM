"""Enable the measured CSR selection pair in the original boot route."""
from exi_init_boot_lowering import lower as lower_init
import struct


def lower(text, dol):
    text, changes = lower_init(text, dol)
    for change in changes:
        if change.get('address') == '0x8020e3c0':
            before = change['after']
            after = before.replace('experiment_dsp_next_read32', 'experiment_exi_select_boot_read32')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-exi-select-read32'
    marker = '    // 0x8020E3E0: 90646800\n'
    if marker in text:
        header = struct.unpack('>64I', dol[:256])
        section = next(i for i in range(7) if header[18 + i] <= 0x8020e3e0 < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + 0x8020e3e0 - header[18 + section])[0] == 0x90646800
        before = '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[4] + 26624, ctx.gpr[3]); // stw r3, 26624(r4)\n'
        after = '    nwii::runtime::experiment_exi_select_boot_write32(ctx, ctx.gpr[4] + 26624, ctx.gpr[3], 0x8020e3e0); // stw r3, 26624(r4)\n'
        assert text.count(marker + before) == 1
        text = text.replace(marker + before, marker + after)
        changes.append({'address': '0x8020e3e0', 'opcode': '0x90646800', 'kind': 'scoped-exi-select-write32', 'before': before, 'after': after})
    marker = '    // 0x8020DA84: 90036810\n'
    if marker in text:
        header = struct.unpack('>64I', dol[:256])
        section = next(i for i in range(7) if header[18 + i] <= 0x8020da84 < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + 0x8020da84 - header[18 + section])[0] == 0x90036810
        before = '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + 26640, ctx.gpr[0]); // stw r0, 26640(r3)\n'
        after = '    nwii::runtime::experiment_exi_next_write32(ctx, ctx.gpr[3] + 26640, ctx.gpr[0], 0x8020da84); // stw r0, 26640(r3)\n'
        assert text.count(marker + before) == 1
        text = text.replace(marker + before, marker + after)
        changes.append({'address': '0x8020da84', 'opcode': '0x90036810', 'kind': 'observed-exi-immediate-write32', 'before': before, 'after': after})
    return text, changes
