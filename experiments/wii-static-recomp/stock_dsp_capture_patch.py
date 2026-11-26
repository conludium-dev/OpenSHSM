"""Add read-only bounded observation at the existing mailbox and DMA producer."""


def adapt(text):
    replacements = [
        ('    uint32_t ar_a = ar_araddr & 0x00FFFFFF;',
         '    uint32_t ar_a = ar_araddr & 0x00FFFFFF;\n'
         '    if (g_ctx_ptr) {\n'
         '        openshsm::experiment::dsp_command_capture.dma(*g_ctx_ptr, mm, ar_a, count, dir);\n'
         '    }'),
        ('                    uint32_t mail = ((uint32_t)s_cpu_mail_hi << 16) | (val & 0xFFFF);',
         '                    uint32_t mail = ((uint32_t)s_cpu_mail_hi << 16) | (val & 0xFFFF);\n'
         '                    if (g_ctx_ptr) {\n'
         '                        openshsm::experiment::dsp_command_capture.mail(*g_ctx_ptr, mail, dsp_control, s_ax_state);\n'
         '                    }')]
    for before, after in replacements:
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    return '#include "stock_dsp_capture.h"\n' + text
