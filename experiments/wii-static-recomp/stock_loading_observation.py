"""Observe existing main-loop pump and original queued callback before/after points."""
import struct

SITES = {30: [(0x8018FA50, 0x4BFFFBC5), (0x8018FA5C, 0x881D031B)],
    32: [(0x801B51D4, 0x4E800421), (0x801B51D8, 0x4800000C)]}


def adapt(text, dol, index, payloads=False):
    layout = struct.unpack('>64I', dol[:256])
    for address, word in SITES[index]:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        marker = f'loc_{address:08X}: ;\n    // 0x{address:08X}: {word:08X}\n'
        assert text.count(marker) == 1
        hook = f'    stock_loading_observation::observe(ctx, 0x{address:08X});\n'
        if payloads and address == 0x801B51D4:
            hook += '    stock_loading_observation::capture_payload(ctx);\n'
        text = text.replace(marker, marker + hook)
    return '#include "' + ('stock_loading_payload_observation.h' if payloads else 'stock_loading_observation.h') + '"\n' + text
