"""Restore unconditional CR0 recording for original andi./andis. instructions."""
import re
import struct

pattern = re.compile(r'(loc_([0-9A-F]{8}): ;\n    // 0x\2: ([0-9A-F]{8})\n)(    ctx\.gpr\[(\d+)\] = ctx\.gpr\[(\d+)\] & (\d+); // (andis?\.)\n)(    \+\+ctx.inst_count;)')

def lower_logical_record(text, dol):
    offsets = struct.unpack_from('>18I', dol, 0)
    addresses = struct.unpack_from('>18I', dol, 0x48)
    sizes = struct.unpack_from('>18I', dol, 0x90)
    sites = []
    def replace(match):
        address, word = int(match[2], 16), int(match[3], 16)
        section = next((o, a, s) for o, a, s in zip(offsets, addresses, sizes) if a <= address < a + s)
        assert struct.unpack_from('>I', dol, section[0] + address - section[1])[0] == word
        op = word >> 26
        ra, rs = (word >> 16) & 31, (word >> 21) & 31
        immediate = (word & 65535) << (16 if op == 29 else 0)
        assert op in (28, 29) and ra == int(match[5]) and rs == int(match[6]) and immediate == int(match[7])
        record = f'''    ctx.cr[0].lt = ((int32_t)ctx.gpr[{ra}] < 0);
    ctx.cr[0].gt = ((int32_t)ctx.gpr[{ra}] > 0);
    ctx.cr[0].eq = (ctx.gpr[{ra}] == 0);
    ctx.cr[0].so = (ctx.xer >> 31) & 1;
'''
        sites.append({'address': address, 'word': word, 'ra': ra, 'rs': rs, 'immediate': immediate})
        return match[1] + match[4] + record + match[9]
    return pattern.sub(replace, text), sites
