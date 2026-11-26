"""Retain independently addressed TEV banks in the existing GX state/replay seam."""
def state(text):
    marker = '  uint32_t tlutSrcAddr;'
    assert text.count(marker) == 1
    return text.replace(marker, marker + '\n\n    uint32_t tevColorWords[2][8] = {};')

def parser(text):
    marker = '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val) {\n        g_state.bp[reg] = val;'
    assert text.count(marker) == 1
    return text.replace(marker, marker + '''
        if (reg >= 0xE0 && reg <= 0xE7) {
            g_state.tevColorWords[(val >> 23) & 1][reg - 0xE0] = val;
        }''')

def renderer(text):
    start = text.index('  for (int i = 0; i < 4; i++) {\n    uint32_t ra = g_state.bp[0xE0')
    end = text.index('\n  static const bool s_tevtrace', start)
    replacement = '''    for (int bank = 0; bank < 2; ++bank) {
        float* target = bank == 0 ? color : kcolor;
        for (int i = 0; i < 4; ++i) {
            const uint32_t ra = g_state.tevColorWords[bank][i * 2];
            const uint32_t bg = g_state.tevColorWords[bank][i * 2 + 1];
            target[i * 4] = decode11(ra, 0);
            target[i * 4 + 3] = decode11(ra, 12);
            target[i * 4 + 2] = decode11(bg, 0);
            target[i * 4 + 1] = decode11(bg, 12);
        }
    }
'''
    return text[:start] + replacement + text[end:]
