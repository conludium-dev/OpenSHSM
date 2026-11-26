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
    const char* vertex = "#version 330 core\nlayout(location=0) in vec2 p; uniform float z; void main(){gl_Position=vec4(p,z,1);}";
    const char* fragment = "#version 330 core\nuniform vec4 colour; out vec4 result; void main(){result=colour;}";
    GLuint program = CompileShader(vertex, fragment);
    assert(program);
    glUseProgram(program);
    GLuint vao = 0, buffer = 0;
    glGenVertexArrays(1, &vao); glBindVertexArray(vao);
    glGenBuffers(1, &buffer); glBindBuffer(GL_ARRAY_BUFFER, buffer);
    const float points[] = {-1,-1,3,-1,-1,3};
    glBufferData(GL_ARRAY_BUFFER, sizeof(points), points, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,nullptr);
    glViewport(0,0,32,32); glDisable(GL_BLEND); glDisable(GL_CULL_FACE);
    g_state.projSet = true; g_state.projType = 0;
    unsigned failures = 0;
    for (unsigned write = 0; write < 2; ++write) {
        glDepthMask(GL_TRUE); glClearDepth(1); glClear(GL_DEPTH_BUFFER_BIT);
        g_state.bp[0x40] = 7 | (write << 4); ApplyZMode();
        glUniform1f(glGetUniformLocation(program,"z"),-0.5f);
        glUniform4f(glGetUniformLocation(program,"colour"),1,0,0,1);
        glDrawArrays(GL_TRIANGLES,0,3);
        g_state.bp[0x40] = 23; ApplyZMode();
        glUniform1f(glGetUniformLocation(program,"z"),0.5f);
        glUniform4f(glGetUniformLocation(program,"colour"),0,1,0,1);
        glDrawArrays(GL_TRIANGLES,0,3);
        unsigned char pixel[4] = {};
        glReadPixels(16,16,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
        failures += pixel[0] != (write ? 255 : 0) || pixel[1] != (write ? 0 : 255);
        std::printf("DEPTH_WRITE_PIXEL %u %u %u %u\n",write,pixel[0],pixel[1],pixel[2]);
    }
    assert(glGetError() == GL_NO_ERROR);
    std::printf("GX_DEPTH_WRITE_GL checks=2 failures=%u\n",failures);
    SDL_GL_DeleteContext(context); SDL_DestroyWindow(window); SDL_Quit();
    return failures ? 1 : 0;
}
