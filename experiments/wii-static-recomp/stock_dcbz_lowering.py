"""Restore actual THP dcbz stores using the existing stock MMU/interpreter RAM model."""
import re
import struct

def lower_dcbz(text, dol, expected_sites=12):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)    // dcbz \(data cache block zero\) - stub\n')
    def replace(match):
        address, word = int(match[2], 16), int(match[3], 16)
        assert word >> 26 == 31 and ((word >> 1) & 1023) == 1014
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        ra, rb = (word >> 16) & 31, (word >> 11) & 31
        base = f'ctx.gpr[{ra}]' if ra else '0u'
        body = f'''    {{
        const uint32_t address = ({base} + ctx.gpr[{rb}]) & ~31u;
        if (ctx.mmu.is_hw_reg(address & 0x3FFFFFFFu) || !ctx.mmu.get_ptr(address)
            || !ctx.mmu.get_ptr(address + 31)) {{
            throw std::runtime_error("THP dcbz RAM range unverified");
        }}
        for (unsigned offset = 0; offset < 32; offset += 4) {{
            ctx.mmu.write32(address + offset, 0);
        }}
    }}
'''
        sites.append({'address': address, 'word': word, 'ra': ra, 'rb': rb, 'body': body})
        return match[1] + body
    result = pattern.sub(replace, text)
    assert len(sites) == expected_sites
    return result, sites
