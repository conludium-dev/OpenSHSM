"""Coupled EFB coordinate and texture-sampling adaptation for the current US preview."""
from stock_gx_renderer_texgen_patch import replace_once, depth_write
from stock_gx_texture_sampling_patch import renderer as sampling_renderer
from stock_gx_texture_sampling_patch import shader
from stock_gx_sampler_patch import renderer as sampler_renderer


RASTER_SCOPE = '''
struct GuestRasterScope {
    GLint viewport[4];
    GLint scissor[4];
    GLboolean enabled;
    GuestRasterScope() {
        glGetIntegerv(GL_VIEWPORT, viewport);
        glGetIntegerv(GL_SCISSOR_BOX, scissor);
        enabled = glIsEnabled(GL_SCISSOR_TEST);
        float xf[6];
        std::memcpy(xf, &g_state.xf[0x1a], sizeof(xf));
        if (!(xf[0] > 0 && xf[1] < 0)) {
            return;
        }
        const int ox = int(g_state.bp[0x59] & 511) * 2;
        const int oy = int((g_state.bp[0x59] >> 10) & 511) * 2;
        const int x = int(std::lround(xf[3] - xf[0] - ox));
        const int y = int(std::lround(xf[4] + xf[1] - oy));
        const int width = int(std::lround(2 * xf[0]));
        const int height = int(std::lround(-2 * xf[1]));
        glViewport(x, 528 - y - height, width, height);
        const uint32_t tl = g_state.bp[0x20], br = g_state.bp[0x21];
        const int left = std::clamp(int((tl >> 12) & 2047) - ox, 0, 640);
        const int top = std::clamp(int(tl & 2047) - oy, 0, 528);
        const int right = std::clamp(int((br >> 12) & 2047) - ox + 1, 0, 640);
        const int bottom = std::clamp(int(br & 2047) - oy + 1, 0, 528);
        glEnable(GL_SCISSOR_TEST);
        glScissor(left, 528 - bottom, std::max(0, right - left), std::max(0, bottom - top));
    }
    ~GuestRasterScope() {
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        glScissor(scissor[0], scissor[1], scissor[2], scissor[3]);
        if (enabled) {
            glEnable(GL_SCISSOR_TEST);
        } else {
            glDisable(GL_SCISSOR_TEST);
        }
    }
};
'''

EFB_COPY = '''            static GLuint copy_fbo = 0;
            if (!copy_fbo) {
                glGenFramebuffers(1, &copy_fbo);
            }
            GLint previous_draw_fbo = 0;
            glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previous_draw_fbo);
            if (!partial_rgba8) {
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, copy_w, copy_h, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
            }
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, copy_fbo);
            glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                   GL_TEXTURE_2D, tex, 0);
            glDrawBuffer(GL_COLOR_ATTACHMENT0);
            glBlitFramebuffer(g_state.efbSrcX, 528 - int(g_state.efbSrcY),
                              g_state.efbSrcX + w, 528 - int(g_state.efbSrcY + h),
                              0, 0, copy_w, copy_h, GL_COLOR_BUFFER_BIT,
                              half_scale ? GL_LINEAR : GL_NEAREST);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, GLuint(previous_draw_fbo));
'''


def renderer(text):
    text = replace_once(text, '\nstatic void FlushBatch()', RASTER_SCOPE + '\nstatic void FlushBatch()')
    text = replace_once(text, '  glDrawArrays(GL_TRIANGLES, 0, s_batch.size());',
        '  {\n    GuestRasterScope scope;\n'
        '    glDrawArrays(GL_TRIANGLES, 0, s_batch.size());\n  }')
    start = text.index('            if (half_scale) {')
    end = text.index('            const unsigned raw_format', start)
    text = text[:start] + EFB_COPY + text[end:]
    return depth_write(sampler_renderer(sampling_renderer(text)))


def main(text):
    replacements = [
        ('glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 640, 480,',
         'glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 640, 528,'),
        ('GL_DEPTH_COMPONENT24, 640, 480', 'GL_DEPTH_COMPONENT24, 640, 528'),
        ('glViewport(0, 0, 640, 480)', 'glViewport(0, 48, 640, 480)'),
        ('glReadPixels(0, 0, 640, 480', 'glReadPixels(0, 48, 640, 480'),
        ('glBlitFramebuffer(0, 0, 640, 480,', 'glBlitFramebuffer(0, 48, 640, 528,')]
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    return text
