"""Correct RA-zero effective addresses in byte-checked generated sthbrx sites."""
import re
import struct

pattern = re.compile(r'(loc_([0-9A-F]{8}): ;\n    // 0x\2: ([0-9A-F]{8})\n)(    ctx\.mmu\.write16\([^\n]+// sthbrx\n)')

def lower_byte_reverse(text, dol):
    offsets = struct.unpack_from('>18I', dol, 0)
    addresses = struct.unpack_from('>18I', dol, 0x48)
    sizes = struct.unpack_from('>18I', dol, 0x90)
    sites = []
    def replace(match):
        address = int(match[2], 16)
        word = int(match[3], 16)
        section = next((o, a, s) for o, a, s in zip(offsets, addresses, sizes) if a <= address < a + s)
        assert struct.unpack_from('>I', dol, section[0] + address - section[1])[0] == word
        assert word >> 26 == 31 and (word >> 1) & 1023 == 918
        ra = (word >> 16) & 31
        rb = (word >> 11) & 31
        if ra:
            return match[0]
        old = f'ctx.mmu.write16(ctx.gpr[0] + ctx.gpr[{rb}],'
        new = f'ctx.mmu.write16(ctx.gpr[{rb}],'
        assert match[4].count(old) == 1
        sites.append({'address': address, 'word': word, 'rb': rb, 'rs': (word >> 21) & 31})
        return match[1] + match[4].replace(old, new, 1)
    return pattern.sub(replace, text), sites
