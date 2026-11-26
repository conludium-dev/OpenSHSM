"""Replace every original subfic lowering with unsigned result/carry semantics."""
import re
import struct

def lower(text, dol, stock=False):
    header = struct.unpack('>64I', dol[:256])
    lines = text.splitlines(True)
    changes = []
    output = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
        if not match:
            output.append(line)
            index += 1
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        operation = opcode >> 26
        if operation not in (8, 12, 13):
            output.append(line)
            index += 1
            continue
        destination, source = (opcode >> 21) & 31, (opcode >> 16) & 31
        immediate = opcode & 65535
        if immediate & 32768:
            immediate -= 65536
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == opcode
        if operation == 8:
            length = 1
            before = lines[index + 1]
            assert before.strip() == f'ctx.gpr[{destination}] = (uint32_t)({immediate} - (int32_t)ctx.gpr[{source}]); // subfic'
            after = f'    nwii::runtime::experiment_subfic(ctx, {destination}, {source}, {immediate});\n'
        else:
            expected = ['    {\n', f'        uint64_t res = (uint64_t)ctx.gpr[{source}] + {immediate};\n',
                        f'        ctx.gpr[{destination}] = (uint32_t)res;\n',
                        '        ctx.xer = (ctx.xer & ~(1 << 29)) | (((res >> 32) & 1) << 29); // CA\n']
            if operation == 13:
                expected += [f'        ctx.cr[0].lt = ((int32_t)ctx.gpr[{destination}] < 0);\n',
                             f'        ctx.cr[0].gt = ((int32_t)ctx.gpr[{destination}] > 0);\n',
                             f'        ctx.cr[0].eq = (ctx.gpr[{destination}] == 0);\n']
                if not stock or lines[index + 1 + len(expected)] == '        ctx.cr[0].so = (ctx.xer >> 31) & 1;\n':
                    expected += ['        ctx.cr[0].so = (ctx.xer >> 31) & 1;\n']
            expected += ['    }\n']
            length = len(expected)
            before = ''.join(lines[index + 1:index + 1 + length])
            assert before == ''.join(expected), (hex(address), before)
            after = f'    nwii::runtime::experiment_addic(ctx, {destination}, {source}, {immediate}, {str(operation == 13).lower()});\n'
        output.append(line + after)
        changes.append({'address': hex(address), 'opcode': hex(opcode), 'inputLine': index + 2,
                        'before': before, 'after': after})
        index += 1 + length
    return ''.join(output), changes
