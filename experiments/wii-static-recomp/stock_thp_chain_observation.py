"""Extend the same producer observer with prior-callback boundaries and phase-sensitive sampling."""
from stock_thp_producer_observation import adapt as adapt_producer
import struct

EXTRA = [(0x8009BB2C, 0x4E800421), (0x8009BB30, 0x48191051),
    (0x8009BB48, 0x4E800421), (0x8009BB4C, 0x48191035),
    (0x8009BAEC, 0x800DB064), (0x8009BBBC, 0x800DB064)]


def chain_header(text):
    text = text.replace('std::array<uint32_t, 11>', 'std::array<uint32_t, 17>')
    marker = '0x8022CDB8, 0x8022CDBC, 0x8022CDC4};'
    assert text.count(marker) == 1
    text = text.replace(marker, '0x8022CDB8, 0x8022CDBC, 0x8022CDC4, 0x8009BB2C, 0x8009BB30,\n'
        '        0x8009BB48, 0x8009BB4C, 0x8009BAEC, 0x8009BBBC};')
    text = text.replace('std::array<unsigned, 11>', 'std::array<unsigned, 17>')
    marker = '    ++hits[slot];\n    if (events >= 8192 || (hits[slot] > 16 && hits[slot] % 60 != 0)) {'
    assert text.count(marker) == 1
    text = text.replace(marker, '''    static std::array<std::string, 17> phases{};
    const auto phase = stock_loading_observation::copy_ram(ctx, 0x8046BBE0, 8)
        + stock_loading_observation::copy_ram(ctx, ctx.gpr[13] - 14704u, 4);
    const bool phase_changed = phases[slot] != phase;
    phases[slot] = phase;
    ++hits[slot];
    if (events >= 8192 || (!phase_changed && hits[slot] > 64 && hits[slot] % 60 != 0)) {''')
    marker = '        << ",\\\"hits\\\":" << hits[slot]'
    assert text.count(marker) == 1
    text = text.replace(marker, '        << ",\\\"phaseChanged\\\":" << (phase_changed ? "true" : "false")\n' + marker)
    marker = '        << ",\\\"cr0eq\\\":" << (ctx.cr[0].eq ? "true" : "false")'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n        << ",\\\"chainHex\\\":\\\"" << stock_loading_observation::copy_ram(ctx, ctx.gpr[13] - 20384u, 28) << "\\\""')
    return text


def adapt(text, dol, module):
    text = adapt_producer(text, dol, module)
    text = text.replace('#include "stock_thp_producer_observation.h"', '#include "stock_thp_chain_observation.h"')
    if module == 11:
        header = struct.unpack('>64I', dol[:256])
        for address, expected in EXTRA:
            section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
            assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == expected
            marker = f'    // 0x{address:08X}: {expected:08X}'
            assert text.count(marker) == 1
            text = text.replace(marker, marker + f'\n    stock_thp_queue_observation::observe_producer(ctx, 0x{address:08X});')
    return text
