"""Join retained FIFO sources and GX texgen with the existing GL renderer."""
import re


ALPHA_LIGHTING = '''    if (lit || alit) {
        vec3 _normal = normalize(nrm);
        for (int channel = 0; channel < 2; ++channel) {
            int lighting_ctrl = channel == 0 ? ctrl : actrl;
            if ((lighting_ctrl & 2) == 0) {
                continue;
            }
            int lighting_diffuse = (lighting_ctrl >> 7) & 3;
            int lighting_attn = (lighting_ctrl >> 9) & 3;
            int lighting_mask = ((lighting_ctrl >> 2) & 0xF) |
                                (((lighting_ctrl >> 11) & 0xF) << 4);
            for (int i = 0; i < 8; ++i) {
                if ((lighting_mask & (1 << i)) == 0) {
                    continue;
                }
                vec3 ldir; float attn;
                if (lighting_attn == 3) {
                    ldir = uLightPos[i].xyz - pos;
                    float dist2 = dot(ldir, ldir);
                    float dist = sqrt(dist2);
                    ldir = ldir / dist;
                    attn = max(0.0, dot(ldir, uLightDir[i].xyz));
                    attn = max(0.0, uLightCosAtt[i].x + uLightCosAtt[i].y * attn +
                                    uLightCosAtt[i].z * attn * attn) /
                           dot(uLightDistAtt[i].xyz, vec3(1.0, dist, dist2));
                } else if (lighting_attn == 1) {
                    ldir = normalize(uLightPos[i].xyz - pos);
                    attn = (dot(_normal, ldir) >= 0.0)
                               ? max(0.0, dot(_normal, uLightDir[i].xyz)) : 0.0;
                    vec3 cosAttn = uLightCosAtt[i].xyz;
                    vec3 distAttn = (lighting_diffuse == 0) ? uLightDistAtt[i].xyz
                                                           : normalize(uLightDistAtt[i].xyz);
                    attn = max(0.0, dot(cosAttn, vec3(1.0, attn, attn * attn))) /
                           dot(distAttn, vec3(1.0, attn, attn * attn));
                } else {
                    ldir = uLightPos[i].xyz - pos;
                    ldir = (length(ldir) == 0.0) ? _normal : normalize(ldir);
                    attn = 1.0;
                }
                float ndl = (lighting_diffuse == 0) ? 1.0
                          : ((lighting_diffuse == 1) ? dot(ldir, _normal)
                                                      : max(0.0, dot(ldir, _normal)));
                if (channel == 0) {
                    lacc.rgb += attn * ndl * uLightCol[i].rgb;
                } else {
                    lacc.a += attn * ndl * uLightCol[i].a;
                }
            }
        }
    }
'''


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def shader(text, swaps=True, comparisons=True):
    text = replace_once(text,
        '    vs << "layout(location = 1) in vec4 vertexColor;\\n";\n',
        '    vs << "layout(location = 1) in vec4 vertexColor;\\n";\n'
        '    vs << "layout(location = 12) in vec4 vertexColor1;\\n";\n')
    text = replace_once(text,
        '    vs << "    vColor1 = dolphin_chan(1, vertexPosition, vertexNormal, vertexColor);\\n";\n',
        '    vs << "    vColor1 = dolphin_chan(1, vertexPosition, vertexNormal, vertexColor1);\\n";\n')
    text = replace_once(text,
        '    int  diffusefunc = (ctrl >> 7) & 3;\n'
        '    int  attnfunc    = (ctrl >> 9) & 3;\n'
        '    int  lightmask   = ((ctrl >> 2) & 0xF) | (((ctrl >> 11) & 0xF) << 4);\n', '')
    start = text.index('    if (lit) {\n')
    end = text.index('    return clamp(mat * clamp(lacc, 0.0, 1.0), 0.0, 1.0);', start)
    assert text.count('    if (lit) {\n') == 1
    text = text[:start] + ALPHA_LIGHTING + text[end:]
    text = replace_once(text,
        '    vs << "layout(location = 2) in vec2 vertexTexCoord;\\n";\n',
        '    for (int i = 0; i < 8; ++i) {\n'
        '        vs << "layout(location = " << i + 4 << ") in vec3 vertexTexCoord" << i << ";\\n";\n'
        '    }\n')
    text = replace_once(text, 'vs << "out vec2 vTex" << i << ";\\n";',
        'vs << "out vec3 vTex" << i << ";\\n";')
    text = replace_once(text,
        '    vs << "uniform mat4 uTexMtx[8];\\n";\n', '')
    text = replace_once(text,
        '    vs << "uniform vec4 uLightDistAtt[8];\\n";\n',
        '    vs << "uniform vec4 uLightDistAtt[8];\\n";\n'
        '    vs << "uniform int uTexGenColor[8];\\n";\n')
    text = replace_once(text,
        '        vs << "    vTex" << i << " = (uTexMtx[" << i\n'
        '           << "] * vec4(vertexTexCoord, 0.0, 1.0)).xy;\\n";\n',
        '        vs << "    vTex" << i << " = uTexGenColor[" << i\n'
        '           << "] == 1 ? vec3(vColor0.rg, 1.0) : (uTexGenColor[" << i\n'
        '           << "] == 2 ? vec3(vColor1.rg, 1.0) : vertexTexCoord" << i << ");\\n";\n')
    for index in range(8):
        text = replace_once(text, f'fs << "in vec2 vTex{index};\\n";',
            f'fs << "in vec3 vTex{index};\\n";')
    text = replace_once(text,
        '            fs << "    texColor = texture(uTex" << (int)stage.texMap << ", vTex" << (int)stage.texCoord << ");\\n";\n',
        '            fs << "    texColor = vTex" << (int)stage.texCoord\n'
        '               << ".z == 0.0 ? texture(uTex" << (int)stage.texMap << ", vTex"\n'
        '               << (int)stage.texCoord << ".xy) : textureProj(uTex"\n'
        '               << (int)stage.texMap << ", vTex" << (int)stage.texCoord << ");\\n";\n')
    text = tev_swaps(text) if swaps else text
    return tev_compare(text) if comparisons else text


