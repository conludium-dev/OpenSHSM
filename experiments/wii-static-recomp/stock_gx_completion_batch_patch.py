"""Keep ordered BP state updates while publishing PE notifications after a batch GPU fence."""


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'PE batch integration site differs: {old}')
    return text.replace(old, new, 1)


def header(text):
    return once(text, 'void ApplyBPRegister(uint8_t reg, uint32_t val);',
        '''void ApplyBPRegister(uint8_t reg, uint32_t val);
// Split state application from PE publication when the renderer owns the GPU fence.
void ApplyBPRegisterState(uint8_t reg, uint32_t val);
void CompleteBPRegister(uint8_t reg, uint32_t val);''')


def parser(text):
    begin = text.index('        if (reg == 0x45 && (val & 0xFF) == 2) {')
    end = text.index('        g_state.bp[reg] = val;', begin)
    notifications = ''.join(line[4:] if line.startswith('    ') else line
        for line in text[begin:end].splitlines(keepends=True))
    text = text[:begin] + '        if (notify_pe) {\n            CompleteBPRegister(reg, val);\n        }\n' + text[end:]
    text = once(text, '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val);',
        '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val, bool notify_pe);')
    text = once(text, '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val) {',
        '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val, bool notify_pe) {')
    return once(text, 'void ApplyBPRegister(uint8_t reg, uint32_t val) { ApplyBPRegisterImpl(reg, val); }',
        'void CompleteBPRegister(uint8_t reg, uint32_t val) {\n' + notifications + '}\n\n'
        'void ApplyBPRegister(uint8_t reg, uint32_t val) {\n    ApplyBPRegisterImpl(reg, val, true);\n}\n'
        'void ApplyBPRegisterState(uint8_t reg, uint32_t val) {\n    ApplyBPRegisterImpl(reg, val, false);\n}')


def renderer(text):
    text = once(text, '    for (const auto &cmd : commands) {',
        '    bool pending_completion = false;\n    for (const auto &cmd : commands) {')
    text = once(text, '''        if (stock_gx_pe_completion(cmd)) {
            glFinish();
        }
        ApplyBPRegister((uint8_t)cmd.reg, cmd.val);''',
        '''        if (stock_gx_pe_completion(cmd)) {
            ApplyBPRegisterState((uint8_t)cmd.reg, cmd.val);
            pending_completion = true;
        } else {
            ApplyBPRegister((uint8_t)cmd.reg, cmd.val);
        }''')
    return once(text, '''    if (s_batch_open) {
      FlushBatch();
      s_batch_open = false;
    }
  }''', '''    if (s_batch_open) {
      FlushBatch();
      s_batch_open = false;
    }
    if (pending_completion) {
        glFinish();
        for (const auto& command : commands) {
            if (stock_gx_pe_completion(command)) {
                CompleteBPRegister((uint8_t)command.reg, command.val);
            }
        }
    }
  }''')
