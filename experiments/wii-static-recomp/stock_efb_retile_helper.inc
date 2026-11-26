struct RetileCopy {
    GLuint base = 0;
    GLuint view = 0;
    GLint baseWidth = 0;
    GLint baseHeight = 0;
    GLint viewWidth = 0;
    GLint viewHeight = 0;
};

static std::unordered_map<uint32_t, RetileCopy> s_retile_copies;

struct RetileGLState {
    GLint program = 0;
    GLint vao = 0;
    GLint activeTexture = 0;
    GLint drawFbo = 0;
    GLint readFbo = 0;
    GLint viewport[4]{};
    GLint boundTextures[3]{};
    GLboolean colorMask[4]{};
    GLboolean depthMask = GL_FALSE;
    GLboolean scissor = GL_FALSE;
    GLboolean depth = GL_FALSE;
    GLboolean blend = GL_FALSE;
    GLboolean cull = GL_FALSE;
    GLboolean stencil = GL_FALSE;
    GLboolean srgb = GL_FALSE;

    RetileGLState() {
        glGetIntegerv(GL_CURRENT_PROGRAM, &program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);
        glGetIntegerv(GL_ACTIVE_TEXTURE, &activeTexture);
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &drawFbo);
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &readFbo);
        glGetIntegerv(GL_VIEWPORT, viewport);
        glGetBooleanv(GL_COLOR_WRITEMASK, colorMask);
        glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);
        scissor = glIsEnabled(GL_SCISSOR_TEST);
        depth = glIsEnabled(GL_DEPTH_TEST);
        blend = glIsEnabled(GL_BLEND);
        cull = glIsEnabled(GL_CULL_FACE);
        stencil = glIsEnabled(GL_STENCIL_TEST);
        srgb = glIsEnabled(GL_FRAMEBUFFER_SRGB);
        for (int index = 0; index < 3; ++index) {
            glActiveTexture(GL_TEXTURE0 + index);
            glGetIntegerv(GL_TEXTURE_BINDING_2D, &boundTextures[index]);
        }
        glActiveTexture(activeTexture);
    }

    ~RetileGLState() {
        glUseProgram(program);
        glBindVertexArray(vao);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, drawFbo);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, readFbo);
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        glColorMask(colorMask[0], colorMask[1], colorMask[2], colorMask[3]);
        glDepthMask(depthMask);
        auto restore = [](GLenum feature, GLboolean enabled) {
            if (enabled) {
                glEnable(feature);
            } else {
                glDisable(feature);
            }
        };
        restore(GL_SCISSOR_TEST, scissor);
        restore(GL_DEPTH_TEST, depth);
        restore(GL_BLEND, blend);
        restore(GL_CULL_FACE, cull);
        restore(GL_STENCIL_TEST, stencil);
        restore(GL_FRAMEBUFFER_SRGB, srgb);
        for (int index = 0; index < 3; ++index) {
            glActiveTexture(GL_TEXTURE0 + index);
            glBindTexture(GL_TEXTURE_2D, boundTextures[index]);
        }
        glActiveTexture(activeTexture);
    }
};

static GLuint RetileRgba8Copy(uint32_t dest, GLuint baseTexture, GLint oldWidth,
    GLint oldHeight, GLint newWidth, GLint stripHeight, GLint srcX, GLint srcY,
    GLint srcWidth, GLint srcHeight) {
    static const char* vertex = R"(#version 330 core
void main() {
    vec2 points[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    gl_Position = vec4(points[gl_VertexID], 0.0, 1.0);
}
)";
    static const char* fragment = R"(#version 330 core
uniform sampler2D oldCopy;
uniform sampler2D newStrip;
uniform int oldTilesPerRow;
uniform int newTilesPerRow;
uniform int stripHeight;
out vec4 outputColor;
void main() {
    ivec2 xy = ivec2(gl_FragCoord.xy);
    if (xy.y < stripHeight) {
        outputColor = texelFetch(newStrip, xy, 0);
    } else {
        int tile = (xy.y / 4) * newTilesPerRow + xy.x / 4;
        ivec2 oldXY = ivec2((tile % oldTilesPerRow) * 4 + xy.x % 4,
                            (tile / oldTilesPerRow) * 4 + xy.y % 4);
        outputColor = texelFetch(oldCopy, oldXY, 0);
    }
}
)";
    static GLuint program = 0;
    static GLuint vao = 0;
    static GLuint stripTexture = 0;
    static GLuint stripFbo = 0;
    static GLuint viewFbo = 0;
    static GLint stripWidth = 0;
    static GLint stripAllocatedHeight = 0;
    if (!program) {
        program = CompileShader(vertex, fragment);
        glGenVertexArrays(1, &vao);
        glGenTextures(1, &stripTexture);
        glGenFramebuffers(1, &stripFbo);
        glGenFramebuffers(1, &viewFbo);
    }
    const GLint viewHeight = oldWidth * oldHeight / newWidth;
    RetileCopy& copy = s_retile_copies[dest & 0x01ffffffu];
    if (!copy.view) {
        glGenTextures(1, &copy.view);
    }
    RetileGLState saved;
    glDisable(GL_SCISSOR_TEST);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);
    glDisable(GL_STENCIL_TEST);
    glDisable(GL_FRAMEBUFFER_SRGB);
    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glDepthMask(GL_FALSE);
    glActiveTexture(GL_TEXTURE1);
    glBindTexture(GL_TEXTURE_2D, stripTexture);
    if (stripWidth != newWidth || stripAllocatedHeight != stripHeight) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, newWidth, stripHeight, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        stripWidth = newWidth;
        stripAllocatedHeight = stripHeight;
    }
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, stripFbo);
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D, stripTexture, 0);
    glDrawBuffer(GL_COLOR_ATTACHMENT0);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, saved.readFbo);
    glBlitFramebuffer(srcX, 528 - srcY, srcX + srcWidth, 528 - srcY - srcHeight,
        0, 0, newWidth, stripHeight, GL_COLOR_BUFFER_BIT, GL_NEAREST);
    glActiveTexture(GL_TEXTURE2);
    glBindTexture(GL_TEXTURE_2D, copy.view);
    if (copy.viewWidth != newWidth || copy.viewHeight != viewHeight) {
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, newWidth, viewHeight, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        copy.viewWidth = newWidth;
        copy.viewHeight = viewHeight;
    }
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, viewFbo);
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D, copy.view, 0);
    glDrawBuffer(GL_COLOR_ATTACHMENT0);
    glViewport(0, 0, newWidth, viewHeight);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, baseTexture);
    glActiveTexture(GL_TEXTURE1);
    glBindTexture(GL_TEXTURE_2D, stripTexture);
    glUseProgram(program);
    glUniform1i(glGetUniformLocation(program, "oldCopy"), 0);
    glUniform1i(glGetUniformLocation(program, "newStrip"), 1);
    glUniform1i(glGetUniformLocation(program, "oldTilesPerRow"), oldWidth / 4);
    glUniform1i(glGetUniformLocation(program, "newTilesPerRow"), newWidth / 4);
    glUniform1i(glGetUniformLocation(program, "stripHeight"), stripHeight);
    glBindVertexArray(vao);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    copy.base = baseTexture;
    copy.baseWidth = oldWidth;
    copy.baseHeight = oldHeight;
    return copy.view;
}

