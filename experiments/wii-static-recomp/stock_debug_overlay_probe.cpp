#include "stock_debug_overlay.h"
#include <array>
#include <cassert>

int main() {
    setenv("NWII_DEBUG_OVERLAY", "1", 1);
    unsetenv("NWII_SCREENSHOT");
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM debug overlay probe", 0, 0, 640, 480,
        SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    GLuint fbo, texture, vao, buffer;
    glGenFramebuffers(1, &fbo);
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 8, 8, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    glClearColor(0.25f, 0.5f, 0.75f, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    std::array<unsigned char, 256> before{}, after{};
    glReadPixels(0, 0, 8, 8, GL_RGBA, GL_UNSIGNED_BYTE, before.data());
    glGenVertexArrays(1, &vao);
    glGenBuffers(1, &buffer);
    glBindVertexArray(vao);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glViewport(5, 6, 32, 40);
    glScissor(2, 3, 7, 8);
    glPointSize(3);
    glColorMask(GL_FALSE, GL_TRUE, GL_FALSE, GL_TRUE);
    const GLenum caps[] = {GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_PROGRAM_POINT_SIZE,
        GL_STENCIL_TEST, GL_RASTERIZER_DISCARD};
    for (auto cap : caps) {
        glEnable(cap);
    }
    openshsm::experiment::DebugOverlay overlay;
    overlay.audio(0, 128, true, false);
    overlay.draw(640, 480, 1);
    GLint value, box[4];
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &value);
    assert(value == GLint(fbo));
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &value);
    assert(value == GLint(fbo));
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &value);
    assert(value == GLint(vao));
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &value);
    assert(value == GLint(buffer));
    glGetIntegerv(GL_VIEWPORT, box);
    assert(box[0] == 5 && box[1] == 6 && box[2] == 32 && box[3] == 40);
    glGetIntegerv(GL_SCISSOR_BOX, box);
    assert(box[0] == 2 && box[1] == 3 && box[2] == 7 && box[3] == 8);
    GLboolean mask[4];
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    assert(!mask[0] && mask[1] && !mask[2] && mask[3]);
    GLfloat point, clear[4];
    glGetFloatv(GL_POINT_SIZE, &point);
    glGetFloatv(GL_COLOR_CLEAR_VALUE, clear);
    assert(point == 3 && clear[0] == 0.25f && clear[1] == 0.5f && clear[2] == 0.75f && clear[3] == 1);
    for (auto cap : caps) {
        assert(glIsEnabled(cap));
    }
    glReadPixels(0, 0, 8, 8, GL_RGBA, GL_UNSIGNED_BYTE, after.data());
    assert(before == after && glGetError() == GL_NO_ERROR);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glReadBuffer(GL_BACK);
    std::array<unsigned char, 4> white{};
    glReadPixels(10, 470, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, white.data());
    assert(white[0] == 255 && white[1] == 255 && white[2] == 255);
    overlay.release();
    glDeleteBuffers(1, &buffer);
    glDeleteVertexArrays(1, &vao);
    glDeleteTextures(1, &texture);
    glDeleteFramebuffers(1, &fbo);
    std::cout << "DEBUG_OVERLAY_GL_STATE_EFB_PRESERVED DRIVER " << glGetString(GL_VERSION) << '\n';
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
