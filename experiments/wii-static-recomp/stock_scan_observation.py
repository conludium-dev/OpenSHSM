"""Attach bounded host-only snapshots to the existing original scan wrapper."""
import re
import struct


def adapt(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    for address, word in ((0x8019D434, 0x9421FF80), (0x8019D554, 0x80010084)):
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        marker = f'loc_{address:08X}: ;\n    // 0x{address:08X}: {word:08X}\n'
        assert text.count(marker) == 1
        hook = 'begin' if address == 0x8019D434 else 'finish'
        text = text.replace(marker, marker + f'    stock_scan_observation::{hook}(ctx);\n')
    return '#include "runtime/cpu_context.h"\n#include "stock_scan_observation.h"\n' + text
