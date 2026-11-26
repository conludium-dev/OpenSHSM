"""Lower measured single transfers to bit-exact existing BAT/cache operations."""
import re
import struct


def opcode_supported(opcode):
    primary = opcode >> 26
    return primary in (48,52) or (primary == 31 and not opcode & 1 and (opcode >> 1) & 1023 in (535,663))


def lower(text,dol):
    header = struct.unpack('>64I',dol[:256])
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)(.*?)(?=    \+\+ctx\.inst_count;\nloc_|\n}\n)',re.S)
    changes = []

    def replace(match):
        address, opcode = int(match[2],16), int(match[3],16)
        if not opcode_supported(opcode):
            return match[0]
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I',dol,header[section] + address - header[18 + section])[0] == opcode
        before = match[4]
        assert 'experiment_ni_guard' in before and ('read_f32' in before or 'write_f32' in before), hex(address)
        assert 'ctx.pc' not in before and 'return' not in before, hex(address)
        after = f'    nwii::runtime::experiment_fp32_transfer(ctx, 0x{opcode:08x});\n'
        changes.append({'address':hex(address),'opcode':hex(opcode),'before':before,'after':after})
        return match[1] + after

    return pattern.sub(replace,text), changes
