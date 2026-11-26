"""Convert GX texgen coordinates to normalized GL sampling per texture stage."""
from stock_gx_renderer_texgen_patch import replace_once


def renderer(text):
    text = replace_once(text,
        '  GLint uMatColor, uAmbColor, uChanCtrl, uTexGenColor;',
        '  GLint uMatColor, uAmbColor, uChanCtrl, uTexGenColor, uTexSampling;')
    anchor = '    sh.uTexGenColor = glGetUniformLocation(sh.id, "uTexGenColor[0]");'
    text = replace_once(text, anchor, anchor + '\n'
        '    sh.uTexSampling = glGetUniformLocation(sh.id, "uTexSampling[0]");')
    anchor = '  glUseProgram(s_active_shader.id);'
    return replace_once(text, anchor, anchor + '''
    if (s_active_shader.uTexSampling >= 0) {
        GLfloat sampling[32];
        for (unsigned index = 0; index < 8; ++index) {
            sampling[2 * index] = float((g_state.bp[0x30 + 2 * index] & 65535) + 1);
            sampling[2 * index + 1] = float((g_state.bp[0x31 + 2 * index] & 65535) + 1);
            sampling[16 + 2 * index] = float(std::max(1u, unsigned(g_state.texStages[index].width)));
            sampling[17 + 2 * index] = float(std::max(1u, unsigned(g_state.texStages[index].height)));
        }
        glUniform2fv(s_active_shader.uTexSampling, 16, sampling);
    }
''')


def shader(text):
    anchor = '    fs << "uniform vec4 uTevColor[4];\\n";'
    text = replace_once(text, anchor, anchor + '\n'
        '    fs << "uniform vec2 uTexSampling[16];\\n";')
    start = text.index('            fs << "    texColor = vTex"')
    end = text.index('\n', text.index('<< (int)stage.texCoord << ");\\n";', start))
    return text[:start] + r'''            fs << "    vec3 sampleCoord = vec3(vTex" << unsigned(stage.texCoord)
               << ".xy * uTexSampling[" << unsigned(stage.texCoord)
               << "] / uTexSampling[" << unsigned(stage.texMap) + 8
               << "], vTex" << unsigned(stage.texCoord) << ".z);\n";
            fs << "    texColor = sampleCoord.z == 0.0 ? texture(uTex" << unsigned(stage.texMap)
               << ", sampleCoord.xy) : textureProj(uTex" << unsigned(stage.texMap)
               << ", sampleCoord);\n";''' + text[end:]
