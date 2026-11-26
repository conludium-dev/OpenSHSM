"""Opt-in AX execution within the existing retained DSP mailbox and ADMA path."""
from stock_dsp_replies_patch import adapt as adapt_replies


def adapt(text):
    text = adapt_replies(text)
    patches = [
        ('static openshsm::experiment::DspMailReplies dsp_mail_replies;',
         'static openshsm::experiment::DspMailReplies dsp_mail_replies;\n'
         'static openshsm::experiment::AxWiiDspExecution dsp_ax_execution;\n'
         'static bool dsp_ax_enabled() {\n'
         '    const char* value = std::getenv("OPENSHSM_AXWII_MIXER");\n'
         '    return value && std::strcmp(value, "1") == 0;\n'
         '}'),
        ('                    auto reply = [](uint16_t lo) {',
         '                    if (g_ctx_ptr && dsp_ax_enabled()) {\n'
         '                        const auto observed = dsp_ax_execution.observe(*g_ctx_ptr, mail);\n'
         '                        if (observed != openshsm::experiment::AxWiiDspExecution::MailObservation::Other) {\n'
         '                            if (observed == openshsm::experiment::AxWiiDspExecution::MailObservation::BootComplete) {\n'
         '                                dsp_queue_reply(0);\n'
         '                            }\n'
         '                            return;\n'
         '                        }\n'
         '                        if (mail == 0xcdd10003u) { s_ax_state = 0; return; }\n'
         '                    }\n'
         '                    auto reply = [](uint16_t lo) {'),
        ('                    } else if ((mail & 0xFFFF0000u) == 0xCDD10000u) {\n',
         '                    } else if (dsp_ax_enabled() && mail == 0xcdd10000u) {\n'
         '                        reply(0x0001);\n'
         '                        s_ax_state = 0;\n'
         '                    } else if ((mail & 0xFFFF0000u) == 0xCDD10000u) {\n'),
        ('                    if (s_ax_state == 1) {\n'
         '                        \n'
         '                        reply(0x0002); ',
         '                    if (s_ax_state == 1) {\n'
         '                        if (dsp_ax_enabled()) {\n'
         '                            if (!g_ctx_ptr) { throw std::runtime_error("AXWii missing CPU context"); }\n'
         '                            try {\n'
         '                                dsp_ax_execution.execute(*g_ctx_ptr, mail, [](uint32_t value) noexcept {\n'
         '                                    try { dsp_queue_reply(uint16_t(value)); }\n'
         '                                    catch (...) {\n'
         '                                        std::cerr << "[AXWii] DSP reply queue failure\\n";\n'
         '                                        if (g_ctx_ptr) { g_ctx_ptr->is_running = false; }\n'
         '                                    }\n'
         '                                });\n'
         '                            } catch (const std::exception& error) {\n'
         '                                std::cerr << "[AXWii] refused command list: " << error.what() << "\\n";\n'
         '                                g_ctx_ptr->is_running = false;\n'
         '                                return;\n'
         '                            }\n'
         '                            if (!g_ctx_ptr->is_running) { return; }\n'
         '                        }\n'
         '                        reply(0x0002); '),
        ('                if (val16 & 0x0001) {\n'
         '                    adma_control = 0;',
         '                if (val16 & 0x0001) {\n'
         '                    dsp_ax_execution = {};\n'
         '                    adma_control = 0;')]
    for before, after in patches:
        assert text.count(before) == 1, before
        text = text.replace(before, after, 1)
    return '#include "stock_axwii_device.h"\n' + text
