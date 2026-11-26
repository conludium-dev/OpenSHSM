"""Reuse the existing own-DOL scanner wrapper, not a host sscanf replacement."""
import re
import struct
from stock_fp_guard_lowering import lower


def restore_guest(text, mass, dol, tables):
    start = mass.index('void func_8019D434(CPUContext& ctx) {')
    end = mass.find('\nvoid func_', start + 1)
    body = mass[start:end if end >= 0 else len(mass)].rstrip('\n') + '\n'
    layout = struct.unpack('>64I', dol[:256])
    words = []
    for address, word in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body):
        address, word = int(address, 16), int(word, 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        words.append({'address': address, 'word': word})
    assert len(words) == 76
    body, guards, fpscr = lower(body, dol, tables)
    assert len(guards) == 8 and not fpscr
    start = text.index('void func_8019D434(nwii::runtime::CPUContext& ctx) {')
    end = text.index('\n}', start) + 2
    assert 'OSReport(ctx);' in text[start:end]
    return text[:start] + body + text[end:], words


def restore_dispatch(text, continuation_routes=False):
    old = 'static void dispatch_hle_8019D434(CPUContext& ctx) {\n    OSReport(ctx);\n    ctx.pc = ctx.lr;\n}'
    assert text.count(old) == 1
    text = text.replace(old, 'static void dispatch_hle_8019D434(CPUContext& ctx) {\n    func_8019D434(ctx);\n}')
    marker = '    {0x8019D3AC, 0x8019D434, func_8019D3AC},\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '    {0x8019D434, 0x8019D564, func_8019D434},\n')
    if continuation_routes:
        marker = '    {0x8019D434, dispatch_hle_8019D434},\n'
        assert text.count(marker) == 1
        routes = ''.join(f'    {{0x{address:08X}, func_8019D434}},\n'
            for address in range(0x8019D438, 0x8019D564, 4))
        text = text.replace(marker, marker + routes)
    assert 'static void dispatch_hle_80213EA0(CPUContext& ctx) {\n    OSReport(ctx);' in text
    return text
