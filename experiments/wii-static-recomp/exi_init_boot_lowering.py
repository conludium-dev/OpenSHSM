"""Enable measured idle polls and CSR initialization within original EXIInit."""
from set_mask_pi_lowering import lower as lower_pi
import struct


def lower(text, dol):
    text, changes = lower_pi(text, dol)
    for change in changes:
        if change.get('address') == '0x8020e910':
            before = change['after']
            after = before.replace('experiment_dsp_next_read32', 'experiment_exi_init_boot_read32')
            assert text.count(before) == 1
            text = text.replace(before, after)
            change['after'], change['kind'] = after, 'scoped-exi-idle-read32'
    sites = []
    for address, opcode, offset in [(0x8020e920, 0x80036820, 26656), (0x8020e930, 0x80036834, 26676)]:
        before = f'    ctx.gpr[0] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[3] + {offset}); // lwz r0, {offset}(r3)\n'
        after = f'    ctx.gpr[0] = nwii::runtime::experiment_exi_init_boot_read32(ctx, ctx.gpr[3] + {offset}, 0x{address:08x}); // lwz r0, {offset}(r3)\n'
        sites.append((address, opcode, before, after, 'scoped-exi-idle-read32'))
    for address, opcode, offset, reg in [(0x8020e954, 0x93836800, 26624, 28), (0x8020e958, 0x93836814, 26644, 28), (0x8020e95c, 0x93836828, 26664, 28), (0x8020e964, 0x90036800, 26624, 0)]:
        before = f'    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + {offset}, ctx.gpr[{reg}]); // stw r{reg}, {offset}(r3)\n'
        after = f'    nwii::runtime::experiment_exi_init_boot_write32(ctx, ctx.gpr[3] + {offset}, ctx.gpr[{reg}], 0x{address:08x}); // stw r{reg}, {offset}(r3)\n'
        sites.append((address, opcode, before, after, 'scoped-exi-init-write32'))
    sites.append((0x8020e3c0, 0x80646800,
                  '    ctx.gpr[3] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[4] + 26624); // lwz r3, 26624(r4)\n',
                  '    ctx.gpr[3] = nwii::runtime::experiment_dsp_next_read32(ctx, ctx.gpr[4] + 26624, 0x8020e3c0); // lwz r3, 26624(r4)\n', 'read32-observer'))
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