def tev_swaps(text):
    return replace_once(text,
        '        uint32_t ksel_reg = state.bp[0xF6 + (i / 2)];',
        '''        const auto swizzle = [&](unsigned table) {
            const char channels[] = "rgba";
            const uint32_t rg = state.bp[0xF6 + 2 * table];
            const uint32_t ba = state.bp[0xF7 + 2 * table];
            std::string result;
            result += channels[rg & 3];
            result += channels[(rg >> 2) & 3];
            result += channels[ba & 3];
            result += channels[(ba >> 2) & 3];
            return result;
        };
        const uint32_t alpha = state.bp[0xC1 + 2 * i];
        fs << "    rasColor = rasColor." << swizzle(alpha & 3) << ";\\n";
        fs << "    texColor = texColor." << swizzle((alpha >> 2) & 3) << ";\\n";
        uint32_t ksel_reg = state.bp[0xF6 + (i / 2)];''')



def tev_compare(text):
    anchor = '        map_color_input(3, stage.colorInD);\n'
    text = replace_once(text, anchor, anchor + r'''
        fs << "    ivec3 cmpA = ivec3(round(cIn[0] * 255.0)) & ivec3(255);\n";
        fs << "    ivec3 cmpB = ivec3(round(cIn[1] * 255.0)) & ivec3(255);\n";
        const auto compare = [&](unsigned mode, unsigned op, bool alpha) {
            const char* relation = op ? " == " : " > ";
            if (mode == 3) {
                if (alpha) {
                    return std::string("((int(round(aIn[0] * 255.0)) & 255)") + relation +
                        "(int(round(aIn[1] * 255.0)) & 255))";
                }
                return std::string(op ? "equal" : "greaterThan") + "(cmpA, cmpB)";
            }
            const auto packed = [&](const char* value) {
                std::string result = std::string("(") + value + ".r";
                if (mode >= 1) {
                    result += std::string(" + (") + value + ".g << 8)";
                }
                if (mode >= 2) {
                    result += std::string(" + (") + value + ".b << 16)";
                }
                return result + ")";
            };
            return "(" + packed("cmpA") + relation + packed("cmpB") + ")";
        };
''')
    text = replace_once(text, '        if (stage.colorOp == 0) { ', r'''        if (stage.colorBias == 3) {
            fs << "    vec3 cmpC = vec3(ivec3(round(cIn[2] * 255.0)) & ivec3(255)) / 255.0;\n";
            if (stage.colorScale == 3) {
                fs << "    cOut = cIn[3] + mix(vec3(0.0), cmpC, "
                   << compare(3, stage.colorOp, false) << ");\n";
            } else {
                fs << "    cOut = cIn[3] + (" << compare(stage.colorScale, stage.colorOp, false)
                   << " ? cmpC : vec3(0.0));\n";
            }
        } else if (stage.colorOp == 0) { ''')
    text = replace_once(text, '        if (stage.alphaOp == 0) { ', r'''        if (stage.alphaBias == 3) {
            fs << "    aOut = aIn[3] + (" << compare(stage.alphaScale, stage.alphaOp, true)
               << " ? float(int(round(aIn[2] * 255.0)) & 255) / 255.0 : 0.0);\n";
        } else if (stage.alphaOp == 0) { ''')
    for channel in ('color', 'alpha'):
        for scale in (1, 2, 3):
            old = f'if (stage.{channel}Scale == {scale}) fs <<'
            text = replace_once(text, old,
                f'if (stage.{channel}Bias != 3 && stage.{channel}Scale == {scale}) fs <<')
    return text


