"""Byte-check and symbolically admit only original signed-int bias constructor prefixes."""
from pathlib import Path
import hashlib
import re
import struct


def select(dol, directory):
    header = struct.unpack('>64I', dol[:256])

    def read(address, size):
        for index in range(18):
            start, length = header[18 + index], header[36 + index]
            if start <= address and address + size <= start + length:
                offset = header[index] + address - start
                return dol[offset:offset + size]
        raise ValueError('Unmapped original operand')

    sites = []
    for path in sorted(Path(directory).glob('auto_fn_*.s')):
        text = path.read_text()
        if '.section .ctors' not in text or 'fsubs f0, f0, f1' not in text:
            continue
        rows = re.findall(r'/\* ([0-9A-F]{8}) ([0-9A-F]{8})  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', text)
        assert rows
        for address, offset, word in rows:
            assert dol[int(offset, 16):int(offset, 16) + 4] == bytes.fromhex(word)
        registers = {1: ('stack', 0), 2: 0x805335e0, 13: 0x8052e720}
        floats, stack = {}, {}
        for address, offset, encoded in rows:
            word = int(encoded.replace(' ', ''), 16)
            primary, target, base = word >> 26, (word >> 21) & 31, (word >> 16) & 31
            immediate = (word & 0xffff) - (0x10000 if word & 0x8000 else 0)
            if word == 0xec000828:
                expected = ('double', 0x43300000, ('xor', 'signed-input', 0x80000000))
                if floats.get(0) == expected and floats.get(1) == 0x4330000080000000:
                    sites.append({'function': int(rows[0][0], 16), 'address': int(address, 16),
                        'opcode': word, 'assemblySha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                break
            origin = registers.get(base) if base else 0
            if primary == 15 and base == 0:
                registers[target] = (immediate << 16) & 0xffffffff
            elif primary == 14 and origin is not None:
                registers[target] = (('stack', origin[1] + immediate) if isinstance(origin, tuple)
                    and origin[0] == 'stack' else (origin + immediate) & 0xffffffff if isinstance(origin, int) else None)
            elif primary == 27:
                source, destination = target, base
                value = registers.get(source)
                registers[destination] = ('xor', value, (word & 0xffff) << 16)
            elif primary in (32, 36, 37, 50):
                location = (('stack', origin[1] + immediate) if isinstance(origin, tuple) and origin[0] == 'stack'
                    else (origin + immediate) & 0xffffffff if isinstance(origin, int) else None)
                if primary == 32:
                    registers[target] = 'signed-input' if location == 0x8052861c else None
                elif primary in (36, 37):
                    if isinstance(location, tuple):
                        stack[location[1]] = registers.get(target)
                    if primary == 37:
                        registers[base] = location
                elif isinstance(location, int):
                    floats[target] = int.from_bytes(read(location, 8), 'big')
                elif isinstance(location, tuple):
                    floats[target] = ('double', stack.get(location[1]), stack.get(location[1] + 4))
                else:
                    break
            elif word == 0x7c0802a6:
                registers[0] = None
            else:
                break
    assert len({site['address'] for site in sites}) == len(sites)
    return sites


def lower(text, dol, sites):
    changes = []
    for site in sites:
        address = site['address']
        before = (f'    nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x{address:08x});\n'
            '    ctx.fpr[0] = (float)(ctx.fpr[0] - ctx.fpr[1]); // fsubs')
        if before not in text:
            continue
        assert text.count(before) == 1
        after = (f'    if (std::getenv("SHSM_BIAS_CONSTRUCTORS_DISABLED")) {{ nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x{address:08x}); }}\n'
            '    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec000828);')
        text = text.replace(before, after)
        changes.append({**site, 'before': before, 'after': after})
    return text, changes
