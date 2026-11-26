#include <SDL.h>
#include <cassert>
#include <cmath>
#include OPENSHSM_RENDERER_SOURCE

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
uint32_t HW_Reg_Read32(uint32_t) {
    throw std::runtime_error("unexpected hardware read");
}
}
namespace nwii::runtime::gx {
GXState g_state{};
void ApplyBPRegister(uint8_t reg, uint32_t value) {
    g_state.bp[reg] = value;
}
}
namespace nwii::runtime::hle {
TextureCache& TextureCache::get() {
    static TextureCache instance;
    return instance;
}
GLuint TextureCache::get_texture(CPUContext&, const gx::TexStage&) {
    throw std::runtime_error("unexpected guest texture");
}
void TextureCache::register_efb_texture(uint32_t, GLuint) {
    throw std::runtime_error("unexpected texture copy");
}
void TextureCache::register_efb_texture(uint32_t, GLuint, const EfbCopyTexture&) {
    throw std::runtime_error("unexpected texture copy");
}
GLuint TextureCache::find_efb_texture(uint32_t) const {
    throw std::runtime_error("unexpected texture lookup");
}
}
void GX_GetClearColor(unsigned char rgba[4]) {
    std::memset(rgba, 0, 4);
}


#include OPENSHSM_SHADER_SOURCE
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
    unsigned failures = 0;
    auto sample = [&](const std::vector<GXCommand>& commands, uint8_t red, uint8_t green, uint8_t blue, uint8_t alpha) {
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        renderer->Render(commands);
        glFinish();
        std::array<uint8_t, 4> pixel{};
        glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel.data());
        std::printf("TEXGEN_PIXEL %u %u %u %u\n", pixel[0], pixel[1], pixel[2], pixel[3]);
        assert(glGetError() == GL_NO_ERROR);
        failures += pixel[0] != red || pixel[1] != green || pixel[2] != blue || pixel[3] != alpha;
    };
    g_state.bp[0xF6] = 4;
    g_state.bp[0xF7] = 14;
    stage.texMap = 0xff;
    stage.colorChan = 0;
    stage.colorInD = 10;
    stage.alphaInD = 5;
    g_state.xf[0xC] = 0x336699CC;
    for (unsigned color = 0; color < 4; ++color) {
        for (unsigned alpha = 0; alpha < 4; ++alpha) {
            stage.colorRegId = color;
            stage.alphaRegId = alpha;
            sample({draw}, 51, 102, 153, 204);
        }
    }
    std::printf("TEV_FINAL_GL cases=16 failures=%u\n", failures);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return failures ? 1 : 0;
}
