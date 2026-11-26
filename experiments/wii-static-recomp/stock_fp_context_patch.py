"""Use original Wii OSContext paired-single memory layout in the existing HLE path."""
import re
import struct

def adapt_lazy_fp_context(text):
    start = text.index('static void hle_save_context_to_guest(')
    end = text.index('int g_trace_after_dec', start)
    helpers = text[start:end]
    blocks = [
        '''  for (int i = 0; i < 32; i++) {
    uint64_t d;
    std::memcpy(&d, &ctx.fpr[i], 8);
    ctx.mmu.write64(c + 0x90 + i * 8, d);
  }
  ctx.mmu.write32(c + 0x194, ctx.fpscr);
''',
        '''  for (int i = 0; i < 32; i++) {
    ctx.mmu.write_f32(c + 0x1C8 + i * 8, float(ctx.fpr[i]));
    ctx.mmu.write_f32(c + 0x1CC + i * 8, float(ctx.ps1[i]));
  }
''',
        '''  for (int i = 0; i < 32; i++) {
    uint64_t d = ctx.mmu.read64(c + 0x90 + i * 8);
    std::memcpy(&ctx.fpr[i], &d, 8);
  }
  ctx.fpscr = ctx.mmu.read32(c + 0x194);
''',
        '''  for (int i = 0; i < 32; i++) {
    ctx.ps1[i] = ctx.mmu.read_f32(c + 0x1CC + i * 8);
  }
'''
    ]
    for block in blocks:
        assert helpers.count(block) == 1
        helpers = helpers.replace(block, '')
    assert not any(token in helpers for token in ('ctx.fpr', 'ctx.ps1', 'ctx.fpscr'))
    return text[:start] + helpers + text[end:]

def adapt_fp_context(text):
    old = '''  for (int i = 0; i < 32; i++) {
    uint64_t d;
    std::memcpy(&d, &ctx.ps1[i], 8);
    ctx.mmu.write64(c + 0x1C8 + i * 8, d);
  }'''
    new = '''  for (int i = 0; i < 32; i++) {
    ctx.mmu.write_f32(c + 0x1C8 + i * 8, float(ctx.fpr[i]));
    ctx.mmu.write_f32(c + 0x1CC + i * 8, float(ctx.ps1[i]));
  }'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    old = '''  for (int i = 0; i < 32; i++) {
    uint64_t d = ctx.mmu.read64(c + 0x1C8 + i * 8);
    std::memcpy(&ctx.ps1[i], &d, 8);
  }'''
    new = '''  for (int i = 0; i < 32; i++) {
    ctx.ps1[i] = ctx.mmu.read_f32(c + 0x1CC + i * 8);
  }'''
    assert text.count(old) == 1
    return text.replace(old, new)

def verify_fp_sdk(text, dol):
    layout = struct.unpack('>64I', dol[:256])
    rows = []
    for start, base, operation in [(0x802135E0, 4, 'load'), (0x80213794, 5, 'store')]:
        for index in range(32):
            address = start + index * 4
            word = int(re.search(f'// 0x{address:08X}: ([0-9A-F]{{8}})', text)[1], 16)
            section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
            assert word >> 26 == (56 if operation == 'load' else 60)
            assert (word >> 21) & 31 == index and (word >> 16) & 31 == base
            assert ((word >> 12) & 15) == 0 and (word & 4095) == 456 + index * 8
            rows.append({'address': address, 'word': word, 'operation': operation, 'register': index})
    return rows
