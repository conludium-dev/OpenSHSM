struct IndexedCopyGLState {
    RetileGLState draw;
    GLint unpackBuffer = 0;
    GLint unpackAlignment = 0;
    GLint unpackRowLength = 0;
    GLint unpackSkipRows = 0;
    GLint unpackSkipPixels = 0;
    GLint samplers[3]{};
    GLboolean dither = GL_FALSE;
    GLboolean logic = GL_FALSE;
    GLboolean discard = GL_FALSE;

    IndexedCopyGLState() {
        glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING, &unpackBuffer);
        glGetIntegerv(GL_UNPACK_ALIGNMENT, &unpackAlignment);
        glGetIntegerv(GL_UNPACK_ROW_LENGTH, &unpackRowLength);
        glGetIntegerv(GL_UNPACK_SKIP_ROWS, &unpackSkipRows);
        glGetIntegerv(GL_UNPACK_SKIP_PIXELS, &unpackSkipPixels);
        dither = glIsEnabled(GL_DITHER);
        logic = glIsEnabled(GL_COLOR_LOGIC_OP);
        discard = glIsEnabled(GL_RASTERIZER_DISCARD);
        for (unsigned index = 0; index < 3; ++index) {
            glGetIntegeri_v(GL_SAMPLER_BINDING, index, &samplers[index]);
        }
    }

    ~IndexedCopyGLState() {
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpackBuffer);
        glPixelStorei(GL_UNPACK_ALIGNMENT, unpackAlignment);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, unpackRowLength);
        glPixelStorei(GL_UNPACK_SKIP_ROWS, unpackSkipRows);
        glPixelStorei(GL_UNPACK_SKIP_PIXELS, unpackSkipPixels);
        for (unsigned index = 0; index < 3; ++index) {
            glBindSampler(index, samplers[index]);
        }
        const auto restore = [](GLenum feature, GLboolean enabled) {
            if (enabled) {
                glEnable(feature);
            } else {
                glDisable(feature);
            }
        };
        restore(GL_DITHER, dither);
        restore(GL_COLOR_LOGIC_OP, logic);
        restore(GL_RASTERIZER_DISCARD, discard);
    }
};

void RenderIndexedEfbCopy(GLuint source, GLuint target, const TexStage& stage,
        const hle::EfbCopyTexture& copy, const Color* palette, bool allocate) {
    static const char* vertex = R"(#version 330 core
void main() {
    vec2 points[3] = vec2[3](vec2(-1, -1), vec2(3, -1), vec2(-1, 3));
    gl_Position = vec4(points[gl_VertexID], 0, 1);
}
)";
    static const char* fragment = R"(#version 330 core
uniform sampler2D sourceCopy;
uniform sampler2D paletteCopy;
uniform int pixelFormat;
uniform int validHeight;
uniform uvec3 filterWeights;
out vec4 outputColor;
uvec3 sourceColor(ivec2 xy) {
    xy.y = clamp(xy.y, 0, validHeight - 1);
    uvec3 color = uvec3(roundEven(texelFetch(sourceCopy, xy, 0).rgb * 255.0));
    if (pixelFormat == 1) {
        color = (color & uvec3(252)) | (color >> 6);
    } else if (pixelFormat == 2) {
        color = (color & uvec3(248, 252, 248)) | (color >> uvec3(5, 6, 5));
    }
    return color;
}
void main() {
    ivec2 xy = ivec2(gl_FragCoord.xy);
    uvec3 sum = sourceColor(xy + ivec2(0, -1)) * filterWeights.x
        + sourceColor(xy) * filterWeights.y
        + sourceColor(xy + ivec2(0, 1)) * filterWeights.z;
    uvec3 color = min((sum >> 6) & uvec3(511), uvec3(255));
    uint intensity = (66u * color.r + 129u * color.g + 25u * color.b + 4224u) >> 8;
    outputColor = texelFetch(paletteCopy, ivec2(int(intensity), 0), 0);
}
)";
    IndexedCopyGLState saved;
    static GLuint program = 0;
    static GLuint vao = 0;
    static GLuint paletteTexture = 0;
    static GLuint framebuffer = 0;
    static bool paletteAllocated = false;
    if (!program) {
        program = CompileShader(vertex, fragment);
        glGenVertexArrays(1, &vao);
        glGenTextures(1, &paletteTexture);
        glGenFramebuffers(1, &framebuffer);
    }
    glDisable(GL_SCISSOR_TEST);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);
    glDisable(GL_STENCIL_TEST);
    glDisable(GL_FRAMEBUFFER_SRGB);
    glDisable(GL_DITHER);
    glDisable(GL_COLOR_LOGIC_OP);
    glDisable(GL_RASTERIZER_DISCARD);
    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glDepthMask(GL_FALSE);
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
    glPixelStorei(GL_UNPACK_SKIP_ROWS, 0);
    glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0);
    for (unsigned index = 0; index < 3; ++index) {
        glBindSampler(index, 0);
    }
    glActiveTexture(GL_TEXTURE1);
    glBindTexture(GL_TEXTURE_2D, paletteTexture);
    if (!paletteAllocated) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 256, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        paletteAllocated = true;
    }
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 256, 1, GL_RGBA, GL_UNSIGNED_BYTE, palette);
    glActiveTexture(GL_TEXTURE2);
    glBindTexture(GL_TEXTURE_2D, target);
    if (allocate) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, stage.width, stage.height, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    }
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, target, 0);
    glDrawBuffer(GL_COLOR_ATTACHMENT0);
    if (glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        throw std::runtime_error("GX indexed EFB view framebuffer incomplete");
    }
    glViewport(0, 0, stage.width, stage.height);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, source);
    glUseProgram(program);
    glUniform1i(glGetUniformLocation(program, "sourceCopy"), 0);
    glUniform1i(glGetUniformLocation(program, "paletteCopy"), 1);
    glUniform1i(glGetUniformLocation(program, "pixelFormat"), copy.pixel_format);
    glUniform1i(glGetUniformLocation(program, "validHeight"), copy.valid_height);
    const auto coefficient = [&](unsigned index) {
        return index < 4 ? (copy.filter0 >> (index * 6)) & 63u : (copy.filter1 >> ((index - 4) * 6)) & 63u;
    };
    glUniform3ui(glGetUniformLocation(program, "filterWeights"), coefficient(0) + coefficient(1),
        coefficient(2) + coefficient(3) + coefficient(4), coefficient(5) + coefficient(6));
    glBindVertexArray(vao);
    glDrawArrays(GL_TRIANGLES, 0, 3);
}
