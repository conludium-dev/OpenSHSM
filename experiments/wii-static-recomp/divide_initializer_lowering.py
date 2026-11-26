"""Byte-check the complete original function and bind only the new arithmetic routing."""
from pathlib import Path
import re


def lower(text, dol):
    assembly = Path('work/private-game/static-recomp/dtk-output/asm/auto_fn_8013B0C0_text.s').read_text()
    rows = re.findall(r'/\* ([0-9A-F]{8}) ([0-9A-F]{8})  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', assembly)
    assert len(rows) == 5
    for address, offset, encoded in rows:
        assert dol[int(offset, 16):int(offset, 16) + 4] == bytes.fromhex(encoded)
    assert rows[2][0] == '8013B0C8' and rows[2][2] == 'EC 01 00 24'
    before = ('    nwii::runtime::experiment_ni_guard(ctx, 0xec010024, 0x8013b0c8);\n'
        '    ctx.fpr[0] = (float)(ctx.fpr[1] / ctx.fpr[0]); // fdivs')
    if before not in text:
        return text, []
    assert text.count(before) == 1 and '    // 0x8013B0C8: EC010024\n' + before in text
    after = ('    if (std::getenv("SHSM_DIVIDE_INITIALIZER_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec010024, 0x8013b0c8); }\n'
        '    nwii::runtime::experiment_divide_initializer(ctx, 0xec010024);')
    return '#include "divide_initializer_adapter.h"\n' + text.replace(before, after), [{'address': 0x8013b0c8, 'opcode': 0xec010024}]
