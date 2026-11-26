"""Bridge the corrected Wii-generated functions into the preserved stock pipeline."""
import re


TARGETS = {
    'func_80243C80': ('output_41.cpp', 0x80243C80, 0x80243D70),
    'func_8030F870': ('output_52.cpp', 0x8030F870, 0x8030F9AC),
}


def function(source, name):
    matches = list(re.finditer(r'^void ' + name + r'\([^\n]*\) \{.*?^}\n',
        source, re.M | re.S))
    if len(matches) != 1:
        raise ValueError(f'Expected one generated function: {name}')
    return matches[0].group()


def normalized_stock(raw):
    result = dict(raw)
    for name, (filename, _, _) in TARGETS.items():
        source = result[filename]
        original = function(source, name)
        if 'IOS_IoctlvAsync(ctx)' in original:
            raise ValueError(f'Corrected source still calls IOS_IoctlvAsync: {name}')
        legacy = (f'void {name}(nwii::runtime::CPUContext& ctx) {{\n'
            '    IOS_IoctlvAsync(ctx);\n'
            '    ctx.pc = ctx.lr;\n}\n')
        result[filename] = source.replace(original, legacy, 1)

    main = result['main_output.cpp']
    for name, (_, start, end) in TARGETS.items():
        range_line = f'    {{0x{start:08X}, 0x{end:08X}, {name}}},\n'
        if main.count(range_line) != 1:
            raise ValueError(f'Corrected range differs: {name}')
        main = main.replace(range_line, '', 1)
        rows = re.findall(r'^\s*case 0x[0-9A-F]+: ' + name + r'\(ctx\); break;\n', main, re.M)
        if not rows or rows[0].strip() != f'case 0x{start:08X}: {name}(ctx); break;':
            raise ValueError(f'Corrected dispatch differs: {name}')
        block = ''.join(rows)
        if main.count(block) != 1:
            raise ValueError(f'Corrected dispatch rows are not contiguous: {name}')
        main = main.replace(block,
            f'            case 0x{start:08X}: IOS_IoctlvAsync(ctx); ctx.pc = ctx.lr; break;\n', 1)
    result['main_output.cpp'] = main
    return result


def restored_assembly(base_guest, base_fixed, corrected):
    outputs = dict(base_guest)
    fixed = base_fixed
    fresh_main = corrected['main_output.cpp']
    details = {}
    for name, (filename, start, end) in TARGETS.items():
        before = function(outputs[filename], name)
        replacement = function(corrected[filename], name)
        if 'IOS_IoctlvAsync(ctx)' not in before or 'IOS_IoctlvAsync(ctx)' in replacement:
            raise ValueError(f'Unexpected guest function body: {name}')
        outputs[filename] = outputs[filename].replace(before, replacement, 1)
        range_line = f'    {{0x{start:08X}, 0x{end:08X}, {name}}},\n'
        if fresh_main.count(range_line) != 1 or range_line in fixed:
            raise ValueError(f'Generated function range differs: {name}')
        later = [(int(address, 16), row) for row, address in re.findall(
            r'^(    \{(0x[0-9A-F]+), 0x[0-9A-F]+, func_[0-9A-F]+\},)$',
            fixed, re.M) if int(address, 16) >= end]
        if not later:
            raise ValueError(f'Missing following function range: {name}')
        anchor = min(later)[1] + '\n'
        if fixed.count(anchor) != 1:
            raise ValueError(f'Following range is ambiguous: {name}')
        fixed = fixed.replace(anchor, range_line + anchor, 1)
        rows = [(int(address, 16), target) for address, target in re.findall(
            r'^\s*case (0x[0-9A-F]+): (func_[0-9A-F]+)\(ctx\); break;$',
            fresh_main, re.M) if start <= int(address, 16) < end]
        if not rows or rows[0] != (start, name) or any(target != name for _, target in rows):
            raise ValueError(f'Generated dispatch differs: {name}')
        old_row = f'    {{0x{start:08X}, dispatch_hle_{start:08X}}},\n'
        if fixed.count(old_row) != 1:
            raise ValueError(f'Legacy HLE route differs: {name}')
        fixed = fixed.replace(old_row,
            ''.join(f'    {{0x{address:08X}, {name}}},\n' for address, _ in rows), 1)
        details[name] = {'routes': [f'0x{address:08X}' for address, _ in rows],
            'oldBytes': len(before.encode()), 'newBytes': len(replacement.encode())}
    return outputs, fixed, details
