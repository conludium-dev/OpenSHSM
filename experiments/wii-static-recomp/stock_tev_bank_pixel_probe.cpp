#include "runtime/gx/fifo_parser.h"
#include "runtime/gx/tev_shader_gen.h"
#include <SDL.h>
#include <glad/glad.h>
#include <cassert>
#include <cstdlib>
#include <iostream>

extern void stock_read_tev_uniforms(float* color, float* kcolor);

static GLuint compile(GLenum kind, const std::string& source) {
    GLuint shader = glCreateShader(kind);
    const char* pointer = source.c_str();
    glShaderSource(shader, 1, &pointer, nullptr);
    glCompileShader(shader);
    GLint valid = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &valid);
    assert(valid);
    return shader;
}

int main() {
    using namespace nwii::runtime::gx;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM TEV pixel probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::cout << "DRIVER " << glGetString(GL_VERSION) << '\n';
    glDisable(GL_BLEND);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glDisable(GL_DITHER);
    glDisable(GL_FRAMEBUFFER_SRGB);
    glViewport(0, 0, 32, 32);
    GLuint vao, buffer;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glGenBuffers(1, &buffer);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    const float vertices[] = {-1, -1, 0, 3, -1, 0, -1, 3, 0};
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, nullptr);
    const unsigned values[2][4] = {{127, 63, 191, 255}, {31, 159, 95, 255}};
    unsigned cases = 0;
    for (unsigned last = 0; last < 2; ++last) {
        for (unsigned bank : {1 - last, last}) {
            ApplyBPRegister(0xE0, values[bank][0] | (values[bank][3] << 12) | (bank << 23));
            ApplyBPRegister(0xE1, values[bank][2] | (values[bank][1] << 12) | (bank << 23));
        }
        for (unsigned selected = 0; selected < 2; ++selected) {
            g_state.numTevStages = 1;
            auto& stage = g_state.tevStages[0];
            stage = {};
            stage.texMap = 0xFF;
            stage.colorInA = stage.colorInB = stage.colorInC = 15;
            stage.alphaInA = stage.alphaInB = stage.alphaInC = 7;
            stage.colorInD = selected == 0 ? 0 : 14;
            stage.alphaInD = selected == 0 ? 0 : 6;
            stage.colorClamp = stage.alphaClamp = 1;
            g_state.bp[0xF6] = (12 << 4) | (28 << 9);
            const auto shader = GenerateTEVShader(g_state, 0x90);
            const auto vertex = compile(GL_VERTEX_SHADER, shader.vertex_source);
            const auto fragment = compile(GL_FRAGMENT_SHADER, shader.fragment_source);
            const auto program = glCreateProgram();
            glAttachShader(program, vertex);
            glAttachShader(program, fragment);
            glLinkProgram(program);
            GLint valid = 0;
            glGetProgramiv(program, GL_LINK_STATUS, &valid);
            assert(valid);
            glUseProgram(program);
            const float identity[] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
            glUniformMatrix4fv(glGetUniformLocation(program, "mvp"), 1, GL_FALSE, identity);
            float color[16] = {}, kcolor[16] = {};
            stock_read_tev_uniforms(color, kcolor);
            glUniform4fv(glGetUniformLocation(program, "uTevColor"), 4, color);
            glUniform4fv(glGetUniformLocation(program, "uTevKColor"), 4, kcolor);
            glDrawArrays(GL_TRIANGLES, 0, 3);
            unsigned char pixel[4];
            glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
            assert(glGetError() == GL_NO_ERROR);
            for (unsigned component = 0; component < 4; ++component) {
                assert(std::abs(int(pixel[component]) - int(values[selected][component])) <= 1);
            }
            std::cout << "TEV_PIXEL " << last << ' ' << selected << ' '
                << unsigned(pixel[0]) << ' ' << unsigned(pixel[1]) << ' '
                << unsigned(pixel[2]) << ' ' << unsigned(pixel[3]) << '\n';
            ++cases;
            glDeleteProgram(program);
            glDeleteShader(vertex);
            glDeleteShader(fragment);
        }
    }
    glDeleteBuffers(1, &buffer);
    glDeleteVertexArrays(1, &vao);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::cout << "TEV_BANK_NATIVE_GPU_PIXEL_PASS " << cases << '\n';
}
