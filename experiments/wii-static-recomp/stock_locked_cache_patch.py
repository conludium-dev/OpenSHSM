"""Extend the existing MMU and processor model; preserve vendor sources and guest flow."""
import re
import struct

def adapt_cpu_header(text):
    marker = '  std::vector<uint8_t> mem2;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n  std::vector<uint8_t> locked_cache;')
    marker = '    mem2.resize(64 * 1024 * 1024 + 8, 0);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n    locked_cache.resize(256 * 1024 + 8, 0);')
    marker = '  inline uint8_t *get_ptr(uint32_t addr) {\n'
    assert text.count(marker) == 1
    return text.replace(marker, marker + '''    if (addr >= 0xE0000000 && addr < 0xE0040000) {
        return &locked_cache[addr - 0xE0000000];
    }
''')

def adapt_processor_header(text):
    marker = '    uint32_t hid0 = 0;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n    uint32_t dma_u = 0;\n    uint32_t dma_l = 0;')
    marker = 'uint32_t experiment_read_hid2(CPUContext& context);'
    assert text.count(marker) == 1
    return text.replace(marker, '''uint32_t experiment_read_dma(CPUContext& context, unsigned spr);
void experiment_write_dma(CPUContext& context, unsigned spr, uint32_t value);
''' + marker)

def adapt_interpreter(text):
    for marker, extra in (
        ('else if (spr == 920) ctx.gpr[rD] = experiment_read_hid2(ctx);',
         'else if (spr == 922 || spr == 923) ctx.gpr[rD] = experiment_read_dma(ctx, spr);'),
        ('else if (spr == 920) experiment_write_hid2(ctx, ctx.gpr[rD]);',
         'else if (spr == 922 || spr == 923) experiment_write_dma(ctx, spr, ctx.gpr[rD]);')
    ):
        assert text.count(marker) == 1
        text = text.replace(marker, marker + '\n            ' + extra)
    return text

def lower_dma(text, dol):
    header = struct.unpack('>64I', dol[:256])
    pattern = re.compile(r'(    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n)([^\n]*\n)')
    sites = []
    def replace(match):
        address, word = int(match[2], 16), int(match[3], 16)
        xo = (word >> 1) & 1023
        spr = ((word >> 16) & 31) | (((word >> 11) & 31) << 5)
        if word >> 26 != 31 or xo not in (339, 467) or spr not in (922, 923):
            return match[0]
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == word
        register = (word >> 21) & 31
        if xo == 467:
            assert match[4].strip() == f'// unhandled mtspr {spr}'
            replacement = f'    nwii::runtime::experiment_write_dma(ctx, {spr}, ctx.gpr[{register}]);\n'
        else:
            assert match[4].strip() == f'ctx.gpr[{register}] = 0; // mfspr HID {spr}'
            replacement = f'    ctx.gpr[{register}] = nwii::runtime::experiment_read_dma(ctx, {spr});\n'
        sites.append({'address': address, 'word': word, 'spr': spr, 'register': register, 'write': xo == 467})
        return match[1] + replacement
    return pattern.sub(replace, text), sites
