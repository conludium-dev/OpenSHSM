#include <processor_adapter.h>
#include "runtime/gx/fifo_parser.h"
#include "runtime/gx/tev_shader_gen.h"
#include <SDL.h>
#include <glad/glad.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <memory>

namespace nwii::runtime::gx { extern GXState g_state; }

static GLuint shader(GLenum type, const char* source) {
    GLuint result = glCreateShader(type);
    glShaderSource(result, 1, &source, nullptr);
    glCompileShader(result);
    GLint okay = 0;
    glGetShaderiv(result, GL_COMPILE_STATUS, &okay);
    assert(okay);
    return result;
}

static unsigned draw() {
    using namespace nwii::runtime;
    const auto generated = gx::GenerateTEVShader(gx::g_state, 0x80);
    const char* vertex = "#version 330 core\nvoid main(){vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}";
    GLuint vs = shader(GL_VERTEX_SHADER, vertex);
    GLuint fs = shader(GL_FRAGMENT_SHADER, generated.fragment_source.c_str());
    GLuint program = glCreateProgram();
    glAttachShader(program, vs);
    glAttachShader(program, fs);
    glLinkProgram(program);
    GLint okay = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &okay);
    assert(okay);
    glUseProgram(program);
    const GLint konst = glGetUniformLocation(program, "uTevKColor[0]");
    if (konst >= 0) {
        const float values[16] = {0.25f, 0, 0, 1};
        glUniform4fv(konst, 4, values);
    }
    GLuint vao = 0;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    glFinish();
    unsigned char pixel[4];
    glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    assert(std::abs(int(pixel[0]) - int(pixel[1])) <= 1 && std::abs(int(pixel[1]) - int(pixel[2])) <= 1);
    assert(glGetError() == GL_NO_ERROR);
    glDeleteVertexArrays(1, &vao);
    glDeleteProgram(program);
    glDeleteShader(vs);
    glDeleteShader(fs);
    return pixel[0];
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    assert(argc == 2);
    const bool ordered = std::atoi(argv[1]) != 0;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM BP order probe", 0, 0, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::printf("DRIVER %s\n", glGetString(GL_VERSION));
    auto ctx = std::make_unique<CPUContext>();
    gx::g_state = {};
    gx::g_state.numTevStages = 1;
    auto& stage = gx::g_state.tevStages[0];
    stage.texMap = stage.colorChan = 0xFF;
    stage.colorInA = stage.colorInB = stage.colorInC = 15;
    stage.colorInD = 14;
    stage.colorClamp = 1;
    stage.alphaInA = stage.alphaInB = stage.alphaInC = 7;
    stage.alphaInD = 6;
    stage.alphaClamp = 1;
    glViewport(0, 0, 32, 32);
    const auto before = draw();
    std::vector<uint8_t> fifo{0x61, 0xF6, 0, 1, 0};
    std::vector<gx::GXCommand> commands;
    gx::FifoParser::Parse(fifo, commands);
    assert(fifo.empty() && commands.size() == 1);
    const auto parsed = draw();
    gx::ApplyBPRegister(0xF6, commands[0].val);
    const auto executed = draw();
    assert(before >= 254 && std::abs(int(executed) - 64) <= 1);
    assert(ordered ? parsed == before : std::abs(int(parsed) - 64) <= 1);
    std::printf("BP_REAL_GPU ordered=%u before=%u parsed=%u executed=%u\n",
        unsigned(ordered), before, parsed, executed);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
