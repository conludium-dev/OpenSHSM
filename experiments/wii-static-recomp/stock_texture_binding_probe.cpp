#include "runtime/texture_cache_gl.h"
#include <SDL.h>
#include <glad/glad.h>
#include <array>
#include <cassert>
#include <iostream>
#include <memory>

static std::array<unsigned, 3> read_units() {
    std::array<unsigned, 3> result{};
    for (unsigned i = 0; i < 3; ++i) {
        glActiveTexture(GL_TEXTURE0 + i);
        std::array<uint8_t, 128> pixels{};
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        result[i] = pixels[0];
    }
    assert(glGetError() == GL_NO_ERROR);
    return result;
}

int main() {
    using namespace nwii::runtime;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM binding probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::cout << "DRIVER " << glGetString(GL_VERSION) << '\n';
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    std::array<gx::TexStage, 3> stages{};
    const unsigned initial[] = {64, 128, 192};
    for (unsigned i = 0; i < 3; ++i) {
        stages[i].base_addr = 0x80560000 + i * 0x100;
        stages[i].width = 8;
        stages[i].height = 4;
        stages[i].format = 1;
        for (unsigned j = 0; j < 32; ++j) {
            ctx.mmu.write8(stages[i].base_addr + j, initial[i]);
        }
    }
    auto bind = [&](bool corrected) {
        for (unsigned i = 0; i < 3; ++i) {
            if (corrected) { glActiveTexture(GL_TEXTURE0 + i); }
            GLuint tex = hle::TextureCache::get().get_texture(ctx, stages[i]);
            glActiveTexture(GL_TEXTURE0 + i);
            glBindTexture(GL_TEXTURE_2D, tex);
        }
        return read_units();
    };
    hle::TextureCache::get().clear();
    glActiveTexture(GL_TEXTURE0);
    auto cold = bind(false);
    assert((cold == std::array<unsigned, 3>{128, 192, 192}));
    auto warm = bind(false);
    assert((warm == std::array<unsigned, 3>{64, 128, 192}));
    for (unsigned j = 0; j < 32; ++j) { ctx.mmu.write8(stages[1].base_addr + j, 136); }
    auto mixed = bind(false);
    assert((mixed == std::array<unsigned, 3>{136, 136, 192}));
    hle::TextureCache::get().clear();
    auto fixed = bind(true);
    assert((fixed == std::array<unsigned, 3>{64, 136, 192}));
    std::cout << "TEXTURE_BINDING_MISS_CLOBBER_REPRODUCED cold=128,192,192 warm=64,128,192 mixed=136,136,192 fixed=64,136,192\n";
    hle::TextureCache::get().clear();
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