def tev_final_output(text):
    return replace_once(text,
        '    fs << "    FragColor = tevReg[0];\\n";',
        '    const auto& finalStage = state.tevStages[numTevs - 1];\n'
        '    fs << "    FragColor = vec4(tevReg[" << unsigned(finalStage.colorRegId)\n'
        '       << "].rgb, tevReg[" << unsigned(finalStage.alphaRegId) << "].a);\\n";')


def renderer(text):
    text = '#include "stock_gx_texgen_bridge.h"\n#include "stock_gx_shader_key.h"\n#include <array>\n' + text
    text = replace_once(text,
        '  float nx, ny, nz;\n};',
        '  float nx, ny, nz;\n  float texcoords[8][3];\n'
        '  float r1, g1, b1, a1;\n};')
    text = replace_once(text,
        '  GLint uMatColor, uAmbColor, uChanCtrl;\n',
        '  GLint uMatColor, uAmbColor, uChanCtrl, uTexGenColor;\n')
    text = replace_once(text,
        '    sh.uChanCtrl = glGetUniformLocation(sh.id, "uChanCtrl[0]");\n',
        '    sh.uChanCtrl = glGetUniformLocation(sh.id, "uChanCtrl[0]");\n'
        '    sh.uTexGenColor = glGetUniformLocation(sh.id, "uTexGenColor[0]");\n')
    text = replace_once(text,
        '  glUseProgram(s_active_shader.id);\n',
        '  glUseProgram(s_active_shader.id);\n'
        '  if (s_active_shader.uTexGenColor >= 0) {\n'
        '    GLint color_sources[8] = {};\n'
        '    for (unsigned channel = 0; channel < g_state.numTexGens && channel < 8; ++channel) {\n'
        '      const uint32_t info = g_state.xf[0x40 + channel];\n'
        '      const unsigned type = (info >> 4) & 7;\n'
        '      if ((type == 2 || type == 3) && !(info & 4)) {\n'
        '        color_sources[channel] = GLint(type - 1);\n'
        '      }\n'
        '    }\n'
        '    glUniform1iv(s_active_shader.uTexGenColor, 8, color_sources);\n'
        '  }\n')
    text = replace_once(text,
        'static std::vector<BatchVertex> s_batch;\n',
        'static std::vector<BatchVertex> s_batch;\n'
        'static std::array<float, 256> s_post_matrices{};\n'
        'static std::array<bool, 256> s_post_written{};\n')
    assert text.count('g_state.GetShaderHash(cmd.prim_type)') == 2
    text = text.replace('g_state.GetShaderHash(cmd.prim_type)',
        'openshsm::experiment::semantic_tev_shader_key(g_state)')
    text = replace_once(text,
        '    glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, sizeof(BatchVertex),\n'
        '                          (void *)offsetof(BatchVertex, nx));\n',
        '    glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, sizeof(BatchVertex),\n'
        '                          (void *)offsetof(BatchVertex, nx));\n'
        '    for (unsigned index = 0; index < 8; ++index) {\n'
        '      glEnableVertexAttribArray(4 + index);\n'
        '      glVertexAttribPointer(4 + index, 3, GL_FLOAT, GL_FALSE, sizeof(BatchVertex),\n'
        '          (void *)(offsetof(BatchVertex, texcoords) + index * 3 * sizeof(float)));\n'
        '    }\n'
        '    glEnableVertexAttribArray(12);\n'
        '    glVertexAttribPointer(12, 4, GL_FLOAT, GL_FALSE, sizeof(BatchVertex),\n'
        '        (void *)offsetof(BatchVertex, r1));\n')
    text = replace_once(text,
        'static void EmitVertex(const VertexData &vtx) {\n',
        'static void EmitVertex(const GXCommand &cmd, size_t index) {\n'
        '  const VertexData &vtx = cmd.vertices[index];\n')
    text = replace_once(text,
        '  if (vtx.has_norm && vtx.pre_xf) {\n',
        '  bv.r1 = bv.g1 = bv.b1 = bv.a1 = 1.f;\n'
        '  if (cmd.raw && index < cmd.raw->sources.size() &&\n'
        '      cmd.raw->sources[index].has_color[1]) {\n'
        '    const auto &color1 = cmd.raw->sources[index].colors[1];\n'
        '    bv.r1 = color1[0]; bv.g1 = color1[1];\n'
        '    bv.b1 = color1[2]; bv.a1 = color1[3];\n'
        '  }\n'
        '  if (vtx.has_norm && vtx.pre_xf) {\n')
    marker = '  float x = vtx.pos[0], y = vtx.pos[1], z = vtx.pos[2];\n'
    insertion = '''  for (unsigned channel = 0; channel < 8; ++channel) {
    bv.texcoords[channel][0] = bv.u;
    bv.texcoords[channel][1] = bv.v;
    bv.texcoords[channel][2] = 1.0f;
  }
  if (cmd.raw && index < cmd.raw->sources.size()) {
    for (unsigned channel = 0; channel < g_state.numTexGens && channel < 8; ++channel) {
      if (((g_state.xf[0x40 + channel] >> 4) & 7) != 0) {
        continue;
      }
      try {
        const unsigned row = (g_state.xf[0x40 + channel] >> 7) & 31;
        const size_t base = size_t(cmd.raw->sources[index].matrix_indices[channel]) * 4;
        const unsigned columns = (g_state.xf[0x40 + channel] & 2) ? 12 : 8;
        bool loaded = false;
        for (unsigned column = 0; column < columns && base + column < 256; ++column) {
          loaded |= g_state.posMatrices[base + column] != 0.0f;
        }
        bool post_loaded = true;
        if (g_state.xf[0x12] & 1) {
          post_loaded = false;
          const size_t post_base = size_t(g_state.xf[0x50 + channel] & 63) * 4;
          for (unsigned column = 0; column < 12 && post_base + column < 256; ++column) {
            post_loaded |= s_post_written[post_base + column];
          }
        }
        if (!loaded || !post_loaded) {
          if (row >= 5 && row <= 12 && cmd.raw->sources[index].has_uv[row - 5]) {
            bv.texcoords[channel][0] = cmd.raw->sources[index].uv[row - 5][0];
            bv.texcoords[channel][1] = cmd.raw->sources[index].uv[row - 5][1];
            bv.texcoords[channel][2] = 1.0f;
          }
          continue;
        }
        const auto coordinate = openshsm::experiment::generate_draw_regular_texcoord(
            cmd.raw->sources[index], g_state, s_post_matrices, channel);
        const float scale_s = float((g_state.bp[0x30 + 2 * channel] & 0xffff) + 1);
        const float scale_t = float((g_state.bp[0x31 + 2 * channel] & 0xffff) + 1);
        bv.texcoords[channel][0] = coordinate[0] / scale_s;
        bv.texcoords[channel][1] = coordinate[1] / scale_t;
        bv.texcoords[channel][2] = coordinate[2];
      } catch (const std::runtime_error &error) {
        if (gx_trace()) {
          static unsigned refusals = 0;
          if (refusals++ < 8) {
            std::fprintf(stderr, "[GX texgen fallback] %s\\n", error.what());
          }
        }
      }
    }
  }

'''
    text = replace_once(text, marker, insertion + marker)
    text, count = re.subn(r'EmitVertex\(v\[(.*?)\]\);', r'EmitVertex(cmd, \1);', text)
    assert count == 15, count
    text = replace_once(text,
        '    for (const auto &vtx : v)\n      EmitVertex(vtx);',
        '    for (size_t i = 0; i < n; ++i)\n      EmitVertex(cmd, i);')
    assert 'EmitVertex(v[' not in text and 'EmitVertex(vtx)' not in text
    text = replace_once(text,
        '            g_state.normalMatrices[current_addr - 0x0400] = cmd.payload[i];\n'
        '          } else if (current_addr >= 0x0600 && current_addr <= 0x067F) {',
        '            g_state.normalMatrices[current_addr - 0x0400] = cmd.payload[i];\n'
        '          } else if (current_addr >= 0x0500 && current_addr <= 0x05FF) {\n'
        '            s_post_matrices[current_addr - 0x0500] = cmd.payload[i];\n'
        '            s_post_written[current_addr - 0x0500] = true;\n'
        '          } else if (current_addr >= 0x0600 && current_addr <= 0x067F) {')
    text = replace_once(text,
        '            if (!tex)\n'
        '              glGenTextures(1, &tex);\n'
        '            glBindTexture(GL_TEXTURE_2D, tex);\n',
        '            const bool had_copy = tex != 0;\n'
        '            if (!tex)\n'
        '              glGenTextures(1, &tex);\n'
        '            glBindTexture(GL_TEXTURE_2D, tex);\n')
    text = replace_once(text,
        '            glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, g_state.efbSrcX,\n'
        '                             g_state.efbSrcY, w, h, 0);\n',
        '''            GLint existing_w = 0, existing_h = 0;
            if (had_copy) {
                glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &existing_w);
                glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &existing_h);
            }
            const bool half_scale = (cmd.val & 0x200) && w >= 2 && h >= 2;
            const uint32_t copy_w = half_scale ? w / 2 : w;
            const uint32_t copy_h = half_scale ? h / 2 : h;
            const uint32_t stride = g_state.efbCopyStride;
            const bool partial_rgba8 = had_copy && ((cmd.val >> 3) & 15) == 12 &&
                stride != 0 && stride % 16 == 0 &&
                existing_w == GLint(stride / 16) &&
                copy_w <= uint32_t(existing_w) && copy_h <= uint32_t(existing_h) &&
                (copy_w < uint32_t(existing_w) || copy_h < uint32_t(existing_h));
            if (half_scale) {
                static GLuint copy_fbo = 0;
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
                glBlitFramebuffer(g_state.efbSrcX, g_state.efbSrcY,
                                  g_state.efbSrcX + w, g_state.efbSrcY + h,
                                  0, 0, copy_w, copy_h, GL_COLOR_BUFFER_BIT,
                                  GL_LINEAR);
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, GLuint(previous_draw_fbo));
            } else if (partial_rgba8) {
                glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0,
                                    g_state.efbSrcX, g_state.efbSrcY, w, h);
            } else {
                glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, g_state.efbSrcX,
                                 g_state.efbSrcY, w, h, 0);
            }
''')
    text = replace_once(text,
        '  if (!enable) { glDisable(GL_BLEND); return; }',
        '  const GLboolean color_write = (cm & 8) ? GL_TRUE : GL_FALSE;\n'
        '  const GLboolean alpha_write = (cm & 16) ? GL_TRUE : GL_FALSE;\n'
        '  glColorMask(color_write, color_write, color_write, alpha_write);\n'
        '  if (!enable) { glDisable(GL_BLEND); return; }')
    text = replace_once(text,
        '    glDepthMask(GL_TRUE);\n    glClear(GL_DEPTH_BUFFER_BIT);',
        '    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '    glDepthMask(GL_TRUE);\n    glClear(GL_DEPTH_BUFFER_BIT);')
    text = replace_once(text,
        '              glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);',
        '              glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '              glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);')
    return efb_rg8(missing_texcoords(text))


def missing_texcoords(text):
    return replace_once(text,
        '''        const auto coordinate = openshsm::experiment::generate_draw_regular_texcoord(
            cmd.raw->sources[index], g_state, s_post_matrices, channel);''',
        '''        auto source = cmd.raw->sources[index];
        if (row >= 5 && row <= 12 && !source.has_uv[row - 5]) {
            source.uv[row - 5] = {0.0f, 0.0f};
            source.has_uv[row - 5] = true;
        }
        const auto coordinate = openshsm::experiment::generate_draw_regular_texcoord(
            source, g_state, s_post_matrices, channel);''')


def efb_rg8(text):
    needle = '            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);'
    return replace_once(text, needle, '''            const unsigned raw_format = (cmd.val >> 3) & 15;
            const unsigned copy_format = (raw_format >> 1) | ((raw_format & 1) << 3);
            GLint copy_swizzle[4] = {GL_RED, GL_GREEN, GL_BLUE, GL_ALPHA};
            if (copy_format == 11 && !(cmd.val & 0x8000)) {
                copy_swizzle[0] = copy_swizzle[1] = copy_swizzle[2] = GL_RED;
                copy_swizzle[3] = GL_GREEN;
            }
            glTexParameteriv(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_RGBA, copy_swizzle);
''' + needle)


def depth_state(text):
    write_only = ('static void ApplyZMode() {\n'
        '    glDepthMask((g_state.bp[0x40] & 16) ? GL_TRUE : GL_FALSE);\n\n')
    if write_only in text:
        text = replace_once(text, write_only, 'static void ApplyZMode() {\n\n')
    text = replace_once(text,
        '    p[10] = sp[4];\n    p[14] = sp[5];',
        '    p[10] = 2.0f * sp[4];\n    p[14] = 2.0f * sp[5] + 1.0f;')
    text = replace_once(text,
        '  if (!CurrentIsPerspective())\n    bv.z = 0.0f;',
        '  if (std::getenv("NWII_FLATZ")) {\n    bv.z = 0.0f;\n  }')
    text = replace_once(text,
        'static void ApplyZMode() {\n\n'
        '  if (CurrentIsPerspective()) {\n'
        '    glEnable(GL_DEPTH_TEST);\n'
        '    glDepthFunc(GL_LEQUAL);\n'
        '  } else {\n'
        '    glDisable(GL_DEPTH_TEST);\n'
        '  }\n}',
        '''static void ApplyZMode() {
    const uint32_t mode = g_state.bp[0x40];
    static constexpr GLenum functions[8] = {
        GL_NEVER, GL_LESS, GL_EQUAL, GL_LEQUAL,
        GL_GREATER, GL_NOTEQUAL, GL_GEQUAL, GL_ALWAYS};
    if (mode & 1) {
        glEnable(GL_DEPTH_TEST);
    } else {
        glDisable(GL_DEPTH_TEST);
    }
    glDepthFunc(functions[(mode >> 1) & 7]);
    glDepthMask((mode & 16) ? GL_TRUE : GL_FALSE);
}''')
    return text


def depth(text):
    return depth_persistence(depth_state(text))


def depth_persistence(text):
    text = replace_once(text,
        '    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '    glDepthMask(GL_TRUE);\n    glClear(GL_DEPTH_BUFFER_BIT);',
        '    if (!m_depth_initialized) {\n'
        '        glDepthMask(GL_TRUE);\n'
        '        glClear(GL_DEPTH_BUFFER_BIT);\n'
        '        m_depth_initialized = true;\n'
        '    }')
    text = replace_once(text,
        '\n      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);',
        '\n      glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '      glDepthMask(GL_TRUE);\n'
        '      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);')
    text = replace_once(text,
        '  void *m_window = nullptr;',
        '  void *m_window = nullptr;\n    bool m_depth_initialized = false;')
    text = replace_once(text,
        '              glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '              glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);',
        '              glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n'
        '              glDepthMask(GL_TRUE);\n'
        '              glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);')
    return text


def depth_write(text):
    return replace_once(text, 'static void ApplyZMode() {\n\n',
        'static void ApplyZMode() {\n'
        '    glDepthMask((g_state.bp[0x40] & 16) ? GL_TRUE : GL_FALSE);\n\n')
