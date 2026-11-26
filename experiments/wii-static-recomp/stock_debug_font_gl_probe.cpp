#include "stock_debug_overlay.h"
#include <array>
#include <stdexcept>

struct State {
    std::vector<GLint> integers;
    std::array<GLfloat, 4> clear;
    std::array<GLboolean, 4> mask;
    std::array<GLboolean, 7> enabled;
    bool operator==(const State&) const = default;
};

static State snapshot() {
    State result;
    for (GLenum field : {GL_CURRENT_PROGRAM, GL_VERTEX_ARRAY_BINDING, GL_ARRAY_BUFFER_BINDING,
            GL_DRAW_FRAMEBUFFER_BINDING, GL_READ_FRAMEBUFFER_BINDING, GL_READ_BUFFER,
            GL_ACTIVE_TEXTURE, GL_BLEND_SRC_RGB, GL_BLEND_DST_RGB, GL_BLEND_SRC_ALPHA,
            GL_BLEND_DST_ALPHA, GL_BLEND_EQUATION_RGB, GL_BLEND_EQUATION_ALPHA,
            GL_UNPACK_ALIGNMENT, GL_UNPACK_ROW_LENGTH, GL_UNPACK_SKIP_ROWS,
            GL_UNPACK_SKIP_PIXELS, GL_PIXEL_UNPACK_BUFFER_BINDING}) {
        GLint value;
        glGetIntegerv(field, &value);
        result.integers.push_back(value);
    }
    const GLint active = result.integers[6];
    for (GLenum unit : {GL_TEXTURE0, GL_TEXTURE3}) {
        glActiveTexture(unit);
        for (GLenum field : {GL_TEXTURE_BINDING_2D, GL_SAMPLER_BINDING}) {
            GLint value;
            glGetIntegerv(field, &value);
            result.integers.push_back(value);
        }
    }
    glActiveTexture(active);
    GLint values[4];
    for (GLenum field : {GL_VIEWPORT, GL_SCISSOR_BOX}) {
        glGetIntegerv(field, values);
        result.integers.insert(result.integers.end(), values, values + 4);
    }
    glGetIntegerv(GL_POLYGON_MODE, values);
    result.integers.insert(result.integers.end(), values, values + 2);
    glGetFloatv(GL_COLOR_CLEAR_VALUE, result.clear.data());
    glGetBooleanv(GL_COLOR_WRITEMASK, result.mask.data());
    unsigned index = 0;
    for (GLenum field : {GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_PROGRAM_POINT_SIZE,
            GL_STENCIL_TEST, GL_RASTERIZER_DISCARD, GL_CULL_FACE}) {
        result.enabled[index++] = glIsEnabled(field);
    }
    return result;
}

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    setenv("NWII_DEBUG_OVERLAY", "1", 1);
    unsetenv("NWII_SCREENSHOT");
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        std::fprintf(stderr, "%s\n", SDL_GetError());
        return 3;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_Window* window = SDL_CreateWindow("OpenSHSM font probe", 0, 0, 960, 540,
        SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    SDL_GLContext context = window ? SDL_GL_CreateContext(window) : nullptr;
    if (!context || !gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress))) {
        std::fprintf(stderr, "%s\n", SDL_GetError());
        return 4;
    }
    GLuint textures[3], fbo, vao, buffer, unpack, sampler;
    glGenTextures(3, textures);
    glBindTexture(GL_TEXTURE_2D, textures[2]);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 16, 16, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, textures[2], 0);
    glClearColor(0.25f, 0.5f, 0.75f, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    std::array<unsigned char, 16 * 16 * 4> efb_before, efb_after;
    glReadPixels(0, 0, 16, 16, GL_RGBA, GL_UNSIGNED_BYTE, efb_before.data());
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
    glClearColor(0.2f, 0.3f, 0.4f, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fbo);
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glGenBuffers(1, &buffer);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glGenBuffers(1, &unpack);
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpack);
    glBufferData(GL_PIXEL_UNPACK_BUFFER, 64, nullptr, GL_STATIC_DRAW);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 8);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 9);
    glPixelStorei(GL_UNPACK_SKIP_ROWS, 2);
    glPixelStorei(GL_UNPACK_SKIP_PIXELS, 3);
    glGenSamplers(1, &sampler);
    glBindSampler(0, sampler);
    glBindSampler(3, sampler);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, textures[0]);
    glActiveTexture(GL_TEXTURE3);
    glBindTexture(GL_TEXTURE_2D, textures[1]);
    glViewport(3, 5, 7, 9);
    glScissor(2, 4, 6, 8);
    glColorMask(GL_FALSE, GL_TRUE, GL_FALSE, GL_TRUE);
    glBlendFuncSeparate(GL_DST_COLOR, GL_ONE_MINUS_DST_COLOR, GL_DST_ALPHA, GL_ZERO);
    glBlendEquationSeparate(GL_FUNC_SUBTRACT, GL_FUNC_REVERSE_SUBTRACT);
    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);
    for (GLenum field : {GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_PROGRAM_POINT_SIZE,
            GL_STENCIL_TEST, GL_RASTERIZER_DISCARD, GL_CULL_FACE}) {
        glEnable(field);
    }
    const State before = snapshot();
    openshsm::experiment::DebugOverlay overlay;
    for (int width : {960, 640, 1920, 1, 0, 960}) {
        overlay.draw(width, width > 1 ? 540 : width, 30);
        if (!(snapshot() == before) || glGetError() != GL_NO_ERROR) {
            std::fprintf(stderr, "GL state/error failure at width %d\n", width);
            return 5;
        }
    }
    glReadPixels(0, 0, 16, 16, GL_RGBA, GL_UNSIGNED_BYTE, efb_after.data());
    if (efb_before != efb_after) {
        return 6;
    }
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
    glDisable(GL_SCISSOR_TEST);
    glDisable(GL_RASTERIZER_DISCARD);
    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glClear(GL_COLOR_BUFFER_BIT);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fbo);
    glEnable(GL_SCISSOR_TEST);
    glEnable(GL_RASTERIZER_DISCARD);
    glColorMask(GL_FALSE, GL_TRUE, GL_FALSE, GL_TRUE);
    overlay.draw(960, 540, 30);
    if (!(snapshot() == before) || glGetError() != GL_NO_ERROR) {
        return 9;
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glReadBuffer(GL_BACK);
    std::vector<unsigned char> pixels(960 * 540 * 4), flipped(pixels.size());
    glReadPixels(0, 0, 960, 540, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
    unsigned white = 0;
    for (unsigned y = 0; y < 540; ++y) {
        std::memcpy(flipped.data() + y * 960 * 4, pixels.data() + (539 - y) * 960 * 4, 960 * 4);
    }
    for (unsigned y = 0; y < 100; ++y) {
        for (unsigned x = 0; x < 500; ++x) {
            const unsigned char* p = flipped.data() + (y * 960 + x) * 4;
            white += p[0] > 220 && p[1] > 220 && p[2] > 220;
        }
    }
    if (white < 300) {
        return 7;
    }
    SDL_Surface* surface = SDL_CreateRGBSurfaceFrom(flipped.data(), 960, 540, 32, 960 * 4,
        0xff, 0xff00, 0xff0000, 0);
    if (!surface || SDL_SaveBMP(surface, argv[1]) != 0) {
        return 8;
    }
    SDL_FreeSurface(surface);
    overlay.release();
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::printf("DEBUG_FONT_REAL_GL_STATE_EFB_PASS 7 draws; %u white pixels\n", white);
}
