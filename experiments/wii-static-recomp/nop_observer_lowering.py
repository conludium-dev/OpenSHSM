"""Observe the next NOP-template store without allowing it."""
import struct

def lower(text, dol):
    marker = '    // 0x80211A30: 92E40000\n'
    before = '    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[4] + 0, ctx.gpr[23]); // stw r23, 0(r4)\n'
    needle = marker + before
    if needle not in text:
        return text, []
    header = struct.unpack('>64I', dol[:256])
    address = 0x80211a30
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x92e40000
    after = '    nwii::runtime::experiment_observed_write32(ctx, ctx.gpr[4] + 0, ctx.gpr[23], 0x80211a30);\n'
    return text.replace(needle, marker + after), [{'address': hex(address), 'opcode': '0x92e40000', 'before': before, 'after': after}] * text.count(needle)
