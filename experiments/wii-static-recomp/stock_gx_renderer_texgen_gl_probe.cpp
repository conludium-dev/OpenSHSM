#include "runtime/gx/fifo_parser.h"
#include "runtime/gx/renderer.h"
#include "runtime/texture_cache_gl.h"
#include <SDL.h>
#include <glad/glad.h>
#include <array>
#include <algorithm>
#include <cassert>
#include <bit>
#include <cstdio>
#include <cstring>
#include <memory>

namespace nwii::runtime::gx {
std::unique_ptr<IRenderer> CreateRendererGL();
}
uint64_t nwii_stat_shaders();

int main() {
    using namespace nwii::runtime::gx;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM texgen probe", 0, 0, 32, 32,
        SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::printf("DRIVER %s\n", glGetString(GL_VERSION));
    glViewport(0, 0, 32, 32);
    glDisable(GL_DITHER);
    glDisable(GL_FRAMEBUFFER_SRGB);
    GLuint texture = 0;
    glGenTextures(1, &texture);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, texture);
    const std::array<uint8_t, 8> pixels = {255, 0, 0, 255, 0, 255, 0, 255};
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 2, 1, 0, GL_RGBA,
        GL_UNSIGNED_BYTE, pixels.data());
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    g_state = {};
    g_state.bp[0x41] = 0x18;
    g_state.numTevStages = 1;
    g_state.numTexGens = 2;
    g_state.posMatrices[0] = 1.0f;
    g_state.posMatrices[5] = 1.0f;
    auto& stage = g_state.tevStages[0];
    stage.texMap = 0;
    stage.texCoord = 1;
    stage.colorChan = 0xff;
    stage.colorInA = stage.colorInB = stage.colorInC = 15;
    stage.colorInD = 8;
    stage.alphaInA = stage.alphaInB = stage.alphaInC = 7;
    stage.alphaInD = 4;
    stage.colorClamp = stage.alphaClamp = 1;
    g_state.xf[0x40] = 5 << 7;
    g_state.xf[0x41] = 6 << 7;

    GXCommand draw{};
    draw.type = GXCommandType::DrawPrimitive;
    draw.prim_type = 0x90;
    draw.vertices.resize(3);
    draw.raw = std::make_shared<DrawRaw>();
    draw.raw->sources.resize(3);
    const std::array<std::array<float, 3>, 3> positions = {{{-1, -1, 0}, {3, -1, 0}, {-1, 3, 0}}};
    for (unsigned index = 0; index < 3; ++index) {
        auto& vertex = draw.vertices[index];
        auto& source = draw.raw->sources[index];
        for (unsigned axis = 0; axis < 3; ++axis) {
            vertex.pos[axis] = positions[index][axis];
        }
        vertex.has_pos = true;
        vertex.pre_xf = true;
        vertex.has_tex[0] = true;
        vertex.tex[0][0] = 0.0f;
        source.has_uv[0] = source.has_uv[1] = true;
        source.uv[0] = {0.0f, 0.0f};
        source.uv[1] = {1.0f, 0.0f};
    }
    auto renderer = CreateRendererGL();
    renderer->Initialize(window);
    auto sample = [&](const std::vector<GXCommand>& commands, uint8_t red, uint8_t green) {
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        renderer->Render(commands);
        glFinish();
        std::array<uint8_t, 4> pixel{};
        glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel.data());
        std::printf("TEXGEN_PIXEL %u %u %u %u\n", pixel[0], pixel[1], pixel[2], pixel[3]);
        assert(glGetError() == GL_NO_ERROR);
        assert(pixel[0] == red && pixel[1] == green);
    };
    sample({draw}, 0, 255);
    for (auto& source : draw.raw->sources) {
        source.has_uv[0] = false;
    }
    sample({draw}, 0, 255);
    for (auto& source : draw.raw->sources) {
        source.has_uv[0] = true;
    }
    for (auto& source : draw.raw->sources) {
        source.uv[1][0] = 0.0f;
    }
    sample({draw}, 255, 0);
    g_state.xf[0x41] = (6 << 7) | 2;
    g_state.posMatrices[11] = 0.5f;
    for (auto& source : draw.raw->sources) {
        source.uv[1][0] = 0.3f;
    }
    sample({draw}, 0, 255);
    g_state.xf[0x41] = 6 << 7;
    for (auto& source : draw.raw->sources) {
        source.uv[1][0] = 0.0f;
    }
    GXCommand dual{};
    dual.type = GXCommandType::XFRegister;
    dual.reg = 0x1012;
    dual.payload = {std::bit_cast<float>(uint32_t(1))};
    GXCommand post{};
    post.type = GXCommandType::XFRegister;
    post.reg = 0x500;
    post.payload.resize(12);
    post.payload[3] = 1.0f;
    post.payload[11] = 1.0f;
    sample({dual, post, draw}, 0, 255);
    g_state.xf[0x51] = 8;
    for (auto& source : draw.raw->sources) {
        source.uv[1][0] = 1.0f;
    }
    sample({draw}, 0, 255);
    g_state.xf[0x51] = 0;
    g_state.xf[0x12] = 0;
    g_state.bp[0x32] = 63;
    g_state.bp[0x33] = 31;
    for (auto& source : draw.raw->sources) {
        source.uv[1][0] = 1.0f;
    }
    sample({draw}, 0, 255);
    std::fill_n(g_state.posMatrices, 256, 0.0f);
    sample({draw}, 0, 255);
    const auto xf = [](uint16_t reg, uint32_t value) {
        GXCommand command{};
        command.type = GXCommandType::XFRegister;
        command.reg = reg;
        command.payload = {std::bit_cast<float>(value)};
        return command;
    };
    sample({xf(0x1041, 2 << 4), xf(0x100C, 0xFFFFFFFF), draw}, 0, 255);
    sample({xf(0x100C, 0x000000FF), draw}, 255, 0);
    sample({xf(0x1041, 3 << 4), xf(0x100D, 0xFFFFFFFF), draw}, 0, 255);
    sample({xf(0x100D, 0x000000FF), draw}, 255, 0);
    for (auto& source : draw.raw->sources) {
        source.has_color[1] = true;
        source.colors[1][0] = 1.0f;
    }
    sample({xf(0x100F, 1), draw}, 0, 255);
    for (auto& source : draw.raw->sources) {
        source.colors[1][0] = 0.0f;
    }
    sample({draw}, 255, 0);
    for (auto& source : draw.raw->sources) {
        source.has_color[1] = false;
    }
    renderer->Render({xf(0x100F, 0)});
    renderer->Render({xf(0x1041, 6 << 7)});
    stage.texMap = 0xff;
    stage.colorInD = 14;
    g_state.bp[0xC0] = 1;
    const auto bp = [](uint8_t reg, uint32_t value) {
        GXCommand command{};
        command.type = GXCommandType::BPRegister;
        command.reg = reg;
        command.val = value;
        return command;
    };
    sample({bp(0xE0, 0x800000 | (255 << 12) | 255),
        bp(0xE1, 0x800000), bp(0xE2, 0x800000 | (255 << 12)),
        bp(0xE3, 0x800000 | (255 << 12)), bp(0xF6, 0x0C << 4), draw}, 255, 0);
    const uint64_t shader_count = nwii_stat_shaders();
    sample({bp(0xF6, 0x0D << 4), draw}, 0, 255);
    assert(nwii_stat_shaders() == shader_count + 1);
    sample({bp(0x41, 0x1a), draw}, 0, 255);
    assert(nwii_stat_shaders() == shader_count + 2);
    sample({draw}, 0, 255);
    assert(nwii_stat_shaders() == shader_count + 2);
    stage.colorChan = 0;
    stage.texMap = 0xff;
    stage.colorInD = 11;
    stage.alphaInD = 7;
    g_state.xf[0x00A] = 0;
    g_state.xf[0x00C] = 0xffffffff;
    g_state.xf[0x00E] = 0;
    g_state.xf[0x010] = 6;
    const uint32_t alpha_light_color = 0x00000080;
    std::memcpy(&g_state.lights[0][3], &alpha_light_color, sizeof(alpha_light_color));
    sample({bp(0x41, 0x18), draw}, 128, 128);
    g_state.xf[0x010] = 2;
    sample({draw}, 0, 0);
    g_state.xf[0x010] = 6;
    g_state.xf[0x00E] = 2;
    sample({draw}, 128, 128);
    g_state.xf[0x00E] = 10;
    sample({draw}, 128, 128);
    GLuint efb_color = 0, efb_fbo = 0;
    glGenTextures(1, &efb_color);
    glBindTexture(GL_TEXTURE_2D, efb_color);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 8, 8, 0, GL_RGBA,
        GL_UNSIGNED_BYTE, nullptr);
    glGenFramebuffers(1, &efb_fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, efb_fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D, efb_color, 0);
    glDrawBuffer(GL_COLOR_ATTACHMENT0);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    glViewport(0, 0, 8, 8);
    glClearColor(1, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    const uint32_t copy_dest = 0x1000;
    const auto copy = [&](uint32_t control, int expected_size, uint32_t stride) {
        renderer->Render({bp(0x49, 0), bp(0x4A, 7 | (7 << 10)),
            bp(0x4B, copy_dest >> 5), bp(0x4D, stride), bp(0x52, control)});
        const GLuint copied = nwii::runtime::hle::TextureCache::get()
            .find_efb_texture(copy_dest);
        assert(copied != 0);
        glBindTexture(GL_TEXTURE_2D, copied);
        GLint width = 0, height = 0;
        glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &width);
        glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &height);
        std::array<uint8_t, 8 * 8 * 4> copied_pixels{};
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE,
            copied_pixels.data());
        std::printf("EFB_COPY_SIZE %d %d %u %u %u\n", width, height,
            copied_pixels[0], copied_pixels[1], copied_pixels[2]);
        assert(width == expected_size && height == expected_size);
        assert(copied_pixels[0] == 255 && copied_pixels[1] == 0 &&
            copied_pixels[2] == 0);
        assert(glGetError() == GL_NO_ERROR);
    };
    copy(0x10263, 4, 2);
    glEnable(GL_SCISSOR_TEST);
    glScissor(0, 0, 2, 2);
    glClearColor(0, 1, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glDisable(GL_SCISSOR_TEST);
    renderer->Render({bp(0x4A, 1 | (1 << 10)), bp(0x52, 0x10063)});
    const GLuint partially_copied = nwii::runtime::hle::TextureCache::get()
        .find_efb_texture(copy_dest);
    glBindTexture(GL_TEXTURE_2D, partially_copied);
    GLint partial_width = 0, partial_height = 0;
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &partial_width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &partial_height);
    std::array<uint8_t, 4 * 4 * 4> partial_pixels{};
    glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE,
        partial_pixels.data());
    const size_t opposite = (3 + 3 * 4) * 4;
    std::printf("EFB_COPY_PARTIAL %d %d %u %u %u %u\n",
        partial_width, partial_height, partial_pixels[0], partial_pixels[1],
        partial_pixels[opposite], partial_pixels[opposite + 1]);
    assert(partial_width == 4 && partial_height == 4);
    assert(partial_pixels[0] == 0 && partial_pixels[1] == 255);
    assert(partial_pixels[opposite] == 255 && partial_pixels[opposite + 1] == 0);
    assert(glGetError() == GL_NO_ERROR);
    glClearColor(1, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    copy(0x10063, 8, 4);
    renderer->Render({bp(0x41, 0x08), draw});
    GLboolean mask[4]{};
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    assert(mask[0] && mask[1] && mask[2] && !mask[3]);
    renderer->Render({bp(0x41, 0x10), draw});
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    assert(!mask[0] && !mask[1] && !mask[2] && mask[3]);
    renderer->Render({bp(0x41, 0x18), draw});
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    assert(mask[0] && mask[1] && mask[2] && mask[3]);
    std::puts("BP41_COLOR_ALPHA_MASK_GL_PASS 3");
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glViewport(0, 0, 32, 32);
    glDeleteFramebuffers(1, &efb_fbo);
    glDeleteTextures(1, &efb_color);
    renderer.reset();
    glDeleteTextures(1, &texture);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::puts("GX_RENDERER_TEXGEN_GL_PASS 25");
}
