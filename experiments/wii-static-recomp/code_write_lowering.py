"""Observe one original store through the unchanged BAT memory frontend."""
import struct

def lower(text, dol):
    before = '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[28] + 0, ctx.gpr[0]); // stw r0, 0(r28)\n'
    marker = '    // 0x802119A8: 901C0000\n'
    needle = marker + before
    if needle not in text:
        return text, []
    header = struct.unpack('>64I', dol[:256])
    address = 0x802119a8
    section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x901c0000
    after = '    nwii::runtime::experiment_observed_write32(ctx, ctx.gpr[28] + 0, ctx.gpr[0], 0x802119a8);\n'
    changes = [{'address': hex(address), 'opcode': '0x901c0000', 'before': before, 'after': after}] * text.count(needle)
    return text.replace(needle, marker + after), changes
