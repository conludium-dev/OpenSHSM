"""Attach original subtitle loop/time checkpoints after FP side effects where applicable."""
import struct

SITES = [(0x800D806C, 0x931F0000), (0x800D80E4, 0x7F83E378),
    (0x800D8114, 0x480C6C0D), (0x800D8120, 0x7F83E378),
    (0x800D8280, 0x7F83E378), (0x800D82B0, 0x39610030)]


def adapt(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    for address, word in SITES:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        marker = f'loc_{address:08X}: ;\n    // 0x{address:08X}: {word:08X}\n'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'    stock_subtitle_progress::observe(ctx, 0x{address:08X});\n')
    return '#include "stock_subtitle_progress.h"\n' + text
