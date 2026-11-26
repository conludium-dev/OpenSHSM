"""Keep DrawDone IRQ distinct from EFB copy commands."""

def adapt_draw_done(text):
    old = 'if (reg == 0x45 && (val & 0xF) == 2)'
    assert text.count(old) == 1
    text = text.replace(old, 'if (reg == 0x45 && (val & 0xFF) == 2)')
    old = '            nwii::runtime::hw::pe_signal_finish();\n        }\n    }'
    assert text.count(old) == 1
    return text.replace(old, '        }\n    }')
