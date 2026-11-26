"""Replace only the byte-checked measured instruction in the existing source body."""
import struct


def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(7) if header[18 + i] <= 0x800d8dfc < header[18 + i] + header[36 + i])
    offset = header[section] + 0x800d8dfc - header[18 + section]
    assert dol[offset:offset + 4] == bytes.fromhex('ec020028')
    before = ('    nwii::runtime::experiment_ni_guard(ctx, 0xec020028, 0x800d8dfc);\n'
        '    ctx.fpr[0] = (float)(ctx.fpr[2] - ctx.fpr[0]); // fsubs')
    if before not in text:
        return text, []
    assert text.count(before) == 1 and '    // 0x800D8DFC: EC020028\n' + before in text
    after = ('    if (std::getenv("SHSM_GENERAL_SUBTRACT_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec020028, 0x800d8dfc); }\n'
        '    nwii::runtime::experiment_general_subtract(ctx, 0xec020028);')
    return '#include "general_subtract_adapter.h"\n' + text.replace(before, after), [{'address': 0x800d8dfc, 'opcode': 0xec020028}]
