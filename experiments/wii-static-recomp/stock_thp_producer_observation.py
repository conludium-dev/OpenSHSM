"""Exact original registration, DMA handler and movie-fill boundaries."""
import struct

SITES = {
    11: [(0x8009BA88, 0x9421FFF0), (0x8009BBF0, 0x9421FFD0), (0x8009BC38, 0x3FE0803F),
        (0x8009BC90, 0x807E00FC), (0x8009BE40, 0x807F00FC)],
    39: [(0x8022CA84, 0x4BFEAA9D), (0x8022CD80, 0x2C030000), (0x8022CD90, 0x40820034),
        (0x8022CDB8, 0x4E800421), (0x8022CDBC, 0x38000000), (0x8022CDC4, 0x38610008)]}


def adapt(text, dol, module):
    header = struct.unpack('>64I', dol[:256])
    for address, expected in SITES[module]:
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == expected
        marker = f'    // 0x{address:08X}: {expected:08X}'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'\n    stock_thp_queue_observation::observe_producer(ctx, 0x{address:08X});')
    return '#include "stock_thp_producer_observation.h"\n' + text
