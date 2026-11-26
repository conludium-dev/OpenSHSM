#include <SDL.h>
#include <cassert>
#include <cmath>
#include OPENSHSM_RENDERER_SOURCE

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("unexpected hardware read"); }
}
namespace nwii::runtime::gx {
GXState g_state{};
void ApplyBPRegister(uint8_t reg, uint32_t value) { g_state.bp[reg] = value; }
GeneratedShader GenerateTEVShader(const GXState&, uint8_t) {
    throw std::runtime_error("depth fixture must not compile guest shaders");
}
}
namespace nwii::runtime::hle {
TextureCache& TextureCache::get() { static TextureCache instance; return instance; }
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
void GX_GetClearColor(unsigned char rgba[4]) { std::memset(rgba, 0, 4); }

int main() {
    using namespace nwii::runtime::gx;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
    auto* window = SDL_CreateWindow("OpenSHSM depth probe", 0, 0, 32, 32,
        SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    auto renderer = CreateRendererGL();
    renderer->Initialize(window);
    renderer->Render({});
    const auto bp = [](uint16_t reg, uint32_t value) {
        GXCommand command{};
        command.type = GXCommandType::BPRegister;
        command.reg = reg;
        command.val = value;
        return command;
    };
    unsigned failures = 0, checks = 0;
    const auto check = [&](bool passed) { ++checks; failures += !passed; };
    const GLenum functions[] = {GL_NEVER, GL_LESS, GL_EQUAL, GL_LEQUAL,
        GL_GREATER, GL_NOTEQUAL, GL_GEQUAL, GL_ALWAYS};
    g_state.projSet = true;
    for (unsigned projection = 0; projection < 2; ++projection) {
        g_state.projType = projection;
        for (unsigned comparison = 0; comparison < 8; ++comparison) {
            for (unsigned write = 0; write < 2; ++write) {
                renderer->Render({bp(0x40, 1 | (comparison << 1) | (write << 4))});
                GLint function = 0;
                GLboolean mask = GL_FALSE;
                glGetIntegerv(GL_DEPTH_FUNC, &function);
                glGetBooleanv(GL_DEPTH_WRITEMASK, &mask);
                check(glIsEnabled(GL_DEPTH_TEST) && GLenum(function) == functions[comparison] &&
                    bool(mask) == bool(write));
            }
        }
    }
    renderer->Render({bp(0x40, 0)});
    check(!glIsEnabled(GL_DEPTH_TEST));
    glDepthMask(GL_TRUE);
    glClearDepth(0.25);
    glClear(GL_DEPTH_BUFFER_BIT);
    glClearDepth(1.0);
    glDepthMask(GL_FALSE);
    for (const auto& commands : std::vector<std::vector<GXCommand>>{{}, {bp(0x45, 2)}, {bp(0x47, 0)}}) {
        renderer->Render(commands);
        float value = 0;
        GLboolean mask = GL_TRUE;
        glReadPixels(16, 16, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT, &value);
        glGetBooleanv(GL_DEPTH_WRITEMASK, &mask);
        check(std::abs(value - 0.25f) < 0.00001f && !mask);
    }
    g_state.pe_clear_pending = true;
    renderer->Render({});
    float value = 0;
    glReadPixels(16, 16, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT, &value);
    check(std::abs(value - 1.0f) < 0.00001f && !g_state.pe_clear_pending);
    check(glGetError() == GL_NO_ERROR);
    std::printf("GX_DEPTH_GL checks=%u failures=%u\n", checks, failures);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return failures ? 1 : 0;
}
