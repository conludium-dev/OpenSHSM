"""Replace complete FP64 bodies with bit transfers on the existing BAT/cache frontend."""
import re
import struct

def fp64_opcode(opcode):
    primary = opcode >> 26
    return primary in (50, 51, 54, 55) or primary == 31 and not opcode & 1 and (opcode >> 1) & 1023 in (599, 727)

def lower(text, dol):
    header = struct.unpack('>64I', dol[:256])
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)(.*?)(?=    \+\+ctx\.inst_count;\nloc_|\n}\n)', re.S)
    changes = []
    def replace(match):
        address, opcode = int(match[2], 16), int(match[3], 16)
        if not fp64_opcode(opcode):
            return match[0]
        section = next(index for index in range(18) if header[18 + index] <= address < header[18 + index] + header[36 + index])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        before = match[4]
        assert 'experiment_ni_guard' in before and ('bat_memory_read_f64' in before or 'bat_memory_write_f64' in before)
        assert 'ctx.pc' not in before and 'return' not in before
        after = f'    nwii::runtime::experiment_fp64_transfer(ctx, 0x{opcode:08x});\n'
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'before': before, 'after': after})
        return match[1] + after
    return pattern.sub(replace, text), changes
