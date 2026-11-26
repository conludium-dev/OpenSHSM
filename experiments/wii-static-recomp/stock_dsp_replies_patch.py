"""Attach ordered replies to the existing DSP mailbox producer and consumer only."""


def adapt(text):
    replacements = [
        ('static uint16_t dsp_mbox_dsp_lo = 0;',
         'static uint16_t dsp_mbox_dsp_lo = 0;\n'
         'static openshsm::experiment::DspMailReplies dsp_mail_replies;'),
        ('int dsp_pending_os_interrupt() {',
         'static void dsp_reply_interrupt(int) noexcept {\n'
         '    dsp_control |= 0x0080;\n'
         '    dsp_update_pi();\n'
         '}\n\n'
         'static void dsp_queue_reply(uint16_t low) {\n'
         '    dsp_mail_replies.push(0xdcd10000u | low, true, 0, dsp_reply_interrupt);\n'
         '}\n\n'
         'int dsp_pending_os_interrupt() {'),
        ('if (addr == 0xCC005004) return dsp_mbox_dsp_hi;',
         'if (addr == 0xCC005004) {\n'
         '                dsp_mbox_dsp_hi = dsp_mail_replies.read_high();\n'
         '                return dsp_mbox_dsp_hi;\n'
         '            }'),
        ('                uint16_t val = dsp_mbox_dsp_lo;\n'
         '                dsp_mbox_dsp_hi &= ~0x8000;\n\n'
         '                \n'
         '                \n'
         '                dsp_control &= ~0x0080;\n'
         '                dsp_update_pi();',
         '                dsp_control &= ~0x0080;\n'
         '                uint16_t val = dsp_mail_replies.read_low(dsp_reply_interrupt);\n'
         '                dsp_mbox_dsp_lo = val;\n'
         '                dsp_mbox_dsp_hi &= ~0x8000;\n'
         '                dsp_update_pi();'),
        ('                                dsp_mbox_dsp_hi = 0xDCD1;\n'
         '                                dsp_mbox_dsp_lo = lo;\n'
         '                                dsp_control |= 0x0080;\n'
         '                                dsp_update_pi();',
         '                                dsp_queue_reply(lo);'),
        ('                if ((val16 & 0x0001) || (was_halted && !is_halted)) {\n'
         '                    dsp_mbox_dsp_hi = 0xDCD1;\n'
         '                    dsp_mbox_dsp_lo = 0x0000;\n'
         '                }',
         '                dsp_mail_replies.set_halted((dsp_control & 0x0004) != 0);\n'
         '                if ((val16 & 0x0001) || (was_halted && !is_halted)) {\n'
         '                    dsp_mail_replies.clear_pending();\n'
         '                    dsp_mail_replies.push(0xdcd10000u, false, 0, dsp_reply_interrupt);\n'
         '                    dsp_mbox_dsp_hi = 0xDCD1;\n'
         '                    dsp_mbox_dsp_lo = 0x0000;\n'
         '                }')]
    for before, after in replacements:
        assert text.count(before) == 1, before
        text = text.replace(before, after, 1)
    return '#include "stock_dsp_replies.h"\n' + text
