"""Apply GX wrapping and base-level filtering to existing GL texture units."""
from stock_gx_renderer_texgen_patch import replace_once


def renderer(text):
    anchor = '  glUseProgram(s_active_shader.id);'
    return replace_once(text, anchor, anchor + '''
    static GLuint texture_samplers[8] = {};
    if (!texture_samplers[0]) {
        glGenSamplers(8, texture_samplers);
    }
    static constexpr GLenum wrap_modes[4] = {
        GL_CLAMP_TO_EDGE, GL_REPEAT, GL_MIRRORED_REPEAT, GL_CLAMP_TO_EDGE};
    for (unsigned unit = 0; unit < 8; ++unit) {
        const unsigned reg = 0x80 + (unit / 4) * 0x20 + unit % 4;
        const uint32_t mode = g_state.bp[reg];
        const GLuint sampler = texture_samplers[unit];
        glSamplerParameteri(sampler, GL_TEXTURE_WRAP_S, wrap_modes[mode & 3]);
        glSamplerParameteri(sampler, GL_TEXTURE_WRAP_T, wrap_modes[(mode >> 2) & 3]);
        glSamplerParameteri(sampler, GL_TEXTURE_MAG_FILTER, (mode & 16) ? GL_LINEAR : GL_NEAREST);
        glSamplerParameteri(sampler, GL_TEXTURE_MIN_FILTER, (mode & 128) ? GL_LINEAR : GL_NEAREST);
        glBindSampler(unit, sampler);
    }
''')
