"""Four non-floating original update boundaries, after active store where applicable."""
import struct

SITES = [(0x8009B72C, 0x2C1C0000), (0x8009B750, 0x41820014),
    (0x8009B760, 0x4817C5D1), (0x8009B770, 0x3CA08047)]


def adapt(text, dol):
    header = struct.unpack('>64I', dol[:256])
    for address, expected in SITES:
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == expected
        marker = f'    // 0x{address:08X}: {expected:08X}'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'\n    stock_thp_queue_observation::observe_update(ctx, 0x{address:08X});')
    return '#include "stock_thp_update_observation.h"\n' + text
