"""Latch the existing host presentation at an XFB-copy command."""
from stock_gx_renderer_texgen_patch import replace_once


CAPTURE = '''
static GLuint completed_frame_fbo = 0;
static GLuint completed_frame_texture = 0;
extern "C" unsigned OpenSHSMCompletedFramebuffer() {
    return completed_frame_fbo;
}
static void CaptureCompletedFrame() {
    GLint previous_read = 0, previous_draw = 0, previous_texture = 0;
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &previous_read);
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previous_draw);
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &previous_texture);
    const GLboolean scissor = glIsEnabled(GL_SCISSOR_TEST);
    if (!completed_frame_fbo) {
        glGenTextures(1, &completed_frame_texture);
        glBindTexture(GL_TEXTURE_2D, completed_frame_texture);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 640, 480, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glGenFramebuffers(1, &completed_frame_fbo);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, completed_frame_fbo);
        glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D, completed_frame_texture, 0);
        if (glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
            throw std::runtime_error("completed-frame framebuffer incomplete");
        }
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, GLuint(previous_draw));
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, completed_frame_fbo);
    glDisable(GL_SCISSOR_TEST);
    glBlitFramebuffer(0, 0, 640, 480, 0, 0, 640, 480, GL_COLOR_BUFFER_BIT, GL_NEAREST);
    if (scissor) {
        glEnable(GL_SCISSOR_TEST);
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, GLuint(previous_read));
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, GLuint(previous_draw));
    glBindTexture(GL_TEXTURE_2D, GLuint(previous_texture));
}
'''


def renderer(text):
    text = replace_once(text, 'namespace nwii::runtime::gx {\n',
        'namespace nwii::runtime::gx {\n' + CAPTURE)
    anchor = '        ApplyBPRegister((uint8_t)cmd.reg, cmd.val);'
    return replace_once(text, anchor, anchor + '\n'
        '        if (cmd.reg == 0x52 && (cmd.val & 0x4000)) {\n'
        '            CaptureCompletedFrame();\n'
        '        }\n')


def main(text):
    assert 'OpenSHSMCompletedFramebuffer' not in text
    text = 'extern "C" unsigned OpenSHSMCompletedFramebuffer();\n' + text
    start = text.index('      host_phases.mark(3);')
    end = text.index('        nwii::runtime::gx::g_state.frame_ready = false;', start)
    section = text[start:end]
    old = 'glBindFramebuffer(GL_READ_FRAMEBUFFER, efb_fbo);'
    assert section.count(old) == 2
    section = section.replace(old, 'glBindFramebuffer(GL_READ_FRAMEBUFFER, '
        'OpenSHSMCompletedFramebuffer() ? OpenSHSMCompletedFramebuffer() : efb_fbo);')
    return text[:start] + section + text[end:]
