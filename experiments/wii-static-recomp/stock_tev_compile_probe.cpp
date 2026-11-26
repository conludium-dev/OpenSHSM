#include "runtime/gx/tev_shader_gen.h"
#include <SDL.h>
#include <glad/glad.h>
#include <cassert>
#include <fstream>
#include <iostream>
#include <memory>

static bool compile(GLenum kind, const std::string& source) {
    const auto shader = glCreateShader(kind);
    const char* pointer = source.c_str();
    glShaderSource(shader, 1, &pointer, nullptr);
    glCompileShader(shader);
    GLint status = 0, size = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
    glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &size);
    if (!status) {
        std::string log(size > 0 ? size : 1, '\0');
        glGetShaderInfoLog(shader, log.size(), nullptr, log.data());
        std::cout << "DRIVER_ERROR " << log << '\n';
    }
    glDeleteShader(shader);
    return status != 0;
}

int main(int argc, char** argv) {
    assert(argc == 3);
    const bool baseline = std::string(argv[1]) == "baseline";
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM shader probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::cout << "DRIVER " << glGetString(GL_VERSION) << '\n';
    auto state = std::make_unique<nwii::runtime::gx::GXState>();
    for (auto count : {1u, 2u, 3u, 16u}) {
        state->numTevStages = count;
        for (auto& stage : state->tevStages) {
            stage.texMap = 0xFF;
            stage.colorInA = stage.colorInB = stage.colorInC = 15;
            stage.colorInD = 12;
            stage.alphaInA = stage.alphaInB = stage.alphaInC = 7;
            stage.alphaInD = 6;
            stage.colorClamp = stage.alphaClamp = 1;
        }
        auto shader = nwii::runtime::gx::GenerateTEVShader(*state, 0x80);
        std::ofstream(std::string(argv[2]) + "/stage-" + std::to_string(count) + ".frag") << shader.fragment_source;
        const bool vertex = compile(GL_VERTEX_SHADER, shader.vertex_source);
        const bool fragment = compile(GL_FRAGMENT_SHADER, shader.fragment_source);
        assert(vertex && fragment == (!baseline || count == 1));
        std::cout << "TEV_COMPILE " << count << ' ' << vertex << ' ' << fragment << '\n';
    }
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::cout << (baseline ? "BASELINE_MULTI_TEV_COMPILE_FAILURE_REPRODUCED" : "SCOPED_MULTI_TEV_COMPILE_PASS") << '\n';
}
