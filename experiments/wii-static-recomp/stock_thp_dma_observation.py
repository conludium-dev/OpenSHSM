"""Extend the same phase observer with original DMA/cache continuation points."""
import struct
from stock_thp_chain_observation import adapt as adapt_chain, chain_header

EXTRA = [(0x8009BB34, 0x3C038000), (0x8009BB58, 0x800DB064),
    (0x8009BB7C, 0x4817B985), (0x8009BB80, 0x800DB070),
    (0x8009BB9C, 0x800DB064), (0x8009BBB8, 0x48000039)]


def dma_header(text):
    text = chain_header(text)
    for kind in ('uint32_t', 'unsigned', 'std::string'):
        text = text.replace(f'std::array<{kind}, 17>', f'std::array<{kind}, 23>')
    marker = '0x8009BB48, 0x8009BB4C, 0x8009BAEC, 0x8009BBBC};'
    assert text.count(marker) == 1
    return text.replace(marker, '0x8009BB48, 0x8009BB4C, 0x8009BAEC, 0x8009BBBC,\n'
        '        0x8009BB34, 0x8009BB58, 0x8009BB7C, 0x8009BB80, 0x8009BB9C, 0x8009BBB8};')


def adapt(text, dol, module):
    text = adapt_chain(text, dol, module)
    text = text.replace('#include "stock_thp_chain_observation.h"', '#include "stock_thp_dma_observation.h"')
    if module == 11:
        header = struct.unpack('>64I', dol[:256])
        for address, expected in EXTRA:
            section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
            assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == expected
            marker = f'    // 0x{address:08X}: {expected:08X}'
            assert text.count(marker) == 1
            text = text.replace(marker, marker + f'\n    stock_thp_queue_observation::observe_producer(ctx, 0x{address:08X});')
    return text
